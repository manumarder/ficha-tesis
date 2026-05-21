"""
Módulo de Extracción para Canasta Básica
Responsabilidad: Leer links de BASE DE DATOS e extraer productos
"""
import os
import sys
import pandas as pd
import logging
import time
import threading
import queue
from datetime import datetime
from typing import Dict, List
from dotenv import load_dotenv
import random

# Agregar directorio padre (raíz del proyecto)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from data_pipeline.utils.utils_db import ConexionBaseDatos  # Usamos DB en lugar de Sheets
from utils.cookie_manager import CookieManager
from utils.optimization import ResultCache, set_parallel_mode
from extractors.carrefour_extractor import CarrefourExtractor
from extractors.delimart_extractor import DelimartExtractor
from extractors.depot_extractor import DepotExtractor
from extractors.dia_extractor import DiaExtractor

logger = logging.getLogger(__name__)

class ExtractCanastaBasica:
    def __init__(self, enable_parallel: bool = True, max_workers: int = 3):
        load_dotenv()
        self.enable_parallel = enable_parallel
        self.max_workers = max_workers if enable_parallel else 1
        
        # Mapeo de clases
        self.extractor_classes = {
            'Carrefour': CarrefourExtractor,
            'Delimart': DelimartExtractor,
            'Depot': DepotExtractor, 
            'Día': DiaExtractor,
            'dia': DiaExtractor,
            'DIA%': DiaExtractor
        }

        from config.settings import settings
        self.db = ConexionBaseDatos(
            host=settings.db.host,
            user=settings.db.user,
            password=settings.db.password,
            database=settings.db.name,
            port=settings.db.port
        )

        # Cookies y Cache
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.cookie_manager = CookieManager(base_dir)
        cache_dir = os.path.join(base_dir, 'cache')
        self.result_cache = ResultCache(cache_dir)

    def read_links_from_db(self, supermercado_filtro=None) -> List[Dict]:
        """
        Lee los links activos directamente de la base de datos.
        Retorna una lista de diccionarios con la info necesaria.
        """
        logger.info("[EXTRACT] Leyendo links de la base de datos...")
        
        if not self.db.connect_db():
            raise Exception("No se pudo conectar a la BD para leer links")

        # Query optimizada con JOIN para traer el nombre del super
        query = """
            SELECT 
                lp.id as id_link_producto, 
                lp.url_producto as link, 
                s.nombre as nombre_super
            FROM link_productos lp
            JOIN supermercados s ON lp.id_supermercado = s.id
            WHERE lp.activo = TRUE
        """
        
        params = None
        if supermercado_filtro:
            query += " AND s.nombre = %s"
            params = (supermercado_filtro,)
        
        try:
            # Ejecutar query usando pandas para facilitar el manejo
            df_links = pd.read_sql(query, self.db.connection, params=params)
            
            # Convertir a lista de diccionarios para el procesamiento
            links_list = df_links.to_dict('records')
            logger.info(f"[EXTRACT] Se obtuvieron {len(links_list)} links activos.")
            return links_list
            
        except Exception as e:
            logger.error(f"Error leyendo links de DB: {e}")
            return []
        finally:
            self.db.close_connections()

    def extract(self, links_list: List[Dict]) -> pd.DataFrame:
        """Proceso principal de extracción"""
        logger.info(f"[EXTRACT] Iniciando extracción con {self.max_workers} workers...")
        
        # Activar modo paralelo para evitar limpiezas globales accidentales que maten otros browsers
        set_parallel_mode(True)
        
        start_time = time.time()
        
        try:
            # 1. Llenar la cola
            task_queue = queue.Queue()
            
            for item in links_list:
                # Mapear nombre de DB a clave del extractor (normalizando si es necesario)
                # El diccionario extractor_classes usa los nombres exactos de la BD ahora
                super_name = item['nombre_super']
                
                if super_name in self.extractor_classes:
                    task = {
                        'id_link_producto': item['id_link_producto'], # VITAL para la carga
                        'supermarket': super_name,
                        'url': item['link']
                    }
                    task_queue.put(task)
                else:
                    logger.warning(f"No hay extractor configurado para: {super_name}")

            total_tasks = task_queue.qsize()
            logger.info(f"[EXTRACT] Cola generada con {total_tasks} tareas.")

            results_list = []
            results_lock = threading.Lock()

            # 2. Worker Loop
            def worker_loop(worker_id):
                # AJUSTE: Delay aleatorio entre el inicio de cada worker para evitar logins simultáneos
                stagger_delay = random.uniform(1, 3)
                logger.info(f"[WORKER {worker_id}] Esperando {stagger_delay:.2f}s para inicio escalonado...")
                time.sleep(stagger_delay)
                
                local_extractors = {}
                while True:
                    try:
                        task = task_queue.get(block=False)
                    except queue.Empty:
                        break
                    
                    sm = task['supermarket']
                    
                    try:
                        if sm not in local_extractors:
                            # Instanciamos la clase (ej: LareinaExtractor)
                            local_extractors[sm] = self.extractor_classes[sm]()

                        df_result = self._process_single_task(local_extractors[sm], task)
                        
                        if not df_result.empty:
                            with results_lock:
                                results_list.append(df_result)
                    
                    except Exception as e:
                        logger.error(f"[WORKER {worker_id}] Error: {e}")
                    finally:
                        task_queue.task_done()
                
                # Limpieza del worker
                for ext in local_extractors.values():
                    if hasattr(ext, 'cleanup_driver'): ext.cleanup_driver()
                    elif hasattr(ext, 'driver') and ext.driver: ext.driver.quit()

            # 3. Lanzar hilos
            threads = []
            num_workers = min(self.max_workers, total_tasks)
            if num_workers < 1: num_workers = 1

            for i in range(num_workers):
                t = threading.Thread(target=worker_loop, args=(i,))
                t.start()
                threads.append(t)

            for t in threads:
                t.join()

            # 4. Consolidar
            final_df = pd.DataFrame()
            if results_list:
                final_df = pd.concat(results_list, ignore_index=True)
            
            elapsed = time.time() - start_time
            logger.info(f"[EXTRACT] Finalizado en {elapsed:.2f}s. Registros extraídos: {len(final_df)}")
            return final_df
        finally:
            # Desactivar modo paralelo al terminar
            set_parallel_mode(False)

    def _raw_extract_to_dataframe(self, raw_data) -> pd.DataFrame:
        """
        Normaliza la salida de extraer_producto a un DataFrame.
        Varios extractores devuelven dict; Parada Canga devuelve list[dict];
        Carrefour devolvía None ante excepciones (antes se marcaba todo como SIN_DATOS).
        """
        if raw_data is None:
            return pd.DataFrame([{'error_type': 'SIN_DATOS'}])
        if isinstance(raw_data, pd.DataFrame):
            return raw_data if not raw_data.empty else pd.DataFrame([{'error_type': 'SIN_DATOS'}])
        if isinstance(raw_data, dict):
            return pd.DataFrame([raw_data])
        if isinstance(raw_data, list):
            if not raw_data:
                return pd.DataFrame([{'error_type': 'SIN_DATOS'}])
            rows = [r for r in raw_data if isinstance(r, dict)]
            if not rows:
                return pd.DataFrame([{'error_type': 'SIN_DATOS'}])
            return pd.DataFrame(rows)
        return pd.DataFrame([{'error_type': 'SIN_DATOS'}])

    def _process_single_task(self, extractor, task) -> pd.DataFrame:
        url = task['url']
        
        # Intentar extracción
        try:
            raw_data = extractor.extraer_producto(url)
        except Exception as e:
            raw_data = {'error_type': str(e)}

        df = self._raw_extract_to_dataframe(raw_data)

        if df.empty: return df

        # INYECTAR DATOS DE LA BASE (CLAVE FORÁNEA)
        df['id_link_producto'] = task['id_link_producto']

        # DIA (y similares) pueden devolver 'unidad_medida'; transform espera 'unidad' → unidad_medida
        if 'unidad' not in df.columns and 'unidad_medida' in df.columns:
            df = df.rename(columns={'unidad_medida': 'unidad'})
        
        return df