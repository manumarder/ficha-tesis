"""
Módulo de Transformación
Responsabilidad: Normalizar datos para coincidir con la tabla precios_productos
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

        # 1. Renombrar columnas para coincidir con SQL
        # SQL: nombre_producto, unidad_medida
        # Scraper: nombre, unidad
        rename_map = {
            'nombre': 'nombre_producto',
            'unidad': 'unidad_medida'
        }
        df = df.rename(columns=rename_map)

        # Eliminar columnas duplicadas si existen (esto causaba el error 'DataFrame object has no attribute str')
        if df.columns.duplicated().any():
            logger.warning("[TRANSFORM] Se detectaron columnas duplicadas. Eliminando duplicados...")
            df = df.loc[:, ~df.columns.duplicated()]

        # 2. Asegurar columnas requeridas por la tabla SQL
        required_cols = [
            'id_link_producto', 'nombre_producto', 'precio_normal', 
            'precio_descuento', 'precio_por_unidad', 'unidad_medida', 'peso'
        ]
        
        for col in required_cols:
            if col not in df.columns:
                df[col] = None

        # 3. Limpieza de Precios (Asegurar que sean float para DECIMAL SQL)
        price_cols = ['precio_normal', 'precio_descuento', 'precio_por_unidad', 'peso']
        
        for col in price_cols:
            # Forzar conversión a numérico, convirtiendo errores a NaN
            df[col] = pd.to_numeric(df[col], errors='coerce')
            # Reemplazar NaN con 0.0 o NULL según prefieras (MySQL DECIMAL acepta NULL si está configurado, o 0.00)
            df[col] = df[col].fillna(0.0)

        # 4. Truncar textos largos (por seguridad)
        # Convertimos a string primero para evitar errores si viene como objeto
        if 'nombre_producto' in df.columns:
            df['nombre_producto'] = df['nombre_producto'].astype(str).str.slice(0, 255)
            
        if 'unidad_medida' in df.columns:
            df['unidad_medida'] = df['unidad_medida'].astype(str).str.slice(0, 20)
            
        # 5. Filtrar solo columnas finales
        final_df = df[required_cols].copy()
        
        logger.info(f"[TRANSFORM] Datos listos para carga: {len(final_df)} filas.")
        return final_df