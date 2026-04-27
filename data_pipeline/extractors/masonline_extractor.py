import os
import sys
import time
import re
import unicodedata
import pandas as pd
import logging
from dotenv import load_dotenv
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pickle

# Agregar directorio padre al path para imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.cookie_manager import CookieManager
from utils.optimization import optimize_driver_options, SmartWait, create_driver_with_retry

load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MasonlineExtractor:
    """Extractor mejorado para Masonline combinando lo mejor de ambos enfoques"""
    
    # Configuraciones centralizadas (estilo Delimart) - OPTIMIZADO
    CONFIG = {
        'timeout': 15,  # OPTIMIZADO: Reducido de 30 a 15
        'wait_between_requests': 0.5,  # OPTIMIZADO: Reducido de 2 a 0.5
        'supermarket_name': 'Masonline',
        'base_url': 'https://www.masonline.com.ar'
    }

    # VTEX/Valtech embeben un índice en las clases (p. ej. …-1-x-… → …-2-x-… al redeployar).
    # Usar subcadenas evita que falle la toma de precio masivamente.
    _SEL_DYNAMIC_PRODUCT_PRICE = "div[class*='dynamicProductPrice']"
    
    def __init__(self):
        self.nombre_super = self.CONFIG['supermarket_name']
        self.timeout = self.CONFIG['timeout']
        self.driver = None
        self.wait = None
        self.sesion_iniciada = False
        
        # OPTIMIZADO: Usar CookieManager centralizado
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.cookie_manager = CookieManager(base_dir)
        self.cookies_file = str(self.cookie_manager.get_cookie_path('masonline'))
        
        self.email = 'manumarder@gmail.com'
        self.password = 'Ipecd2025'
    
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
                self.wait = WebDriverWait(self.driver, self.timeout)
        
        return self.driver, self.wait
    
    
    def extract_products(self, urls):
        """Extrae múltiples productos manteniendo la misma sesión"""
        resultados = []
        
        if not self.asegurar_sesion_activa():
            logger.error("No se pudo establecer sesión para la extracción")
            return resultados
        
        for i, url in enumerate(urls, 1):
            logger.info(f"Extrayendo producto {i}/{len(urls)}")
            logger.info(f"URL: {url}")

            producto = self.extraer_producto(url)
            if producto:
                resultados.append(producto)
            
            SmartWait.wait_minimal(0.2)  # OPTIMIZADO: Reducido
        
        self.guardar_sesion()
        return resultados

    def extraer_producto(self, url):
        """Extrae datos de un producto individual - VERSIÓN MEJORADA"""
        try:
            # Asegurar sesión activa
            if not self.sesion_iniciada:
                if not self.asegurar_sesion_activa():
                    logger.error("No se pudo establecer sesión en Masonline")
                    return {"error_type": "no_session", "url": url, "titulo": "No se pudo establecer sesión"}
            
            logger.info(f"[SEARCH] Navegando a: {url}")
            self.driver.get(url)
            
            # ═══════════════════════════════════════════════════════════
            # ESPERAS MEJORADAS - CLAVE PARA CARGAR PRECIOS
            # ═══════════════════════════════════════════════════════════
            
            # OPTIMIZADO: Espera mínima para carga de página
            logger.info("Esperando carga completa de la página...")
            SmartWait.wait_minimal(0.5)  # Reducido de 2s a 0.5s
            
            # Espera 2: Esperar elementos críticos
            try:
                # Esperar que al menos el título esté presente
                self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
                logger.info("[OK] Título cargado")
            except Exception as e:
                logger.warning(f"[WARNING] Timeout esperando h1: {e}")
            
            # Espera 3: Esperar específicamente elementos de precio
            logger.info("Esperando elementos de precio...")
            try:
                # Esperar contenedor de precio principal
                self.wait.until(EC.presence_of_element_located(
                    (By.CSS_SELECTOR, self._SEL_DYNAMIC_PRODUCT_PRICE)
                ))
                logger.info("[OK] Contenedor de precio cargado")
                
                # OPTIMIZADO: Espera mínima para precios dinámicos
                SmartWait.wait_minimal(0.5)  # Reducido de 1.5s a 0.5s
                
            except Exception as e:
                logger.warning(f"[WARNING] Contenedor de precio no encontrado: {e}")
                # OPTIMIZADO: Espera de fallback reducida
                SmartWait.wait_minimal(1)  # Reducido de 3s a 1s
            
            logger.info(f"Título de página: {self.driver.title}")
            
            # ═══════════════════════════════════════════════════════════
            # PASO 1: Verificar si es página de error
            # ═══════════════════════════════════════════════════════════
            if self._es_pagina_error():
                logger.warning(f"[ERROR] Página no encontrada (404): {url}")
                return {"error_type": "404", "url": url, "titulo": self.driver.title}
            
            # ═══════════════════════════════════════════════════════════
            # PASO 2: Verificar disponibilidad del producto
            # ═══════════════════════════════════════════════════════════
            SmartWait.wait_minimal(2.0)  # AUMENTADO: Crítico para carga de precios en VTEX
            disponibilidad = self._verificar_disponibilidad_detallada()
            
            if disponibilidad["estado"] == "no_disponible":
                logger.warning(f"[STOP] PRODUCTO NO DISPONIBLE: {self.driver.title}")
                name = self._extract_name()
                return self._build_product_data(
                    name, 0, 0, None, None, ["NO DISPONIBLE"], url
                )
            elif disponibilidad["estado"] == "disponible":
                logger.info("[OK] PRODUCTO DISPONIBLE")
            else:
                logger.warning(f"[WARNING] Estado de disponibilidad incierto: {disponibilidad['estado']}")
            
            # ═══════════════════════════════════════════════════════════
            # PASO 3: Extraer datos del producto
            # ═══════════════════════════════════════════════════════════
            
            name = self._extract_name()
            if not name:
                logger.warning(f"[ERROR] No se pudo extraer nombre de {url}")
                return {"error_type": "no_name", "url": url, "titulo": self.driver.title}
            
            logger.info(f"[PRODUCT] Nombre extraído: {name}")
            
            # Extraer precios con debugging detallado
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

            # ═══════════════════════════════════════════════════════════
            # PASO 4: Verificar resultado final
            # ═══════════════════════════════════════════════════════════
            final_price = prices["descuento"] or prices["normal"]
            if final_price and final_price > 0:
                logger.info(f"[OK] EXTRACCIÓN EXITOSA: {name} - Precio: ${final_price}")
            elif final_price == 0:
                logger.warning(f"[ERROR] Producto sin precio (0): {name}")
            else:
                logger.warning(f"[WARNING] Producto sin precio detectado: {name}")

            return product_data

        except Exception as e:
            logger.error(f"ERROR crítico extrayendo {url}: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.sesion_iniciada = False
            return {"error_type": "exception", "url": url, "titulo": str(e)}
        
    def _extract_name(self):
        """Extrae el nombre del producto"""
        selectors = [
            "h1.vtex-store-components-3-x-productNameContainer",
            "h1.vtex-store-components-3-x-productBrand", 
            "h1[data-testid='product-name']",
            "h1"
        ]
        
        for selector in selectors:
            try:
                element = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                name = element.text.strip()
                if name:
                    return name
            except:
                continue
        
        # Fallback al título
        try:
            title = self.driver.title
            if ' - Masonline' in title:
                return title.split(' - Masonline')[0].strip()
            return title
        except:
            return "Producto sin nombre"
    
    def _clean_name(self, raw_name):
        """Limpia el nombre del producto (estilo Delimart)"""
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
            logger.warning(f" Error al limpiar nombre: {str(e)}, usando nombre original")
            return raw_name
        
    # ==================================================================================
    # MÉTODOS DE EXTRACCIÓN DE PRECIOS - VERSIÓN CORREGIDA
    # ==================================================================================

    def _es_producto_no_disponible(self):
        """
        Detecta si producto NO está disponible
        
        CRITERIO: Si hay botón "Agregar" habilitado → DISPONIBLE
        """
        try:
            # PRIMERA VERIFICACIÓN: Buscar botón "Agregar" habilitado
            try:
                botones_agregar = self.driver.find_elements(By.XPATH, 
                    "//button[contains(., 'Agregar') or contains(., 'AGREGAR')]")
                
                for boton in botones_agregar:
                    if boton.is_displayed() and boton.is_enabled():
                        # Si hay botón agregar HABILITADO → producto DISPONIBLE
                        logger.debug(f"   [OK] Botón 'Agregar' habilitado → DISPONIBLE")
                        return False
            except:
                pass
            
            # SEGUNDA VERIFICACIÓN: Buscar botón "No Disponible" DESHABILITADO
            try:
                botones_no_disp = self.driver.find_elements(By.XPATH, 
                    "//button[contains(., 'No Disponible')]")
                
                for boton in botones_no_disp:
                    if boton.is_displayed():
                        clases = boton.get_attribute('class') or ''
                        
                        # Solo marcar como no disponible si está DESHABILITADO
                        if 'bg-disabled' in clases or not boton.is_enabled():
                            logger.info(f"   [STOP] Botón 'No Disponible' deshabilitado → NO DISPONIBLE")
                            return True
            except:
                pass
            
            # TERCERA VERIFICACIÓN: Texto "Sin stock" visible
            try:
                elementos = self.driver.find_elements(By.XPATH, 
                    "//*[contains(text(), 'Sin stock') or contains(text(), 'Agotado')]")
                
                for elemento in elementos:
                    if elemento.is_displayed():
                        logger.info(f"   [STOP] Texto '{elemento.text}' → NO DISPONIBLE")
                        return True
            except:
                pass
            
            # Por defecto: DISPONIBLE
            logger.debug(f"   [OK] No se encontraron indicadores de no disponible → DISPONIBLE")
            return False
            
        except Exception as e:
            logger.debug(f"   Error verificando disponibilidad: {e}")
            return False
        
    def _verificar_disponibilidad_detallada(self):
        """Verifica disponibilidad con debugging detallado"""
        logger.info("[SEARCH] Verificando disponibilidad del producto...")
        
        try:
            # 1. Buscar botón "Agregar" habilitado
            botones_agregar = self.driver.find_elements(By.XPATH, 
                "//button[contains(., 'Agregar') or contains(., 'AGREGAR')]")
            
            logger.info(f"   Encontrados {len(botones_agregar)} botones 'Agregar'")
            
            for i, boton in enumerate(botones_agregar):
                try:
                    displayed = boton.is_displayed()
                    enabled = boton.is_enabled()
                    clases = boton.get_attribute('class') or ''
                    texto = boton.text
                    
                    logger.info(f"   Botón {i+1}: texto='{texto}', visible={displayed}, habilitado={enabled}, clases={clases}")
                    
                    if displayed and enabled and 'disabled' not in clases.lower():
                        logger.info("   [OK] Botón 'Agregar' HABILITADO encontrado → PRODUCTO DISPONIBLE")
                        return {"estado": "disponible", "tipo": "boton_agregar"}
                except Exception as e:
                    logger.debug(f"   Error analizando botón {i+1}: {e}")

            # 2. Buscar botones deshabilitados o "No Disponible"
            botones_no_disp = self.driver.find_elements(By.XPATH, 
                "//button[contains(., 'No Disponible') or contains(., 'Agotado') or contains(., 'Sin stock')]")
            
            logger.info(f"   Encontrados {len(botones_no_disp)} botones de no disponible")
            
            for i, boton in enumerate(botones_no_disp):
                try:
                    displayed = boton.is_displayed()
                    enabled = boton.is_enabled()
                    clases = boton.get_attribute('class') or ''
                    texto = boton.text
                    
                    logger.info(f"   Botón no-disp {i+1}: texto='{texto}', visible={displayed}, habilitado={enabled}")
                    
                    if displayed and (not enabled or 'disabled' in clases.lower()):
                        logger.info("   [STOP] Botón 'No Disponible' encontrado → PRODUCTO NO DISPONIBLE")
                        return {"estado": "no_disponible", "tipo": "boton_no_disponible"}
                except Exception as e:
                    logger.debug(f"   Error analizando botón no-disp {i+1}: {e}")

            # 3. Buscar textos de no disponibilidad
            textos_no_disp = [
                "Sin stock", "Agotado", "No disponible", "Out of stock", 
                "Producto agotado", "Temporalmente no disponible"
            ]
            
            for texto_buscar in textos_no_disp:
                try:
                    elementos = self.driver.find_elements(By.XPATH, f"//*[contains(text(), '{texto_buscar}')]")
                    for elemento in elementos:
                        if elemento.is_displayed():
                            logger.info(f"   [STOP] Texto '{texto_buscar}' visible → PRODUCTO NO DISPONIBLE")
                            return {"estado": "no_disponible", "tipo": f"texto_{texto_buscar}"}
                except:
                    continue

            # 4. Verificar estructura de precios (si no hay precios, probablemente no disponible)
            try:
                contenedor_precio = self.driver.find_elements(By.CSS_SELECTOR, 
                    self._SEL_DYNAMIC_PRODUCT_PRICE)
                
                if not contenedor_precio:
                    logger.warning("   [WARNING] No se encontró contenedor de precio")
                    return {"estado": "indeterminado", "tipo": "sin_contenedor_precio"}
                    
            except Exception as e:
                logger.debug(f"   Error buscando contenedor de precio: {e}")

            logger.info("   [OK] No se encontraron indicadores de no disponible → ASUNIENDO DISPONIBLE")
            return {"estado": "disponible", "tipo": "asumido"}
            
        except Exception as e:
            logger.error(f"   Error en verificación de disponibilidad: {e}")
            return {"estado": "error", "tipo": f"error: {str(e)}"}
    
    def _extract_prices(self):
        """Extrae precios con debugging detallado"""
        logger.info("Iniciando extracción de precios...")
        
        try:
            # PRIMERO: Buscar todos los elementos de precio visibles como fallback
            logger.info("[SEARCH] Búsqueda inicial de precios visibles...")
            precios_fallback = self._buscar_todos_precios_visibles()
            logger.info(f"Precios encontrados en búsqueda general: {precios_fallback}")
            
            # Buscar contenedor principal de precio
            try:
                contenedor = self.driver.find_element(By.CSS_SELECTOR, 
                    self._SEL_DYNAMIC_PRODUCT_PRICE)
                logger.info("[OK] Contenedor principal de precio encontrado")
                
                # Buscar precio principal
                precio_principal = None
                
                # LISTA PRIORIZADA DE SELECTORES (Nuevos de VTEX + Custom Masonline)
                selectores_valor = [
                    "[class*='sellingPriceValue']",
                    "[class*='currencyContainer']",
                    "[class*='sellingPrice'] [class*='currencyContainer']",
                    "span[class*='sellingPrice']",
                    "[data-testid='product-price']"
                ]

                for sel in selectores_valor:
                    try:
                        precio_elem = contenedor.find_element(By.CSS_SELECTOR, sel)
                        if precio_elem.is_displayed():
                            texto_precio = self._extraer_precio_de_contenedor(precio_elem)
                            if texto_precio:
                                texto_limpio = self._limpiar_texto_precio(texto_precio)
                                precio_principal = self._parsear_precio(texto_limpio)
                                if precio_principal and precio_principal > 0:
                                    logger.info(f"   [OK] Precio encontrado con '{sel}': {precio_principal}")
                                    break
                    except:
                        continue
                
                # Si no hay precio principal, usar fallback
                if not precio_principal or precio_principal == 0:
                    logger.warning("   [WARNING] No se pudo extraer precio principal, usando fallback")
                    if precios_fallback:
                        precio_principal = precios_fallback[0]  # Tomar el mayor
                        logger.info(f"   Usando precio de fallback: ${precio_principal}")
                    else:
                        logger.error("   No hay precios disponibles")
                        return {"normal": None, "descuento": None}
                
                # Buscar precio de lista (precio anterior)
                precio_lista = None
                try:
                    selectores_lista = [
                        "[class*='listPriceValue']",
                        "span[class*='weighableListPrice']",
                        "span[class*='listPrice']"
                    ]
                    
                    elementos_lista = []
                    for sel_l in selectores_lista:
                        elementos_lista = self.driver.find_elements(By.CSS_SELECTOR, sel_l)
                        if elementos_lista: break
                    
                    logger.info(f"   Encontrados {len(elementos_lista)} elementos de precio lista")
                    
                    for i, elem_lista in enumerate(elementos_lista):
                        if elem_lista.is_displayed():
                            try:
                                precio_elem_lista = elem_lista.find_element(By.CSS_SELECTOR,
                                    "[class*='currencyContainer']")
                                
                                texto_precio_lista = self._extraer_precio_de_contenedor(precio_elem_lista)
                                logger.info(f"   Precio lista {i+1}: '{texto_precio_lista}'")
                                
                                if texto_precio_lista:
                                    texto_limpio_lista = self._limpiar_texto_precio(texto_precio_lista)
                                    precio_lista_candidato = self._parsear_precio(texto_limpio_lista)
                                    
                                    if precio_lista_candidato and precio_lista_candidato > precio_principal:
                                        precio_lista = precio_lista_candidato
                                        logger.info(f"   [OK] Precio lista válido: ${precio_lista}")
                                        break
                            except Exception as e:
                                logger.debug(f"   Error procesando precio lista {i+1}: {e}")
                                continue
                                
                except Exception as e:
                    logger.warning(f"   Error buscando precio lista: {e}")
                
                # Determinar precios finales
                if precio_lista and precio_lista > precio_principal:
                    logger.info(f"PRECIO CON DESCUENTO - Normal: ${precio_lista}, Oferta: ${precio_principal}")
                    return {"normal": precio_lista, "descuento": precio_principal}
                else:
                    logger.info(f"PRECIO NORMAL - Precio: ${precio_principal}")
                    return {"normal": precio_principal, "descuento": precio_principal}
                    
            except Exception as e:
                logger.error(f"No se pudo encontrar contenedor principal de precio: {e}")
                
                # Usar fallback si no se encuentra el contenedor
                if precios_fallback:
                    precio_fallback = precios_fallback[0]
                    logger.info(f"Usando precios de fallback: ${precio_fallback}")
                    return {"normal": precio_fallback, "descuento": precio_fallback}
                else:
                    logger.error("No se pudieron extraer precios")
                    return {"normal": None, "descuento": None}
                    
        except Exception as e:
            logger.error(f"Error general en extracción de precios: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {"normal": None, "descuento": None}
        
    def _extract_prices_with_debug(self):
        """Extrae precios con foco en el precio FINAL visible"""
        logger.info("Iniciando extracción de precios...")
        
        try:
            # PRIMERO: Buscar el precio más prominente (precio final)
            precio_final = self._buscar_precio_final_visible()
            if precio_final:
                logger.info(f"Precio final encontrado: ${precio_final}")
                
                # Buscar precio de lista para comparar
                precio_lista = self._buscar_precio_lista()
                
                if precio_lista and precio_lista > precio_final:
                    logger.info(f"[OK] CON DESCUENTO - Normal: ${precio_lista}, Oferta: ${precio_final}")
                    return {"normal": precio_lista, "descuento": precio_final}
                else:
                    logger.info(f"[OK] PRECIO NORMAL - Precio: ${precio_final}")
                    return {"normal": precio_final, "descuento": precio_final}
            
            # FALLBACK: Método original
            logger.warning("[WARNING] No se encontró precio final, usando método original")
            return self._extract_prices()
            
        except Exception as e:
            logger.error(f"Error en extracción de precios: {e}")
            return {"normal": None, "descuento": None}
    
    def _buscar_precio_final_visible(self):
        """Busca el precio FINAL más prominente en la página"""
        try:
            logger.info("[SEARCH] Buscando precio FINAL visible...")
            
            # Estrategia 1: Buscar el precio más grande y prominente
            selectores_precio_final = [
                # Selector para precio principal grande
                "h1[class*='price'], h2[class*='price'], h3[class*='price']",
                "div[class*='sellingPrice'] span",
                "span[class*='sellingPrice']",
                "div[class*='price'] span",
                # Buscar por tamaño de texto
                "span[style*='font-size']",
                "div[style*='font-size']",
                # Selectores generales
                "[class*='sellingPrice'] [class*='currencyContainer']",
                "div[class*='dynamicProductPrice'] [class*='currencyContainer']"
            ]
            
            for selector in selectores_precio_final:
                try:
                    elementos = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for elemento in elementos:
                        if elemento.is_displayed():
                            texto = elemento.text.strip()
                            if texto and '$' in texto:
                                precio = self._parsear_precio(texto)
                                if precio and precio > 0:
                                    logger.info(f"   [OK] Precio en selector '{selector}': ${precio} ('{texto}')")
                                    return precio
                except:
                    continue
            
            # Estrategia 2: Buscar por contexto visual (elementos cerca del nombre del producto)
            try:
                # Buscar contenedores que probablemente contengan el precio final
                contenedores = self.driver.find_elements(By.XPATH, 
                    "//div[contains(@class, 'price') or contains(@class, 'Price')] | //span[contains(@class, 'price') or contains(@class, 'Price')]")
                
                for contenedor in contenedores:
                    if contenedor.is_displayed():
                        texto = contenedor.text.strip()
                        if texto and '$' in texto and len(texto) < 50:  # Texto razonable
                            # Filtrar precios base (que contienen "sin impuestos")
                            if 'sin impuestos' not in texto.lower() and 'precio sin' not in texto.lower():
                                precio = self._parsear_precio(texto)
                                if precio and precio > 0:
                                    logger.info(f"   [OK] Precio en contenedor: ${precio} ('{texto}')")
                                    return precio
            except Exception as e:
                logger.debug(f"   Error en estrategia 2: {e}")
            
            # Estrategia 3: Buscar todos los precios y tomar el más prominente
            precios_todos = self._buscar_todos_precios_visibles()
            if precios_todos:
                logger.info(f"Precios encontrados: {precios_todos}")
                return precios_todos[0]  # Tomar el mayor
            
            logger.warning("   [ERROR] No se encontró precio final")
            return None
            
        except Exception as e:
            logger.error(f"Error buscando precio final: {e}")
            return None
        
    def _buscar_precio_lista(self):
        """Busca precio de lista/regular"""
        try:
            selectores_precio_lista = [
                "span[class*='listPrice']",
                "div[class*='listPrice'] span", 
                "[class*='listPrice'] [class*='currencyContainer']",
                "span[class*='weighableListPrice'] [class*='currencyContainer']"
            ]
            
            for selector in selectores_precio_lista:
                try:
                    elementos = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for elemento in elementos:
                        if elemento.is_displayed():
                            texto = elemento.text.strip()
                            if texto and '$' in texto:
                                precio = self._parsear_precio(texto)
                                if precio and precio > 0:
                                    logger.info(f"Precio lista: ${precio}")
                                    return precio
                except:
                    continue
            return None
        except:
            return None

    def _limpiar_texto_precio(self, texto):
        """Extrae solo el precio del texto"""
        try:
            if not texto:
                return None
            
            # Buscar patrón $ + números
            match = re.search(r'\$\s*[\d\.,]+', texto)
            if match:
                return match.group(0)
            
            return texto
        except:
            return texto
        
    def _extraer_precio_de_contenedor(self, elemento):
        """
        Extrae precio usando textContent para capturar elementos invisibles
        """
        try:
            partes = []
            
            # 1. Símbolo $
            try:
                signo = elemento.find_element(By.CSS_SELECTOR, 
                    "[class*='currencyCode']")
                partes.append(signo.text.strip() or '$')
            except:
                partes.append('$')
            
            # Espacio
            partes.append(' ')
            
            # 2. Números enteros
            enteros = []
            try:
                elementos_enteros = elemento.find_elements(By.CSS_SELECTOR, 
                    "[class*='currencyInteger']")
                
                for entero in elementos_enteros:
                    # Usar textContent porque .text puede fallar
                    texto = entero.get_attribute('textContent') or entero.text
                    texto = texto.strip()
                    if texto:
                        enteros.append(texto)
            except Exception as e:
                logger.debug(f"Error obteniendo enteros: {e}")
            
            if not enteros:
                logger.warning("No se encontraron números enteros")
                return None
            
            # Reconstruir parte entera
            if len(enteros) >= 2:
                partes.append(enteros[0])
                partes.append('.')
                partes.append(enteros[1])
            else:
                partes.append(enteros[0])
            
            # 3. Coma decimal - USAR textContent
            tiene_coma = False
            try:
                decimal = elemento.find_element(By.CSS_SELECTOR, 
                    "[class*='currencyDecimal']")
                
                # ✨ CLAVE: Usar textContent en lugar de .text
                texto_decimal = decimal.get_attribute('textContent') or decimal.text
                texto_decimal = texto_decimal.strip()
                
                logger.debug(f"currencyDecimal textContent: '{texto_decimal}'")
                
                if texto_decimal:
                    partes.append(texto_decimal)
                    tiene_coma = True
                    logger.debug(f"[OK] Coma agregada: '{texto_decimal}'")
                else:
                    # Fallback: asumir que es coma
                    partes.append(',')
                    tiene_coma = True
                    logger.debug(f"[WARNING] Coma asumida (elemento existe pero vacío)")
            
            except Exception as e:
                logger.debug(f"No se encontró currencyDecimal: {e}")
                tiene_coma = False
            
            # 4. Fracción (decimales) - USAR textContent
            if tiene_coma:
                try:
                    fraccion = elemento.find_element(By.CSS_SELECTOR, 
                        "[class*='currencyFraction']")
                    
                    # ✨ CLAVE: Usar textContent
                    texto_fraccion = fraccion.get_attribute('textContent') or fraccion.text
                    texto_fraccion = texto_fraccion.strip()
                    
                    logger.debug(f"currencyFraction textContent: '{texto_fraccion}'")
                    
                    if texto_fraccion:
                        partes.append(texto_fraccion)
                        logger.debug(f"[OK] Decimales agregados: '{texto_fraccion}'")
                
                except Exception as e:
                    logger.debug(f"No se encontró currencyFraction: {e}")
            
            # Reconstruir precio
            precio_reconstruido = ''.join(partes)
            
            logger.debug(f"Precio reconstruido: '{precio_reconstruido}'")
            logger.debug(f"Partes: {partes}")
            
            return precio_reconstruido
            
        except Exception as e:
            logger.error(f"Error extrayendo precio: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _parsear_precio(self, precio_str):
        """Parsea precio argentino"""
        try:
            if not precio_str or '$' not in precio_str:
                return None
            
            match = re.search(r'\$\s*([\d\.,]+)', precio_str)
            if not match:
                return None
            
            texto = match.group(1).strip()
            
            # Con coma = decimales
            if ',' in texto:
                texto_sin_miles = texto.replace('.', '')
                texto_normalizado = texto_sin_miles.replace(',', '.')
                return float(texto_normalizado)
            
            # Solo puntos = miles
            elif '.' in texto:
                return float(texto.replace('.', ''))
            
            # Solo números
            else:
                return float(texto)
        
        except Exception as e:
            logger.error(f"Error parseando '{precio_str}': {e}")
            return None

    def _buscar_todos_precios_visibles(self):
        """Busca TODOS los precios visibles con mejor filtrado"""
        try:
            precios_encontrados = []
            
            # Buscar elementos que contengan símbolo de peso
            elementos = self.driver.find_elements(By.XPATH, "//*[contains(text(), '$')]")
            logger.info(f"[SEARCH] Analizando {len(elementos)} elementos con '$'")
            
            for i, elemento in enumerate(elementos):
                try:
                    if not elemento.is_displayed():
                        continue
                    
                    texto = elemento.text.strip()
                    if not texto or len(texto) > 100:
                        continue
                    
                    # EXCLUIR elementos que son precios base/sin impuestos
                    texto_lower = texto.lower()
                    exclusion_patterns = [
                        'sin impuestos', 'precio sin', 'impuestos nacionales',
                        'x kg', 'x kilo', 'por kg', '/kg',
                        'impuesto', 'kilo', 'kg', 'unidad', 'ahorra', 'x ', 'litro', 'lt', 
                        'por', 'gramo', 'gr', 'precio anterior', 'antes', 'envío', 'cuota',
                        'c/u', 'total', 'subtotal', 'descuento', 'oferta', 'ahorro', '%'
                    ]
                    
                    if any(pattern in texto_lower for pattern in exclusion_patterns):
                        continue
                    
                    # Buscar patrones de precio válidos (formato argentino)
                    patrones_precio = [
                        r'\$\s*\d{1,3}(?:\.\d{3})*(?:,\d{2})?',  # $ 1.429, $ 1.429,00
                        r'\$\s*\d+(?:,\d{2})?',                  # $ 1429, $ 1429,00
                    ]
                    
                    for patron in patrones_precio:
                        if re.search(patron, texto):
                            precio = self._parsear_precio(texto)
                            if precio and precio > 0:
                                # Calcular "score" de prominencia (precios más altos y textos más cortos son más probables)
                                score = precio / (len(texto) if len(texto) > 0 else 1)
                                precios_encontrados.append((precio, score, texto))
                                logger.debug(f"   [OK] Precio {i+1}: ${precio} ('{texto}')")
                                break
                            
                except Exception as e:
                    continue
            
            # Ordenar por score de prominencia (precio alto, texto corto)
            if precios_encontrados:
                precios_encontrados.sort(key=lambda x: x[1], reverse=True)
                precios_unicos = []
                for precio, score, texto in precios_encontrados:
                    if not precios_unicos or abs(precio - precios_unicos[-1]) / precios_unicos[-1] > 0.05:
                        precios_unicos.append(precio)
                
                logger.info(f"Precios únicos por prominencia: {precios_unicos}")
                return precios_unicos
            
            return []
            
        except Exception as e:
            logger.error(f"Error en búsqueda de precios visibles: {e}")
            return []
    
    def _extract_unit_price(self):
        """Busca precios unitarios (por kg, lt, etc.)."""
        try:
            el = self.driver.find_element(By.XPATH, "//*[contains(text(), 'x')]")
            txt = el.text.strip()
            match = re.search(r"\$[\d\.,]+\s*x\s*\w+", txt)
            return (txt, match.group(0)) if match else (None, None)
        except:
            return (None, None)
        
    def _build_product_data(self, name, price_normal, price_discount, unit_price, unit_text, discounts, url):
        """
        Construye los datos del producto con manejo correcto de precios
        
        Casos:
        - None: "Sin precio"
        - 0: "0" (no disponible)
        - Valor: string del número
        """
        # Manejo de precio normal
        if price_normal is None:
            precio_normal_str = ""
        elif price_normal == 0:
            precio_normal_str = "0"
        else:
            precio_normal_str = str(price_normal)
        
        # Manejo de precio descuento
        if price_discount is None:
            precio_descuento_str = ""
        elif price_discount == 0:
            precio_descuento_str = "0"
        else:
            precio_descuento_str = str(price_discount)
        
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
    
    def _extract_discounts(self): 
        """Detecta textos de promociones o descuentos visibles.""" 
        try: 
            promos = [] 
            discount_selectors = [ "//*[contains(text(),'Descuento')]", "//*[contains(text(),'Promo')]", "//*[contains(text(),'Oferta')]", "//*[contains(text(),'%')]" ] 
            for selector in discount_selectors: 
                elements = self.driver.find_elements(By.XPATH, selector) 
                for el in elements: 
                    text = el.text.strip() 
                    if text and len(text) < 100: 
                        promos.append(text) 
                    
            return self.procesar_descuentos(promos)
        except: 
            return []
    
    def limpiar_descuento(self, texto: str) -> str:
        """
        Limpieza unificada para descuentos:
        - minuscula
        - sin acentos
        - sin emojis
        - sin caracteres raros
        - espacios normalizados
        """
        if not texto:
            return ""

        # 1) eliminar emojis y símbolos no textuales
        texto = texto.encode('ascii', 'ignore').decode('ascii')

        # 2) pasar a minúscula
        texto = texto.lower()

        # 3) eliminar acentos
        texto = ''.join(
            c for c in unicodedata.normalize('NFD', texto)
            if unicodedata.category(c) != 'Mn'
        )

        # 4) normalizar espacios
        texto = " ".join(texto.split())

        # 5) eliminar basura: solo letras, números, %, x
        texto = re.sub(r"[^a-z0-9% x/\.]", "", texto)

        # 6) normalizar formato de descuento: ej: "20 %", "20%off"
        texto = texto.replace(" %", "%")
        texto = texto.replace("% ", "% ")
        texto = texto.replace("off", "off")  # ya está minúscula

        return texto.strip()
    
    def descuento_es_valido(self, texto: str) -> bool:
        if not texto or len(texto) > 80:
            return False

        text = texto.lower()

        keywords = ["%", "off", "descuento", "dcto", "promo", "oferta", "2x1", "3x2"]
        has_keyword = any(k in text for k in keywords)

        has_digit = any(c.isdigit() for c in text)

        return has_keyword and has_digit
    
    def normalizar_descuento(self, texto: str) -> str:
        t = texto

        # unir "20 %"
        t = re.sub(r"(\d+)\s*%", r"\1%", t)

        # ordenar formato clásico: "20% off"
        t = t.replace("off", " off")

        # arreglar doble espacio
        t = " ".join(t.split())

        return t.strip()

    def procesar_descuentos(self, descuentos_raw):
        """
        Aplica: limpiar → validar → normalizar → quitar duplicados
        """
        final = []

        for d in descuentos_raw:
            limpio = self.limpiar_descuento(d)

            if self.descuento_es_valido(limpio):
                norm = self.normalizar_descuento(limpio)
                final.append(norm)

        # eliminar duplicados manteniendo orden
        final = list(dict.fromkeys(final))

        # ordenar poniendo primero los que tienen %
        final.sort(key=lambda x: "%" not in x)

        return final



    def login_con_email_password(self):
        """Login completo con DEBUGGING DETALLADO para Masonline - VERSIÓN MEJORADA"""
        try:
            logger.info("=== DEBUG LOGIN MASONLINE ===")
            
            # Paso 1: Ir a página de login
            logger.info("[SEARCH] Navegando a login de Masonline...")
            self.driver.get(f"{self.CONFIG['base_url']}/login")
            SmartWait.wait_minimal(1)  # OPTIMIZADO: Reducido de 3s a 1s
            
            # DEBUG: Mostrar estructura de la página
            logger.info("[SEARCH] Estructura inicial de la página:")
            try:
                h3_elements = self.driver.find_elements(By.TAG_NAME, "h3")
                for i, h3 in enumerate(h3_elements):
                    if h3.is_displayed():
                        logger.info(f"H3 {i}: '{h3.text}'")
            except:
                pass
            
            # Paso 2: Ingresar credenciales
            logger.info("[SEARCH] Ingresando credenciales...")
            if not self.ingresar_credenciales_con_debug():
                return False
            
            # Paso 3: Verificar login
            logger.info("[SEARCH] Verificando login...")
            if self._verificar_sesion_activa():
                self.sesion_iniciada = True
                self.guardar_sesion()
                logger.info("[OK] LOGIN MASONLINE EXITOSO")
                return True
            else:
                logger.error("[ERROR] LOGIN MASONLINE FALLIDO")
                return False
                
        except Exception as e:
            logger.error(f"[ERROR] Error en login Masonline: {e}")
            return False
    
    def ingresar_credenciales_con_debug(self):
        """Ingresar credenciales en Masonline con debugging - VERSIÓN CORREGIDA"""
        try:
            logger.info("Ingresando credenciales en Masonline...")
            SmartWait.wait_minimal(1)  # OPTIMIZADO: Reducido de 3s a 1s
            
            # PRIMERO: HACER CLIC EN "ENTRAR CON E-MAIL Y CONTRASEÑA"
            logger.info("[SEARCH] Buscando opción 'Entrar con e-mail y contraseña'...")
            
            opciones_login = [
                "//h3[contains(text(), 'Entrar con e-mail y contraseña')]",
                "//*[contains(text(), 'Entrar con e-mail y contraseña')]",
                "//button[contains(text(), 'Entrar con e-mail y contraseña')]",
                "//div[contains(text(), 'Entrar con e-mail y contraseña')]"
            ]
            
            opcion_encontrada = False
            for opcion in opciones_login:
                try:
                    elemento = self.driver.find_element(By.XPATH, opcion)
                    if elemento.is_displayed() and elemento.is_enabled():
                        logger.info(f"[OK] Opción encontrada: {opcion}")
                        
                        # Hacer clic en la opción
                        try:
                            elemento.click()
                            logger.info("[OK] Clic en opción 'Entrar con e-mail y contraseña'")
                            opcion_encontrada = True
                            SmartWait.wait_minimal(0.5)  # OPTIMIZADO: Reducido de 2s a 0.5s
                            break
                        except Exception as click_error:
                            logger.warning(f"[WARNING] Clic normal falló: {click_error}")
                            try:
                                self.driver.execute_script("arguments[0].click();", elemento)
                                logger.info("[OK] Clic JS en opción")
                                opcion_encontrada = True
                                SmartWait.wait_minimal(0.5)  # OPTIMIZADO: Reducido de 2s a 0.5s
                                break
                            except Exception as js_error:
                                logger.error(f"[ERROR] Clic JS falló: {js_error}")
                except Exception as e:
                    logger.debug(f"Opción {opcion} no encontrada: {e}")
            
            if not opcion_encontrada:
                logger.warning("[WARNING] No se encontró la opción específica, intentando continuar...")
            
            # VERIFICAR ESTRUCTURA DE LA PÁGINA
            logger.info("[SEARCH] Analizando estructura de login...")
            try:
                forms = self.driver.find_elements(By.TAG_NAME, "form")
                logger.info(f"Formularios encontrados: {len(forms)}")
                for i, form in enumerate(forms):
                    logger.info(f"Form {i}: {form.get_attribute('id') or form.get_attribute('class')}")
            except Exception as e:
                logger.debug(f"Error analizando forms: {e}")
            
            # CAMPO EMAIL - Selectores específicos para Masonline
            campo_email = None
            selectores_email = [
                "input[placeholder='Ej.: ejemplo@mail.com']",  # ESPECÍFICO de Masonline
                "input[type='email']",
                "input[name='email']", 
                "input[placeholder*='email']",
                "input[placeholder*='Email']",
                "input[placeholder*='mail']",
                "#email",
                ".email-input",
                "input[data-testid='email']",
                "input[id*='email']"
            ]
            
            for selector in selectores_email:
                try:
                    campo_email = self.wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    if campo_email.is_displayed() and campo_email.is_enabled():
                        logger.info(f"[OK] Campo email encontrado: {selector}")
                        break
                    else:
                        campo_email = None
                except:
                    continue
            
            if not campo_email:
                logger.error("[ERROR] No se pudo encontrar campo email")
                # Debug: mostrar todos los inputs
                try:
                    inputs = self.driver.find_elements(By.TAG_NAME, "input")
                    logger.info(f"Inputs totales: {len(inputs)}")
                    for i, inp in enumerate(inputs):
                        if inp.is_displayed():
                            logger.info(f"Input {i}: type={inp.get_attribute('type')}, name={inp.get_attribute('name')}, placeholder={inp.get_attribute('placeholder')}")
                except Exception as e:
                    logger.debug(f"Error en debug inputs: {e}")
                return False
            
            # INGRESAR EMAIL
            campo_email.clear()
            campo_email.send_keys(self.email)
            logger.info("[OK] Email ingresado")
            SmartWait.wait_minimal(0.3)  # OPTIMIZADO: Reducido de 1s a 0.3s
            
            # VERIFICAR EMAIL INGRESADO
            valor_email = campo_email.get_attribute('value')
            if valor_email != self.email:
                logger.error(f"[ERROR] Email no se ingresó correctamente: {valor_email}")
                return False
            
            # CAMPO PASSWORD
            campo_password = None
            selectores_password = [
                "input[type='password']",
                "input[name='password']",
                "#password", 
                "input[placeholder*='contraseña']",
                "input[placeholder*='password']",
                ".password-input",
                "input[data-testid='password']",
                "input[id*='password']"
            ]
            
            for selector in selectores_password:
                try:
                    campo_password = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if campo_password.is_displayed() and campo_password.is_enabled():
                        logger.info(f"[OK] Campo password encontrado: {selector}")
                        break
                    else:
                        campo_password = None
                except:
                    continue
            
            if not campo_password:
                logger.error("[ERROR] No se pudo encontrar campo password")
                return False
            
            campo_password.clear()
            campo_password.send_keys(self.password)
            logger.info("[OK] Contraseña ingresada")
            SmartWait.wait_minimal(0.3)  # OPTIMIZADO: Reducido de 1s a 0.3s
            
            # BOTÓN LOGIN
            boton_login = None
            selectores_boton = [
                "button[type='submit']",
                "button[class*='login']",
                "button[class*='submit']",
                "input[type='submit']",
                ".login-button",
                ".submit-button",
                "button[data-testid='login']",
                "//button[contains(text(), 'Entrar')]",
                "//button[contains(text(), 'Ingresar')]"
            ]
            
            for selector in selectores_boton:
                try:
                    if selector.startswith("//"):
                        boton_login = self.driver.find_element(By.XPATH, selector)
                    else:
                        boton_login = self.driver.find_element(By.CSS_SELECTOR, selector)
                        
                    if boton_login.is_displayed() and boton_login.is_enabled():
                        logger.info(f"[OK] Botón login encontrado: {selector}")
                        break
                    else:
                        boton_login = None
                except:
                    continue
            
            if not boton_login:
                logger.error("[ERROR] No se pudo encontrar botón login")
                # Mostrar todos los botones para debug
                try:
                    botones = self.driver.find_elements(By.TAG_NAME, "button")
                    logger.info(f"Botones totales: {len(botones)}")
                    for i, btn in enumerate(botones):
                        if btn.is_displayed():
                            logger.info(f"Botón {i}: text='{btn.text}', type={btn.get_attribute('type')}")
                except:
                    pass
                return False
            
            # HACER CLIC EN LOGIN
            try:
                boton_login.click()
                logger.info("[OK] Clic en botón login")
            except Exception as e:
                logger.warning(f"[WARNING] Clic normal falló: {e}")
                try:
                    self.driver.execute_script("arguments[0].click();", boton_login)
                    logger.info("[OK] Clic JS en botón login")
                except Exception as js_error:
                    logger.error(f"[ERROR] Clic JS falló: {js_error}")
                    return False
            
            SmartWait.wait_minimal(2)  # OPTIMIZADO: Reducido de 5s a 2s
            return True
            
        except Exception as e:
            logger.error(f"[ERROR] Error en credenciales Masonline: {e}")
            return False
        
    def _hacer_login_manual(self):
        """Realiza el login manual con las credenciales"""
        try:
            logger.info("Navegando a página de login...")
            self.driver.get(f"{self.CONFIG['base_url']}/login")
            SmartWait.wait_minimal(1)  # OPTIMIZADO: Reducido de 3s a 1s
            
            # Buscar y hacer clic en "Entrar con email y contraseña"
            logger.info("Buscando opción de login con email...")
            opciones_login = [
                "//h3[contains(text(), 'Entrar con e-mail y contraseña')]",
                "//*[contains(text(), 'Entrar con e-mail y contraseña')]",
                "//button[contains(text(), 'Entrar con e-mail y contraseña')]"
            ]
            
            for opcion in opciones_login:
                try:
                    elemento = self.driver.find_element(By.XPATH, opcion)
                    if elemento.is_displayed() and elemento.is_enabled():
                        elemento.click()
                        logger.info("Clic en opción de login con email")
                        SmartWait.wait_minimal(0.5)  # OPTIMIZADO: Reducido de 2s a 0.5s
                        break
                except:
                    continue
            
            # Ingresar email
            logger.info("Ingresando email...")
            campo_email = None
            selectores_email = [
                "input[type='email']",
                "input[name='email']",
                "#email",
                "input[placeholder*='email']"
            ]
            
            for selector in selectores_email:
                try:
                    campo_email = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if campo_email.is_displayed():
                        campo_email.clear()
                        campo_email.send_keys(self.email)
                        logger.info("Email ingresado")
                        break
                except:
                    continue
            
            if not campo_email:
                logger.error("No se pudo encontrar campo email")
                return False
            
            # Ingresar contraseña
            logger.info("Ingresando contraseña...")
            campo_password = None
            selectores_password = [
                "input[type='password']",
                "input[name='password']",
                "#password"
            ]
            
            for selector in selectores_password:
                try:
                    campo_password = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if campo_password.is_displayed():
                        campo_password.clear()
                        campo_password.send_keys(self.password)
                        logger.info("Contraseña ingresada")
                        break
                except:
                    continue
            
            if not campo_password:
                logger.error("No se pudo encontrar campo password")
                return False
            
            # Hacer clic en botón de login
            logger.info("Haciendo clic en botón login...")
            boton_login = None
            selectores_boton = [
                "button[type='submit']",
                "//button[contains(text(), 'Entrar')]",
                "//button[contains(text(), 'Ingresar')]"
            ]
            
            for selector in selectores_boton:
                try:
                    if selector.startswith("//"):
                        boton_login = self.driver.find_element(By.XPATH, selector)
                    else:
                        boton_login = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    if boton_login.is_displayed() and boton_login.is_enabled():
                        boton_login.click()
                        logger.info("Clic en botón login realizado")
                        break
                except:
                    continue
            
            if not boton_login:
                logger.error("No se pudo encontrar botón login")
                return False
            
            # OPTIMIZADO: Espera mínima para verificar login
            SmartWait.wait_minimal(2)  # Reducido de 5s a 2s
            
            if self._verificar_sesion_activa():
                self.sesion_iniciada = True
                self.guardar_sesion()
                logger.info("Login exitoso")
                return True
            else:
                logger.error("Login fallido")
                return False
                
        except Exception as e:
            logger.error(f"Error en login manual: {e}")
            return False
    
    def _verificar_sesion_activa(self):
        """Verifica si la sesión está activa"""
        try:
            # Intentar acceder a una página protegida
            self.driver.get(f"{self.CONFIG['base_url']}/my-account")
            SmartWait.wait_minimal(1)  # OPTIMIZADO: Reducido de 2s a 1s
            
            # Si no redirige a login, la sesión está activa
            if 'login' not in self.driver.current_url.lower():
                return True
            
            # Buscar indicadores de sesión activa
            indicadores = [
                "//*[contains(text(), 'Mi cuenta')]",
                "//*[contains(text(), 'Cerrar sesión')]",
                "//*[contains(text(), 'Mis pedidos')]"
            ]
            
            for indicador in indicadores:
                try:
                    elemento = self.driver.find_element(By.XPATH, indicador)
                    if elemento.is_displayed():
                        return True
                except:
                    continue
            
            return False
        except:
            return False
    
    def asegurar_sesion_activa(self):
        """Asegura que haya una sesión activa - OPTIMIZADO con CookieManager"""
        if self.driver is None:
            self.setup_driver()
        
        # OPTIMIZADO: Intentar cargar cookies existentes primero
        cookies = self.cookie_manager.load_cookies('masonline')
        if cookies:
            try:
                self.driver.get(f"{self.CONFIG['base_url']}")
                self.driver.delete_all_cookies()
                for cookie in cookies:
                    try:
                        self.driver.add_cookie(cookie)
                    except:
                        pass
                self.driver.refresh()
                SmartWait.wait_minimal(1)
                
                if self._verificar_sesion_activa():
                    self.sesion_iniciada = True
                    logger.info("[OK] Sesión cargada desde cookies")
                    return True
            except Exception as e:
                logger.debug(f"Error cargando cookies: {e}")
        
        # Si no hay cookies o no funcionan, hacer login
        logger.info("Iniciando sesión manualmente...")
        if self.login_con_email_password():
            self.sesion_iniciada = True
            logger.info("Sesión iniciada exitosamente")
            return True
        else:
            logger.error("No se pudo iniciar sesión")
            return False
    
    def guardar_sesion(self):
        """Guarda las cookies de la sesión actual - OPTIMIZADO con CookieManager"""
        try:
            if self.driver and self.sesion_iniciada:
                cookies = self.driver.get_cookies()
                # OPTIMIZADO: Usar CookieManager centralizado
                if self.cookie_manager.save_cookies('masonline', cookies):
                    logger.info("Sesión Masonline guardada con CookieManager")
                    return True
            return False
        except Exception as e:
            logger.error(f"Error guardando sesión Masonline: {e}")
            return False
    
    def _es_pagina_error(self):
        """Detecta si la página actual es una página de error"""
        try:
            indicadores_error = ["404", "página no encontrada", "error", "no existe", "not found"]
            titulo = self.driver.title.lower()
            body_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
            
            for indicador in indicadores_error:
                if indicador in titulo or indicador in body_text:
                    return True
                    
            return False
        except:
            return False
    
    def cleanup_driver(self):
        """Cierra el driver de Selenium"""
        try:
            if self.driver:
                self.driver.quit()
                self.driver = None
                self.wait = None
                self.sesion_iniciada = False
                logger.info("Driver de Masonline cerrado correctamente")
        except Exception as e:
            logger.error(f"Error cerrando driver Masonline: {e}")



            