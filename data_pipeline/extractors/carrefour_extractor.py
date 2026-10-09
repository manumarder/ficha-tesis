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
        
        # Credenciales para login con Mi Carrefour (DNI sin puntos/guiones + contraseña)
        self.dni = os.getenv('CARREFOUR_DNI', '')
        self.password = os.getenv('CARREFOUR_PASSWORD', '')
        
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
            
            # OPTIMIZADO: Estrategia 'eager' para no esperar a que carguen imágenes/trackers pesados
            options.page_load_strategy = 'eager'
            
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
                "//button[contains(text(), 'Rechazar todo')]",
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
        """
        Extrae datos de un producto individual.
        Asegura que el driver esté inicializado antes de navegar y valida la URL.
        """
        try:
            logger.info(f"[EXTRACT] Navegando al producto...")

            if not isinstance(url, str) or not url.strip().startswith(('http://', 'https://')):
                logger.warning(f"[EXTRACT] URL inválida: {url!r}")
                return {"error_type": "invalid_url", "url": url, "titulo": "URL inválida"}

            # CRÍTICO: Asegurar sesión activa UNA SOLA VEZ al inicio.
            # Si no cargamos las cookies de sesión/ubicación, Carrefour no hidrata los precios en la web.
            if not self.sesion_iniciada:
                if not self.asegurar_sesion_activa():
                    logger.error("[ERROR] No se pudo establecer sesión ni cargar cookies")
                    return {"error_type": "no_session", "url": url, "titulo": "No se pudo establecer sesión"}

            self.driver.get(url)
            # Aumentamos un segundo la espera para asegurar la hidratación de los precios en VTEX
            SmartWait.wait_minimal(3.0)
            self._cerrar_popups_molestos()

            if self._es_pagina_error():
                logger.warning(f"[WARNING] Página no encontrada (404): {url}")
                return {"error_type": "404", "url": url, "titulo": self.driver.title}

            if self._producto_no_disponible():
                logger.warning(f"[STOCK] Cancelando extracción: Producto sin stock.")
                return {"error_type": "no_disponible", "url": url, "titulo": self.driver.title}

            nombre = self._extraer_nombre(self.wait)
            if not nombre:
                return {"error_type": "no_name", "url": url, "titulo": self.driver.title}

            # Usamos los métodos originales, sólidos
            precio_desc = self._extraer_precio_descuento(self.driver)
            precio_normal = self._extraer_precio_normal(self.driver, precio_desc)

            if precio_desc == "0" and precio_normal == "0":
                logger.warning(f"[EXTRACT] No se encontraron precios para: {nombre}. Asumiendo sin stock.")
                return {"error_type": "no_disponible", "url": url, "nombre": nombre, "titulo": self.driver.title}

            precio_completo, unidad_text = self._extraer_precio_unidad(self.driver)
            descuentos = self._extraer_descuentos(self.driver)

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
            logger.error(f"[EXTRACT] Error crítico: {e}")
            # Si el renderer explota por Timeout, matamos la ventana zombie para salvar el resto de la extracción
            if "timeout" in str(e).lower() or "renderer" in str(e).lower() or "disconnected" in str(e).lower():
                self.cleanup_driver()
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
        
        for intento in range(2):
            for selector in selectores:
                try:
                    elemento = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    nombre = elemento.text.strip()
                    if not nombre:
                        nombre = elemento.get_attribute("textContent").strip()
                    
                    if nombre:
                        return nombre
                except:
                    continue
            
            # Si no encontró texto en el primer intento, esperamos a que JS hidrate el DOM
            if intento == 0:
                time.sleep(1.5)
                
        return None
    
    def _extraer_precio_descuento(self, driver):
        """Extrae precio con descuento"""
        selectores = [
            ".vtex-product-price-1-x-sellingPriceValue",
            "span.valtech-carrefourar-product-price-0-x-sellingPriceValue",
            "span.valtech-carrefourar-product-price-0-x-currencyInteger",
            "span.valtech-carrefourar-product-price-0-x-currencyContainer",
            "span[class*='sellingPrice']",
            "[class*='sellingPriceValue']",
            "[data-testid='price-value']"
        ]
        
        return self._buscar_precio(driver, selectores, "0")

    def _extraer_precio_normal(self, driver, precio_desc):
        """Extrae precio normal"""
        selectores = [
            ".vtex-product-price-1-x-listPriceValue",
            "span.valtech-carrefourar-product-price-0-x-listPriceValue",
            "span[class*='listPrice']",
            "[class*='listPriceValue']",
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
            try:
                # Intento alternativo: buscar cualquier texto visible con formato de precio y unidad
                precio_unidad = driver.find_element(By.XPATH, "//*[contains(text(), 'kg') or contains(text(), 'l') or contains(text(), 'unidad')]")
                texto = precio_unidad.text.strip()
                if texto:
                    unidad_text = texto
            except:
                pass
            
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
                            if self.descuento_es_valido(texto):
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
                            if self.descuento_es_valido(texto):
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
                        if (self.descuento_es_valido(texto) and 
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
        """Busca precio en múltiples selectores - VERSIÓN CON ESPERA PARA JS"""
        logger.info(f"[SEARCH] BUSCANDO PRECIO - Selectores: {len(selectores)}, Default: {default}")
        
        # Loop de reintentos para dar tiempo a VTEX de inyectar el precio en el DOM
        for intento in range(3):
            for i, selector in enumerate(selectores):
                try:
                    elementos = driver.find_elements(By.CSS_SELECTOR, selector)
                    if intento == 0:  # Evita llenar el log con los mismos mensajes
                        logger.info(f"   Selector {i+1}: '{selector}' - Elementos: {len(elementos)}")
                    
                    for j, elem in enumerate(elementos):
                        texto = elem.text.strip()
                        if not texto:
                            texto = elem.get_attribute("textContent").strip()
                        
                        if intento == 0:
                            is_visible = elem.is_displayed()
                            logger.info(f"     Elemento {j+1}: '{texto}' - Visible: {is_visible}")
                        
                        if texto and any(c.isdigit() for c in texto):
                            logger.info(f"     [OK] PRECIO ENCONTRADO: '{texto}' (Intento {intento+1}/3)")
                            return texto
                            
                except Exception as e:
                    if intento == 0:
                        logger.debug(f"   Error en selector {selector}: {e}")
                    continue
            
            # Si no encontró en esta pasada, esperamos 2 segundos a que el JS renderice
            if intento < 2:
                logger.info(f"   [WAIT] Precios no listos. Esperando renderizado JS... (Intento {intento+1}/3)")
                time.sleep(2)

        logger.warning(f"[WARNING] No se encontró precio, usando default: {default}")
        return default

    def login_con_email_password(self):
        """Inicia sesión siguiendo el flujo de Mi Carrefour y popup OAuth."""
        try:
            logger.info("=== LOGIN MI CARREFOUR ===")
            self.driver.get("https://www.carrefour.com.ar/")
            SmartWait.wait_minimal(2)
            self._cerrar_popups_molestos()

            # 1. Abrir menú de usuario (personita) y clickear "Ingresar con Mi Carrefour"
            if not self.hacer_clic_ingresar_con_mail():
                return False

            # 2. Completar DNI y contraseña en la ventana/pestaña OAuth
            if not self.ingresar_credenciales_con_debug():
                return False

            # 3. Volver al foco de la ventana principal de Carrefour
            origin_handle = getattr(self, "_login_origin_handle", None)
            if origin_handle and origin_handle in self.driver.window_handles:
                self.driver.switch_to.window(origin_handle)
            else:
                self.driver.switch_to.window(self.driver.window_handles[0])

            # Esperar a que impacte la sesión y verificar
            SmartWait.wait_minimal(4)
            if self.verificar_sesion_con_debug():
                self.sesion_iniciada = True
                self.guardar_sesion()
                logger.info("[OK] LOGIN MI CARREFOUR EXITOSO")
                return True

            logger.error("Login enviado, pero no se pudo confirmar la sesión activa")
            return False

        except Exception as e:
            logger.error(f"Error en login: {e}")
            return False
        
    def hacer_clic_ingresar_con_mail(self):
        """Abre el modal de cuenta y hace clic en 'Ingresar con Mi Carrefour'."""
        try:
            self._cerrar_popups_molestos()

            # 1. Buscar y cliquear el icono de la personita
            logger.info("Buscando icono de personita / mi cuenta...")
            selectores_persona = [
                "div[class*='myAccountWrapper'] div[role='button']",
                "div[class*='myAccountWrapperLink']",
                "[data-testid='user-menu']",
                "//div[contains(@class, 'myAccountWrapper')]//div[@role='button']"
            ]

            btn_persona = None
            for sel in selectores_persona:
                try:
                    if sel.startswith("//"):
                        elems = self.driver.find_elements(By.XPATH, sel)
                    else:
                        elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    if elems and elems[0].is_displayed():
                        btn_persona = elems[0]
                        break
                except:
                    continue

            if not btn_persona:
                # Si no está visible directo, forzamos navegación a /login
                logger.info("Icono no visible directo, navegando a /login...")
                self.driver.get("https://www.carrefour.com.ar/login")
                SmartWait.wait_minimal(2)
                self._cerrar_popups_molestos()
            else:
                self.driver.execute_script("arguments[0].click();", btn_persona)
                SmartWait.wait_minimal(1.5)

            # 2. Guardar ventana base antes de que se abra la ventana OAuth
            self._login_origin_handle = self.driver.current_window_handle
            handles_previos = set(self.driver.window_handles)

            # 3. Buscar el botón "Ingresar con Mi Carrefour" en el modal
            logger.info("[SEARCH] Buscando botón 'Ingresar con Mi Carrefour' en modal...")
            selectores_btn_carrefour = [
                ".vtex-login-2-x-customOAuthOptionBtn button",
                "div.vtex-login-2-x-buttonSocial button",
                "//button[contains(., 'Ingresar con Mi Carrefour')]",
                "//button[contains(., 'Mi Carrefour')]",
                "//div[contains(@class, 'vtex-button__label') and contains(., 'Mi Carrefour')]/parent::button"
            ]

            btn_oauth = None
            for sel in selectores_btn_carrefour:
                try:
                    if sel.startswith("//"):
                        elem = self.wait.until(EC.element_to_be_clickable((By.XPATH, sel)))
                    else:
                        elem = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, sel)))
                    if elem:
                        btn_oauth = elem
                        break
                except:
                    continue

            if not btn_oauth:
                logger.error("No se pudo encontrar el botón 'Ingresar con Mi Carrefour'")
                return False

            # Click en el botón OAuth
            self.driver.execute_script("arguments[0].click();", btn_oauth)
            logger.info("Clic realizado en 'Ingresar con Mi Carrefour'")

            # 4. Esperar y cambiar de ventana/pestaña si se abrió una nueva (Keycloak)
            WebDriverWait(self.driver, 10).until(lambda d: len(d.window_handles) > len(handles_previos) or "id.carrefour.com.ar" in d.current_url)

            nuevos_handles = [h for h in self.driver.window_handles if h not in handles_previos]
            if nuevos_handles:
                self.driver.switch_to.window(nuevos_handles[-1])
                logger.info("Cambiado a la pestaña de Mi Carrefour ID (Keycloak)")

            # Esperar a que cargue el campo DNI
            WebDriverWait(self.driver, 15).until(EC.presence_of_element_located((By.ID, "username")))
            return True

        except Exception as e:
            logger.error(f"Fallo al abrir ventana de Mi Carrefour: {e}")
            return False
        
    def ingresar_credenciales_con_debug(self):
        """Ingresa DNI y contraseña en el formulario id.carrefour.com.ar."""
        try:
            logger.info("Completando credenciales en Mi Carrefour...")

            if not self.dni or not self.password:
                logger.error("Faltan CARREFOUR_DNI o CARREFOUR_PASSWORD en el entorno")
                return False

            # 1. Campo DNI
            campo_dni = self.wait.until(EC.element_to_be_clickable((By.ID, "username")))
            campo_dni.clear()
            campo_dni.send_keys(self.dni)
            SmartWait.wait_minimal(0.3)

            # 2. Campo Contraseña
            campo_pwd = self.wait.until(EC.element_to_be_clickable((By.ID, "password")))
            campo_pwd.clear()
            campo_pwd.send_keys(self.password)
            SmartWait.wait_minimal(0.3)

            # 3. Botón Enviar / Iniciar Sesión
            selectores_submit = [
                "#kc-login",
                "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'iniciar sesión')]",
                "//button[@type='submit']",
                "//input[@type='submit']"
            ]

            btn_submit = None
            for sel in selectores_submit:
                try:
                    if sel.startswith("//"):
                        btn_submit = self.driver.find_element(By.XPATH, sel)
                    else:
                        btn_submit = self.driver.find_element(By.CSS_SELECTOR, sel)
                    if btn_submit.is_displayed():
                        break
                except:
                    continue

            if not btn_submit:
                campo_pwd.send_keys(Keys.RETURN)
            else:
                self.driver.execute_script("arguments[0].click();", btn_submit)

            logger.info("Credenciales enviadas correctamente")
            return True

        except Exception as e:
            logger.error(f"Error cargando credenciales: {e}")
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
                "no encontrada",
                "¡disculpanos!",
                "no pudimos encontrar la página"
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
                error_element = self.driver.find_element(By.XPATH, "//*[contains(text(), '¡Ups!') or contains(text(), 'Página no encontrada') or contains(text(), '¡Disculpanos!')]")
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
            # 1. Convertir a string y quitar espacios
            txt = str(price_text).strip()

            # 2. Remover caracteres no numéricos excepto punto y coma
            clean_price = re.sub(r'[^\d,.]', '', txt)
            
            # 3. ELIMINAR el punto de los miles y REEMPLAZAR coma por punto
            clean_price = clean_price.replace('.', '').replace(',', '.')

            # Convertir a float y luego a string para formato consistente
            try:
                price_float = float(clean_price)
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
                "//p[contains(@class, 'vtex-rich-text-0-x-paragraph--notFoundTitle') and (contains(., 'Ups!') or contains(., 'Disculpanos!'))]",
                "//div[contains(@class, 'vtex-rich-text-0-x-container--notFoundTitle')]//*[contains(., 'Ups!') or contains(., 'Disculpanos!')]",
                "//div[contains(@class, 'vtex-flex-layout-0-x-flexCol--notFoundCol2')]//*[contains(., 'Ups!') or contains(., 'Disculpanos!')]",
                
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
            if ("¡Ups!" in page_text and "Página no encontrada" in page_text) or ("¡Disculpanos!" in page_text):
                logger.info(" Página de error detectada por texto '¡Ups!' o '¡Disculpanos!'")
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
        Verifica si el producto está sin stock enfocándose en el contenedor principal
        para evitar falsos positivos provenientes del mini-carrito.
        """
        try:
            selectores = [
                "//div[contains(@class, 'product-info')]//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'no disponible')]",
                "//div[contains(@class, 'product-info')]//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'sin stock')]",
                "//*[contains(@class, 'buy-button-out-of-stock')]"
            ]
            
            for sel in selectores:
                elementos = self.driver.find_elements(By.XPATH, sel)
                for elem in elementos:
                    if elem.is_displayed():
                        logger.info("[STOCK] Producto sin stock confirmado visualmente.")
                        return True
            return False
        except Exception as e:
            logger.debug(f"Error verificando no disponibilidad: {e}")
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