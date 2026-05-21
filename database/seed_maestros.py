import os
import sys
import logging
import pandas as pd
from urllib.parse import urlparse
import re
from psycopg2.extras import execute_values
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
from data_pipeline.utils.utils_db import ConexionBaseDatos

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def clean_product_name(url):
    """
    Extrae y limpia el nombre del producto de la URL para usarlo como llave de agrupamiento.
    """
    try:
        path = urlparse(url).path.strip('/')
        segments = path.split('/')
        
        # Si el último segmento es "p" (caso Carrefour), tomamos el anterior
        if segments[-1] == 'p' and len(segments) > 1:
            filename = segments[-2]
        else:
            filename = segments[-1]
        
        # Eliminar sufijos de URLs
        filename = filename.replace('.html', '')
        
        # Reemplazar guiones por espacios
        name = filename.replace('_', ' ').replace('-', ' ')
        
        # Remover códigos numéricos largos al final (ej. de Carrefour)
        name = re.sub(r'\b\d{5,}\b', '', name) 
        
        # Normalizar espacios
        name = " ".join(name.split()).title()
        
        return name if len(name) > 2 else "Producto Desconocido"
    except:
        return "Producto Desconocido"

def normalize(s):
    """Normaliza texto: pasa a minúsculas, elimina espacios extra, puntos finales y acentos."""
    s = str(s).lower().strip().rstrip('.')
    
    # Mapeo manual para corregir diferencias comunes entre el Excel y la BD
    sinonimos = {
        'shampoo': 'champu',
        'toallitas': 'toallitas femeninas',
        'tomate': 'tomate perita',
        'piedritas / arena sanitaria para gatos': 'arena sanitaria para gatos'
    }
    
    s_norm = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    
    return sinonimos.get(s_norm, s_norm)

def run_seeder_maestros():
    db = ConexionBaseDatos(
        host=settings.db.host,
        user=settings.db.user,
        password=settings.db.password,
        database=settings.db.name,
        port=settings.db.port
    )
    
    if not db.connect_db():
        logger.error("No se pudo conectar a la BD.")
        return

    try:
        files_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data_pipeline', 'files')
        excel_path = os.path.join(files_dir, 'Links_productos_Fichá.xlsx')
        
        logger.info(f"Leyendo Excel: {excel_path}")
        xls = pd.ExcelFile(excel_path)
        
        with db.engine.connect() as conn:
            cursor = conn.connection.cursor()
            
            # 1. Obtener mapeo de Supermercados desde la BD
            cursor.execute("SELECT id, nombre FROM supermercados")
            supers = cursor.fetchall()
            super_map = {normalize(nombre): id_super for id_super, nombre in supers}
            
            # 2. Obtener mapeo de Categorías desde la BD
            cursor.execute("SELECT id, nombre FROM categorias")
            cats = cursor.fetchall()
            cat_map = {normalize(nombre): id_cat for id_cat, nombre in cats}
            
            # 3. Leer hojas del Excel y unificar links
            links_crudos = []
            for sheet_name in xls.sheet_names:
                if normalize(sheet_name) == 'categorias':
                    continue
                    
                df_sheet = pd.read_excel(xls, sheet_name=sheet_name)
                # Normalizar nombre del super para buscar su ID
                id_super = super_map.get(normalize(sheet_name))
                if not id_super:
                    logger.warning(f"Supermercado '{sheet_name}' no encontrado en BD. Omitiendo hoja.")
                    continue
                
                for _, row in df_sheet.iterrows():
                    nombre_cat = row.get('Producto')
                    url = row.get('Link')
                    
                    if pd.isna(nombre_cat) or pd.isna(url):
                        continue
                        
                    id_cat = cat_map.get(normalize(nombre_cat))
                    if not id_cat:
                        logger.warning(f"Categoría '{nombre_cat}' no encontrada en BD. Omitiendo link: {url}")
                        continue
                        
                    links_crudos.append({
                        'url': str(url).strip(),
                        'id_cat': id_cat,
                        'id_super': id_super
                    })
            
            logger.info(f"Total de links extraídos del Excel: {len(links_crudos)}")

            logger.info("Vaciando tablas para el Seeding Definitivo (Maestros, Links y Precios)...")
            # IMPORTANTE: NO truncar supermercados ni categorias porque el usuario ya las llenó
            cursor.execute("TRUNCATE TABLE productos_maestros, link_productos, extracciones, precios_productos RESTART IDENTITY CASCADE;")
            
            # 4. Lógica de Agrupamiento
            logger.info("Agrupando productos maestros...")
            maestros_map = {}
            maestros_creados = 0
            links_records = []
            
            for item in links_crudos:
                url = item['url']
                id_cat = item['id_cat']
                
                nombre_generico = clean_product_name(url)
                maestro_key = f"{nombre_generico}_{id_cat}"
                
                if maestro_key not in maestros_map:
                    # Crear nuevo maestro
                    cursor.execute(
                        "INSERT INTO productos_maestros (nombre_generico, id_categoria) VALUES (%s, %s) RETURNING id",
                        (nombre_generico, id_cat)
                    )
                    id_maestro = cursor.fetchone()[0]
                    maestros_map[maestro_key] = id_maestro
                    maestros_creados += 1
                else:
                    id_maestro = maestros_map[maestro_key]
                
                # Asumimos 'activo' = True
                links_records.append((
                    id_maestro, 
                    item['id_super'], 
                    url, 
                    True
                ))

            logger.info("Insertando links por lotes (Bulk Insert)...")
            execute_values(
                cursor,
                "INSERT INTO link_productos (id_maestro, id_supermercado, url_producto, activo) VALUES %s",
                links_records
            )
            links_insertados = len(links_records)

            conn.connection.commit()
            cursor.close()
            
        logger.info(f"✅ Seeding Completado! Se crearon {maestros_creados} productos maestros únicos a partir de {links_insertados} enlaces.")

    except Exception as e:
        logger.error(f"Error en el seeding: {e}")
    finally:
        db.close_connections()

if __name__ == "__main__":
    run_seeder_maestros()
