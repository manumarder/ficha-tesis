import os
import sys
import logging
import pandas as pd
from urllib.parse import urlparse

# Añadir el directorio raíz al path para importar
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
from data_pipeline.utils.utils_db import ConexionBaseDatos

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def generar_nombre_generico(url):
    """Extrae la última parte de la URL para usarla como nombre genérico."""
    try:
        path = urlparse(url).path
        filename = path.strip('/').split('/')[-1]
        name = filename.replace('_', ' ').replace('-', ' ').title()
        return name if name else "Producto Desconocido"
    except:
        return "Producto Desconocido"

def run_seeder():
    db = ConexionBaseDatos(
        host=settings.db.host,
        user=settings.db.user,
        password=settings.db.password,
        database=settings.db.name,
        port=settings.db.port
    )
    
    if not db.connect_db():
        logger.error("No se pudo conectar a la base de datos.")
        return

    try:
        files_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data_pipeline', 'files')
        
        df_super = pd.read_csv(os.path.join(files_dir, 'supermercados_202604242247.csv'))
        df_cat = pd.read_csv(os.path.join(files_dir, 'categorias_202604242246.csv'))
        df_links = pd.read_csv(os.path.join(files_dir, 'link_productos_202604242247.csv'))

        with db.engine.connect() as conn:
            cursor = conn.connection.cursor()
            
            # Limpiar tablas previas (Cascada)
            logger.info("Limpiando tablas...")
            cursor.execute("TRUNCATE TABLE supermercados, categorias, productos_maestros, link_productos RESTART IDENTITY CASCADE;")
            
            # 1. Insertar Supermercados
            logger.info(f"Insertando {len(df_super)} supermercados...")
            for _, row in df_super.iterrows():
                cursor.execute(
                    "INSERT INTO supermercados (id, nombre, activo) VALUES (%s, %s, %s)",
                    (row['id_super'], row['nombre'], bool(row['activo']))
                )
            
            # 2. Insertar Categorías
            logger.info(f"Insertando {len(df_cat)} categorias...")
            for _, row in df_cat.iterrows():
                cursor.execute(
                    "INSERT INTO categorias (id, nombre, descripcion) VALUES (%s, %s, %s)",
                    (row['id_categoria'], row['nombre'], row['descripcion'] if pd.notna(row['descripcion']) else None)
                )

            # 3. Insertar Productos Maestros y Links
            logger.info(f"Insertando {len(df_links)} productos maestros y enlaces...")
            
            # Para la prueba vamos a limitar a 50 links aleatorios si el archivo es muy grande, 
            # para no estar 10 minutos insertando
            if len(df_links) > 200:
                logger.info("Tomando una muestra de 200 links para la prueba piloto...")
                df_links = df_links.sample(200, random_state=42)

            for _, row in df_links.iterrows():
                nombre_generico = generar_nombre_generico(row['link'])
                
                # Crear maestro
                cursor.execute(
                    "INSERT INTO productos_maestros (nombre_generico, id_categoria) VALUES (%s, %s) RETURNING id",
                    (nombre_generico, int(row['id_categoria']))
                )
                id_maestro = cursor.fetchone()[0]
                
                # Crear link
                cursor.execute(
                    """
                    INSERT INTO link_productos (id, id_maestro, id_supermercado, url_producto, activo) 
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (int(row['id_link_producto']), id_maestro, int(row['id_supermercado']), row['link'], bool(row['activo']))
                )

            conn.connection.commit()
            cursor.close()
            
        logger.info("✅ ¡Migración de datos inicial completada con éxito!")

    except Exception as e:
        logger.error(f"Error en la migración: {e}")
    finally:
        db.close_connections()

if __name__ == "__main__":
    run_seeder()
