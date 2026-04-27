"""
Implementación local de ConexionGoogleSheets para reemplazar etl_modular
"""
import os
from googleapiclient.discovery import build
from google.oauth2 import service_account
import pandas as pd
import logging
from json import loads

logger = logging.getLogger(__name__)

class ConexionGoogleSheets:
    """Clase para interactuar con Google Sheets API"""
    
    def __init__(self, sheet_id):
        self.sheet_id = sheet_id
        self.service = None
        self._setup_service()
    
    def _setup_service(self):
        """Configura el servicio de Google Sheets"""
        try:
            # Intentar cargar credenciales desde variable de entorno JSON directo
            credentials_json = os.getenv('GOOGLE_SHEETS_API_KEY')
            
            # O desde GOOGLE_SHEETS_CREDENTIALS_FILE que también puede contener JSON
            if not credentials_json:
                credentials_json = os.getenv('GOOGLE_SHEETS_CREDENTIALS_FILE')
            
            if credentials_json:
                # Cargar desde JSON string en variable de entorno
                credentials_dict = loads(credentials_json)
                credentials = service_account.Credentials.from_service_account_info(
                    credentials_dict,
                    scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
                )
            else:
                # Intentar cargar desde archivo físico
                credentials_file = os.getenv('GOOGLE_SHEETS_CREDENTIALS_FILE', 'credentials.json')
                if os.path.exists(credentials_file) and not credentials_file.startswith('{'):
                    credentials = service_account.Credentials.from_service_account_file(
                        credentials_file,
                        scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
                    )
                else:
                    logger.warning("No se encontraron credenciales de Google Sheets")
                    return
            
            self.service = build('sheets', 'v4', credentials=credentials)
            logger.info("Servicio de Google Sheets configurado correctamente")
            
        except Exception as e:
            logger.error(f"Error configurando Google Sheets: {e}")
    
    def leer_df(self, range_name, header=True):
        """Lee datos de Google Sheets y retorna un DataFrame"""
        try:
            if not self.service:
                logger.error("Servicio de Google Sheets no disponible")
                return pd.DataFrame()
            
            # Leer datos de la hoja
            sheet = self.service.spreadsheets()
            result = sheet.values().get(
                spreadsheetId=self.sheet_id,
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            
            if not values:
                logger.warning("No se encontraron datos en el rango especificado")
                return pd.DataFrame()
            
            # Convertir a DataFrame
            if header:
                df = pd.DataFrame(values[1:], columns=values[0])
            else:
                df = pd.DataFrame(values)
            
            logger.info(f"Datos leídos correctamente: {len(df)} filas")
            return df
            
        except Exception as e:
            logger.error(f"Error leyendo Google Sheets: {e}")
            return pd.DataFrame()
    
    def escribir_datos(self, range_name, values):
        """Escribe datos en Google Sheets"""
        try:
            if not self.service:
                logger.error("Servicio de Google Sheets no disponible")
                return False
            
            body = {
                'values': values
            }
            
            result = self.service.spreadsheets().values().update(
                spreadsheetId=self.sheet_id,
                range=range_name,
                valueInputOption='RAW',
                body=body
            ).execute()
            
            logger.info(f"Datos escritos correctamente: {result.get('updatedCells', 0)} celdas")
            return True
            
        except Exception as e:
            logger.error(f"Error escribiendo en Google Sheets: {e}")
            return False