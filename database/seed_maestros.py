import os
import sys
import logging
import pandas as pd
from pathlib import Path
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

    sinonimos = {
        'shampoo': 'champu',
        'toallitas': 'toallitas femeninas',
        'tomate': 'tomate perita',
        'piedritas / arena sanitaria para gatos': 'arena sanitaria para gatos'
    }

    s_norm = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    s_norm = ' '.join(s_norm.split())

    return sinonimos.get(s_norm, s_norm)


def find_workbook_path():
    """Busca el Excel maestro dentro de data_pipeline/files."""
    files_dir = Path(__file__).resolve().parent.parent / 'data_pipeline' / 'files'
    candidates = [
        files_dir / 'Ficha_tablas_20260527.xlsx',
        files_dir / 'Links_productos_Fichá.xlsx',
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError('No se encontró el archivo Excel maestro en data_pipeline/files/.')


def upsert_supermercados(cursor, df_super):
    """Actualiza supermercados desde la hoja de Excel."""
    existing = {}
    cursor.execute('SELECT id, nombre FROM supermercados')
    for id_super, nombre in cursor.fetchall():
        existing[normalize(nombre)] = id_super

    inserted = 0
    for _, row in df_super.iterrows():
        nombre = str(row.get('nombre') or '').strip()
        url_base = row.get('url_base') or None
        activo = bool(row.get('activo', True)) if not pd.isna(row.get('activo')) else True

        if not nombre:
            continue

        key = normalize(nombre)
        id_super = existing.get(key)

        if id_super is not None:
            cursor.execute(
                'UPDATE supermercados SET nombre=%s, url_base=%s, activo=%s WHERE id=%s',
                (nombre, url_base, activo, id_super)
            )
        else:
            cursor.execute(
                'INSERT INTO supermercados (nombre, url_base, activo) VALUES (%s, %s, %s) RETURNING id',
                (nombre, url_base, activo)
            )
            id_super = cursor.fetchone()[0]
            existing[key] = id_super
            inserted += 1

    return existing, inserted


def upsert_categorias(cursor, df_cat):
    """Actualiza categorías desde la hoja de Excel."""
    existing = {}
    cursor.execute('SELECT id, nombre FROM categorias')
    for id_cat, nombre in cursor.fetchall():
        existing[normalize(nombre)] = id_cat

    inserted = 0
    for _, row in df_cat.iterrows():
        nombre = str(row.get('nombre') or '').strip()
        if not nombre:
            continue

        key = normalize(nombre)
        id_cat = existing.get(key)

        if id_cat is not None:
            cursor.execute('UPDATE categorias SET nombre=%s WHERE id=%s', (nombre, id_cat))
        else:
            cursor.execute('INSERT INTO categorias (nombre) VALUES (%s) RETURNING id', (nombre,))
            id_cat = cursor.fetchone()[0]
            existing[key] = id_cat
            inserted += 1

    return existing, inserted


def run_seeder_maestros():
    db = ConexionBaseDatos(
        host=settings.db.host,
        user=settings.db.user,
        password=settings.db.password,
        database=settings.db.name,
        port=settings.db.port,
        database_url=settings.db.database_url,
        ssl_mode=settings.db.ssl_mode
    )
    
    if not db.connect_db():
        logger.error("No se pudo conectar a la BD.")
        return

    try:
        excel_path = find_workbook_path()
        logger.info(f"Leyendo Excel: {excel_path}")
        xls = pd.ExcelFile(excel_path)

        with db.engine.connect() as conn:
            cursor = conn.connection.cursor()

            df_super = pd.read_excel(xls, sheet_name='supermercados') if 'supermercados' in xls.sheet_names else pd.DataFrame()
            df_cat = pd.read_excel(xls, sheet_name='categorias') if 'categorias' in xls.sheet_names else pd.DataFrame()

            if df_super.empty:
                logger.warning('No se encontró la hoja "supermercados" en el Excel; se omite la actualización.')
            else:
                super_map, supers_insertados = upsert_supermercados(cursor, df_super)
                logger.info(f"Supermercados actualizados/insertados: {supers_insertados}")

            if df_cat.empty:
                logger.warning('No se encontró la hoja "categorias" en el Excel; se omite la actualización.')
            else:
                cat_map, cats_insertados = upsert_categorias(cursor, df_cat)
                logger.info(f"Categorías actualizadas/insertadas: {cats_insertados}")

            super_map = super_map if 'super_map' in locals() else {}
            cat_map = cat_map if 'cat_map' in locals() else {}

            links_crudos = []
            for sheet_name in xls.sheet_names:
                norm_sheet = normalize(sheet_name)
                if norm_sheet in ('supermercados', 'categorias'):
                    continue

                df_sheet = pd.read_excel(xls, sheet_name=sheet_name)
                id_super = super_map.get(norm_sheet)
                if id_super is None:
                    logger.warning(f"Supermercado '{sheet_name}' no encontrado en la tabla. Omitiendo hoja.")
                    continue

                for _, row in df_sheet.iterrows():
                    nombre_cat = row.get('Producto')
                    url = row.get('Link')

                    if pd.isna(nombre_cat) or pd.isna(url):
                        continue

                    id_cat = cat_map.get(normalize(nombre_cat))
                    if id_cat is None:
                        logger.warning(f"Categoría '{nombre_cat}' no encontrada en BD. Omitiendo link: {url}")
                        continue

                    links_crudos.append({
                        'url': str(url).strip(),
                        'id_cat': id_cat,
                        'id_super': id_super,
                    })

            logger.info(f"Total de links extraídos del Excel: {len(links_crudos)}")

            if links_crudos:
                logger.info('Actualizando links desde el Excel (refresh por supermercado)...')
                existing_links = {}
                cursor.execute('SELECT id, id_supermercado, url_producto FROM link_productos')
                for id_link, id_super, url in cursor.fetchall():
                    existing_links[(int(id_super), normalize(url))] = id_link

                for sheet_name in xls.sheet_names:
                    norm_sheet = normalize(sheet_name)
                    if norm_sheet in ('supermercados', 'categorias'):
                        continue

                maestros_map = {}
                maestros_creados = 0
                links_records = []

                for item in links_crudos:
                    url = item['url']
                    id_cat = item['id_cat']
                    id_super = item['id_super']

                    nombre_generico = clean_product_name(url)
                    maestro_key = f"{nombre_generico}_{id_cat}"

                    if maestro_key not in maestros_map:
                        cursor.execute(
                            'SELECT id FROM productos_maestros WHERE nombre_generico=%s AND id_categoria=%s LIMIT 1',
                            (nombre_generico, id_cat)
                        )
                        row = cursor.fetchone()
                        if row:
                            id_maestro = row[0]
                        else:
                            cursor.execute(
                                'INSERT INTO productos_maestros (nombre_generico, id_categoria) VALUES (%s, %s) RETURNING id',
                                (nombre_generico, id_cat)
                            )
                            id_maestro = cursor.fetchone()[0]
                            maestros_creados += 1
                        maestros_map[maestro_key] = id_maestro
                    else:
                        id_maestro = maestros_map[maestro_key]

                    key = (id_super, normalize(url))
                    existing_id = existing_links.get(key)
                    if existing_id:
                        cursor.execute(
                            'UPDATE link_productos SET id_maestro=%s, url_producto=%s, activo=%s WHERE id=%s',
                            (id_maestro, url, True, existing_id)
                        )
                    else:
                        links_records.append((id_maestro, id_super, url, True))

                if links_records:
                    execute_values(
                        cursor,
                        'INSERT INTO link_productos (id_maestro, id_supermercado, url_producto, activo) VALUES %s',
                        links_records
                    )

                links_insertados = len(links_records)
                conn.connection.commit()
                cursor.close()

                logger.info(f"✅ Seeding Completado! Se actualizaron supermercados/categorías y se insertaron {links_insertados} nuevos links. Se crearon {maestros_creados} productos maestros nuevos.")
            else:
                conn.connection.commit()
                cursor.close()
                logger.info('✅ Seeding Completado. No se encontraron links válidos para actualizar.')

    except Exception as e:
        logger.error(f"Error en el seeding: {e}")
    finally:
        db.close_connections()

if __name__ == "__main__":
    run_seeder_maestros()
