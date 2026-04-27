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

# Agregar directorio padre al path para imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.optimization import optimize_driver_options, SmartWait, create_driver_with_retry

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('paradacanga_extractor')

load_dotenv()

class ParadacangaExtractor:
    CONFIG = {
        'timeout': 15,
        'wait_between_requests': 1.0,
        'supermarket_name': 'Parada Canga'
    }

    SELECTORS = {
        'product_card': [".inboxpro"],
        'data_link': ["a.zoom"],
    }

    def __init__(self):
        self.driver = None
        self.wait = None
        self.session_active = False

    def setup_driver(self):
        if self.driver is None:
            options = Options()
            optimize_driver_options(options)
            options.add_argument('--window-size=1920,1080')
            
            # USAR REINTENTOS PARA CREACIÓN DEL DRIVER (Resiliencia)
            self.driver = create_driver_with_retry(options, max_retries=2, wait_seconds=5)
            
            if self.driver:
                self.driver.set_page_load_timeout(30)
                self.wait = WebDriverWait(self.driver, self.CONFIG['timeout'])
        return self.driver

    def asegurar_sesion_activa(self):
        if self.driver is None:
            self.setup_driver()
        self.session_active = True
        return True

    def extraer_producto(self, url):
        try:
            if self.driver is None:
                self.setup_driver()

            logger.info(f"Escaneando catálogo: {url}")
            self.driver.get(url)
            
            try:
                WebDriverWait(self.driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".inboxpro")))
            except:
                pass

            cards = self.driver.find_elements(By.CSS_SELECTOR, ".inboxpro")
            
            if not cards:
                return [{"error_type": "no_products_found", "url": url}]

            extracted_products = []
            logger.info(f"Encontradas {len(cards)} tarjetas.")

            for index, card in enumerate(cards):
                try:
                    if not card.is_displayed(): continue
                    
                    full_info_str = ""
                    try:
                        link_elem = card.find_element(By.CSS_SELECTOR, "a.zoom")
                        full_info_str = link_elem.get_attribute("title") 
                    except:
                        continue

                    if not full_info_str: continue

                    if ":" in full_info_str:
                        parts = full_info_str.split(":")
                        raw_name = parts[0].strip()
                        raw_price_unit = parts[1].strip()
                    else:
                        raw_name = full_info_str
                        raw_price_unit = ""

                    # Limpieza de Nombre
                    nombre_final = self._clean_text_encoding(raw_name)

                    # Obtener Precio
                    precio_clean = "0"
                    match_precio = re.search(r'\$\s?([\d.,]+)', raw_price_unit)
                    if match_precio:
                        precio_clean = self._clean_price(match_precio.group(1))
                    
                    # Obtener Unidad y Peso (MEJORADO)
                    peso, unidad = self._extract_unit_weight(raw_name, raw_price_unit)

                    ppu = self._calculate_ppu(precio_clean, peso, unidad)

                    product_data = {
                        "nombre": nombre_final,         # Nombre del producto (Aguja...)
                        "producto_nombre": nombre_final,# Se sobrescribirá en extract.py con la categoría
                        "precio_normal": precio_clean,
                        "precio_descuento": precio_clean,
                        "precio_por_unidad": ppu,
                        "unidad": unidad,               # KG, UN, L
                        "peso": peso,
                        "descuentos": "Ninguno",
                        "fecha": datetime.today().strftime("%Y-%m-%d"),
                        "supermercado": self.CONFIG['supermarket_name'],
                        "url": url,
                        "origen_dato": f"card_{index}"
                    }
                    
                    extracted_products.append(product_data)

                except Exception as e:
                    logger.warning(f"Error parseando tarjeta {index}: {e}")
                    continue

            if not extracted_products:
                return [{"error_type": "parsing_error", "url": url}]

            return extracted_products

        except Exception as e:
            logger.error(f"Error crítico en URL {url}: {str(e)}")
            return [{"error_type": "exception", "msg": str(e), "url": url}]

    def _clean_text_encoding(self, text):
        if not text: return ""
        cleaned = text
        if cleaned.count('í') > len(cleaned) * 0.4:
            cleaned = cleaned.replace('í', '')
        cleaned = cleaned.replace('\x00', '')
        correcciones = {
            r'\bVaco\b': 'Vacío', r'\bVaci\b': 'Vacío', r'\bVaca\b': 'Vacío', 
            r'\bNovillit\b': 'Novillito', r'\.\.\.': '',
        }
        for mal, bien in correcciones.items():
            cleaned = re.sub(mal, bien, cleaned, flags=re.IGNORECASE)
        return cleaned.strip()

    def _extract_unit_weight(self, name_text, price_text):
        """
        Detecta unidad y peso desde el nombre o el texto del precio.
        """
        combined_text = (name_text + " " + price_text).upper()
        
        peso = "1"
        unidad = "UN" # Default

        # 1. Búsqueda explícita de "KG" o "L" sueltos en el texto del precio
        # Esto soluciona tu problema: detecta "17300 Kg." como 1 KG.
        price_upper = price_text.upper()
        if "KG" in price_upper or "KILO" in price_upper:
            return "1", "KG"
        if " LT" in price_upper or "LITRO" in price_upper: # Espacio antes de LT para no confundir palabras
            return "1", "L"

        # 2. Buscar patrones específicos (ej: 1.5 L, 500 Gr)
        regex = r'(\d+(?:[.,]\d+)?)\s*(KG|G|GR|GRAMOS|L|LT|LITRO|ML|CC|UN|U|UNID)\b'
        match = re.search(regex, combined_text)
        
        if match:
            peso_str = match.group(1).replace(',', '.')
            unidad_str = match.group(2)
            
            if unidad_str in ['GR', 'GRAMOS']: unidad = 'G'
            elif unidad_str in ['KGS', 'KILO']: unidad = 'KG'
            elif unidad_str in ['LT', 'LITRO', 'LITROS']: unidad = 'L'
            elif unidad_str in ['U', 'UNID', 'UN']: unidad = 'UN'
            else: unidad = unidad_str
            peso = peso_str
            
        return peso, unidad

    def _clean_price(self, price_text):
        if not price_text: return "0"
        try:
            clean = re.sub(r'[^\d,.]', '', str(price_text))
            if ',' in clean: clean = clean.replace(',', '.')
            return clean
        except:
            return "0"

    def _calculate_ppu(self, price, peso, unidad):
        try:
            p = float(price)
            w = float(peso)
            if w == 0: return "0"
            return f"{p/w:.2f}"
        except:
            return "0"

    def cleanup_driver(self):
        if self.driver:
            self.driver.quit()
            self.driver = None

    def guardar_sesion(self):
        return True