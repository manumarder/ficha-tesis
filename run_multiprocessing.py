# run_multiprocessing.py
import sys
import os
import time
import random
import pandas as pd
import logging
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed

# Configurar path interno para que encuentre los módulos de data_pipeline
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data_pipeline'))

from utils.optimization import cleanup_environment, set_parallel_mode
from utils.logger import setup_logger
from extractors.base_extract import ExtractCanastaBasica
from transformers.transform import TransformCanastaBasica
from transformers.validate import ValidateCanastaBasica
from loaders.load import LoadCanastaBasica
from utils.report import ReportCanastaBasica
from dotenv import load_dotenv

def extraer_chunk_aislado(chunk_links, chunk_id):
    """
    Función MAP (Worker): Recibe un 'chunk' (lote mezclado) de links.
    Procesa secuencialmente, evitando sobrecargar un solo supermercado.
    """
    load_dotenv()
    setup_logger(f"worker_chunk_{chunk_id}")
    logger = logging.getLogger(f"Worker-Chunk-{chunk_id}")
    
    set_parallel_mode(True) 
    
    # Staggering aleatorio inicial
    delay = random.uniform(1, 5)
    logger.info(f"⏳ Chunk {chunk_id} - Esperando {delay:.2f}s antes de iniciar...")
    time.sleep(delay)
    
    extractor = ExtractCanastaBasica(enable_parallel=False, max_workers=1)
    
    logger.info(f"📦 Chunk {chunk_id} - Iniciando extracción de {len(chunk_links)} links mezclados...")
    df_raw = extractor.extract(chunk_links)
    
    if hasattr(extractor, 'db') and extractor.db:
        extractor.db.close_connections()
        
    return df_raw, chunk_id

