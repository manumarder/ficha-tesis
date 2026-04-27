"""
Módulo de Carga
Responsabilidad: Gestionar la tabla 'extracciones' e insertar en 'precios_productos' en PostgreSQL
"""
import os
import sys
import pandas as pd
import logging
from sqlalchemy import text
from datetime import datetime
from dotenv import load_dotenv

# Agregar directorio padre (raíz del proyecto)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from data_pipeline.utils.utils_db import ConexionBaseDatos
from config.settings import settings

logger = logging.getLogger(__name__)

class LoadCanastaBasica:
    def __init__(self):
        # Configuración Base Nueva (PostgreSQL) usando settings centralizados
        self.db = ConexionBaseDatos(
            host=settings.db.host,
            user=settings.db.user,
            password=settings.db.password,
            database=settings.db.name,
            port=settings.db.port
        )

    def registrar_inicio_extraccion(self, nombre_log):
        if not self.db.connect_db():
            return None

        try:
            # Nuevo esquema: id (serial), fecha_ejecucion (default), estado, items_procesados, error_log
            query = "INSERT INTO extracciones (estado, items_procesados) VALUES ('procesando', 0) RETURNING id"
            
            with self.db.connection.cursor() as cursor:
                cursor.execute(query)
                id_generado = cursor.fetchone()[0] # El ID viene del RETURNING
                self.db.connection.commit()
                return id_generado
        except Exception as e:
            logger.error(f"[LOAD] Error registrando extracción en {nombre_log}: {e}")
            return None
        finally:
            self.db.close_connections()

    def _ejecutar_carga(self, df, nombre_log):
        """Lógica de carga en PostgreSQL"""
        total_productos = len(df)
        
        id_extraccion = self.registrar_inicio_extraccion(nombre_log)
        
        if not id_extraccion:
            logger.error(f"[LOAD] No se pudo obtener id_extraccion para {nombre_log}")
            return False

        # Preparar DF para esta base
        df_local = df.copy()
        df_local['id_extraccion'] = id_extraccion

        if self.db.connect_db():
            try:
                # Inserción masiva
                success = self.db.insert_append('precios_productos', df_local)
                estado = 'exitoso' if success else 'fallido'
                
                # Actualizar estado e items procesados en la tabla extracciones
                query_update = f"""
                    UPDATE extracciones 
                    SET estado = '{estado}', 
                        items_procesados = {total_productos}
                    WHERE id = {id_extraccion}
                """
                with self.db.connection.cursor() as cursor:
                    cursor.execute(query_update)
                    self.db.connection.commit()

                if success:
                    logger.info(f"[OK] Carga finalizada en {nombre_log}. ID de extracción: {id_extraccion}")
                else:
                    logger.error(
                        f"[ERROR] Inserción rechazada o incompleta en {nombre_log}. "
                        f"ID extracción: {id_extraccion}. Revisar logs de insert_append."
                    )
                return success
            except Exception as e:
                logger.error(f"[ERROR] Carga fallida en {nombre_log}: {e}")
                # Registrar error_log
                query_error = f"UPDATE extracciones SET estado = 'fallido', error_log = %s WHERE id = %s"
                with self.db.connection.cursor() as cursor:
                    cursor.execute(query_error, (str(e), id_extraccion))
                    self.db.connection.commit()
                return False
            finally:
                self.db.close_connections()
        return False

    def load(self, df: pd.DataFrame) -> bool:
        if df.empty:
            logger.warning("[LOAD] DataFrame vacío, nada que cargar.")
            return False

        # --- Filtrado de precios nulos o cero (usamos precio_normal que viene del transformador) ---
        total_inicial = len(df)
        if 'precio_normal' in df.columns:
            df = df[df['precio_normal'] > 0].copy()
            
        logger.info(f"[LOAD] Filtrado: {total_inicial - len(df)} productos eliminados por precio 0 o inválido.")

        if df.empty:
            return False

        # Un registro por id_link por extracción (eliminar duplicados)
        if 'id_link' in df.columns:
            antes = len(df)
            df = df.drop_duplicates(subset=['id_link'], keep='last').copy()
            if len(df) < antes:
                logger.warning(
                    "[LOAD] Eliminadas %d filas duplicadas (mismo id_link); quedan %d.",
                    antes - len(df),
                    len(df),
                )

        # La columna created_at la genera la base de datos automáticamente (DEFAULT CURRENT_TIMESTAMP)
        # por lo que no es necesario enviarla desde Pandas si el insert_append la omite.
        # Tampoco enviamos precio_final porque es GENERATED ALWAYS AS.
        
        logger.info("Iniciando carga en PostgreSQL...")
        
        exito = self._ejecutar_carga(df, "BASE DE DATOS (PostgreSQL)")
        
        return exito