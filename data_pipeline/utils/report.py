"""
Módulo de Reportes para CanastaBasica
Responsabilidad: Generar informes sobre links fallidos y calidad de extracción.
"""
import pandas as pd
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ReportCanastaBasica:
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_broken_links_report(self, df: pd.DataFrame) -> str:
        """
        Identifica links que fallaron y guarda un reporte CSV + Imprime en Logs.
        """
        if df.empty:
            logger.warning("[REPORT] DataFrame vacío, no se puede generar reporte.")
            return None

        # 1. Identificar fallos
        df_copy = df.copy()
        df_copy['precio_normal_val'] = pd.to_numeric(df_copy.get('precio_normal', 0), errors='coerce').fillna(0)
        
        cond_error = df_copy['error_type'].notna() if 'error_type' in df_copy.columns else False
        cond_no_price = (df_copy['precio_normal_val'] <= 0)
        
        df_broken = df_copy[cond_error | cond_no_price].copy()
        
        if df_broken.empty:
            logger.info("[REPORT] No se detectaron links fallidos.")
            return None

        # --- NUEVO: Log directo a consola para Airflow ---
        self._log_broken_links_to_console(df_broken)

        # 2. Generar nombre de archivo y guardar (como backup en el server)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        report_path = os.path.join(self.output_dir, f"LINKS_FALLIDOS_{timestamp}.csv")
        
        try:
            cols_to_keep = ['url', 'supermercado', 'nombre', 'error_type', 'precio_normal']
            cols_present = [c for c in cols_to_keep if c in df_broken.columns]
            df_broken[cols_present].to_csv(report_path, index=False)
            return report_path
        except Exception as e:
            logger.error(f"[REPORT] Error guardando reporte: {e}")
            return None

    def _log_broken_links_to_console(self, df_broken: pd.DataFrame):
        """Imprime los links fallidos en el log de manera estructurada"""
        logger.info("\n" + "!"*40)
        logger.info("REPORTE DETALLADO DE LINKS FALLIDOS")
        logger.info("!"*40)

        # Agrupar por supermercado para mejor lectura
        supers = df_broken['supermercado'].unique() if 'supermercado' in df_broken.columns else ['General']
        
        for super_name in supers:
            df_super = df_broken[df_broken['supermercado'] == super_name] if 'supermercado' in df_broken.columns else df_broken
            logger.info(f"\n>>> SUPERMERCADO: {super_name} ({len(df_super)} fallos)")
            
            # Mostrar hasta 100 links por super para no romper el log de Airflow si son demasiados
            count = 0
            for _, row in df_super.iterrows():
                url = row.get('url', 'N/A')
                error = row.get('error_type', 'Precio 0.0 o No encontrado')
                nombre = row.get('nombre', 'Sin nombre')
                logger.info(f"  - [{error}] {nombre} -> {url}")
                count += 1
                if count >= 100:
                    logger.info(f"  ... y {len(df_super)-100} links más (ver CSV para lista completa)")
                    break
        
        logger.info("\n" + "!"*40 + "\n")

    def clean_old_reports(self, keep_last: int = 5):
        """Limpia reportes antiguos"""
        try:
            files = sorted(
                [f for f in os.listdir(self.output_dir) if f.startswith('LINKS_FALLIDOS_')],
                reverse=True
            )
            for f in files[keep_last:]:
                os.remove(os.path.join(self.output_dir, f))
        except Exception as e:
            logger.warning(f"[REPORT] No se pudo limpiar reportes antiguos: {e}")
