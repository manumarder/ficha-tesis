import os
import sys
import time
import re
import unicodedata
import pandas as pd
import logging
from dotenv import load_dotenv
from datetime import datetime
from typing import Dict, List, Tuple, Optional
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
import random
from selenium_stealth import stealth

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

class CarrefourExtractor:
    """Extractor específico para Carrefour"""
    
    def __init__(self):
        self.nombre_super = "Carrefour"
        self.timeout = 15  # OPTIMIZADO: Reducido de 30 a 15 segundos
        self.driver = None
        self.wait = None
        self.sesion_iniciada = False
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.files_dir = os.path.join(base_dir, 'files')
        os.makedirs(self.files_dir, exist_ok=True)
        
        # OPTIMIZADO: Usar CookieManager centralizado
        self.cookie_manager = CookieManager(base_dir)
        self.cookies_file = str(self.cookie_manager.get_cookie_path('carrefour'))
        
        self.email = os.getenv('CARREFOUR_EMAIL', 'manumarder@gmail.com')
        self.password = os.getenv('CARREFOUR_PASSWORD', 'Ipecd2025')
        
        # Lista de User-Agents reales para rotación
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        ]
    
    def setup_driver(self, user_agent=None):
        """Configura el driver de Selenium - OPTIMIZADO"""
        if self.driver is None:
            options = Options()
            # OPTIMIZADO: Aplicar optimizaciones automáticas (incluye flags obligatorios)
            optimize_driver_options(options)
            
            # Configuraciones adicionales específicas
            ua = user_agent if user_agent else random.choice(self.user_agents)
            logger.info(f"[DRIVER] Usando User-Agent: {ua}")
            options.add_argument(f'user-agent={ua}')
            
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option('excludeSwitches', ['enable-automation'])
            options.add_experimental_option('useAutomationExtension', False)
            
            # USAR REINTENTOS PARA CREACIÓN DEL DRIVER (Resiliencia)
            # Nota: create_driver_with_retry ya aplica timeouts de 40s por defecto
            self.driver = create_driver_with_retry(options, max_retries=2, wait_seconds=5)
            
            if self.driver:
                self.wait = WebDriverWait(self.driver, self.timeout)
                
                # APLICAR STEALTH PARA OCULTAR AUTOMATIZACIÓN
                stealth(self.driver,
                    languages=["es-ES", "es"],
                    vendor="Google Inc.",
                    platform="Win32",
                    webgl_vendor="Intel Inc.",
                    renderer="Intel Iris OpenGL Engine",
                    fix_hairline=True,
                )
        
        return self.driver, self.wait
    
    def _cerrar_popups_molestos(self):
        """Cierra modales de ubicación, cookies y publicidad"""
        if not self.driver: return

        try:
            # 1. Cartel de Cookies (Varios idiomas y textos)
            selectores_cookies = [
                "//button[contains(text(), 'Aceptar todo')]",
                "//button[contains(text(), 'Aceptar')]",
                "//button[contains(text(), 'Entendido')]",
                "//button[contains(text(), 'Accept all')]",
                "#onetrust-accept-btn-handler",
                ".vtex-cookie-consent-0-x-hideButton"
            ]
            
            for selector in selectores_cookies:
                try:
                    if selector.startswith("//"):
                        elementos = self.driver.find_elements(By.XPATH, selector)
                    else:
                        elementos = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    if elementos and elementos[0].is_displayed():
                        self.driver.execute_script("arguments[0].click();", elementos[0])
                        logger.info(f"[POPUP] Cookie banner cerrado con: {selector}")
                        time.sleep(0.5)
                        break
                except:
                    continue

            # 2. Modal de Sucursal / Ubicación
            botones_sucursal = self.driver.find_elements(By.XPATH, "//button[contains(@class, 'confirm') or contains(text(), 'Confirmar') or contains(text(), 'Si, continuar')]")
            if botones_sucursal:
                for btn in botones_sucursal:
                    if btn.is_displayed():
                        self.driver.execute_script("arguments[0].click();", btn)
                        logger.info("[POPUP] Modal de sucursal confirmado")
                        time.sleep(0.5)
            
            # 3. Publicidades genéricas y botones de cerrar
            selectores_cerrar = [
                "button[aria-label='Close']",
                ".vtex-modal-layout-0-x-closeButton",
                ".c-close",
                ".close-button",
                "//button[contains(text(), 'No, gracias')]"
            ]
            for sel in selectores_cerrar:
                try:
                    if sel.startswith("//"):
                        elementos = self.driver.find_elements(By.XPATH, sel)
                    else:
                        elementos = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    
                    for btn in elementos:
                        if btn.is_displayed():
                            self.driver.execute_script("arguments[0].click();", btn)
                            logger.info(f"[POPUP] Popup cerrado con: {sel}")
                except:
                    continue
        
        except Exception as e:
            logger.debug(f"Error silencioso en _cerrar_popups_molestos: {e}")
        
    def extraer_producto(self, url):
        """Extrae datos de un producto individual - VERSIÓN CORREGIDA CON ANTI-CACHE"""
        try:
            logger.info("[EXTRACT] INICIANDO EXTRACCIÓN CARREFOUR")
            logger.info(f"[EXTRACT] URL: {url}")
            
            # Asegurar sesión activa UNA SOLA VEZ al inicio
            if not self.sesion_iniciada:
                if not self.asegurar_sesion_activa():
                    logger.error("[ERROR] No se pudo establecer sesión")
                    return {"error_type": "no_session", "url": url, "titulo": "No se pudo establecer sesión"}
                
            self.driver.get(url)
            # AUMENTADO: Dar más tiempo para que VTEX hidrate los precios (crítico en AWS)
            SmartWait.wait_minimal(2.0) 
            logger.info(f"[EXTRACT] Página cargada: {self.driver.title}")
            
            self._cerrar_popups_molestos()

            # Verificar si es página de error 404
            if self._es_pagina_error():
                logger.warning(f"[WARNING] Página no encontrada (404): {url}")
                return {"error_type": "404", "url": url, "titulo": self.driver.title}
            
            # Nombre del producto
            logger.info("[EXTRACT] EXTRAYENDO NOMBRE...")
            nombre = self._extraer_nombre(self.wait)
            if not nombre:
                logger.warning(f"[ERROR] No se pudo extraer nombre de {url}")
                return {"error_type": "no_name", "url": url, "titulo": self.driver.title}
            logger.info(f"[OK] Nombre extraído: {nombre}")
            
            # Precios - USAR MÉTODOS ORIGINALES
            logger.info("[EXTRACT] ========== EXTRACCIÓN DE PRECIOS ==========")
            precio_desc = self._extraer_precio_descuento(self.driver)  # MÉTODO ORIGINAL
            precio_normal = self._extraer_precio_normal(self.driver, precio_desc)  # MÉTODO ORIGINAL
            precio_completo, unidad_text = self._extraer_precio_unidad(self.driver)
            logger.info("[EXTRACT] ===========================================")
            
            # Descuentos
            logger.info("[EXTRACT] EXTRAYENDO DESCUENTOS...")
            descuentos = self._extraer_descuentos(self.driver)
            logger.info(f"[OK] Descuentos encontrados: {len(descuentos)}")
            
            # Construir resultado
            resultado = {
                "nombre": nombre,
                "precio_normal": self._clean_price(precio_normal),
                "precio_descuento": self._clean_price(precio_desc),
                "precio_por_unidad": self._clean_price(precio_completo),
                "unidad": unidad_text,
                "descuentos": " | ".join(descuentos) if descuentos else "Ninguno",
                "fecha": datetime.today().strftime("%Y-%m-%d"),
                "supermercado": self.nombre_super,
                "url": url
            }
            
            # Verificación final
            logger.info("RESUMEN EXTRACCIÓN:")
            logger.info(f"   Nombre: {resultado['nombre']}")
            logger.info(f"   Precio normal: {resultado['precio_normal']}")
            logger.info(f"   Precio descuento: {resultado['precio_descuento']}")
            logger.info(f"   Precio unidad: {resultado['precio_por_unidad']}")
            logger.info(f"   Unidad: {resultado['unidad']}")
            logger.info(f"   Descuentos: {resultado['descuentos']}")
            
            if resultado['precio_descuento'] != "0":
                logger.info(f"[OK] EXTRACCIÓN EXITOSA: {nombre}")
            else:
                logger.warning(f"[WARNING] Producto sin precio: {nombre}")
                
            return resultado
            
        except Exception as e:
            logger.error(f"ERROR crítico extrayendo {url}: {str(e)}")
            # NO resetear sesión automáticamente - solo en casos muy específicos
            return {"error_type": "exception", "url": url, "titulo": str(e)}
        
    def extract_products(self, urls):
        """Extrae múltiples productos manteniendo la misma sesión"""
        resultados = []
        
        # Establecer sesión una sola vez
        if not self.asegurar_sesion_activa():
            logger.error("No se pudo establecer sesión para la extracción")
            return resultados
        
        # Extraer cada producto
        for i, url in enumerate(urls, 1):
            logger.info(f"Extrayendo producto {i}/{len(urls)}")
            producto = self.extraer_producto(url)
            if producto:
                resultados.append(producto)
            
            # OPTIMIZADO: Pausa mínima entre requests
            SmartWait.wait_minimal(0.2)
        
        # Guardar sesión al finalizar
        self.guardar_sesion()
        return resultados
    
    def _extraer_nombre(self, wait):
        """Extrae el nombre del producto"""
        selectores = [
            "h1 .vtex-store-components-3-x-productBrand",
            "h1 span.vtex-store-components-3-x-productBrand",
            "h1.vtex-store-components-3-x-productNameContainer",
            "h1[data-testid='product-name']",
            "h1"
        ]
        
        for selector in selectores:
            try:
                elemento = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                nombre = elemento.text.strip()
                if nombre:
                    return nombre
            except:
                continue
        return None
    
    def _extraer_precio_descuento(self, driver):
        """Extrae precio con descuento"""
        selectores = [
            ".vtex-product-price-1-x-sellingPriceValue",
            "span.valtech-carrefourar-product-price-0-x-sellingPriceValue",
            "span.valtech-carrefourar-product-price-0-x-currencyInteger",
            "span.valtech-carrefourar-product-price-0-x-currencyContainer",
            "span[class*='sellingPrice']",
            "[data-testid='price-value']"
        ]
        
        return self._buscar_precio(driver, selectores, "0")
    
    def _extraer_precio_normal(self, driver, precio_desc):
        """Extrae precio normal"""
        selectores = [
            ".vtex-product-price-1-x-listPriceValue",
            "span.valtech-carrefourar-product-price-0-x-listPriceValue",
            "span[class*='listPrice']",
            ".list-price",
            ".original-price"
        ]
        
        precio = self._buscar_precio(driver, selectores, precio_desc)
        return precio if precio != precio_desc else precio_desc
    
    def _extraer_precio_unidad(self, driver):
        """Extrae precio por unidad - mantiene tu lógica actual"""
        precio_completo = ""
        unidad_text = ""
        
        try:
            # Tu lógica actual de precio por unidad
            contenedor_unidad = driver.find_element(By.CSS_SELECTOR, "div.valtech-carrefourar-dynamic-weight-price-0-x-container")
            
            try:
                precio_elem = contenedor_unidad.find_element(By.CSS_SELECTOR, "span.valtech-carrefourar-dynamic-weight-price-0-x-currencyContainer")
                precio_completo = precio_elem.text.strip()
            except:
                pass
            
            try:
                unidad_elem = contenedor_unidad.find_element(By.CSS_SELECTOR, "span.valtech-carrefourar-dynamic-weight-price-0-x-unit")
                unidad_text = unidad_elem.text.strip()
            except:
                pass
                
        except Exception as e:
            logger.info(f"No se pudo obtener precio por unidad: {e}")
            # Aquí puedes agregar tus intentos alternativos
            
        return precio_completo, unidad_text
    
    def _extraer_descuentos(self, driver):
        """Extrae descuentos con múltiples estrategias"""
        descuentos = []
        
        try:
            # ESTRATEGIA 1: Buscar por selectores CSS específicos
            selectores_descuentos = [
                ".valtech-carrefourar-product-price-0-x-discountContainer",
                ".promo-badge",
                ".promotion-label",
                ".discount-badge",
                ".offer-tag",
                ".savings",
                "[class*='discount']",
                "[class*='promo']",
                "[class*='offer']",
                "[class*='saving']",
                ".vtex-product-price-1-x-saving",
                ".vtex-store-components-3-x-discountContainer",
                ".carrefourar-product-price-0-x-discount",
                ".vecs-product-price-0-x-discount"
            ]
            
            for selector in selectores_descuentos:
                try:
                    elementos = driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elementos:
                        if elem.is_displayed():
                            texto = elem.text.strip()
                            if self.es_descuento_valido(texto):
                                descuentos.append(texto)
                                logger.debug(f"Descuento encontrado con selector '{selector}': {texto}")
                except:
                    continue
            
            # ESTRATEGIA 2: Buscar por texto que contenga palabras clave de descuento
            palabras_clave = [
                "OFF", "OFF%", "%", "DESCUENTO", "DCTO", "SAVE", "AHORRO", 
                "PROMO", "OFERTA", "2x1", "3x2", "Llevá", "Lleve", "Bonific"
            ]
            
            # Buscar elementos que contengan estas palabras
            for palabra in palabras_clave:
                try:
                    elementos = driver.find_elements(By.XPATH, f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{palabra.lower()}')]")
                    for elem in elementos:
                        if elem.is_displayed():
                            texto = elem.text.strip()
                            if self.es_descuento_valido(texto):
                                descuentos.append(texto)
                                logger.debug(f"Descuento encontrado por texto '{palabra}': {texto}")
                except:
                    continue
            # ESTRATEGIA 3: Buscar elementos con estilos de descuento
            try:
                # Buscar elementos con colores típicos de descuento (rojo, verde)
                elementos_color = driver.find_elements(By.XPATH, "//*[contains(@style, 'color')]")
                for elem in elementos_color:
                    if elem.is_displayed():
                        estilo = elem.get_attribute('style')
                        texto = elem.text.strip()
                        if (self._es_descuento_valido(texto) and 
                            any(color in estilo.lower() for color in ['red', '#ff0000', '#d32f2f', 'green', '#00ff00', '#4caf50'])):
                            descuentos.append(texto)
                            logger.debug(f"Descuento por estilo de color: {texto}")
            except:
                pass

        except Exception as e:
            logger.error(f"Error extrayendo descuentos: {str(e)}")
        
        # LIMPIEZA Y FILTRADO MEJORADO
        descuentos_limpios = self.procesar_descuentos(descuentos)
        
        logger.info(f"Descuentos finales: {descuentos_limpios}")
        return descuentos_limpios
    
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

    
    def _buscar_precio(self, driver, selectores, default):
        """Busca precio en múltiples selectores - VERSIÓN CON DEBUG"""
        logger.info(f"[SEARCH] BUSCANDO PRECIO - Selectores: {len(selectores)}, Default: {default}")
        
        for i, selector in enumerate(selectores):
            try:
                elementos = driver.find_elements(By.CSS_SELECTOR, selector)
                logger.info(f"   Selector {i+1}: '{selector}' - Elementos: {len(elementos)}")
                
                for j, elem in enumerate(elementos):
                    # FLEXIBILIZADO: Intentar obtener texto incluso si Selenium duda de la visibilidad
                    texto = elem.text.strip()
                    if not texto:
                        texto = elem.get_attribute("textContent").strip()
                    
                    is_visible = elem.is_displayed()
                    logger.info(f"     Elemento {j+1}: '{texto}' - Visible: {is_visible}")
                    
                    # Si tiene números y $ o solo números, lo consideramos válido
                    if texto and any(c.isdigit() for c in texto):
                        logger.info(f"     [OK] PRECIO ENCONTRADO: '{texto}'")
                        return texto
                        
            except Exception as e:
                logger.debug(f"   Error en selector {selector}: {e}")
                continue
        
        logger.warning(f"[WARNING] No se encontró precio, usando default: {default}")
        return default
    
    def login_con_email_password(self):
        """Login completo con DEBUGGING DETALLADO"""
        try:
            logger.info("=== DEBUG LOGIN ===")
            
            # Paso 1: Ir a página de login
            logger.info(" Navegando a login...")
            self.driver.get("https://www.carrefour.com.ar/login")
            SmartWait.wait_minimal(1)  # OPTIMIZADO: Reducido de 3s a 1s
            
            self._cerrar_popups_molestos()
            
            # Paso 2: Buscar botón de email
            logger.info(" Buscando botón email...")
            if not self.hacer_clic_ingresar_con_mail():
                return False
            
            # Paso 3: Ingresar credenciales con más verificación
            logger.info(" Ingresando credenciales...")
            if not self.ingresar_credenciales_con_debug():
                return False
            
            # Paso 4: Verificar login con más detalle
            logger.info("[SEARCH] Verificando login...")
            if self.verificar_sesion_con_debug():
                self.sesion_iniciada = True
                self.guardar_sesion()
                logger.info(" LOGIN EXITOSO")
                return True
            else:
                logger.error(" LOGIN FALLIDO ")
                return False
                
        except Exception as e:
            logger.error(f" Error en login: {e}")
            return False
        
    def hacer_clic_ingresar_con_mail(self):
        """Hacer clic específicamente en el botón 'ingresar con mail y contraseña'"""
        try:
            logger.info("[SEARCH] Buscando botón 'ingresar con mail y contraseña'...")
            
            # Asegurar que los popups no tapen el botón
            self._cerrar_popups_molestos()
            
            # ESTRATEGIA 0: WebDriverWait robusto (NUEVA)
            try:
                xpath_login = "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'mail y contraseña')]"
                boton = self.wait.until(EC.element_to_be_clickable((By.XPATH, xpath_login)))
                logger.info(" Botón encontrado por WebDriverWait")
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", boton)
                time.sleep(1)
                self.driver.execute_script("arguments[0].click();", boton)
                return True
            except:
                logger.debug("WebDriverWait falló para el botón de login, intentando alternativas...")
            
            # ESTRATEGIA 1: Búsqueda exacta por texto completo
            try:
                boton_exacto = self.driver.find_element(
                    By.XPATH, 
                    "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'ingresar con mail y contraseña')]"
                )
                if boton_exacto.is_displayed() and boton_exacto.is_enabled():
                    logger.info(" Botón EXACTO encontrado: 'ingresar con mail y contraseña'")
                    
                    # Scroll para asegurar visibilidad
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", boton_exacto)
                    SmartWait.wait_minimal(0.3)  # OPTIMIZADO: Reducido de 1s a 0.3s
                    
                    # Intentar clic normal
                    try:
                        boton_exacto.click()
                        logger.info(" Clic exitoso en botón exacto")
                        SmartWait.wait_minimal(2)  # OPTIMIZADO: Reducido de 5s a 2s
                        return True
                    except Exception as click_error:
                        logger.warning(f" Clic normal falló: {click_error}")
                        
                        # Intentar clic JavaScript
                        try:
                            self.driver.execute_script("arguments[0].click();", boton_exacto)
                            logger.info(" Clic JS exitoso en botón exacto")
                            time.sleep(5)
                            return True
                        except Exception as js_error:
                            logger.error(f" Clic JS también falló: {js_error}")
                            
            except Exception as e:
                logger.debug(f"Búsqueda exacta falló: {e}")
            
            # ESTRATEGIA 2: Búsqueda por partes del texto (más flexible)
            textos_parciales = [
                "ingresar con mail y contraseña",
                "ingresar con mail",
                "mail y contraseña",
                "ingresar con email y contraseña",
                "ingresar con email"
            ]
            
            for texto in textos_parciales:
                try:
                    boton = self.driver.find_element(
                        By.XPATH, 
                        f"//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{texto.lower()}')]"
                    )
                    if boton.is_displayed() and boton.is_enabled():
                        logger.info(f" Botón encontrado (parcial): '{texto}'")
                        
                        # Scroll para asegurar visibilidad
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", boton)
                        SmartWait.wait_minimal(0.3)  # OPTIMIZADO: Reducido de 1s a 0.3s
                        
                        # Intentar clic normal
                        try:
                            boton.click()
                            logger.info(f" Clic exitoso en: '{texto}'")
                            SmartWait.wait_minimal(2)  # OPTIMIZADO: Reducido de 5s a 2s
                            return True
                        except Exception as click_error:
                            logger.warning(f" Clic normal falló en '{texto}': {click_error}")
                            
                            # Intentar clic JavaScript
                            try:
                                self.driver.execute_script("arguments[0].click();", boton)
                                logger.info(f" Clic JS exitoso en: '{texto}'")
                                SmartWait.wait_minimal(2)  # OPTIMIZADO: Reducido de 5s a 2s
                                return True
                            except Exception as js_error:
                                logger.error(f" Clic JS falló en '{texto}': {js_error}")
                                
                except Exception as e:
                    logger.debug(f"Texto parcial '{texto}' no encontrado: {e}")
            
            # ESTRATEGIA 3: Buscar en modales específicos
            try:
                modal = self.driver.find_element(By.XPATH, "//div[contains(@class, 'vtex-login')]")
                botones = modal.find_elements(By.TAG_NAME, "button")
                
                logger.info(f" Buscando en modal - Botones encontrados: {len(botones)}")
                
                for i, boton in enumerate(botones):
                    texto = boton.text.strip().lower()
                    is_enabled = boton.is_enabled()
                    is_displayed = boton.is_displayed()
                    
                    logger.info(f"Botón {i}: '{texto}' | Habilitado: {is_enabled} | Visible: {is_displayed}")
                    
                    # Buscar específicamente el texto completo o parcial
                    if ('ingresar con mail y contraseña' in texto or 
                        'mail y contraseña' in texto or
                        'ingresar con mail' in texto):
                        
                        if is_enabled and is_displayed:
                            logger.info(f" Botón modal encontrado: '{texto}'")
                            
                            # Scroll para asegurar visibilidad
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", boton)
                            SmartWait.wait_minimal(0.3)  # OPTIMIZADO: Reducido de 1s a 0.3s
                            
                            # Intentar clic normal
                            try:
                                boton.click()
                                logger.info(f" Clic exitoso en botón modal: '{texto}'")
                                SmartWait.wait_minimal(2)  # OPTIMIZADO: Reducido de 5s a 2s
                                return True
                            except Exception as click_error:
                                logger.warning(f" Clic modal falló: {click_error}")
                                
                                # Intentar clic JavaScript
                                try:
                                    self.driver.execute_script("arguments[0].click();", boton)
                                    logger.info(f" Clic JS exitoso en botón modal: '{texto}'")
                                    time.sleep(5)
                                    return True
                                except Exception as js_error:
                                    logger.error(f" Clic JS modal falló: {js_error}")
                        else:
                            logger.warning(f" Botón modal encontrado pero no usable: '{texto}'")
                        
            except Exception as e:
                logger.debug(f"Búsqueda en modal falló: {e}")
            
            # ESTRATEGIA 4: Búsqueda por atributos específicos
            try:
                selectores_especiales = [
                    "button[data-testid*='email']",
                    "button[data-testid*='mail']",
                    "button[aria-label*='mail']",
                    "button[aria-label*='email']",
                    "button[class*='email']",
                    "button[class*='mail']"
                ]
                
                for selector in selectores_especiales:
                    try:
                        boton = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if boton.is_displayed() and boton.is_enabled():
                            logger.info(f" Botón por selector especial: {selector}")
                            
                            # Verificar que el texto contenga lo que buscamos
                            texto_boton = boton.text.strip().lower()
                            if any(palabra in texto_boton for palabra in ['mail', 'email', 'ingresar']):
                                
                                # Scroll para asegurar visibilidad
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", boton)
                                SmartWait.wait_minimal(0.3)  # OPTIMIZADO: Reducido de 1s a 0.3s
                                
                                # Intentar clic JavaScript directamente (más confiable)
                                self.driver.execute_script("arguments[0].click();", boton)
                                logger.info(f" Clic JS en botón especial: {selector} - Texto: '{texto_boton}'")
                                SmartWait.wait_minimal(2)  # OPTIMIZADO: Reducido de 5s a 2s
                                return True
                                
                    except Exception as e:
                        logger.debug(f"Selector especial {selector} falló: {e}")
                        
            except Exception as e:
                logger.debug(f"Búsqueda por atributos falló: {e}")
            
            # ESTRATEGIA 5: Debugging - Mostrar TODOS los botones de la página
            logger.info(" HACIENDO INVENTARIO DE TODOS LOS BOTONES...")
            try:
                todos_los_botones = self.driver.find_elements(By.TAG_NAME, "button")
                logger.info(f" TOTAL de botones en página: {len(todos_los_botones)}")
                
                for i, boton in enumerate(todos_los_botones):
                    try:
                        texto = boton.text.strip()
                        if texto:  # Solo mostrar botones con texto
                            estado = "HABILITADO" if boton.is_enabled() else "DESHABILITADO"
                            visible = "VISIBLE" if boton.is_displayed() else "OCULTO"
                            logger.info(f"Botón {i}: '{texto}' | {estado} | {visible}")
                    except:
                        pass
                        
            except Exception as e:
                logger.error(f"Error en inventario de botones: {e}")
            
            logger.error(" No se pudo encontrar el botón 'ingresar con mail y contraseña'")
            return False
            
        except Exception as e:
            logger.error(f" Error general en búsqueda de botón: {e}")
            return False
        
    def ingresar_credenciales_con_debug(self):
        """Ingresar credenciales con debugging detallado"""
        try:
            logger.info("Ingresando credenciales...")
            SmartWait.wait_minimal(1)  # OPTIMIZADO: Reducido de 3s a 1s
            
            # VERIFICAR SI HAY MENSAJES DE ERROR ANTES
            try:
                errores = self.driver.find_elements(By.CSS_SELECTOR, ".error, .alert, .message-error")
                for error in errores:
                    if error.is_displayed():
                        logger.error(f" Error visible: {error.text}")
            except:
                pass
            
            # CAMPO EMAIL - Múltiples selectores y más tiempo
            campo_email = None
            selectores_email = [
                "input[placeholder='Ej.: ejemplo@mail.com']",  # Por placeholder específico
                "input[type='text'][placeholder*='mail']",  # Tipo text con placeholder de mail
                "input[type='email']",
                "input[name='email']",
                "input[placeholder*='mail']",
                "input[placeholder*='Email']",
                "#email",
                "[data-testid='email']"
            ]
            
            for selector in selectores_email:
                try:
                    campo_email = self.wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    logger.info(f" Campo email encontrado con selector: {selector}")
                    break
                except:
                    continue
            
            if not campo_email:
                logger.error(" No se pudo encontrar campo email con ningún selector")
                return False
            
            # VERIFICAR SI EL CAMPO ESTÁ HABILITADO
            if not campo_email.is_enabled():
                logger.error(" Campo email NO está habilitado")
                return False
            
            campo_email.clear()
            campo_email.send_keys(self.email)
            logger.info(" Email ingresado")
            SmartWait.wait_minimal(0.3)  # OPTIMIZADO: Reducido de 1s a 0.3s
            
            # VERIFICAR SI EL EMAIL SE INGRESÓ CORRECTAMENTE
            valor_email = campo_email.get_attribute('value')
            if valor_email != self.email:
                logger.error(f" Email no se ingresó correctamente. Esperado: {self.email}, Obtenido: {valor_email}")
                return False
            
            # CAMPO CONTRASEÑA - MÚLTIPLES ESTRATEGIAS
            campo_password = None
            selectores = [
                "input[type='password']",
                "input[name='password']",
                "#password",
                "input[placeholder*='contraseña']",
                "input[data-testid='password']"
            ]
            
            for selector in selectores:
                try:
                    campo_password = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if campo_password.is_displayed() and campo_password.is_enabled():
                        logger.info(f" Campo password encontrado: {selector}")
                        break
                except:
                    continue
            
            if not campo_password:
                logger.error(" No se pudo encontrar campo contraseña")
                # Listar todos los inputs para debugging
                try:
                    inputs = self.driver.find_elements(By.TAG_NAME, "input")
                    logger.info(f"Inputs encontrados: {len(inputs)}")
                    for i, inp in enumerate(inputs):
                        if inp.is_displayed():
                            tipo = inp.get_attribute('type')
                            name = inp.get_attribute('name')
                            placeholder = inp.get_attribute('placeholder')
                            logger.info(f"Input {i}: type={tipo}, name={name}, placeholder={placeholder}")
                except:
                    pass
                return False
            
            campo_password.clear()
            campo_password.send_keys(self.password)
            logger.info(" Contraseña ingresada")
            SmartWait.wait_minimal(0.3)  # OPTIMIZADO: Reducido de 1s a 0.3s
            
            # VERIFICAR SI LA CONTRASEÑA SE INGRESÓ
            valor_password = campo_password.get_attribute('value')
            if len(valor_password) != len(self.password):
                logger.error(" Contraseña no se ingresó correctamente")
                return False
            
            # BOTÓN LOGIN - CON JAVASCRIPT COMO ALTERNATIVA
            try:
                boton_login = self.wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
                )
                logger.info(" Botón login encontrado")
                
                # VERIFICAR SI EL BOTÓN ESTÁ HABILITADO
                if not boton_login.is_enabled():
                    logger.error(" Botón login NO está habilitado")
                    return False
                
                # HACER CLIC - INTENTAR NORMAL PRIMERO, LUEGO JAVASCRIPT
                try:
                    boton_login.click()
                    logger.info(" Clic normal en botón login")
                except Exception as click_error:
                    logger.warning(f" Clic normal falló: {click_error}")
                    # Intentar JavaScript click como alternativa
                    try:
                        self.driver.execute_script("arguments[0].click();", boton_login)
                        logger.info(" Clic JS en botón login")
                    except Exception as js_error:
                        logger.error(f" Clic JS también falló: {js_error}")
                        return False
                
                SmartWait.wait_minimal(5)  # AJUSTE: Esperar 5s para que los tokens se asienten
                return True
                
            except Exception as e:
                logger.error(f" Error con botón login: {e}")
                return False
            
        except Exception as e:
            logger.error(f" Error en credenciales: {e}")
            return False

    def verificar_sesion_con_debug(self):
        """Verificar sesión con debugging detallado"""
        try:
            logger.info("Verificando sesión...")
            
            # OPTIMIZADO: Espera mínima para redirección
            SmartWait.wait_minimal(1)  # Reducido de 3s a 1s
            
            # Verificar URL actual
            current_url = self.driver.current_url
            logger.info(f" URL actual: {current_url}")
            
            # Si estamos todavía en login, falló
            if 'login' in current_url.lower():
                logger.error(" Seguimos en página de login")
                # Buscar mensajes de error específicos
                try:
                    errores = self.driver.find_elements(By.CSS_SELECTOR, ".error, .alert, .message-error, .vtex-login-2-x-errorMessage")
                    for error in errores:
                        if error.is_displayed():
                            logger.error(f" Mensaje de error: {error.text}")
                except:
                    pass
                return False
            
            # Buscar indicadores de sesión activa
            indicadores = [
                "//*[contains(text(), 'Mi cuenta')]",
                "//*[contains(text(), 'Hola')]",
                "//*[contains(text(), 'Cuenta')]",
                ".my-account",
                "[data-testid='user-menu']"
            ]
            
            # Buscar indicadores de sesión activa con REINTENTOS y ESPERA
            for i in range(3):
                for indicador in indicadores:
                    try:
                        if indicador.startswith("//"):
                            elemento = self.driver.find_element(By.XPATH, indicador)
                        else:
                            elemento = self.driver.find_element(By.CSS_SELECTOR, indicador)
                        
                        if elemento.is_displayed():
                            logger.info(f" Sesión activa - Indicador: {indicador}")
                            return True
                    except:
                        continue
                logger.info(f" Reintentando verificación de sesión ({i+1}/3)...")
                time.sleep(3)
            
            logger.error(" No se encontraron indicadores de sesión activa tras reintentos")
            return False
            
        except Exception as e:
            logger.error(f" Error verificando sesión: {e}")
            return False
        
    def asegurar_sesion_activa(self):
        """Asegurar sesión con reintentos limitados y rotación de UA"""
        if self.driver is None:
            self.setup_driver()
        
        # Solo 2 intentos máximo
        for intento in range(2):
            logger.info(f"Intento {intento + 1}/2 de establecer sesión")
            
            # En el segundo intento, si el primero falló, rotar User-Agent
            if intento > 0:
                logger.info("[RETRY] Rotando User-Agent para evitar detección...")
                self.cleanup_driver()
                self.setup_driver(user_agent=random.choice(self.user_agents))

            # OPTIMIZADO: Intentar cargar sesión existente usando CookieManager
            if intento == 0:
                cookies = self.cookie_manager.load_cookies('carrefour')
                if cookies:
                    try:
                        self.driver.get("https://www.carrefour.com.ar")
                        self.driver.delete_all_cookies()
                        for cookie in cookies:
                            try:
                                self.driver.add_cookie(cookie)
                            except:
                                pass
                        
                        self.driver.refresh()
                        SmartWait.wait_minimal(1.5)
                        
                        if self.verificar_sesion_con_debug():
                            self.sesion_iniciada = True
                            logger.info("[OK] Sesión cargada desde cookies")
                            return True
                    except Exception as e:
                        logger.debug(f"Error cargando sesión: {e}")
            
            # Login nuevo SOLO si no hay cookies o no funcionan
            # Navegar a login antes de intentar
            self.driver.get("https://www.carrefour.com.ar/login")
            SmartWait.wait_minimal(2)
            
            if self.login_con_email_password():
                self.sesion_iniciada = True
                logger.info("[OK] Sesión iniciada manualmente")
                return True
            
            # OPTIMIZADO: Espera mínima entre intentos
            if intento < 1:  # No esperar después del último intento
                SmartWait.wait_minimal(2)
        
        logger.error("[ERROR] Todos los intentos de login fallaron")
        return False

    def guardar_sesion(self):
        """Guarda las cookies de la sesión actual - OPTIMIZADO con CookieManager"""
        try:
            if self.driver and self.sesion_iniciada:
                cookies = self.driver.get_cookies()
                # OPTIMIZADO: Usar CookieManager centralizado
                if self.cookie_manager.save_cookies('carrefour', cookies):
                    logger.info(f"Sesión guardada con CookieManager")
                    return True
            return False
        except Exception as e:
            logger.error(f"Error guardando sesión: {e}")
            return False

    def _es_pagina_error(self):
        """Detecta si la página actual es una página de error 404"""
        try:
            # Buscar indicadores de página no encontrada
            indicadores_error = [
                "¡Ups!",
                "Página no encontrada", 
                "página no existe",
                "404",
                "no encontrada"
            ]
            
            titulo = self.driver.title.lower()
            body_text = ""
            
            try:
                body_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
            except:
                pass
            
            # Si el título o el contenido contienen indicadores de error
            for indicador in indicadores_error:
                if indicador.lower() in titulo or indicador.lower() in body_text:
                    return True
                    
            # Verificar si hay elementos específicos de error de Carrefour
            try:
                error_element = self.driver.find_element(By.XPATH, "//*[contains(text(), '¡Ups!') or contains(text(), 'Página no encontrada')]")
                return True
            except:
                pass
                
            return False
        except Exception as e:
            logger.debug(f"Error verificando página de error: {e}")
            return False
    
    def _clean_price(self, price_text):
        """Limpia y formatea el precio de manera consistente"""
        if not price_text or price_text == "0":
            return "0"
        
        try:
            # Remover TODOS los caracteres no numéricos excepto punto
            clean_price = re.sub(r'[^\d,]', '', str(price_text))
            # Reemplazar coma por punto para decimales
            clean_price = clean_price.replace(',', '.')
            
            # Convertir a float y luego a string para formato consistente
            try:
                price_float = float(clean_price)
                # Formatear sin decimales si es entero, con 2 decimales si no
                if price_float.is_integer():
                    return str(int(price_float))
                else:
                    return f"{price_float:.2f}"
            except:
                return clean_price
                
        except Exception as e:
            logger.debug("Error limpiando precio %s: %s", price_text, str(e))
            return "0"

    def cleanup_driver(self):
        """Cierra el driver de Selenium"""
        try:
            if self.driver:
                self.driver.quit()
                self.driver = None
                self.wait = None
                self.sesion_iniciada = False
                logger.info("Driver de Selenium cerrado correctamente")
        except Exception as e:
            logger.error(f"Error cerrando driver: {e}")



    #VERIFICACION DE LINKS
    def validar_links_productos(self, urls, nombre_arch_inv = "links_invalidos.csv"):
        """
        Valida todos los links antes de la extracción completa
        Retorna: dict con información de validación por producto
        """
        logger.info(" INICIANDO VALIDACIÓN DE LINKS")
        
        # VERIFICAR QUE LO QUE RECIBIMOS SON URLs VÁLIDAS
        logger.info(f" Datos recibidos para validación: {len(urls)} elementos")
        
        # Filtrar solo URLs válidas
        urls_validas = []
        for item in urls:
            if isinstance(item, str) and item.startswith(('http://', 'https://')):
                urls_validas.append(item)
            else:
                logger.warning(f" Elemento no es URL válida: {item}")
        
        logger.info(f" URLs válidas encontradas: {len(urls_validas)}/{len(urls)}")
        
        if not urls_validas:
            logger.error(" No hay URLs válidas para validar")
            return {}
        
        # Asegurar sesión activa
        if not self.asegurar_sesion_activa():
            logger.error("No se pudo establecer sesión para validación")
            return {}
        
        resultados_validacion = {}
        links_invalidos_data = []
        
        # CORRECCIÓN: Iterar sobre urls_validas en lugar de urls
        for i, url in enumerate(urls_validas, 1):
            logger.info(f" Validando link {i}/{len(urls_validas)}: {url}")
            
            resultado = self._validar_link_individual(url, i)
            resultados_validacion[url] = resultado
            
            # Si es inválido, guardar para el CSV
            if not resultado.get('valido', False):
                # Extraer nombre del producto de la URL o del resultado
                nombre_producto = self._extraer_nombre(url)
                if resultado.get('nombre_producto'):
                    nombre_producto = resultado.get('nombre_producto')
                
                links_invalidos_data.append({
                    'producto': nombre_producto,
                    'link': url,
                    'fecha': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'motivo': resultado.get('estado', 'DESCONOCIDO'),
                    'mensaje': resultado.get('mensaje', '')
                })
            
            # Pequeña pausa entre validaciones
            time.sleep(1)
        
        # Guardar CSV con links inválidos
        if links_invalidos_data:
            self._guardar_links_invalidos_csv(links_invalidos_data, nombre_arch_inv)
        
        # Mostrar resumen de validación
        self._mostrar_resumen_validacion(resultados_validacion)
        
        return resultados_validacion
    
    def _validar_link_individual(self, url, numero_link):
        """
        Valida un link individual y retorna información detallada
        """
        try:
            # VERIFICAR QUE LA URL ES VÁLIDA ANTES DE NAVEGAR
            if not url.startswith(('http://', 'https://')):
                return {
                    "valido": False,
                    "estado": "URL_INVALIDA",
                    "mensaje": f"URL no válida: {url}",
                    "titulo_pagina": "N/A",
                    "url_final": "N/A"
                }
            
            # Configurar timeout más corto para páginas de error
            self.driver.set_page_load_timeout(15)  # Reducir de 30 a 15 segundos
            
            # OPTIMIZADO: Intentar cargar la página con manejo de timeout
            try:
                self.driver.get(url)
                SmartWait.wait_minimal(0.5)  # Reducido de 2s a 0.5s
            except Exception as load_error:
                return {
                    "valido": False,
                    "estado": "ERROR_CARGA",
                    "mensaje": f"No se pudo cargar la página: {str(load_error)}",
                    "titulo_pagina": "N/A",
                    "url_final": "N/A"
                }
            
            # Verificar si la página cargó correctamente
            current_url = self.driver.current_url
            titulo_pagina = self.driver.title
            
            logger.info(f" Página cargada - Título: {titulo_pagina}")
            logger.info(f" URL final: {current_url}")
            
            if "carrefour.com.ar" not in current_url:
                return {
                    "valido": False,
                    "estado": "ERROR_CARGA",
                    "mensaje": "No se pudo cargar la página de Carrefour",
                    "titulo_pagina": titulo_pagina,
                    "url_final": current_url
                }
            
            # DEBUG: Analizar qué está detectando exactamente
            logger.info(" ANALIZANDO ESTADO DEL PRODUCTO...")
            
            # USAR LOS MÉTODOS QUE YA FUNCIONABAN
            es_error = self._es_pagina_error_ups()  # [OK] Método original que funciona
            logger.info(f"   ¿Es página de error '¡Ups!'? {es_error}")
            
            # VERIFICAR DISPONIBILIDAD - LÓGICA ORIGINAL QUE FUNCIONABA
            no_disponible = self._producto_no_disponible()  # [OK] Método original que funciona
            logger.info(f"   ¿No disponible? {no_disponible}")
            
            disponible = self._producto_disponible()  # [OK] Método original que funciona
            logger.info(f"   ¿Disponible? {disponible}")
            
            # DECISIÓN BASADA EN LOS RESULTADOS (LÓGICA ORIGINAL MEJORADA)
            if es_error:
                return {
                    "valido": False,
                    "estado": "PAGINA_NO_ENCONTRADA",
                    "mensaje": "Página no encontrada (Error 404 - ¡Ups!)",
                    "titulo_pagina": titulo_pagina,
                    "url_final": current_url
                }
            
            if no_disponible:
                return {
                    "valido": False,
                    "estado": "NO_DISPONIBLE",
                    "mensaje": "Producto sin stock - Botón 'No Disponible' detectado",
                    "titulo_pagina": titulo_pagina,
                    "url_final": current_url
                }
            
            if disponible:
                # Verificar si podemos extraer información básica
                nombre = self._extraer_nombre(self.wait)
                logger.info(f" Nombre extraído: {nombre}")
                
                if not nombre:
                    return {
                        "valido": False,
                        "estado": "SIN_NOMBRE",
                        "mensaje": "No se puede extraer el nombre del producto",
                        "titulo_pagina": titulo_pagina,
                        "url_final": current_url
                    }
                
                # Verificar si hay precios - CRITERIO PRINCIPAL CORREGIDO
                precio_desc = self._extraer_precio_descuento(self.driver)
                logger.info(f" Precio extraído: {precio_desc}")
                
                # [OK] CRITERIO MEJORADO: Si no hay precio o precio es 0 = NO DISPONIBLE
                if not precio_desc or precio_desc == "0":
                    return {
                        "valido": False,
                        "estado": "NO_DISPONIBLE",
                        "mensaje": "Producto sin precio - No disponible",
                        "titulo_pagina": titulo_pagina,
                        "nombre_producto": nombre,
                        "url_final": current_url
                    }
                
                # Si llegamos aquí, el link es válido
                return {
                    "valido": True,
                    "estado": "OK",
                    "mensaje": "Link válido - Producto disponible y extraíble",
                    "titulo_pagina": titulo_pagina,
                    "nombre_producto": nombre,
                    "precio_descuento": precio_desc,
                    "url_final": current_url
                }
            
            # Si no cumple ninguna de las condiciones anteriores, verificar por datos
            logger.info(" No se pudo determinar por botones - Verificando por datos...")
            nombre = self._extraer_nombre(self.wait)
            precio_desc = self._extraer_precio_descuento(self.driver)
            
            logger.info(f" Verificación por datos - Nombre: {nombre}, Precio: {precio_desc}")
            
            # [OK] CRITERIO MEJORADO: Si tiene nombre pero NO tiene precio = NO DISPONIBLE
            if nombre and (not precio_desc or precio_desc == "0"):
                return {
                    "valido": False,
                    "estado": "NO_DISPONIBLE",
                    "mensaje": "Producto con nombre pero sin precio - No disponible",
                    "titulo_pagina": titulo_pagina,
                    "nombre_producto": nombre,
                    "url_final": current_url
                }
            
            # Si tiene nombre y precio, considerar como disponible
            if nombre and precio_desc and precio_desc != "0":
                return {
                    "valido": True,
                    "estado": "OK",
                    "mensaje": "Link válido - Producto con datos extraíbles",
                    "titulo_pagina": titulo_pagina,
                    "nombre_producto": nombre,
                    "precio_descuento": precio_desc,
                    "url_final": current_url
                }
            
            # Si llegamos aquí, es inválido
            logger.info(" No se pudo determinar el estado - Marcando como DESCONOCIDO")
            return {
                "valido": False,
                "estado": "DESCONOCIDO",
                "mensaje": "No se pudo determinar el estado del producto",
                "titulo_pagina": titulo_pagina,
                "url_final": current_url
            }
                
        except Exception as e:
            logger.error(f" Error validando link {numero_link}: {str(e)}")
            return {
                "valido": False,
                "estado": "ERROR_EXCEPCION",
                "mensaje": f"Error inesperado: {str(e)}",
                "titulo_pagina": self.driver.title if self.driver else "No disponible",
                "url_final": self.driver.current_url if self.driver else "No disponible"
            }
        
    def _es_pagina_error_ups(self):
        """
        Verifica si la página muestra el error "¡Ups! Página no encontrada"
        CON SELECTORES ESPECÍFICOS DE LAS FOTOS
        """
        try:
            # SELECTORES ESPECÍFICOS de la foto que me enviaste
            selectores_error_especificos = [
                # Selector del texto "¡Ups!"
                "//p[contains(@class, 'vtex-rich-text-0-x-paragraph--notFoundTitle') and contains(., 'Ups!')]",
                "//div[contains(@class, 'vtex-rich-text-0-x-container--notFoundTitle')]//*[contains(., 'Ups!')]",
                "//div[contains(@class, 'vtex-flex-layout-0-x-flexCol--notFoundCol2')]//*[contains(., 'Ups!')]",
                
                # Selectores de la estructura del error
                ".vtex-rich-text-0-x-container--notFoundTitle",
                ".vtex-flex-layout-0-x-flexCol--notFoundCol2",
                "[class*='notFoundTitle']",
                "[class*='notFoundCol2']"
            ]
            
            # Verificar con selectores específicos
            for selector in selectores_error_especificos:
                try:
                    if selector.startswith("//"):
                        elementos = self.driver.find_elements(By.XPATH, selector)
                    else:
                        elementos = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    for elemento in elementos:
                        if elemento.is_displayed():
                            logger.info(f" Página de error detectada con selector: {selector}")
                            return True
                except:
                    continue
            
            # También verificar por texto en la página (backup)
            page_text = self.driver.page_source
            if "¡Ups!" in page_text and "Página no encontrada" in page_text:
                logger.info(" Página de error detectada por texto '¡Ups!'")
                return True
                    
            return False
            
        except Exception as e:
            logger.debug(f"Error verificando página de error: {e}")
            return False
        
    def _producto_disponible(self):
        """
        VERIFICACIÓN MEJORADA - Detecta disponibilidad con más precisión
        """
        try:
            # ESTRATEGIA 1: Buscar botones de "Agregar" HABILITADOS y VISIBLES
            textos_agregar = ["Agregar", "Agregar al carrito", "Comprar"]
            
            for texto in textos_agregar:
                try:
                    xpath = f"//button[contains(., '{texto}') and not(@disabled) and not(contains(@class, 'disabled'))]"
                    botones = self.driver.find_elements(By.XPATH, xpath)
                    
                    for boton in botones:
                        if boton.is_displayed() and boton.is_enabled():
                            # VERIFICAR que NO contenga texto "No Disponible"
                            texto_boton = boton.text.strip()
                            if "No Disponible" not in texto_boton:
                                logger.info(f" Botón '{texto}' HABILITADO encontrado: {texto_boton}")
                                return True
                except Exception as e:
                    logger.debug(f"Error buscando botón '{texto}': {e}")
                    continue
            
            # ESTRATEGIA 2: Buscar la estructura específica de Carrefour para productos disponibles
            # Basado en el HTML que me mostraste
            selectores_disponibilidad = [
                "//button[contains(@class, 'bg-action-primary') and not(@disabled)]",
                "//button[contains(@class, 'vtex-button') and not(contains(@class, 'disabled'))]",
                "//div[contains(@class, 'isAvailable')]",
                "//button[.//div[contains(@class, 'vtex-button__label')] and not(@disabled)]"
            ]
            
            for selector in selectores_disponibilidad:
                try:
                    if selector.startswith("//"):
                        elementos = self.driver.find_elements(By.XPATH, selector)
                    else:
                        elementos = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    for elemento in elementos:
                        if elemento.is_displayed() and elemento.is_enabled():
                            # Verificar que no sea un falso positivo
                            texto = elemento.text.strip()
                            if texto and "No Disponible" not in texto:
                                logger.info(f" Elemento disponible encontrado: {selector} - Texto: '{texto}'")
                                return True
                except:
                    continue
            
            # ESTRATEGIA 3: Verificar si podemos extraer información del producto exitosamente
            try:
                nombre = self._extraer_nombre(self.wait)
                precio = self._extraer_precio_descuento(self.driver)
                
                logger.info(f"[SEARCH] Verificación por datos - Nombre: '{nombre}', Precio: '{precio}'")
                
                if nombre and precio != "0":
                    # Si tenemos nombre y precio, y NO hay indicadores claros de no disponibilidad
                    if not self._producto_no_disponible():
                        logger.info(" Producto disponible (tiene datos válidos y sin indicadores de no disponibilidad)")
                        return True
            except Exception as e:
                logger.debug(f"Error en verificación por datos: {e}")
            
            return False
            
        except Exception as e:
            logger.error(f"Error en verificación mejorada de disponibilidad: {e}")
            return False
    
    def _producto_no_disponible(self):
        """
        VERIFICACIÓN MEJORADA - Solo marca como no disponible si hay indicadores CLAROS
        """
        try:
            # SELECTORES MÁS ESPECÍFICOS Y CONFIABLES para "No Disponible"
            selectores_estrictos = [
            # Botón deshabilitado con texto EXPLÍCITO "No Disponible"
            "//button[@disabled]//span[contains(text(), 'No Disponible')]",
            "//span[contains(text(), 'No Disponible') and contains(@class, 'isUnavailable')]",
            # Elemento que claramente dice "No Disponible" y está visible
            "//*[contains(text(), 'No Disponible') and not(ancestor::*[contains(@style, 'display:none')])]"
             ]

            
            for selector in selectores_estrictos:
                try:
                    elementos = self.driver.find_elements(By.XPATH, selector)
                    for elemento in elementos:
                        if elemento.is_displayed():
                            texto = elemento.text.strip()
                            if "No Disponible" in texto:
                                logger.info(f" Confirmado: Producto NO disponible - {selector}")
                                return True
                except:
                    continue
            
            # Verificación adicional: Si hay botón deshabilitado PERO sin texto claro, no asumir no disponible
            return False
            
        except Exception as e:
            logger.debug(f"Error en verificación mejorada de no disponibilidad: {e}")
            return False


    
    def _guardar_links_invalidos_csv(self, datos, nombre_archivo):
        """
        Guarda los links inválidos en un archivo CSV
        """
        try:
            df = pd.DataFrame(datos)
            df.to_csv(nombre_archivo, index=False, encoding='utf-8')
            logger.info(f" CSV con links inválidos guardado: {nombre_archivo}")
            logger.info(f" Total de links inválidos registrados: {len(datos)}")
            
            # Mostrar resumen por tipo de error
            if not df.empty:
                resumen_errores = df['motivo'].value_counts()
                logger.info(" Resumen de errores:")
                for motivo, cantidad in resumen_errores.items():
                    logger.info(f"   - {motivo}: {cantidad} links")
                    
        except Exception as e:
            logger.error(f" Error guardando CSV de links inválidos: {e}")

    def _mostrar_resumen_validacion(self, resultados):
        """
        Muestra un resumen detallado de la validación
        """
        logger.info(" ========== RESUMEN DE VALIDACIÓN ==========")
        
        total_links = len(resultados)
        links_validos = sum(1 for r in resultados.values() if r.get('valido', False))
        links_invalidos = total_links - links_validos
        
        logger.info(f" Total links procesados: {total_links}")
        logger.info(f" Links válidos: {links_validos}")
        logger.info(f" Links inválidos: {links_invalidos}")
        
        # Detalle por estado
        estados = {}
        for resultado in resultados.values():
            estado = resultado.get('estado', 'DESCONOCIDO')
            estados[estado] = estados.get(estado, 0) + 1
        
        logger.info(" Detalle por estado:")
        for estado, cantidad in estados.items():
            logger.info(f"   - {estado}: {cantidad} links")
        
        logger.info("==============================================")