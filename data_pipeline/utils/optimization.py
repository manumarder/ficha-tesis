"""
Módulo de optimizaciones para mejorar el rendimiento del pipeline
Incluye procesamiento paralelo, caché y optimizaciones de tiempo
"""
import os
import time
import subprocess
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Callable, Any, Optional
from functools import wraps
import hashlib
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

logger = logging.getLogger(__name__)

# Flag global para saber si estamos en ejecución paralela
_PARALLEL_ACTIVE = False

def set_parallel_mode(active: bool):
    global _PARALLEL_ACTIVE
    _PARALLEL_ACTIVE = active


def cleanup_environment(force=False):
    """
    Matar procesos de ejecuciones anteriores y limpiar archivos temporales.
    Llamar al inicio y después de bloques de extracción.
    Si force=False y estamos en modo paralelo, no mata procesos globales.
    """
    if _PARALLEL_ACTIVE and not force:
        logger.debug("[SYSTEM] Modo paralelo activo, limpieza global omitida para evitar afectar a otros hilos.")
        return

    logger.info("[SYSTEM] Ejecutando limpieza de ambiente (Self-healing)...")
    try:
        # Matar procesos de chrome y chromedriver
        if os.name == 'posix':  # Linux/Ubuntu
            os.system("pkill -9 -f chrome || true")
            os.system("pkill -9 -f chromedriver || true")
            # Limpiar archivos temporales de Chrome
            os.system("rm -rf /tmp/.com.google.Chrome.*")
            os.system("rm -rf /tmp/crashpad")
        else:  # Windows fallback
            os.system("taskkill /f /im chrome.exe /t >nul 2>&1")
            os.system("taskkill /f /im chromedriver.exe /t >nul 2>&1")
        
        logger.info("[SYSTEM] Limpieza completada.")
    except Exception as e:
        logger.error(f"[SYSTEM] Error durante la limpieza: {e}")


