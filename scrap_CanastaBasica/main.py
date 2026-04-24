"""
MAIN - Orquestador ETL para CanastaBasica
Responsabilidad: Coordinar Extract (DB) → Transform → Validate → Load (DB)
"""
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
import random
from etl.extract import ExtractCanastaBasica
from etl.transform import TransformCanastaBasica
from etl.load import LoadCanastaBasica
from etl.validate import ValidateCanastaBasica
from etl.report import ReportCanastaBasica
from utils.logger import setup_logger
from utils.optimization import cleanup_environment


def main():
    setup_logger("canasta_basica_scraper")
    logger = logging.getLogger(__name__)

    # Limpieza inicial de procesos huérfanos
    cleanup_environment(force=True)

    load_dotenv()
    inicio = datetime.now()
    logger.info("=" * 80)
    logger.info("=== INICIO ETL CANASTA BÁSICA - %s ===", inicio.strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 80)

    SYNC_MODE = False

    extractor = None
    loader    = None

    try:

        # EXTRACT
        logger.info("1. [EXTRACT] Inicializando extractor...")
        extractor = ExtractCanastaBasica(enable_parallel=True, max_workers=2)  # 2 workers para no saturar RAM del servidor
        links_list = extractor.read_links_from_db()

        if not links_list:
            logger.error("[ERROR] No se encontraron links activos en la base de datos.")
            return

        df_raw = extractor.extract(links_list)
        if df_raw.empty:
            logger.error("[ERROR] La extracción no generó datos. Abortando.")
            return
        logger.info("[OK] Extracción finalizada: %d filas.", len(df_raw))

        # --- GENERAR REPORTE DE LINKS FALLIDOS ---
        try:
            report_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'files')
            reporter = ReportCanastaBasica(report_dir)
            report_file = reporter.generate_broken_links_report(df_raw)
            if report_file:
                logger.warning(f"!!! ATENCIÓN: Se detectaron links con problemas. Reporte generado en: {report_file}")
            reporter.clean_old_reports()
        except Exception as e:
            logger.error(f"Error generando reporte de links fallidos: {e}")

        # Backup
        backup_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'files',
            f'BACKUP_RAW_{datetime.now().strftime("%Y%m%d_%H%M")}.csv'
        )
        os.makedirs(os.path.dirname(backup_file), exist_ok=True)
        try:
            df_raw.to_csv(backup_file, index=False)
            logger.info("BACKUP guardado: %s", backup_file)
        except Exception as e:
            logger.warning("No se pudo crear backup: %s", e)

        # Limpieza de backups: conservar solo los últimos 3
        try:
            archivos_backup = sorted(
                [f for f in os.listdir(os.path.dirname(backup_file)) if f.startswith('BACKUP_RAW_')],
                reverse=True
            )
            for viejo in archivos_backup[3:]:
                os.remove(os.path.join(os.path.dirname(backup_file), viejo))
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

        # --- NUEVA SECCIÓN DE SINCRONIZACIÓN ---
        if SYNC_MODE:
            logger.info(">>> MODO SINCRONIZACIÓN ACTIVADO <<<")
            extractor = LoadCanastaBasica()
            # Suponiendo que metiste la función en el extractor
            registros = extractor.sync_mysql_to_postgres()
            logger.info(f"Proceso de sincronización finalizado. Registros: {registros}")
            return # Terminamos aquí para no correr el scraper normal
        # ---------------------------------------

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
            if hasattr(loader, 'db_v1') and loader.db_v1:
                loader.db_v1.close_connections()
            if hasattr(loader, 'db_v2') and loader.db_v2:
                loader.db_v2.close_connections()
        duracion = (datetime.now() - inicio).total_seconds()
        logger.info("=== FIN EJECUCIÓN - Duración total: %.2f segundos ===", duracion)
        logger.info("=" * 80)


if __name__ == "__main__":
    main()