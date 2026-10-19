import logging
import os
import sys
from typing import List
from config.settings import settings
from data_pipeline.utils.utils_db import ConexionBaseDatos
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from pydantic import BaseModel, Field

# Añadimos la raíz del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configuración de Logging del Backend
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

LATEST_AUDIT_QUERY = """
    WITH precios_recientes AS (
        SELECT DISTINCT ON (id_link) *
        FROM public.vista_auditoria_consumo
        ORDER BY id_link, created_at DESC
    )
"""


def leer_dataframe(
    db: ConexionBaseDatos, query: str, params=None
) -> list[dict]:
  """Ejecuta una consulta analítica y devuelve registros serializables sin columnas duplicadas."""
  dataframe = pd.read_sql(query, db.engine, params=params)
  # Eliminamos columnas duplicadas si las hubiera para evitar el UserWarning de Pandas
  dataframe = dataframe.loc[:, ~dataframe.columns.duplicated()]
  return dataframe.where(pd.notna(dataframe), None).to_dict(orient="records")


def error_de_datos(logger_message: str, error: Exception) -> HTTPException:
  """Registra el detalle técnico sin exponerlo en la respuesta pública."""
  logger.exception("%s: %s", logger_message, error)
  return HTTPException(
      status_code=500, detail="No se pudo completar la consulta de datos."
  )


# Inicialización de la Aplicación FastAPI
app = FastAPI(
    title="Fichá API - Motor Analítico de Consumo",
    description=(
        "Backend de servicios para auditoría de precios y detección de"
        " asimetrías de información."
    ),
    version="1.0.0",
)

# Configuración de CORS controlada por CORS_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://ficha-tesis.vercel.app",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "*",  # Permite cualquier subdominio de Vercel (previews)
    ],
    allow_credentials=False,  # En False permite usar "*" sin conflicto
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================
# INYECCIÓN DE DEPENDENCIAS DE BASE DE DATOS
# ==========================================
def get_db():
  db = ConexionBaseDatos(
      host=settings.db.host,
      user=settings.db.user,
      password=settings.db.password,
      database=settings.db.name,
      port=settings.db.port,
      database_url=settings.db.database_url,
      ssl_mode=settings.db.ssl_mode,
  )

  success = db.connect_db()
  if not success:
    logger.error("No se pudo establecer conexión con Supabase en la API")
    raise HTTPException(
        status_code=500,
        detail="Error interno de conexión con la base de datos cloud",
    )

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
  return {
      "status": "online",
      "proyecto": "Fichá - Auditoría de precios",
      "entorno": settings.environment,
  }


@app.get("/api/filtros")
def obtener_opciones_filtro(db: ConexionBaseDatos = Depends(get_db)):
  query = """
        SELECT DISTINCT s.nombre AS supermercado, c.nombre AS categoria
        FROM public.link_productos l
        JOIN public.supermercados s ON s.id = l.id_supermercado
        LEFT JOIN public.productos_maestros pm ON pm.id = l.id_maestro
        LEFT JOIN public.categorias c ON c.id = pm.id_categoria
        WHERE l.activo = TRUE AND s.activo = TRUE
        ORDER BY s.nombre, c.nombre;
    """
  try:
    rows = leer_dataframe(db, query)
    return {
      "status": "success",
      "supermercados": sorted(
          {row["supermercado"] for row in rows if row.get("supermercado")}
      ),
      "categorias": sorted(
          {row["categoria"] for row in rows if row.get("categoria")}
      ),
    }
  except Exception as e:
    raise error_de_datos("Error consultando opciones de filtros", e)


def _consulta_auditoria_filtrada(
    semaforo: str,
    orden: str,
    supermercado: str | None,
    categoria: str | None,
    db: ConexionBaseDatos,
):
  query = (
      LATEST_AUDIT_QUERY
      + f"""
        SELECT pr.*,
               COALESCE(pr.precio_descuento, pr.precio_normal) AS precio_final,
               c.nombre AS categoria
        FROM precios_recientes pr
        LEFT JOIN public.link_productos l ON l.id = pr.id_link
        LEFT JOIN public.productos_maestros pm ON pm.id = l.id_maestro
        LEFT JOIN public.categorias c ON c.id = pm.id_categoria
        WHERE pr.semaforo = %s
          AND (%s::text IS NULL OR pr.supermercado = %s)
          AND (%s::text IS NULL OR c.nombre = %s)
        ORDER BY pr.{orden};
    """
  )
  return leer_dataframe(
      db,
      query,
      params=(semaforo, supermercado, supermercado, categoria, categoria),
  )


@app.get("/api/ofertas-reales")
def obtener_ofertas_reales(
    supermercado: str | None = Query(default=None, max_length=100),
    categoria: str | None = Query(default=None, max_length=100),
    db: ConexionBaseDatos = Depends(get_db),
):
  try:
    resultado = _consulta_auditoria_filtrada(
        "🟢", "ahorro_real_pct DESC", supermercado, categoria, db
    )
    return {
      "status": "success",
      "count": len(resultado),
      "data": resultado,
    }
  except Exception as e:
    raise error_de_datos("Error consultando ofertas reales", e)


@app.get("/api/alertas-trampa")
def obtener_alertas_trampa(
    supermercado: str | None = Query(default=None, max_length=100),
    categoria: str | None = Query(default=None, max_length=100),
    db: ConexionBaseDatos = Depends(get_db),
):
  try:
    resultado = _consulta_auditoria_filtrada(
        "🔴", "ahorro_real_pct ASC", supermercado, categoria, db
    )
    return {
      "status": "success",
      "count": len(resultado),
      "data": resultado,
    }
  except Exception as e:
    raise error_de_datos("Error consultando alertas trampa", e)


