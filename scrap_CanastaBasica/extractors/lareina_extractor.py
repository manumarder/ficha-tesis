import os
import sys
import time
import pandas as pd
import logging
from dotenv import load_dotenv
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re
import traceback

# Agregar directorio padre al path para imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.optimization import optimize_driver_options, SmartWait, create_driver_with_retry

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('lareina_extractor')

# Cargar variables de entorno
load_dotenv()

class LareinaExtractor:
    """Extractor optimizado para La Reina"""
    
    # Configuraciones centralizadas - OPTIMIZADO
    CONFIG = {
        'timeout': 15,  # OPTIMIZADO: Reducido de 30 a 15
        'wait_between_requests': 0.3,  # OPTIMIZADO: Reducido de 1 a 0.3
        'supermarket_name': 'Lareina'
    }

    # Selectores centralizados para fácil mantenimiento
    SELECTORS = {
        'name': [
            "h1.product_title.entry-title",
            ".product_title",
            "h1.entry-title", 
            "h1"
        ],
        'price': [
            ".price .woocommerce-Price-amount.amount",
            ".woocommerce-Price-amount.amount",
            ".price",
            ".product-price",
            "[class*='price']"
        ],
        'price_normal': [  # Precio normal (sin descuento)
            "del .woocommerce-Price-amount.amount",
            ".price del",
            ".regular-price"
        ],
        'price_discount': [  # Precio con descuento
            "ins .woocommerce-Price-amount.amount", 
            ".price ins",
            ".sale-price"
        ],
        'unit_price': [
            ".unidad",
            ".price-per-unit",
            "[class*='unit']"
        ],
        'discounts': [
            ".onsale",
            ".sale-badge",
            ".discount-badge",
            ".promotion",
            "[class*='sale']",
            "[class*='discount']"
        ],
        'main_container': [
            ".summary.entry-summary",
            ".product-details",
            ".woocommerce-product-details"
        ]
    }
    
    def __init__(self):
        self.driver = None
        self.wait = None
        self.session_active = False

    def setup_driver(self):
        """Configura el driver de Selenium - OPTIMIZADO"""
        if self.driver is None:
            options = Options()
            # OPTIMIZADO: Aplicar optimizaciones automáticas (incluye flags obligatorios)
            optimize_driver_options(options)
            
            # Configuraciones adicionales específicas
            options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option('excludeSwitches', ['enable-automation'])
            options.add_experimental_option('useAutomationExtension', False)
            
            # USAR REINTENTOS PARA CREACIÓN DEL DRIVER (Resiliencia)
            self.driver = create_driver_with_retry(options, max_retries=2, wait_seconds=5)
            
            if self.driver:
                self.driver.set_page_load_timeout(15)  # OPTIMIZADO: Timeout reducido
                self.wait = WebDriverWait(self.driver, self.CONFIG['timeout'])
        
        return self.driver, self.wait
    
    def asegurar_sesion_activa(self):
        """Asegura que haya una sesión activa"""
        try:
            if self.driver is None:
                self.setup_driver()
                self.session_active = True
                logger.info("Sesión de La Reina inicializada")
                return True
            else:
                # Verificar que el driver siga funcionando
                try:
                    self.driver.current_url
                    self.session_active = True
                    return True
                except:
                    # Driver está muerto, reiniciar
                    self.cleanup_driver()
                    self.setup_driver()
                    self.session_active = True
                    return True
        except Exception as e:
            logger.error("Error asegurando sesión activa de La Reina: %s", str(e))
            self.session_active = False
            return False
    
    def guardar_sesion(self):
        """Guarda la sesión"""
        try:
            logger.debug("Sesión de La Reina - no requiere guardado especial")
            return True
        except Exception as e:
            logger.error("Error guardando sesión de La Reina: %s", str(e))
            return False
    
    def cerrar(self):
        """Cierra recursos"""
        self.cleanup_driver()
        self.session_active = False

    def extract_products(self, urls):
        """Extrae múltiples productos manteniendo la misma sesión"""
        self.setup_driver()
        results = []

        for i, url in enumerate(urls, 1):
            logger.info(f"Extrayendo producto {i}/{len(urls)}")
            product_data = self.extraer_producto(url)
            if product_data:
                results.append(product_data)
            
            time.sleep(self.CONFIG['wait_between_requests'])

        self.cleanup_driver()
        return pd.DataFrame(results) if results else pd.DataFrame()
    
    def extraer_producto(self, url):
        """Extrae datos de un producto individual - VERSIÓN CON MEJOR MANEJO DE ERRORES"""
        try:
            if self.driver is None:
                self.setup_driver()

            logger.info(f"Navegando a: {url}")
            self.driver.set_page_load_timeout(30)
            self.driver.get(url)
            
            # Esperar carga de la página
            time.sleep(3)
            logger.info(f"Página cargada: {self.driver.title}")
        
            name = self._extract_name()
            if not name:
                logger.warning(f"No se pudo extraer nombre de {url}")
                return {"error_type": "no_name", "url": url, "titulo": self.driver.title}
        
            logger.info(f"Nombre encontrado: {name}")
        
            # Extraer precios (normal y descuento)
            prices = self._extract_prices()
            unit_price, unit_text = self._extract_unit_price()
            discounts = self._extract_discounts()
        
            product_data = self._build_product_data(
                name,
                prices["normal"],
                prices["descuento"],
                unit_price,
                unit_text,
                discounts,
                url
            )

            # Verificar resultado final
            final_price = prices["descuento"] or prices["normal"]
            if final_price and float(final_price) > 0:  # Convertir a float para comparar
                logger.info(f"EXTRACCIÓN EXITOSA: {name} - Precio: ${final_price}")
            else:
                logger.warning(f"Producto sin precio detectado: {name}")

            return product_data
        
        except Exception as e:
            logger.error(f"ERROR crítico extrayendo {url}: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {"error_type": "exception", "url": url, "titulo": str(e)}
        
    def _extract_name(self):
        """Extrae y limpia el nombre del producto"""
        for i, selector in enumerate(self.SELECTORS['name'], 1):
            try:
                logger.debug(f"Probando selector de nombre {i}: {selector}")
                element = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                raw_name = element.text.strip()
                
                if raw_name:
                    logger.debug(f"Nombre encontrado con selector {i}: {raw_name}")
                    clean_name = self._clean_name(raw_name)
                    logger.debug(f"Nombre limpio: {clean_name}")
                    return clean_name
                    
            except Exception as e:
                logger.debug(f"Selector {i} fallo: {str(e)}")
                continue
        
        logger.error("No se pudo encontrar el nombre con ningun selector")
        return None

    def _clean_name(self, raw_name):
        """Limpia el nombre del producto"""
        try:
            lines = raw_name.split('\n')
            
            if len(lines) >= 2:
                # Buscar línea más relevante
                for line in lines:
                    clean_line = line.strip()
                    if clean_line and len(clean_line) > 3:  # Línea con contenido significativo
                        return clean_line
                
                # Si no encuentra patrones claros, tomar la primera línea no vacía
                for line in lines:
                    if line.strip():
                        return line.strip()
            else:
                return raw_name
                
        except Exception as e:
            logger.warning(f"Error al limpiar nombre: {str(e)}, usando nombre original")
            return raw_name
    
    def _extract_prices(self):
        """Extrae precios normal y con descuento - VERSIÓN CORREGIDA"""
        logger.info("Buscando precios...")

        precio_normal = None
        precio_descuento = None

        # PRIMERO: Buscar precio con descuento
        for selector in self.SELECTORS['price_discount']:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                if element.is_displayed():
                    price_text = element.text.strip()
                    if price_text:
                        precio_descuento = self._clean_price(price_text)
                        logger.info(f"Precio con descuento encontrado: ${precio_descuento}")
                        break
            except:
                continue

        # SEGUNDO: Buscar precio normal
        for selector in self.SELECTORS['price_normal']:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                if element.is_displayed():
                    price_text = element.text.strip()
                    if price_text:
                        precio_normal = self._clean_price(price_text)
                        logger.info(f"Precio normal encontrado: ${precio_normal}")
                        break
            except:
                continue

        # TERCERO: Si no hay precios específicos, buscar precio general
        if not precio_normal and not precio_descuento:
            for selector in self.SELECTORS['price']:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if element.is_displayed():
                        price_text = element.text.strip()
                        if price_text:
                            precio_general = self._clean_price(price_text)
                            logger.info(f"Precio general encontrado: ${precio_general}")
                            precio_normal = precio_general
                            precio_descuento = precio_general
                            break
                except:
                    continue

        # ═══════════════════════════════════════════════════════════
        # CORRECCIÓN: Convertir a float antes de comparar
        # ═══════════════════════════════════════════════════════════
        
        # Convertir strings a float para comparación
        try:
            if precio_normal:
                precio_normal_float = float(precio_normal)
            else:
                precio_normal_float = None
                
            if precio_descuento:
                precio_descuento_float = float(precio_descuento)
            else:
                precio_descuento_float = None
        except (ValueError, TypeError) as e:
            logger.error(f"Error convirtiendo precios a float: {e}")
            # Si hay error de conversión, usar valores por defecto
            if precio_normal:
                return {"normal": precio_normal, "descuento": precio_normal}
            elif precio_descuento:
                return {"normal": precio_descuento, "descuento": precio_descuento}
            else:
                return {"normal": None, "descuento": None}

        # Si tenemos ambos precios, determinar cuál es cuál
        if precio_normal_float and precio_descuento_float:
            if precio_normal_float > precio_descuento_float:
                logger.info(f"PRODUCTO CON DESCUENTO - Normal: ${precio_normal}, Oferta: ${precio_descuento}")
                return {"normal": precio_normal, "descuento": precio_descuento}
            else:
                logger.info(f"PRECIO NORMAL - Ambos iguales: ${precio_normal}")
                return {"normal": precio_normal, "descuento": precio_normal}
        elif precio_descuento_float:
            logger.info(f"SOLO PRECIO DESCUENTO: ${precio_descuento}")
            return {"normal": precio_descuento, "descuento": precio_descuento}
        elif precio_normal_float:
            logger.info(f"SOLO PRECIO NORMAL: ${precio_normal}")
            return {"normal": precio_normal, "descuento": precio_normal}
        else:
            logger.warning("No se pudieron extraer precios")
            return {"normal": None, "descuento": None}
    
    def _extract_unit_price(self):
        """Extrae precio por unidad"""
        for selector in self.SELECTORS['unit_price']:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                if element.is_displayed():
                    unit_text = element.text.strip()
                    if unit_text:
                        # Extraer precio del texto de unidad si existe
                        if '$' in unit_text:
                            unit_price = self._clean_price(unit_text)
                            return unit_price, unit_text
                        else:
                            return None, unit_text
            except:
                continue
        return None, None
    
    def _extract_discounts(self):
        """Extrae descuentos aplicables"""
        discounts = []
        
        try:
            for selector in self.SELECTORS['discounts']:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    if element.is_displayed():
                        text = element.text.strip()
                        if self._is_valid_discount(text):
                            discounts.append(text)
        except Exception as e:
            logger.debug(f"Error extrayendo descuentos: {str(e)}")
        
        unique_discounts = list(set(discounts))
        logger.info(f"Descuentos encontrados: {len(unique_discounts)}")
        return unique_discounts
    
    def _is_valid_discount(self, text):
        """Determina si un texto es un descuento válido"""
        if not text or len(text) > 50:
            return False
        
        text_upper = text.upper()
        has_discount_keywords = any(word in text_upper for word in ['%', 'OFF', 'DCTO', 'DESCUENTO', '2X1', '3X2', 'SALE'])
        has_digits = any(c.isdigit() for c in text)
        
        return has_discount_keywords and has_digits
    
    def _build_product_data(self, name, price_normal, price_discount, unit_price, unit_text, discounts, url):
        """Construye el diccionario de datos del producto"""
        # Manejo de precios
        precio_normal_str = str(price_normal) if price_normal else ""
        precio_descuento_str = str(price_discount) if price_discount else ""
        
        return {
            "nombre": name,
            "precio_normal": precio_normal_str,
            "precio_descuento": precio_descuento_str,
            "precio_por_unidad": unit_price if unit_price else "",
            "unidad": unit_text if unit_text else "",
            "descuentos": " | ".join(discounts) if discounts else "Ninguno",
            "fecha": datetime.today().strftime("%Y-%m-%d"),
            "supermercado": self.CONFIG['supermarket_name'],
            "url": url
        }
    
    def _clean_price(self, price_text):
        """Limpia y formatea el precio - versión mejorada para La Reina"""
        if not price_text or price_text == "0":
            return ""
        
        try:
            # Remover todo excepto números, coma y punto
            clean_price = re.sub(r'[^\d,.]', '', str(price_text))
            
            # Si hay coma, asumir que es el separador decimal
            if ',' in clean_price:
                # Eliminar puntos (miles) y convertir coma a punto decimal
                clean_price = clean_price.replace('.', '').replace(',', '.')
            # Si solo hay puntos y tiene más de 6 caracteres, probablemente son miles
            elif '.' in clean_price and len(clean_price) > 6:
                # Eliminar puntos de miles
                clean_price = clean_price.replace('.', '')
            
            # Convertir a float y luego a string para normalizar
            if clean_price:
                return str(float(clean_price))
            else:
                return ""
        except Exception as e:
            logger.warning(f"Error limpiando precio '{price_text}': {e}")
            return price_text
    
    def cleanup_driver(self):
        """Limpia recursos del driver"""
        if self.driver:
            self.driver.quit()
            self.driver = None
            self.wait = None 
            self.session_active = False
            logger.debug("Driver cerrado correctamente")

    def validar_links_productos(self, urls):
        """Validación simple de links para La Reina"""
        logger.info("Validando links de La Reina")
        
        if not self.asegurar_sesion_activa():
            logger.error("No se pudo establecer sesión para validación")
            return {}
        
        resultados = {}
        
        for i, url in enumerate(urls, 1):
            logger.info("Validando link %d/%d: %s", i, len(urls), url)
            
            try:
                # Configurar timeout corto para validación
                self.driver.set_page_load_timeout(15)
                self.driver.get(url)
                time.sleep(2)
                
                # Verificar si la página carga correctamente
                titulo = self.driver.title
                current_url = self.driver.current_url
                
                if "lareinacorrientes.com.ar" not in current_url:
                    resultados[url] = {
                        'valido': False,
                        'estado': 'ERROR_CARGA',
                        'mensaje': 'No se pudo cargar página de La Reina',
                        'titulo_pagina': titulo
                    }
                    continue
                
                # Verificar si es página de error
                if any(word in titulo.lower() for word in ['error', 'not found', '404']):
                    resultados[url] = {
                        'valido': False,
                        'estado': 'PAGINA_ERROR',
                        'mensaje': 'Página de error detectada',
                        'titulo_pagina': titulo
                    }
                    continue
                
                # Intentar extraer nombre como prueba
                nombre = self._extract_name()
                if nombre:
                    resultados[url] = {
                        'valido': True,
                        'estado': 'OK', 
                        'mensaje': 'Link válido',
                        'titulo_pagina': titulo,
                        'nombre_producto': nombre
                    }
                else:
                    resultados[url] = {
                        'valido': False,
                        'estado': 'SIN_NOMBRE',
                        'mensaje': 'No se pudo extraer nombre del producto',
                        'titulo_pagina': titulo
                    }
                    
            except Exception as e:
                resultados[url] = {
                    'valido': False,
                    'estado': 'ERROR_EXCEPCION',
                    'mensaje': str(e),
                    'titulo_pagina': 'No disponible'
                }
            
            time.sleep(1)  # Pausa entre validaciones
        
        return resultados