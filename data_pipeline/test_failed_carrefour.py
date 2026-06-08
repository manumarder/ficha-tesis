import os
import glob
import random
import argparse
from datetime import datetime
import pandas as pd
import logging

from extractors.carrefour_extractor import CarrefourExtractor

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

FAILED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'files', 'links_fallidos')


def get_latest_failed_file(directory: str) -> str:
    files = sorted(glob.glob(os.path.join(directory, 'LINKS_FALLIDOS_*.csv')), reverse=True)
    return files[0] if files else None


def load_failed_links(csv_path: str, supermarket: str = 'Carrefour') -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    if 'supermercado' not in df.columns or 'url' not in df.columns:
        raise ValueError('El CSV no tiene las columnas esperadas: supermercado, url')

    df = df[df['supermercado'].astype(str).str.contains(supermarket, case=False, na=False)]
    return df.dropna(subset=['url'])


def sample_urls(df: pd.DataFrame, sample_size: int) -> list[str]:
    urls = df['url'].astype(str).unique().tolist()
    if sample_size <= 0 or sample_size >= len(urls):
        return urls
    return random.sample(urls, sample_size)


def test_urls(urls: list[str], output_dir: str) -> pd.DataFrame:
    extractor = CarrefourExtractor()
    results = []

    for index, url in enumerate(urls, 1):
        logger.info(f'[{index}/{len(urls)}] Probando URL: {url}')
        result = extractor.extraer_producto(url)
        
        # Determinar éxito: no hay error y el producto fue extraído correctamente
        ok = 'error_type' not in result and 'nombre' in result
        error_msg = result.get('error_type', '')

        results.append({
            'url': url,
            'success': ok,
            'error_type': error_msg,
            'precio_descuento': result.get('precio_descuento', '0'),
            'precio_normal': result.get('precio_normal', '0'),
            'unidad': result.get('unidad', ''),
            'titulo': result.get('titulo', ''),
            'raw_nombre': result.get('nombre', ''),
        })

    df_results = pd.DataFrame(results)
    output_file = os.path.join(output_dir, f'RETEST_CARREFOUR_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
    df_results.to_csv(output_file, index=False)
    logger.info(f'Resultados guardados en: {output_file}')
    logger.info(f'\n{df_results.to_string()}')
    return df_results


def main():
    parser = argparse.ArgumentParser(description='Reprobar links de Carrefour con pruebas específicas.')
    parser.add_argument('--urls', nargs='+', type=str, default=None, 
                        help='URLs específicas a probar (separadas por espacio)')
    parser.add_argument('--source', type=str, default=None, 
                        help='CSV de links fallidos a usar')
    parser.add_argument('--sample-size', type=int, default=50, 
                        help='Cantidad de links a muestrear (solo si no se usan --urls)')
    parser.add_argument('--output-dir', type=str, 
                        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'files', 'diagnostics'), 
                        help='Carpeta de salida para resultados')
    parser.add_argument('--latest', action='store_true', 
                        help='Usar el CSV más reciente de links fallidos')

    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    # Si se proporcionan URLs específicas, usarlas directamente
    if args.urls:
        logger.info(f'Probando {len(args.urls)} URLs específicas')
        test_urls(args.urls, args.output_dir)
        return

    # Si no, usar el CSV de links fallidos
    source_file = args.source
    if args.latest or not source_file:
        source_file = get_latest_failed_file(FAILED_DIR)

    if not source_file or not os.path.exists(source_file):
        raise FileNotFoundError('No se encontró un CSV válido de links fallidos en ' + FAILED_DIR)

    df_failed = load_failed_links(source_file)
    if df_failed.empty:
        raise ValueError('No se encontraron links de Carrefour en el CSV de links fallidos.')

    urls = sample_urls(df_failed, args.sample_size)
    logger.info(f'Se van a evaluar {len(urls)} links de Carrefour extraídos de: {source_file}')

    test_urls(urls, args.output_dir)


if __name__ == '__main__':
    main()
