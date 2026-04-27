import pandas as pd
import logging
from datetime import datetime
from etl.load import LoadCanastaBasica
from utils.logger import setup_logger

def test_dual_load():
    setup_logger("test_dual")
    logger = logging.getLogger(__name__)
    
    logger.info(">>> INICIANDO PRUEBA DE CARGA DUAL (MySQL + Postgres) <<<")
    
    # 1. Registro de prueba con nombres de columnas REALES (según tu DB)
    data = {
        'id_link_producto': 1, 
        'nombre_producto': 'PRODUCTO PRUEBA DUAL SIMULTANEO',
        'precio_normal': 1500.00,    # Antes era precio_lista
        'precio_descuento': 1300.00, # Antes era precio_promo
        'precio_por_unidad': 1300.00,
        'unidad_medida': 'un',
        'peso': 1.0
    }
    
    df_test = pd.DataFrame([data])
    
    try:
        loader = LoadCanastaBasica()
        
        # 2. Ejecutamos el método load oficial
        # Este método primero carga en MySQL, saca el ID, y lo replica en Postgres
        logger.info("Ejecutando loader.load(df)...")
        exito = loader.load(df_test)
        
        if exito:
            logger.info("¡EXITO TOTAL! El registro debería estar en ambas bases con el mismo ID.")
            logger.info("Verificá en DBeaver que ambas tablas de 'extracciones' tengan el mismo nuevo ID.")
        else:
            logger.error("La carga dual falló en alguna de las instancias.")
            
    except Exception as e:
        logger.error(f"Error crítico en el test dual: {e}", exc_info=True)

if __name__ == "__main__":
    test_dual_load()