def timeit(func: Callable) -> Callable:
    """Decorador para medir el tiempo de ejecución de funciones"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        logger.debug(f"[TIMING] {func.__name__} ejecutado en {elapsed:.2f}s")
        return result
    return wrapper


class SmartWait:
    """Clase para esperas inteligentes en lugar de time.sleep() fijos"""
    
    @staticmethod
    def wait_for_element(driver, selector, timeout=10, poll_frequency=0.5):
        """
        Espera inteligente para elementos usando WebDriverWait
        
        Args:
            driver: Instancia de WebDriver
            selector: Selector del elemento
            timeout: Tiempo máximo de espera
            poll_frequency: Frecuencia de verificación
            
        Returns:
            True si el elemento aparece, False en caso contrario
        """
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By
        
        try:
            wait = WebDriverWait(driver, timeout, poll_frequency=poll_frequency)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
            return True
        except:
            return False
    
    @staticmethod
    def wait_minimal(delay=0.5):
        """
        Espera mínima solo cuando es absolutamente necesario
        
        Args:
            delay: Tiempo de espera en segundos (por defecto 0.5s)
        """
        time.sleep(delay)


class ResultCache:
    """Caché simple para resultados de extracción"""
    
    def __init__(self, cache_dir: str = None):
        """
        Inicializa el caché
        
        Args:
            cache_dir: Directorio para guardar el caché (opcional)
        """
        self.cache_dir = cache_dir
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)
        self.memory_cache = {}
    
    def _get_cache_key(self, url: str, timestamp: str = None) -> str:
        """
        Genera una clave única para el caché
        
        Args:
            url: URL del producto
            timestamp: Timestamp opcional para invalidar caché
            
        Returns:
            Clave de caché
        """
        key_data = f"{url}_{timestamp or ''}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, url: str, max_age_hours: int = 24) -> Optional[Dict]:
        """
        Obtiene un resultado del caché si existe y no está expirado
        
        Args:
            url: URL del producto
            max_age_hours: Edad máxima del caché en horas
            
        Returns:
            Resultado en caché o None
        """
        # Verificar caché en memoria primero
        if url in self.memory_cache:
            cached_data, cached_time = self.memory_cache[url]
            age_hours = (time.time() - cached_time) / 3600
            
            if age_hours < max_age_hours:
                logger.debug(f"[CACHE] Hit en memoria para {url}")
                return cached_data
            else:
                del self.memory_cache[url]
        
        return None
    
    def set(self, url: str, data: Dict):
        """
        Guarda un resultado en el caché
        
        Args:
            url: URL del producto
            data: Datos a guardar
        """
        self.memory_cache[url] = (data, time.time())
        logger.debug(f"[CACHE] Guardado en memoria para {url}")


class ParallelProcessor:
    """Procesador paralelo para ejecutar tareas en múltiples threads"""
    
    def __init__(self, max_workers: int = 3):
        """
        Inicializa el procesador paralelo
        
        Args:
            max_workers: Número máximo de workers paralelos
        """
        self.max_workers = max_workers
        logger.info(f"[PARALLEL] Procesador inicializado con {max_workers} workers")
    
    def process_supermarkets(self, 
                            supermarkets_data: Dict[str, Any],
                            process_func: Callable,
                            *args, **kwargs) -> Dict[str, Any]:
        """
        Procesa múltiples supermercados en paralelo
        
        Args:
            supermarkets_data: Diccionario con datos por supermercado
            process_func: Función a ejecutar para cada supermercado
            *args, **kwargs: Argumentos adicionales para process_func
            
        Returns:
            Diccionario con resultados por supermercado
        """
        results = {}
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Enviar tareas
            future_to_supermarket = {
                executor.submit(process_func, supermarket, data, *args, **kwargs): supermarket
                for supermarket, data in supermarkets_data.items()
            }
            
            # Recoger resultados
            for future in as_completed(future_to_supermarket):
                supermarket = future_to_supermarket[future]
                try:
                    result = future.result()
                    results[supermarket] = result
                    logger.info(f"[PARALLEL] {supermarket} completado")
                except Exception as e:
                    logger.error(f"[PARALLEL] Error procesando {supermarket}: {e}")
                    results[supermarket] = None
        
        return results
    
    def process_products_batch(self,
                              products: List[Dict],
                              process_func: Callable,
                              batch_size: int = 10,
                              *args, **kwargs) -> List[Any]:
        """
        Procesa productos en lotes paralelos
        
        Args:
            products: Lista de productos a procesar
            process_func: Función a ejecutar para cada producto
            batch_size: Tamaño del lote
            *args, **kwargs: Argumentos adicionales para process_func
            
        Returns:
            Lista de resultados
        """
        results = []
        
        # Dividir en lotes
        batches = [products[i:i + batch_size] for i in range(0, len(products), batch_size)]
        
        logger.info(f"[PARALLEL] Procesando {len(products)} productos en {len(batches)} lotes")
        
        for batch_idx, batch in enumerate(batches, 1):
            logger.info(f"[PARALLEL] Procesando lote {batch_idx}/{len(batches)} ({len(batch)} productos)")
            
            with ThreadPoolExecutor(max_workers=min(self.max_workers, len(batch))) as executor:
                futures = [
                    executor.submit(process_func, product, *args, **kwargs)
                    for product in batch
                ]
                
                for future in as_completed(futures):
                    try:
                        result = future.result()
                        if result:
                            results.append(result)
                    except Exception as e:
                        logger.error(f"[PARALLEL] Error procesando producto: {e}")
        
        return results


def optimize_driver_options(options: Options):
    """
    Optimiza las opciones del driver de Selenium para mejor rendimiento y estabilidad.
    Incluye argumentos obligatorios para entornos de servidor (AWS EC2).
    """
    # ARGUMENTOS OBLIGATORIOS PARA ESTABILIDAD EN SERVIDOR
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage') # CRÍTICO: Mueve la memoria compartida al disco
    options.add_argument('--disable-gpu')
    # REMOVIDO: options.add_argument('--remote-debugging-port=9222') 
    # Provocaba conflictos al abrir múltiples drivers en paralelo
    
    # Optimizaciones de rendimiento adicionales
    options.page_load_strategy = 'eager'
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-plugins')
    options.add_argument('--disable-images')
    options.add_argument('--blink-settings=imagesEnabled=false')
    
    # Bloquear imágenes vía prefs
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.default_content_setting_values.notifications": 2
    }
    options.add_experimental_option("prefs", prefs)
    
    logger.debug("[OPTIMIZATION] Opciones del driver estandarizadas para servidor")


def create_driver_with_retry(options: Options, max_retries: int = 2, wait_seconds: int = 5):
    """
    Intenta crear una instancia de webdriver.Chrome con lógica de reintento.
    """
    from selenium.common.exceptions import SessionNotCreatedException, WebDriverException
    
    for attempt in range(max_retries + 1):
        try:
            driver = webdriver.Chrome(options=options)
            
            # Ajuste de Timeouts solicitado por el usuario (40 segundos)
            driver.set_page_load_timeout(40)
            driver.set_script_timeout(40)
            
            return driver
        except (SessionNotCreatedException, WebDriverException) as e:
            if attempt < max_retries:
                logger.warning(f"[RETRY] Fallo al crear driver (Intento {attempt + 1}/{max_retries + 1}): {e}")
                logger.info(f"[RETRY] Ejecutando limpieza y esperando {wait_seconds}s...")
                cleanup_environment()
                time.sleep(wait_seconds)
            else:
                logger.error(f"[ERROR] No se pudo crear el driver tras {max_retries + 1} intentos.")
                raise
    return None


def reduce_wait_times(func: Callable) -> Callable:
    """
    Decorador para reducir tiempos de espera en funciones de extracción
    
    Args:
        func: Función a decorar
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Reducir timeouts si están configurados
        original_timeout = kwargs.get('timeout', 30)
        if original_timeout > 15:
            kwargs['timeout'] = 15
            logger.debug(f"[OPTIMIZATION] Timeout reducido de {original_timeout} a 15s")
        
        return func(*args, **kwargs)
    return wrapper


