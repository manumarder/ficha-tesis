"""
Módulo de Transformación
Responsabilidad: Normalizar datos para coincidir con la nueva tabla precios_productos (PostgreSQL)
"""
import pandas as pd
import logging
import numpy as np

logger = logging.getLogger(__name__)

class TransformCanastaBasica:
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        logger.info("[TRANSFORM] Iniciando transformación...")
        
        if df.empty:
            return pd.DataFrame()

        # Eliminar columnas duplicadas si existen
        if df.columns.duplicated().any():
            logger.warning("[TRANSFORM] Se detectaron columnas duplicadas. Eliminando duplicados...")
            df = df.loc[:, ~df.columns.duplicated()]

        # 1. Renombrar columnas para coincidir con el nuevo esquema
        rename_map = {
            'id_link_producto': 'id_link'
        }
        df = df.rename(columns=rename_map)

        # 2. Asegurar columnas requeridas por la tabla SQL precios_productos
        required_cols = ['id_link', 'precio_normal', 'precio_descuento']
        
        for col in required_cols:
            if col not in df.columns:
                df[col] = np.nan

        # 3. Limpieza de Precios (Asegurar que sean numéricos)
        price_cols = ['precio_normal', 'precio_descuento']
        
        for col in price_cols:
            # Forzar conversión a numérico, convirtiendo errores a NaN
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # Convertir NaN a None para que SQLAlchemy/Pandas lo inserte como NULL en PostgreSQL
        df['precio_descuento'] = df['precio_descuento'].replace({np.nan: None})
        # Si precio_descuento es 0, también lo hacemos None (sin descuento)
        df.loc[df['precio_descuento'] == 0, 'precio_descuento'] = None
        
        # Opcional: Eliminar filas donde no hay id_link o precio_normal es inválido
        df = df.dropna(subset=['id_link', 'precio_normal'])

        # 4. Filtrar solo las columnas finales que van a la DB
        final_df = df[required_cols].copy()
        
        logger.info(f"[TRANSFORM] Datos listos para carga: {len(final_df)} filas.")
        return final_df