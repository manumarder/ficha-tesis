import os
import glob
import random
import argparse
from datetime import datetime
import pandas as pd
import logging

# IMPORTANTE: Reemplaza esta importación con el nombre real de tu extractor de Depot
from extractors.depot_extractor import DepotExtractor

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

base_dir = os.path.dirname(os.path.abspath(__file__))
FAILED_DIR = os.path.join(base_dir, 'files', 'links_fallidos')


def get_latest_failed_file(directory: str) -> str:
    files = sorted(glob.glob(os.path.join(directory, 'LINKS_FALLIDOS_*.csv')), reverse=True)
    return files[0] if files else None


def load_failed_links(csv_path: str, supermarket: str = 'Depot') -> pd.DataFrame:
    df = pd.read_csv(csv_path, on_bad_lines='skip')
    
    if 'url' not in df.columns:
        raise ValueError('El CSV no tiene la columna esperada: url')
        
    df = df.dropna(subset=['url'])
    df['url'] = df['url'].astype(str)
    
    # ESTRATEGIA DEFENSIVA: Si la columna supermercado falló o es NaN,
    # deducimos el origen analizando el dominio de la URL de forma segura.
    if 'supermercado' in df.columns:
        df['supermercado'] = df['supermercado'].fillna('').astype(str)
        filtro_super = (
            df['supermercado'].str.contains(supermarket, case=False, na=False) |
            df['url'].str.contains('depotexpress', case=False) |
            df['url'].str.contains('depot', case=False)
        )
    else:
        filtro_super = df['url'].str.contains('depotexpress', case=False) | df['url'].str.contains('depot', case=False)
        
    df_filtrado = df[filtro_super]
    return df_filtrado


def sample_urls(df: pd.DataFrame, sample_size: int) -> list[str]:
    urls = df['url'].unique().tolist()
    if sample_size <= 0 or sample_size >= len(urls):
        return urls
    return random.sample(urls, sample_size)


def test_urls(urls: list[str], output_dir: str) -> pd.DataFrame:
    # Instanciamos el extractor de Depot
    extractor = DepotExtractor()
    extractor.setup_driver()
    results = []

    for index, url in enumerate(urls, 1):
        url = url.strip()
        logger.info(f'[{index}/{len(urls)}] Probando URL en Depot: {url}')
        
        try:
            result = extractor.extraer_producto(url)
            
            # Determinar éxito de la extracción lógica
            ok = 'error_type' not in result and ('nombre' in result or 'titulo' in result)
            error_msg = result.get('error_type', '')
            
            results.append({
                'url': url,
                'success': ok,
                'error_type': error_msg,
                'precio_descuento': result.get('precio_descuento', '0'),
                'precio_normal': result.get('precio_normal', '0'),
                'unidad': result.get('unidad', ''),
                'titulo': result.get('titulo', result.get('nombre', '')),
                'raw_nombre': result.get('nombre', ''),
            })
        except Exception as e:
            logger.error(f'💥 EXCEPCIÓN CRÍTICA NO CAPTURADA en el driver para la URL: {url}. Error: {e}')
            results.append({
                'url': url,
                'success': False,
                'error_type': f'CRASH_DRIVER: {str(e)[:50]}',
                'precio_descuento': '0',
                'precio_normal': '0',
                'unidad': '',
                'titulo': 'ERROR',
                'raw_nombre': '',
            })

    df_results = pd.DataFrame(results)
    output_file = os.path.join(output_dir, f'RETEST_DEPOT_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
    df_results.to_csv(output_file, index=False)
    
    logger.info(f'🏁 Pruebas finalizadas. Resultados guardados en: {output_file}')
    logger.info(f'\n{df_results.to_string()}')

    extractor.cleanup_driver()
    return df_results


def main():
    parser = argparse.ArgumentParser(description='Reprobar links de Depot Express con volcado de excepciones.')
    parser.add_argument('--urls', nargs='+', type=str, default=None, 
                        help='URLs específicas a probar (separadas por espacio)')
    parser.add_argument('--source', type=str, default=None, 
                        help='CSV de links fallidos a usar')
    parser.add_argument('--sample-size', type=int, default=10, 
                        help='Cantidad de links a muestrear (por defecto 10)')
    parser.add_argument('--output-dir', type=str, 
                        default=os.path.join(base_dir, 'files', 'files', 'diagnostics'), 
                        help='Carpeta de salida para resultados')
    parser.add_argument('--latest', action='store_true', 
                        help='Usar el CSV más reciente de links fallidos')

    args = parser.parse_args()
    
    # Corregimos la ruta del directorio de salida para que respete tu estructura files/diagnostics
    output_path = os.path.join(base_dir, 'files', 'diagnostics')
    os.makedirs(output_path, exist_ok=True)

    # Caso A: Si pasás las URLs directo por consola
    if args.urls:
        # Si las pasas separadas por comas en Windows, las separamos limpiamente
        lista_urls = []
        for u in args.urls:
            lista_urls.extend([url.strip() for url in u.split(',') if url.strip()])
            
        logger.info(f'Probando {len(lista_urls)} URLs específicas de Depot pasadas por argumento.')
        test_urls(lista_urls, output_path)
        return

    # Caso B: Leer del CSV masivo de fallas
    source_file = args.source
    if args.latest or not source_file:
        source_file = get_latest_failed_file(FAILED_DIR)

    if not source_file or not os.path.exists(source_file):
        raise FileNotFoundError('No se encontró un CSV válido de links fallidos en ' + FAILED_DIR)

    df_failed = load_failed_links(source_file)
    if df_failed.empty:
        raise ValueError('No se detectaron enlaces de Depot en el reporte de fallas: ' + source_file)

    urls = sample_urls(df_failed, args.sample_size)
    logger.info(f'Se tomaron {len(urls)} links aleatorios de Depot desde: {source_file}')

    test_urls(urls, output_path)


if __name__ == '__main__':
    main()