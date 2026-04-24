"""
Carga en BD a partir de un BACKUP_RAW_*.csv ya generado (sin volver a scrapear).

Uso:
  cd automaticos/scrap_CanastaBasica
  python cargar_desde_backup.py
  python cargar_desde_backup.py --csv files/BACKUP_RAW_20260420_1951.csv
  python cargar_desde_backup.py --skip-validate   # solo si VALIDATE bloquea por umbral

Requiere .env con credenciales igual que main.py.
"""
from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from etl.transform import TransformCanastaBasica
from etl.load import LoadCanastaBasica
from etl.validate import ValidateCanastaBasica
from utils.logger import setup_logger


def _latest_backup(files_dir: str) -> str | None:
    candidates = [
        f for f in os.listdir(files_dir)
        if f.startswith("BACKUP_RAW_") and f.endswith(".csv")
    ]
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return os.path.join(files_dir, candidates[0])


def main() -> None:
    base = os.path.dirname(os.path.abspath(__file__))
    files_dir = os.path.join(base, "files")

    parser = argparse.ArgumentParser(description="Cargar BD desde CSV BACKUP_RAW (sin extract).")
    parser.add_argument(
        "--csv",
        help="Ruta al BACKUP_RAW_*.csv (por defecto: el más reciente en files/)",
        default=None,
    )
    parser.add_argument(
        "--skip-validate",
        action="store_true",
        help="Omite ValidateCanastaBasica (útil si falla el mínimo de precios > 0).",
    )
    args = parser.parse_args()

    setup_logger("canasta_basica_carga_backup")
    import logging

    logger = logging.getLogger(__name__)
    load_dotenv()

    csv_path = args.csv or _latest_backup(files_dir)
    if not csv_path or not os.path.isfile(csv_path):
        logger.error(
            "No encontré CSV. Colocá un BACKUP_RAW_*.csv en %s o pasá --csv explícito.",
            files_dir,
        )
        sys.exit(1)

    logger.info("=== CARGA DESDE BACKUP (sin scraping) ===")
    logger.info("Archivo: %s", csv_path)

    import pandas as pd

    df_raw = pd.read_csv(csv_path)
    if df_raw.empty:
        logger.error("CSV vacío.")
        sys.exit(1)

    logger.info("Filas leídas: %d", len(df_raw))

    df = TransformCanastaBasica().transform(df_raw)
    if df.empty:
        logger.error("[ERROR] DataFrame vacío tras transformación.")
        sys.exit(1)

    if args.skip_validate:
        logger.warning("[WARN] VALIDATE omitido (--skip-validate).")
    else:
        logger.info("[VALIDATE] Validando datos...")
        ValidateCanastaBasica().validate(df)

    logger.info("[LOAD] Cargando a base de datos...")
    loader = LoadCanastaBasica()
    try:
        exito = loader.load(df)
    finally:
        if hasattr(loader, "db_v1") and loader.db_v1:
            loader.db_v1.close_connections()
        if hasattr(loader, "db_v2") and loader.db_v2:
            loader.db_v2.close_connections()

    if exito:
        logger.info("=== Carga desde backup completada OK ===")
    else:
        logger.error("=== Carga terminó con errores (ver logs LOAD) ===")
        sys.exit(1)


if __name__ == "__main__":
    main()
