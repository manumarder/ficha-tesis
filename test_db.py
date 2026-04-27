import logging
from config.settings import settings
from data_pipeline.utils.utils_db import ConexionBaseDatos

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_connection():
    logger.info(f"Intentando conectar a {settings.db.host}:{settings.db.port}...")
    logger.info(f"Base de datos: {settings.db.name}")
    logger.info(f"Usuario: {settings.db.user}")
    
    db = ConexionBaseDatos(
        host=settings.db.host,
        user=settings.db.user,
        password=settings.db.password,
        database=settings.db.name,
        port=settings.db.port
    )
    
    # Intentar conectar
    success = db.connect_db()
    
    if success:
        logger.info("✅ ¡CONEXIÓN EXITOSA A GOOGLE CLOUD SQL!")
        # Cerrar conexión
        db.close_connections()
    else:
        logger.error("❌ ERROR AL CONECTARSE A LA BASE DE DATOS.")
        logger.info("Posibles causas:")
        logger.info("1. Tu IP pública cambió y no está autorizada en Google Cloud.")
        logger.info("2. La base de datos no existe (revisa el menú 'Bases de datos' en Cloud SQL).")
        logger.info("3. La contraseña es incorrecta.")

if __name__ == "__main__":
    test_connection()
