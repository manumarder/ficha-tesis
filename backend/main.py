import os
import sys
import logging
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from pydantic import BaseModel
from typing import List

# Añadimos la raíz del proyecto al path para que Python encuentre los módulos hermanos
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
from data_pipeline.utils.utils_db import ConexionBaseDatos

# Configuración de Logging del Backend
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inicialización de la Aplicación FastAPI
app = FastAPI(
    title="Fichá API - Motor Analítico de Consumo",
    description="Backend de servicios para auditoría de precios y detección de asimetrías de información.",
    version="1.0.0"
)

# Configuración de CORS (Permite que Streamlit se comunique con la API sin bloqueos de seguridad)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # En producción se restringe a dominios específicos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# INYECCIÓN DE DEPENDENCIAS DE BASE DE DATOS
# ==========================================
def get_db():
    """
    Dependencia que asegura la apertura y cierre limpio de la conexión
    a Supabase Cloud por cada petición de la API.
    """
    db = ConexionBaseDatos(
        host=settings.db.host,
        user=settings.db.user,
        password=settings.db.password,
        database=settings.db.name,
        port=settings.db.port,
        database_url=settings.db.database_url,
        ssl_mode=settings.db.ssl_mode
    )
    
    success = db.connect_db()
    if not success:
        logger.error("No se pudo establecer conexión con Supabase en la API")
        raise HTTPException(status_code=500, detail="Error interno de conexión con la base de datos cloud")
    
    try:
        yield db
    finally:
        db.close_connections()
        logger.info("[BACKEND] Conexiones pooled liberadas correctamente.")

# ==========================================
# ENDPOINTS DE LA CAPA ORO (VISTAS SQL)
# ==========================================

@app.get("/")
def read_root():
    """Ruta base para verificar estado de salud del servicio (Health Check)"""
    return {
        "status": "online",
        "proyecto": "Fichá - Asistente Inteligente",
        "entorno": settings.environment
    }

@app.get("/api/ofertas-reales")
def obtener_ofertas_reales(db: ConexionBaseDatos = Depends(get_db)):
    """
    Trae los productos de la Canasta Básica cuyo semáforo es VERDE 🟢
    calculado dinámicamente contra su promedio móvil de 21 días.
    """
    query = "SELECT * FROM public.vista_auditoria_consumo WHERE semaforo = '🟢' ORDER BY ahorro_real_pct DESC;"
    try:
        # Usamos Pandas para leer directo la query y transformarla a JSON nativo
        df = pd.read_sql(query, db.engine)
        resultado = df.to_dict(orient="records")
        return {
            "status": "success",
            "count": len(resultado),
            "data": resultado
        }
    except Exception as e:
        logger.error(f"Error consultando ofertas reales: {e}")
        raise HTTPException(status_code=500, detail=f"Error analítico de base de datos: {str(e)}")

@app.get("/api/alertas-trampa")
def obtener_alertas_trampa(db: ConexionBaseDatos = Depends(get_db)):
    """
    Trae los productos de la Canasta Básica cuyo semáforo es ROJO 🔴
    (Productos con inflado artificial previo en el precio normal).
    """
    query = "SELECT * FROM public.vista_auditoria_consumo WHERE semaforo = '🔴' ORDER BY ahorro_real_pct ASC;"
    try:
        df = pd.read_sql(query, db.engine)
        resultado = df.to_dict(orient="records")
        return {
            "status": "success",
            "count": len(resultado),
            "data": resultado
        }
    except Exception as e:
        logger.error(f"Error consultando alertas trampa: {e}")
        raise HTTPException(status_code=500, detail=f"Error analítico de base de datos: {str(e)}")
    

# ==========================================
# ESTRUCTURAS DE DATOS (PAYLOADS MODEL)
# ==========================================
class CanastaRequest(BaseModel):
    productos: List[str]

# ==========================================
# ENDPOINTS AVANZADOS DE BÚSQUEDA Y NEGOCIO
# ==========================================

