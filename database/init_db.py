import os
import sys
import logging

# Añadir el directorio raíz al path para poder importar config y data_pipeline
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from config.settings import settings
from data_pipeline.utils.utils_db import ConexionBaseDatos

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def inicializar_base_datos():
    # Ruta al archivo SQL
    schema_path = os.path.join(os.path.dirname(__file__), 'schema', 'database_schema.sql')
    
    if not os.path.exists(schema_path):
        logger.error(f"❌ No se encontró el archivo {schema_path}")
        return

    logger.info(f"Leyendo esquema desde: {schema_path}")
    with open(schema_path, 'r', encoding='utf-8') as file:
        sql_script = file.read()

    db = ConexionBaseDatos(
        host=settings.db.host,
        user=settings.db.user,
        password=settings.db.password,
        database=settings.db.name,
        port=settings.db.port,
        database_url=settings.db.database_url,
        ssl_mode=settings.db.ssl_mode
    )
    
    if db.connect_db():
        try:
            logger.info("⏳ Ejecutando script SQL...")
            with db.engine.connect() as conn:
                # SQLAlchemy text() maneja multiples sentencias si ejecutamos el bloque entero.
                # A veces es mejor separar por punto y coma si falla, pero SQLAlchemy psycopg2 suele soportarlo
                # si usamos conn.connection.cursor()
                cursor = conn.connection.cursor()
                cursor.execute(sql_script)
                conn.connection.commit()
                cursor.close()
            logger.info("✅ ¡Base de datos inicializada correctamente con todas las tablas y vistas!")
        except Exception as e:
            logger.error(f"❌ Error al ejecutar el SQL: {e}")
        finally:
            db.close_connections()
    else:
        logger.error("❌ No se pudo conectar a la base de datos.")

if __name__ == "__main__":
    inicializar_base_datos()
