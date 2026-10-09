"""Diagnóstico seguro de extractores: toma muestras aleatorias de la base."""

import argparse
import csv
import os
import random
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_pipeline.extractors.base_extract import ExtractCanastaBasica


SUPERMERCADOS = ("Carrefour", "Día", "Delimart", "Depot")
SAMPLE_SIZE = int(os.getenv("SAMPLE_PER_SUPER", "1"))
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "files", "diagnostics")


def extraer_campos_resultado(result):
    """Normaliza las variantes conocidas de salida de los extractores."""
    if isinstance(result, dict):
        return result
    if isinstance(result, list):
        return next((item for item in result if isinstance(item, dict)), {})
    return {}


def seleccionar_urls(extractor, supermercado, sample_size):
    links = extractor.read_links_from_db(supermercado)
    if len(links) <= sample_size:
        print(f"[{supermercado}] Hay {len(links)} URLs; se usarán todas.")
        return links

    print(f"[{supermercado}] Seleccionando {sample_size} de {len(links)} URLs aleatorias...")
    return random.sample(links, sample_size)


def probar_supermercado(extractor, supermercado, sample_size):
    urls = seleccionar_urls(extractor, supermercado, sample_size)
    if not urls:
        print(f"[{supermercado}] No hay links activos para probar.")
        return []

    extractor_class = extractor.extractor_classes[supermercado]
    instance = extractor_class()
    rows = []

    print(f"\n=== {supermercado} ({len(urls)} productos) ===")
    for index, item in enumerate(urls, 1):
        url = item["link"]
        started = time.monotonic()
        try:
            raw_result = instance.extraer_producto(url)
            elapsed = time.monotonic() - started
            result = extraer_campos_resultado(raw_result)
            error = result.get("error_type", "")
            nombre = result.get("nombre") or result.get("producto_nombre") or result.get("titulo") or ""
            precio_normal = result.get("precio_normal", "")
            precio_descuento = result.get("precio_descuento", "")
            precio_unidad = result.get("precio_por_unidad", "")
            unidad = result.get("unidad") or result.get("unidad_medida") or ""
            result_type = "" if isinstance(raw_result, (dict, list)) else "RESULTADO_NO_DIC"
            rows.append({
                "supermercado": supermercado,
                "id_link_producto": item.get("id_link_producto", ""),
                "url": url,
                "nombre": nombre,
                "precio_normal": precio_normal,
                "precio_descuento": precio_descuento,
                "precio_por_unidad": precio_unidad,
                "unidad": unidad,
                "error_type": error or result_type,
                "duracion_segundos": round(elapsed, 2),
            })
            precio = precio_normal or precio_descuento or precio_unidad or "-"
            print(f"{index:02d}/ {elapsed:5.1f}s | {error or result_type or 'OK'} | {nombre or '-'} | {precio} | {url}")
        except Exception as exc:
            elapsed = time.monotonic() - started
            print(f"{index:02d}/ {elapsed:5.1f}s | EXCEPCION | {type(exc).__name__}: {exc} | {url}")
            rows.append({
                "supermercado": supermercado,
                "id_link_producto": item.get("id_link_producto", ""),
                "url": url,
                "nombre": "",
                "precio_normal": "",
                "precio_descuento": "",
                "precio_por_unidad": "",
                "unidad": "",
                "error_type": f"EXCEPCION: {type(exc).__name__}: {exc}",
                "duracion_segundos": round(elapsed, 2),
            })

    try:
        if hasattr(instance, "cleanup_driver"):
            instance.cleanup_driver()
        elif hasattr(instance, "driver") and instance.driver:
            instance.driver.quit()
    except Exception as exc:
        print(f"[{supermercado}] Aviso: error cerrando el navegador: {exc}")
    return rows


def main():
    parser = argparse.ArgumentParser(description="Prueba extractores de supermercados con una muestra pequeña.")
    parser.add_argument("supermercado", nargs="?", choices=SUPERMERCADOS)
    parser.add_argument("--sample-size", type=int, default=SAMPLE_SIZE,
                        help="Links aleatorios por supermercado (predeterminado: 1)")
    args = parser.parse_args()

    if args.sample_size < 1:
        parser.error("--sample-size debe ser al menos 1")

    print(f"Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Muestras por supermercado: {args.sample_size}")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    extractor = ExtractCanastaBasica(enable_parallel=False, max_workers=1)
    all_rows = []
    try:
        supermercados = [args.supermercado] if args.supermercado else list(SUPERMERCADOS)
        for supermercado in supermercados:
            all_rows.extend(probar_supermercado(extractor, supermercado, args.sample_size))
    finally:
        if hasattr(extractor, "db") and extractor.db:
            extractor.db.close_connections()

    output_file = os.path.join(OUTPUT_DIR, f"MUESTRA_EXTRACCION_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    fieldnames = ["supermercado", "id_link_producto", "url", "nombre", "precio_normal",
                  "precio_descuento", "precio_por_unidad", "unidad", "error_type", "duracion_segundos"]
    with open(output_file, "w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"Resultados guardados en: {output_file} ({len(all_rows)} registros)")
    print(f"Fin: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