@app.get("/api/productos")
def listar_productos_maestros(db: ConexionBaseDatos = Depends(get_db)):
    """
    Retorna la lista única de nombres genéricos de productos maestros.
    Útil para alimentar el componente multiselect en el Frontend.
    """
    query = "SELECT DISTINCT nombre_generico FROM public.productos_maestros ORDER BY nombre_generico ASC;"
    try:
        cursor = db.connection.cursor()
        cursor.execute(query)
        # Extraemos los strings limpios en una lista plana
        productos = [fila[0] for fila in cursor.fetchall()]
        return {
            "status": "success",
            "count": len(productos),
            "data": productos
        }
    except Exception as e:
        logger.error(f"Error listando productos maestros: {e}")
        raise HTTPException(status_code=500, detail=f"Error en capa de datos: {str(e)}")


@app.get("/api/buscar")
def buscar_productos(q: str, db: ConexionBaseDatos = Depends(get_db)):
    """
    Busca coincidencias de texto en el catálogo analítico.
    Filtra por nombre genérico o retail y ordena de menor a mayor por precio final.
    """
    if not q or len(q.strip()) < 2:
        raise HTTPException(status_code=400, detail="La query de búsqueda debe tener al menos 2 caracteres.")
    
    # Búsqueda insensible a mayúsculas/minúsculas (ILIKE) para una UX robusta
    query = """
        SELECT * FROM public.vista_auditoria_consumo 
        WHERE nombre_generico ILIKE %s OR url_producto ILIKE %s
        ORDER BY precio_descuento ASC;
    """
    param_busqueda = f"%{q.strip()}%"
    
    try:
        df = pd.read_sql(query, db.engine, params=(param_busqueda, param_busqueda))
        resultado = df.to_dict(orient="records")
        return {
            "status": "success",
            "term": q,
            "count": len(resultado),
            "data": resultado
        }
    except Exception as e:
        logger.error(f"Error en buscador: {e}")
        raise HTTPException(status_code=500, detail=f"Error en el motor de búsqueda: {str(e)}")


@app.post("/api/comparar-canasta")
def comparar_canasta(payload: CanastaRequest, db: ConexionBaseDatos = Depends(get_db)):
    """
    Algoritmo central de optimización de canastas grupales.
    Recibe una lista de nombres genéricos, busca el precio actual más reciente de cada uno
    en cada supermercado y computa los totales consolidados para determinar el más económico.
    """
    if not payload.productos:
        raise HTTPException(status_code=400, detail="La canasta de productos no puede estar vacía.")
    
    # Query que extrae las últimas lecturas vigentes para los productos seleccionados
    query = """
        SELECT DISTINCT ON (supermercado, nombre_generico)
            supermercado, nombre_generico, precio_descuento, semaforo
        FROM public.vista_auditoria_consumo
        WHERE nombre_generico ANY(%s)
        ORDER BY supermercado, nombre_generico, created_at DESC;
    """
    
    try:
        # Convertimos la lista de Python a una estructura compatible con el operador ANY de Postgres
        df = pd.read_sql(query, db.engine, params=(payload.productos,))
        
        if df.empty:
            return {"status": "success", "mensaje": "No se encontraron precios vigentes para los productos seleccionados.", "totales": {}, "desglose": {}}
        
        # 1. Calcular el costo total sumando los productos agrupados por supermercado
        df_totales = df.groupby("supermercado")["precio_descuento"].sum().reset_index()
        df_totales = df_totales.sort_values(by="precio_descuento", ascending=True)
        totales_dict = df_totales.set_index("supermercado")["precio_descuento"].to_dict()
        
        # 2. Generar el desglose individual por ítem para auditoría visual en el frontend
        desglose_dict = {}
        for superm in df["supermercado"].unique():
            df_sub = df[df["supermercado"] == superm]
            desglose_dict[superm] = df_sub.set_index("nombre_generico")[["precio_descuento", "semaforo"]].to_dict(orient="index")
            
        return {
            "status": "success",
            "productos_solicitados": payload.productos,
            "totales": totales_dict,
            "desglose": desglose_dict
        }
    except Exception as e:
        logger.error(f"Error optimizando presupuesto de canasta: {e}")
        raise HTTPException(status_code=500, detail=f"Error algorítmico en el Backend: {str(e)}")
