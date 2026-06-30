#data_pipeline\pipeline.py

"""
MAIN - Orquestador ETL para CanastaBasica
Responsabilidad: Coordinar Extract (DB) → Transform → Validate → Load (DB)
"""
import os
import sys
import logging
from datetime import datetime

# Añadir el directorio raíz al path para importar config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
import random
from extractors.base_extract import ExtractCanastaBasica
from transformers.transform import TransformCanastaBasica
from loaders.load import LoadCanastaBasica
from transformers.validate import ValidateCanastaBasica
from utils.report import ReportCanastaBasica
from utils.logger import setup_logger
from utils.optimization import cleanup_environment


def main():
    # --- NUEVA LÓGICA DE PARÁMETROS POR CONSOLA (FASE 20) ---
    # Capturamos el filtro primero para aislar los logs y archivos
    supermercado_filtro = sys.argv[1] if len(sys.argv) > 1 else None

    # Cada proceso tiene su propio archivo de log (ej: canasta_basica_carrefour.log)
    log_name = f"canasta_basica_{supermercado_filtro.lower()}" if supermercado_filtro else "canasta_basica_global"
    setup_logger(log_name)
    logger = logging.getLogger(__name__)

    # La limpieza se delegó al run_multiprocessing.py para evitar matarse entre procesos.
    load_dotenv()
    inicio = datetime.now()

    logger.info("=" * 80)
    logger.info("=== INICIO ETL FICHÁ [%s] - %s ===", 
                supermercado_filtro.upper() if supermercado_filtro else "GLOBAL", 
                inicio.strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 80)

    extractor = None
    loader    = None

    try:
        # EXTRACT
        logger.info("1. [EXTRACT] Inicializando extractor...")
        # Por proceso asilado, desactivamos multithreading interno
        extractor = ExtractCanastaBasica(enable_parallel=False, max_workers=1)
        links_list = extractor.read_links_from_db(supermercado_filtro=supermercado_filtro)

        if not links_list:
            logger.error(f"[ERROR] No se encontraron links activos para: {supermercado_filtro}")
            return

        # Modo configurable: por defecto usa 50 links para pruebas, pero puedes forzar todos con EXTRACTION_SAMPLE_SIZE=0
        sample_size = os.getenv("EXTRACTION_SAMPLE_SIZE", "50")
        try:
            sample_size = int(sample_size)
        except ValueError:
            sample_size = 50

        if sample_size > 0 and sample_size < len(links_list):
            links_list = random.sample(links_list, sample_size)
            logger.info(f"Se extraerán {len(links_list)} links aleatorios (muestra de prueba).")
        else:
            logger.info(f"Se extraerán todos los {len(links_list)} links activos.")

        df_raw = extractor.extract(links_list)
        if df_raw.empty:
            logger.error("[ERROR] La extracción no generó datos. Abortando.")
            return
        logger.info("[OK] Extracción finalizada: %d filas.", len(df_raw))

        # --- GENERAR REPORTE DE LINKS FALLIDOS ---
        files_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'files')
        links_fallidos_dir = os.path.join(files_dir, 'links_fallidos')
        backup_raw_dir = os.path.join(files_dir, 'backup_raw')

        os.makedirs(files_dir, exist_ok=True)
        os.makedirs(links_fallidos_dir, exist_ok=True)
        os.makedirs(backup_raw_dir, exist_ok=True)

        try:
            reporter = ReportCanastaBasica(links_fallidos_dir)
            report_file = reporter.generate_broken_links_report(df_raw)
            if report_file:
                logger.warning(f"!!! ATENCIÓN: Se detectaron links con problemas. Reporte generado en: {report_file}")
            reporter.clean_old_reports(keep_last=21)
        except Exception as e:
            logger.error(f"Error generando reporte de links fallidos: {e}")

        # Backup en subcarpeta específica AÑADIENDO EL NOMBRE DEL SUPER PARA EVITAR COLISIONES
        prefijo_super = supermercado_filtro.upper() if supermercado_filtro else "GLOBAL"
        backup_file = os.path.join(
            backup_raw_dir,
            f'BACKUP_RAW_{prefijo_super}_{datetime.now().strftime("%Y%m%d_%H%M")}.csv'
        )
        try:
            df_raw.to_csv(backup_file, index=False)
            logger.info("BACKUP guardado: %s", backup_file)
        except Exception as e:
            logger.warning("No se pudo crear backup: %s", e)

        # Limpieza de backups: conservar solo los últimos 21 archivos
        try:
            archivos_backup = sorted(
                [f for f in os.listdir(backup_raw_dir) if f.startswith('BACKUP_RAW_')],
                reverse=True
            )
            for viejo in archivos_backup[21:]:
                os.remove(os.path.join(backup_raw_dir, viejo))
                logger.info("Backup antiguo eliminado: %s", viejo)
        except Exception as e:
            logger.warning("No se pudo limpiar backups: %s", e)

        # TRANSFORM
        logger.info("2. [TRANSFORM] Normalizando datos...")
        df = TransformCanastaBasica().transform(df_raw)
        if df.empty:
            logger.error("[ERROR] DataFrame vacío tras transformación.")
            return

        # VALIDATE
        logger.info("3. [VALIDATE] Validando datos...")
        ValidateCanastaBasica().validate(df)

        # LOAD
        logger.info("4. [LOAD] Cargando a base de datos...")
        loader = LoadCanastaBasica()
        exito = loader.load(df)



        if exito:
            logger.info("=== Proceso ETL completado EXITOSAMENTE ===")
        else:
            logger.error("=== El proceso ETL finalizó con ERRORES en la etapa de carga ===")

    except Exception as e:
        logger.error("[ERROR CRÍTICO] %s", e, exc_info=True)
        raise
    finally:
        if extractor and hasattr(extractor, 'db') and extractor.db:
            extractor.db.close_connections()
        if loader:
            if hasattr(loader, 'db') and loader.db:
                loader.db.close_connections()
        duracion = (datetime.now() - inicio).total_seconds()
        logger.info("=== FIN EJECUCIÓN - Duración total: %.2f segundos ===", duracion)
        logger.info("=" * 80)


if __name__ == "__main__":
    main()