def lanzar_pipeline_consolidado():
    """
    Función REDUCE (Master): Orquesta los workers, unifica los DataFrames 
    y hace 1 sola inserción, 1 solo backup y 1 solo reporte.
    """
    load_dotenv()
    setup_logger("master_orquestador")
    logger = logging.getLogger("Orquestador")
    
    inicio = datetime.now()
    start_time = time.time()
    print("======================================================================")
    logger.info("🚀 FICHÁ DATAOPS - INICIANDO MULTIPROCESSING SHARDING (CHUNK MIXTO)")
    logger.info("=== INICIO ETL CONSOLIDADO - %s ===", inicio.strftime("%Y-%m-%d %H:%M:%S"))
    print("======================================================================")
    
    logger.info("🧹 Limpiando procesos huérfanos residuales antes de iniciar...")
    cleanup_environment(force=True)
    
    # 1. LEER TODOS LOS LINKS DESDE EL ORQUESTADOR MÁSTER
    logger.info("📥 Obteniendo universo total de links activos...")
    extractor_master = ExtractCanastaBasica(enable_parallel=False, max_workers=1)
    todos_los_links = extractor_master.read_links_from_db(supermercado_filtro=None)
    
    if hasattr(extractor_master, 'db') and extractor_master.db:
        extractor_master.db.close_connections()
        
    if not todos_los_links:
        logger.error("🚨 No hay links en la base de datos. Abortando.")
        return
        
    # --- NUEVA LÓGICA: MODO REINTENTO DE FALLIDOS ---
    retry_failed = os.getenv("RETRY_FAILED", "false").lower() == "true"
    if retry_failed:
        logger.info("♻️ Modo RETRY_FAILED activado. Buscando el último reporte de fallos...")
        files_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data_pipeline', 'files')
        links_fallidos_dir = os.path.join(files_dir, 'links_fallidos')
        
        if os.path.exists(links_fallidos_dir):
            # Encontrar el archivo CSV más reciente
            archivos_csv = [os.path.join(links_fallidos_dir, f) for f in os.listdir(links_fallidos_dir) if f.startswith('LINKS_FALLIDOS_') and f.endswith('.csv')]
            if archivos_csv:
                ultimo_csv = max(archivos_csv, key=os.path.getmtime)
                logger.info(f"📄 Leyendo URLs fallidas desde: {os.path.basename(ultimo_csv)}")
                try:
                    df_fallidos = pd.read_csv(ultimo_csv)
                    if 'url' in df_fallidos.columns:
                        urls_fallidas = set(df_fallidos['url'].dropna().tolist())
                        
                        # Filtrar `todos_los_links` guardando solo los que están en el CSV
                        todos_los_links = [item for item in todos_los_links if item['link'] in urls_fallidas]
                        logger.info(f"🎯 Links filtrados: {len(todos_los_links)} a reintentar de {len(urls_fallidas)} en el CSV.")
                    else:
                        logger.warning("⚠️ El CSV no tiene la columna 'url'. Se procesará todo el universo.")
                except Exception as e:
                    logger.error(f"❌ Error leyendo el CSV de fallidos: {e}. Se procesará todo el universo.")
            else:
                logger.warning("⚠️ No se encontraron archivos de links fallidos. Se procesará todo el universo.")
                
        if not todos_los_links:
            logger.error("🚨 No quedaron links para procesar después de filtrar. Abortando.")
            return
    
    sample_size = os.getenv("EXTRACTION_SAMPLE_SIZE", "50")
    try:
        sample_size = int(sample_size)
    except ValueError:
        sample_size = 0
        
    if sample_size > 0 and sample_size < len(todos_los_links):
        todos_los_links = random.sample(todos_los_links, sample_size)
        logger.info(f"📦 Procesando MUESTRA DE PRUEBA: {sample_size} links.")
    else:
        logger.info(f"📦 Procesando UNIVERSO COMPLETO: {len(todos_los_links)} links.")
        
    # 2. SHUFFLE Y CHUNKING (LA MAGIA ANTI-BLOQUEO Y BALANCEO DE CARGA)
    random.shuffle(todos_los_links)
    
    # Particionamos en lotes de 50 links.
    CHUNK_SIZE = 50
    chunks = [todos_los_links[i:i + CHUNK_SIZE] for i in range(0, len(todos_los_links), CHUNK_SIZE)]
    
    logger.info(f"🧩 Universo dividido en {len(chunks)} Chunks de hasta {CHUNK_SIZE} links.")
    
    dataframes_crudos = []
    
    # ---------------------------------------------------------
    # FASE 1: MAP (Extracción Paralela y Aislada)
    # ---------------------------------------------------------
    logger.info("\n" + "="*50)
    logger.info("🛠️ FASE 1: EXTRACCIÓN (WORKERS)")
    logger.info("="*50)
    
    # Lanzar a los 4 núcleos procesadores de forma balanceada
    with ProcessPoolExecutor(max_workers=4) as executor:
        futuros = {
            executor.submit(extraer_chunk_aislado, chunk, i): i 
            for i, chunk in enumerate(chunks)
        }
        
        for futuro in as_completed(futuros):
            chunk_id = futuros[futuro]
            try:
                df_resultado, cid = futuro.result(timeout=3600) # Timeout 1 hora por chunk
                if not df_resultado.empty:
                    dataframes_crudos.append(df_resultado)
                    logger.info(f"✅ Chunk {cid} completado: {len(df_resultado)} registros.")
                else:
                    logger.warning(f"⚠️ Chunk {cid} devolvió 0 registros.")
            except Exception as e:
                logger.error(f"❌ Error crítico en el Chunk {chunk_id}: {e}")
    
    if not dataframes_crudos:
        logger.error("🚨 No se extrajeron datos de ningún supermercado. Abortando ETL.")
        return
        
    # Unificar todos los dataframes en uno solo masivo
    df_raw_consolidado = pd.concat(dataframes_crudos, ignore_index=True)
    logger.info(f"\n📊 [CONSOLIDACIÓN] Se unificaron {len(df_raw_consolidado)} registros crudos en total.")
    
    # ---------------------------------------------------------
    # FASE 2: REDUCE (Reportes, Transformación, Validación y Carga)
    # ---------------------------------------------------------
    logger.info("\n" + "="*50)
    logger.info("🛠️ FASE 2: CONSOLIDACIÓN Y CARGA (MASTER)")
    logger.info("="*50)

    files_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data_pipeline', 'files')
    links_fallidos_dir = os.path.join(files_dir, 'links_fallidos')
    backup_raw_dir = os.path.join(files_dir, 'backup_raw')

    os.makedirs(links_fallidos_dir, exist_ok=True)
    os.makedirs(backup_raw_dir, exist_ok=True)
    
    # 1 SOLO REPORTE DE FALLAS GLOBAL
    try:
        reporter = ReportCanastaBasica(links_fallidos_dir)
        report_file = reporter.generate_broken_links_report(df_raw_consolidado)
        if report_file:
            logger.warning(f"⚠️ Se detectaron links con problemas. 1 SOLO Reporte global generado en: {report_file}")
        reporter.clean_old_reports(keep_last=21)
    except Exception as e:
        logger.error(f"Error generando reporte global: {e}")
        
    # 1 SOLO BACKUP GLOBAL
    backup_file = os.path.join(backup_raw_dir, f'BACKUP_RAW_GLOBAL_{datetime.now().strftime("%Y%m%d_%H%M")}.csv')
    try:
        df_raw_consolidado.to_csv(backup_file, index=False)
        logger.info(f"💾 BACKUP GLOBAL guardado: {backup_file}")
    except Exception as e:
        logger.warning(f"No se pudo crear backup global: {e}")

    # TRANSFORM
    logger.info("🔄 [TRANSFORM] Normalizando datos unificados...")
    df_transformado = TransformCanastaBasica().transform(df_raw_consolidado)
    if df_transformado.empty:
        logger.error("🚨 DataFrame vacío tras transformación.")
        return

    # VALIDATE
    logger.info("✅ [VALIDATE] Validando datos unificados...")
    ValidateCanastaBasica().validate(df_transformado)

    # LOAD (1 Sola Inserción Masiva, 1 Solo ID Extracción)
    logger.info("☁️ [LOAD] Inyectando datos globales a Supabase Cloud...")
    loader = LoadCanastaBasica()
    try:
        exito = loader.load(df_transformado)
        if exito:
            logger.info("🎉 === PROCESO ETL GLOBAL COMPLETADO EXITOSAMENTE ===")
        else:
            logger.error("💥 === EL PROCESO ETL FINALIZÓ CON ERRORES EN LA CARGA ===")
    finally:
        if hasattr(loader, 'db') and loader.db:
            loader.db.close_connections()

    end_time = time.time()
    print("======================================================================")
    logger.info(f"⏱️ ¡PROCESAMIENTO MAP-REDUCE FINALIZADO EN {end_time - start_time:.2f} SEGUNDOS!")
    print("======================================================================")

if __name__ == "__main__":
    lanzar_pipeline_consolidado()