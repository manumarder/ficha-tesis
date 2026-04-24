
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
logger = logging.getLogger('delimart_extractor')

# Cargar variables de entorno
load_dotenv()


class DelimartExtractor:
    """Extractor optimizado para Delimart"""
    
    # Configuraciones centralizadas - OPTIMIZADO
    CONFIG = {
        'timeout': 15,  # OPTIMIZADO: Reducido de 30 a 15
        'wait_between_requests': 0.3,  # OPTIMIZADO: Reducido de 1 a 0.3
        'supermarket_name': 'Delimart'
    }
    
    # Selectores centralizados para fácil mantenimiento
    SELECTORS = {
        'name': [
            ".product-detail h1",
            ".product-name",
            "h1.name",             # Selector específico para lo que pasaste
            ".product-name h1",
            "h1", 
            "[class*='product-name']",
            "h1 .vtex-store-components-3-x-productBrand"
        ],
        'price_actual': [  # El precio que pagás (Naranja/Grande)
            "h5.product-price",
            "h4.product-price",
            ".product-price h4",   # El nuevo ganador según tu HTML
            ".product-price h5",
            ".product-detail .product-price h5",

            ".product-info-main .product-price",
            "main .product-price h5",
            ".product-price h5"
        ],
        'price_regular': [  # El precio tachado (Gris/Chico)
            ".product-detail .product-price-regular",
            ".product-price-regular",
            "p.product-price-regular"
        ],
        'unit_price': [
            ".price-per-unit", ".unit-price", ".price-by-weight",
            ".weight-price", "[class*='unit']", "[class*='weight']",
            "[class*='measurement']"
        ],
        'discounts': [
            ".promo-badge", ".discount-badge", ".offer-tag", 
            ".savings", ".promotion", ".discount",
            "[class*='promo']", "[class*='offer']", "[class*='discount']"
        ],
        'main_container': [
            ".col-md-5",
            ".product-detail", 
            "[class*='product']",
            "main", "article"
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
                self.driver.set_page_load_timeout(15)
                self.wait = WebDriverWait(self.driver, self.CONFIG['timeout'])
        
        return self.driver, self.wait
    
    # === MÉTODOS COMPATIBILIDAD CON run.py ===
    
    def extraer_producto(self, url):
        """Wrapper para compatibilidad con run.py"""
        return self.extract_product(url)
    
    def asegurar_sesion_activa(self):
        """Asegura que haya una sesión activa"""
        try:
            if self.driver is None:
                self.setup_driver()
                self.session_active = True
                logger.info("Sesión de Delimart inicializada")
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
            logger.error("Error asegurando sesión activa de Delimart: %s", str(e))
            self.session_active = False
            return False
    
    def guardar_sesion(self):
        """Guarda la sesión"""
        try:
            logger.debug("Sesión de Delimart - no requiere guardado especial")
            return True
        except Exception as e:
            logger.error("Error guardando sesión de Delimart: %s", str(e))
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
            product_data = self.extract_product(url)
            if product_data:
                results.append(product_data)
            
            time.sleep(self.CONFIG['wait_between_requests'])

        self.cleanup_driver()
        return pd.DataFrame(results) if results else pd.DataFrame()
    
    def extract_product(self, url):
        """Extrae datos de un producto individual"""
        try:
            if self.driver is None:
                self.setup_driver()

            logger.info(f"Navegando a: {url}")
            self.driver.set_page_load_timeout(15)  # OPTIMIZADO: Reducido de 30 a 15
            self.driver.get(url)

            # 1. ESPERA ACTIVA: Esperamos a que el nombre sea visible
            # Esto evita que leamos la página anterior (como la Pepsi)
            WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, self.SELECTORS['name'][0]))
            )
            
            # 2. SCROLL DINÁMICO: Forzamos a la página a renderizar el precio
            self.driver.execute_script("window.scrollBy(0, 300);")
            time.sleep(1) # Un segundo real para que el JS de la página calcule el precio
            
            name = self._extract_name()
            if not name:
                logger.warning(f"No se pudo extraer nombre de {url}")
                return {"error_type": "no_name", "url": url, "titulo": self.driver.title}
            
            logger.info(f"Nombre encontrado: {name}")
            
            # CAMBIO AQUÍ: Ahora recibimos el diccionario de precios
            prices_dict = self._extract_price()

            if not prices_dict['actual']:
                # Último intento: un scroll más profundo por si acaso
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/4);")
                time.sleep(1)
                prices_dict = self._extract_price()

            if not prices_dict['actual']:
                logger.warning(f"No se pudo extraer precio de {url}")
                return {"error_type": "no_price", "url": url}
            
            logger.info("Precio encontrado: %s", prices_dict)

            discounts = self._extract_discounts()
            
            # CAMBIO AQUÍ: Pasamos el diccionario a la construcción final
            return self._build_product_data(name, prices_dict, discounts, url)
        
        except Exception as e:
            logger.error("Error extrayendo %s: %s", url, str(e))
            return {"error_type": "exception", "url": url, "titulo": str(e)}
    
    def _extract_name(self):
        """Extrae el nombre con reintentos y scrolls"""
        for selector in self.SELECTORS['name']:
            try:
                # Espera explícita de hasta 5 segundos por cada selector
                element = WebDriverWait(self.driver, 5).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
                )
                raw_name = element.text.strip()
                
                if raw_name:
                    return self._clean_name(raw_name)
            except:
                continue
        return None

    def _clean_name(self, raw_name):
        """Limpia el nombre del producto eliminando marca y eslogan"""
        try:
            if not raw_name:
                return None
            
            # Limpiar saltos de línea y espacios múltiples
            lines = [l.strip() for l in raw_name.split('\n') if l.strip()]
            
            # Si el nombre viene en varias líneas (Marca \n Producto \n Peso)
            # Intentamos reconstruirlo o elegir la línea más descriptiva
            if len(lines) >= 2:
                # Si la primera línea es muy corta (posible marca como "Don Juan") 
                # y la segunda es el producto, las unimos o tomamos la segunda.
                if len(lines[0]) < 10:
                    return f"{lines[0]} {lines[1]}".strip()
                return lines[0]
            
            return lines[0] if lines else raw_name
                
        except Exception as e:
            logger.warning(f"Error al limpiar nombre: {str(e)}")
            return raw_name
    
    def _extract_price(self):
        """Extrae el precio actual y el regular si existe"""
        prices = {'actual': "", 'regular': ""}
        
        # Intentamos esperar específicamente a que el h5 tenga un "$"
        try:
                # Esperamos hasta 5 segundos a que aparezca el símbolo de moneda
                element = WebDriverWait(self.driver, 5).until(
                    lambda d: "$" in d.find_element(By.CSS_SELECTOR, "h5.product-price").text
                )
        except:
            pass
        
        try:

            # 1. Buscar precio de oferta/actual (el naranja grande)
            for selector in self.SELECTORS['price_actual']:
                try:
                    el = self.driver.find_element(By.CSS_SELECTOR, selector)
                    text = el.text.strip()
                    if "$" in text:
                        prices['actual'] = text
                        break
                except: continue

            # 2. Buscar precio regular
            for selector in self.SELECTORS['price_regular']:
                try:
                    el = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if el.is_displayed():
                        prices['regular'] = el.text.strip()
                        break
                except: continue
                
            if not prices['regular']:
                prices['regular'] = prices['actual']
                
        except Exception as e:
            logger.warning(f"Error en bloque de precios: {e}")
            
        return prices
    
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
        logger.debug(f"Descuentos validos encontrados: {unique_discounts}")
        return unique_discounts
    
    def _search_price(self, selectors):
        """Busca precio usando múltiples estrategias"""
        # Primero buscar en contenedor principal
        main_container = self._find_main_container()
        if main_container:
            price = self._search_in_container(main_container, selectors)
            if price:
                return price
        
        # Si no se encuentra, buscar en toda la página
        logger.debug("Buscando precio en toda la pagina")
        all_prices = self._search_all_prices(selectors)
        
        if all_prices:
            selected_price = self._select_best_price(all_prices)
            return selected_price
        
        logger.warning(f"No se encontro precio con {len(selectors)} selectores")
        return ""
    
    def _find_main_container(self):
        """Encuentra el contenedor principal del producto"""
        for container in self.SELECTORS['main_container']:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, container)
                logger.debug(f"Contenedor principal encontrado: {container}")
                return element
            except:
                continue
        return None
    
    def _search_in_container(self, container, selectors):
        """Busca precio dentro de un contenedor específico"""
        for selector in selectors:
            try:
                elements = container.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    if element.is_displayed():
                        text = element.text.strip()
                        if self._is_valid_price(text):
                            logger.debug(f"Precio encontrado en contenedor: '{text}'")
                            return text
            except Exception as e:
                logger.debug(f"Selector '{selector}' fallo en contenedor: {e}")
        return None
    
    def _search_all_prices(self, selectors):
        """Busca todos los precios en la página"""
        prices_found = []
        
        for selector in selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    if element.is_displayed():
                        text = element.text.strip()
                        if self._is_valid_price(text):
                            context = self._get_price_context(element)
                            prices_found.append({
                                'text': text,
                                'selector': selector,
                                'context': context,
                                'element': element
                            })
                            logger.debug(f"Precio encontrado: '{text}' (contexto: {context})")
            except Exception as e:
                logger.debug(f"Selector '{selector}' fallo: {e}")
        
        return prices_found
    
    def _select_best_price(self, prices_found):
        """Selecciona el precio más probable"""
        if not prices_found:
            return ""

        # Intentamos primero los que el script cree que son principales
        main_prices = [p for p in prices_found if p['context'] == 'producto_principal']
        if main_prices:
            return main_prices[0]['text']
        
        # SI NO HAY PRINCIPALES: No devolvemos vacío, devolvemos el primero encontrado
        # Esto es lo que estaba fallando en la carne.
        logger.info(f"Usando precio de respaldo (no detectado como principal): {prices_found[0]['text']}")
        return prices_found[0]['text']
    
    def _is_valid_price(self, text):
        """Determina si un texto es un precio válido"""
        if not text:
            return False
        
        has_currency_symbol = '$' in text or 'USD' in text
        has_digits = any(c.isdigit() for c in text)
        reasonable_length = 2 <= len(text) <= 20
        not_only_text = not text.replace('$', '').replace(',', '').replace('.', '').replace(' ', '').isalpha()
        
        return has_currency_symbol and has_digits and reasonable_length and not_only_text
    
    def _is_valid_discount(self, text):
        """Determina si un texto es un descuento válido"""
        if not text or len(text) > 50:
            return False
        
        text_upper = text.upper()
        has_discount_keywords = any(word in text_upper for word in ['%', 'OFF', 'DCTO', 'DESCUENTO', '2X1', '3X2'])
        has_digits = any(c.isdigit() for c in text)
        
        return has_discount_keywords and has_digits
    
    def _get_price_context(self, element):
        """Obtiene el contexto del precio"""
        try:
            # Subimos varios niveles para ver en qué sección estamos
            parent_text = self.driver.execute_script(
                "return arguments[0].closest('section, div[class*=\"related\"], div[id*=\"related\"], .frecuently-bought') ? 'secundario' : 'principal';", 
                element
            )
            
            # Verificamos si el elemento está dentro de .product-detail (donde está la carne)
            is_in_main = self.driver.execute_script(
                "return arguments[0].closest('.product-detail') !== null;", 
                element
            )

            if is_in_main:
                return "producto_principal"
            return "producto_secundario"
        except:
            return "desconocido"
    
    def _build_product_data(self, name, prices_dict, discounts, url):
        """Construye el diccionario de datos del producto"""
        return {
            "nombre": name,
            "precio_normal": self._clean_price(prices_dict['regular']),
            "precio_descuento": self._clean_price(prices_dict['actual']),
            "precio_por_unidad": "0",
            "unidad": "",
            "descuentos": " | ".join(discounts) if discounts else "Ninguno",
            "fecha": datetime.today().strftime("%Y-%m-%d"),
            "supermercado": self.CONFIG['supermarket_name'],
            "url": url
        }
    
    def _clean_price(self, price_text):
        """Limpia y formatea el precio para formato argentino (1.000,00)"""
        if not price_text or price_text == "0" or price_text == "":
            return "" 
        
        try:
            # 1. Convertir a string y quitar espacios
            txt = str(price_text).strip()

            # 2. Remover caracteres no numéricos excepto punto y coma
            #    (Mantiene el formato original "2.825,83")
            clean_price = re.sub(r'[^\d,.]', '', txt)
            
            # 3. ELIMINAR el punto de los miles
            #    "2.825,83" pasa a ser "2825,83"
            clean_price = clean_price.replace('.', '')
            
            # 4. REEMPLAZAR la coma decimal por punto
            #    "2825,83" pasa a ser "2825.83" (formato correcto para float)
            clean_price = clean_price.replace(',', '.')
            
            return clean_price
        except Exception as e:
            # Es útil imprimir el error para debuggear si falla
            print(f"Error limpiando precio {price_text}: {e}")
            return ""
    
    def cleanup_driver(self):
        """Limpia recursos del driver"""
        if self.driver:
            self.driver.quit()
            self.driver = None
            self.wait = None 
            self.session_active = False
            logger.debug("Driver cerrado correctamente")

    def validar_links_productos(self, urls):
        """Validación simple de links para Delimart"""
        logger.info("Validando links de Delimart")
        
        if not self.asegurar_sesion_activa():
            logger.error("No se pudo establecer sesión para validación")
            return {}
        
        resultados = {}
        
        for i, url in enumerate(urls, 1):
            logger.info("Validando link %d/%d: %s", i, len(urls), url)
            
            try:
                # OPTIMIZADO: Timeout corto para validación
                self.driver.set_page_load_timeout(10)  # Reducido de 15 a 10
                self.driver.get(url)
                SmartWait.wait_minimal(0.5)  # Reducido de 2s a 0.5s
                
                # Verificar si la página carga correctamente
                titulo = self.driver.title
                current_url = self.driver.current_url
                
                if "delimart.com.ar" not in current_url:
                    resultados[url] = {
                        'valido': False,
                        'estado': 'ERROR_CARGA',
                        'mensaje': 'No se pudo cargar página de Delimart',
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
            
            SmartWait.wait_minimal(0.2)  # OPTIMIZADO: Pausa mínima
        
        return resultados