@app.get("/api/productos/{id_link}/historial")
def obtener_historial_producto(
    id_link: int,
    dias: int = Query(default=21, ge=1, le=21),
    db: ConexionBaseDatos = Depends(get_db),
):
  query = """
        SELECT DISTINCT ON (DATE(p.created_at))
            p.created_at::date AS fecha,
            p.precio_normal,
            p.precio_descuento,
            p.precio_final
        FROM public.precios_productos p
        WHERE p.id_link = %s
          AND p.created_at >= CURRENT_DATE - (%s::integer - 1)
        ORDER BY DATE(p.created_at), p.created_at DESC;
    """
  try:
    rows = leer_dataframe(db, query, params=(id_link, dias))
    return {
        "status": "success",
        "id_link": id_link,
        "dias": dias,
        "count": len(rows),
        "data": rows,
    }
  except Exception as e:
    raise error_de_datos("Error consultando historial de precios", e)


# ==========================================
# ESTRUCTURAS DE DATOS (PAYLOADS MODEL)
# ==========================================
class CanastaRequest(BaseModel):
  productos: List[str] = Field(min_length=1, max_length=50)


# ==========================================
# ENDPOINTS AVANZADOS DE BÚSQUEDA Y NEGOCIO
# ==========================================


@app.get("/api/productos")
def listar_productos_maestros(db: ConexionBaseDatos = Depends(get_db)):
  query = "SELECT DISTINCT nombre_generico FROM public.productos_maestros WHERE nombre_generico IS NOT NULL ORDER BY nombre_generico ASC;"
  try:
    cursor = db.connection.cursor()
    cursor.execute(query)
    productos = [fila[0] for fila in cursor.fetchall()]
    return {
        "status": "success",
        "count": len(productos),
        "data": productos,
    }
  except Exception as e:
    raise error_de_datos("Error listando productos maestros", e)


@app.get("/api/buscar")
def buscar_productos(
    q: str = Query(..., min_length=2, max_length=100),
    db: ConexionBaseDatos = Depends(get_db),
):
  termino = " ".join(q.split())
  if len(termino) < 2:
    raise HTTPException(
        status_code=400,
        detail="La query de búsqueda debe tener al menos 2 caracteres.",
    )

  # Hacemos JOIN con categorías para que la tarjeta del frontend tenga todos los datos completos
  query = (
      LATEST_AUDIT_QUERY
      + """
        SELECT pr.*, 
               COALESCE(pr.precio_descuento, pr.precio_normal) AS precio_final,
               c.nombre AS categoria
        FROM precios_recientes pr
        LEFT JOIN public.link_productos l ON l.id = pr.id_link
        LEFT JOIN public.productos_maestros pm ON pm.id = l.id_maestro
        LEFT JOIN public.categorias c ON c.id = pm.id_categoria
        WHERE pr.nombre_generico ILIKE %s OR pr.url_producto ILIKE %s
        ORDER BY precio_final ASC;
    """
  )
  param_busqueda = f"%{termino}%"

  try:
    resultado = leer_dataframe(
        db, query, params=(param_busqueda, param_busqueda)
    )
    return {
        "status": "success",
        "term": termino,
        "count": len(resultado),
        "data": resultado,
    }
  except Exception as e:
    raise error_de_datos("Error en buscador", e)


@app.post("/api/comparar-canasta")
def comparar_canasta(
    payload: CanastaRequest, db: ConexionBaseDatos = Depends(get_db)
):
  productos = list(
      dict.fromkeys(
          " ".join(producto.split())
          for producto in payload.productos
          if producto.strip()
      )
  )
  if not productos:
    raise HTTPException(
        status_code=400,
        detail="La canasta de productos no puede estar vacía.",
    )

  query = """
        SELECT DISTINCT ON (supermercado, nombre_generico)
            supermercado, nombre_generico, 
            COALESCE(precio_descuento, precio_normal) AS precio_efectivo, 
            semaforo, created_at
        FROM public.vista_auditoria_consumo
        WHERE nombre_generico = ANY(%s)
        ORDER BY supermercado, nombre_generico, created_at DESC;
    """

  try:
    df = pd.read_sql(query, db.engine, params=(productos,))

    if df.empty:
      return {
          "status": "success",
          "mensaje": (
              "No se encontraron precios vigentes para los productos"
              " seleccionados."
          ),
          "totales": {},
          "desglose": {},
      }

    df_totales = (
        df.groupby("supermercado")["precio_efectivo"].sum().reset_index()
    )
    df_totales = df_totales.sort_values(by="precio_efectivo", ascending=True)
    totales_dict = (
        df_totales.set_index("supermercado")["precio_efectivo"].to_dict()
    )

    desglose_dict = {}
    for superm in df["supermercado"].unique():
      df_sub = df[df["supermercado"] == superm]
      desglose_dict[superm] = df_sub.set_index("nombre_generico")[
          ["precio_efectivo", "semaforo"]
      ].to_dict(orient="index")

    return {
        "status": "success",
        "productos_solicitados": productos,
        "totales": totales_dict,
        "desglose": desglose_dict,
        "items": df.to_dict(orient="records"),
    }
  except Exception as e:
    raise error_de_datos("Error optimizando presupuesto de canasta", e)