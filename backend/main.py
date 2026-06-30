import os
import sys
import logging
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd

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