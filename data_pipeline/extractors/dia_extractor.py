import os
import sys
import time
import re
import pickle
import logging
from dotenv import load_dotenv
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
# Agregar directorio padre al path para imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.optimization import optimize_driver_options, SmartWait, create_driver_with_retry

load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DiaExtractor:
    """Extractor robusto para Dia (Plataforma VTEX)"""
    
    CONFIG = {
        'timeout': 15,
        'wait_between_requests': 2,
        'supermarket_name': 'Dia',
        'base_url': 'https://diaonline.supermercadosdia.com.ar/'
    }
    
    def __init__(self):
        self.nombre_super = self.CONFIG['supermarket_name']
        self.timeout = self.CONFIG['timeout']
        self.driver = None
        self.wait = None
        self.sesion_iniciada = False
        self.cookies_file = "dia_cookies.pkl"
        # Datos de sesión (Opcionales si usas cookies)
        self.email = 'manumarder@gmail.com' 
        self.login_solicitado = False
    
    def setup_driver(self):
        """Configura el driver de Selenium"""
        if self.driver is None:
            options = Options()
            # OPTIMIZADO: Aplicar optimizaciones automáticas (incluye flags obligatorios)
            optimize_driver_options(options)
            
            options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option('excludeSwitches', ['enable-automation'])
            options.add_experimental_option('useAutomationExtension', False)
            
            # USAR REINTENTOS PARA CREACIÓN DEL DRIVER (Resiliencia)
            self.driver = create_driver_with_retry(options, max_retries=2, wait_seconds=5)
            
            if self.driver:
                self.wait = WebDriverWait(self.driver, self.timeout)
        
        return self.driver, self.wait

    # ==========================================
    # GESTIÓN DE SESIÓN
    # ==========================================
    def asegurar_sesion_activa(self):
        """Maneja la sesión: cookies o espera manual"""
        if self.driver is None:
            self.setup_driver()
            
        # 1. Intentar cargar cookies
        if not self.sesion_iniciada and os.path.exists(self.cookies_file):
            try:
                self.driver.get(self.CONFIG['base_url'])
                cookies = pickle.load(open(self.cookies_file, "rb"))
                for cookie in cookies:
                    try:
                        self.driver.add_cookie(cookie)
                    except: pass
                self.driver.refresh()
                time.sleep(5)
                
                if self._verificar_login_exitoso():
                    self.sesion_iniciada = True
                    logger.info("[DIA] Sesión recuperada desde cookies.")
                    return True
            except Exception as e:
                logger.warning(f"[DIA] Falló carga de cookies: {e}")

        # 2. Login Manual si falla cookie
        if not self.sesion_iniciada:
            if not self.login_solicitado:
                logger.info("=========================================")
                logger.info("[DIA] SE REQUIERE LOGIN MANUAL O SELECCIÓN DE SUCURSAL")
                logger.info("=========================================")
                
                self.driver.get(self.CONFIG['base_url'])
                time.sleep(5)
                
                # Intentar abrir modal de ubicación
                try:
                    boton = self.wait.until(EC.presence_of_element_located((By.ID, "region-locator-trigger")))
                    self.driver.execute_script("arguments[0].click();", boton)
                except:
                    logger.warning("[DIA] No se encontró botón de ubicación automático.")

                # Espera activa
                logger.info("[DIA] Tienes 60 segundos para configurar tu ubicación...")
                start_wait = time.time()
                while time.time() - start_wait < 60:
                    if self._verificar_login_exitoso():
                        self.sesion_iniciada = True
                        self.guardar_sesion()
                        logger.info("[DIA] Login/Ubicación detectada exitosamente.")
                        return True
                    time.sleep(2)
                
                self.login_solicitado = True 
            
            # Verificación final
            if self._verificar_login_exitoso():
                self.sesion_iniciada = True
                self.guardar_sesion()
                return True
            else:
                logger.error("[DIA] No se detectó sesión activa. Continuando sin sesión (precios pueden variar).")
                # Permitimos continuar aunque falle el login para no detener todo el scrape
                return True 
        
        return True

    def _verificar_login_exitoso(self):
        """Busca indicadores de usuario logueado o sucursal seleccionada"""
        try:
            indicadores = [
                "//span[contains(text(), 'Retiras en')]",
                "//div[contains(text(), 'Retiras en')]",
                "//span[contains(@class, 'profile')]"
            ]
            for xpath in indicadores:
                if len(self.driver.find_elements(By.XPATH, xpath)) > 0:
                    return True
            return False
        except:
            return False

    def guardar_sesion(self):
        if self.driver:
            try:
                pickle.dump(self.driver.get_cookies(), open(self.cookies_file, "wb"))
            except: pass

    # ==========================================
    # EXTRACCIÓN
    # ==========================================
    def extraer_producto(self, url):
        """Extrae datos de un producto individual de forma segura"""
        if not self.driver:
            self.setup_driver()

        try:
            self.driver.get(url)
            # Espera inteligente: o carga el precio o espera un tiempo prudencial
            try:
                self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[class*='sellingPriceValue']")))
                SmartWait.wait_minimal(1.5) # Tiempo extra para hidratación de precios
            except:
                SmartWait.wait_minimal(3.0) # Espera mayor si no detecta el elemento rápido

            if "404" in self.driver.title or "Pagina no encontrada" in self.driver.title:
                logger.warning(f"[DIA] 404 No encontrado: {url}")
                return {'error_type': '404_NOT_FOUND'}

            # 1. Extraer Nombre
            name = self._extract_name(url)

            # 2. Extraer Precios (Lógica Robusta)
            prices = self._extract_prices_safe()

            # 3. Construir Datos
            data = {
                "supermercado": "Dia",
                "producto_nombre": name,
                "nombre": name,
                "precio_descuento": prices['precio_descuento'], 
                "precio_normal": prices['precio_normal'],
                "precio_por_unidad": self._extract_text_safe("[class*='measurementUnit']"),
                "unidad_medida": "",
                "descuentos": " | ".join(self._extract_list_safe(".vtex-product-highlights-2-x-productHighlightText")),
                "url": url,
                "fecha_extraccion": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            logger.info(f"[DIA] OK: {name[:30]}... | ${data['precio_descuento']}")
            return data

        except Exception as e:
            logger.error(f"[DIA] Error crítico en {url}: {str(e)}")
            return {'error_type': f'EXCEPTION: {str(e)}'}

    def _extract_name(self, url):
        """Intenta obtener nombre por H1, Clase o URL"""
        try:
            # Opción A: H1
            h1 = self.driver.find_elements(By.TAG_NAME, "h1")
            if h1 and h1[0].text.strip():
                return h1[0].text.strip()
            
            # Opción B: Clase específica de marca
            brand = self.driver.find_elements(By.CSS_SELECTOR, "span.vtex-store-components-3-x-productBrand")
            if brand and brand[0].text.strip():
                return brand[0].text.strip()
                
        except: pass
        
        # Opción C: Fallback URL
        try:
            slug = url.split('.ar/')[-1].split('/p')[0]
            clean_slug = slug.replace('-', ' ').title()
            return clean_slug
        except:
            return "Nombre Desconocido"

    def _extract_prices_safe(self):
        """Busca precios con múltiples selectores y manejo de errores"""
        resultado = {'precio_normal': 0.0, 'precio_descuento': 0.0}
        
        try:
            # Selectores parciales (contienen texto) para mayor compatibilidad
            selling_elems = self.driver.find_elements(By.CSS_SELECTOR, "[class*='sellingPriceValue']")
            list_elems = self.driver.find_elements(By.CSS_SELECTOR, "[class*='listPriceValue']")

            # Precio de Venta (El que se paga)
            if selling_elems:
                resultado['precio_descuento'] = self._clean_price(selling_elems[0].text)
            
            # Precio de Lista (Tachado)
            if list_elems:
                resultado['precio_normal'] = self._clean_price(list_elems[0].text)
            else:
                # Si no hay tachado, el normal es igual al de venta
                resultado['precio_normal'] = resultado['precio_descuento']
                
        except Exception as e:
            logger.debug(f"[DIA] Error extrayendo precios: {e}")
            
        return resultado

    def _clean_price(self, text):
        """Limpia string de precio a float"""
        if not text: return 0.0
        try:
            # Eliminar todo excepto dígitos y coma
            clean = re.sub(r'[^\d,]', '', text)
            # Reemplazar coma decimal por punto
            return float(clean.replace(',', '.'))
        except:
            return 0.0

    def _extract_text_safe(self, selector):
        """Extrae texto de un elemento si existe"""
        try:
            elems = self.driver.find_elements(By.CSS_SELECTOR, selector)
            return elems[0].text.strip() if elems else ""
        except: return ""

    def _extract_list_safe(self, selector):
        """Extrae lista de textos"""
        try:
            return [el.text.strip() for el in self.driver.find_elements(By.CSS_SELECTOR, selector) if el.text.strip()]
        except: return []

    def cleanup_driver(self):
        if self.driver:
            try:
                self.driver.quit()
            except: pass
            self.driver = None