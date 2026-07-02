# Proyecto Canasta Básica - ETL de Precios de Supermercados

## 1. Descripción general
Este proyecto es una tubería ETL para capturar precios de productos de supermercados, almacenar la información en una base de datos PostgreSQL y conservar un histórico de precios y auditorías.

El objetivo principal es extraer datos desde links de productos, transformarlos al esquema de base de datos y cargar registros en las tablas correspondientes para poder analizar ofertas reales, trampa y comportamiento histórico.

---

## 2. Qué está hecho hasta ahora

### 2.1 Flujo principal
- `data_pipeline/pipeline.py`: Orquestador del proceso ETL.
  - Extrae links activos desde la base de datos.
  - Scrapea productos usando extractores específicos por supermercado.
  - Transforma los datos a un formato compatible con la tabla `precios_productos`.
  - Valida la calidad mínima de precios.
  - Carga los resultados en PostgreSQL.

### 2.2 Extractores existentes
- `data_pipeline/extractors/carrefour_extractor.py`
- `data_pipeline/extractors/dia_extractor.py`
- `data_pipeline/extractors/depot_extractor.py`
- `data_pipeline/extractors/delimart_extractor.py`

Cada extractor encapsula la lógica de Selenium para su supermercado.

### 2.3 Transformación y validación
- `data_pipeline/transformers/transform.py`: normaliza columnas y prepara datos para cargar.
- `data_pipeline/transformers/validate.py`: valida que existan precios normales válidos antes de cargar.

### 2.4 Carga de datos
- `data_pipeline/loaders/load.py`: inserta registros en `precios_productos` y guarda el log de ejecución en `extracciones`.
- `data_pipeline/utils/utils_db.py`: conexión y helpers de DB para MySQL/PostgreSQL.

### 2.5 Utilidades comunes
- `data_pipeline/utils/cookie_manager.py`: manejo centralizado de cookies para Selenium.
- `data_pipeline/utils/optimization.py`: optimizaciones de Selenium, caché, paralelismo y limpieza de procesos de Chrome.
- `data_pipeline/utils/logger.py`: configuración de logging.
- `data_pipeline/utils/report.py`: generación de reportes de links fallidos.

### 2.6 Base de datos
- `database/schema/database_schema.sql`: esquema principal con tablas y vista de auditoría.
- `database/init_db.py`: script para crear el esquema en PostgreSQL.
- `database/seed_from_csv.py`: carga datos iniciales desde CSV de `data_pipeline/files`.
- `database/seed_maestros.py`: seeding avanzado con agrupamiento de enlaces y generación de productos maestros.

---

## 3. Estado actual y limpieza aplicada

### 3.1 Archivos mantenidos como parte del flujo principal
- `data_pipeline/pipeline.py`
- `data_pipeline/cargar_desde_backup.py` (fix aplicado)
- `database/init_db.py`
- `database/seed_from_csv.py` (fix de import corregido)
- `database/seed_maestros.py`
- `data_pipeline/scratch_analyze.py` (herramienta exploratoria para análisis de links)

### 3.2 Archivos considerados obsoletos / eliminados
- `test_db.py` → script duplicado/desactualizado.
- `data_pipeline/test_load_postgres.py` → prueba antigua con import `etl` no válido.

---

## 4. Cómo ejecutar el proyecto

### 4.1 Requisitos previos
- Python 3.10+.
- Chrome instalado y `chromedriver` disponible en PATH o en la misma carpeta del proyecto.
- Una base PostgreSQL accesible, local o remota.
- Archivo `.env` con credenciales DB.

### 4.2 Variables necesarias en `.env`
```env
DB_HOST=localhost
DB_PORT=5432
DB_USER=tu_usuario
DB_PASSWORD=tu_contraseña
DB_NAME=tu_base
DB_SSLMODE=prefer
```

Si estás usando Supabase, conviene añadir:
```env
DB_SSLMODE=require
```

También puedes usar la URL completa de conexión:
```env
DATABASE_URL=postgresql://usuario:contraseña@host:5432/base_de_datos
```

### 4.3 Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4.4 Inicializar la base de datos
```bash
python database/init_db.py
```

### 4.5 Cargar datos de ejemplo
```bash
python database/seed_from_csv.py
```

### 4.6 Ejecutar el ETL completo
```bash
python data_pipeline/pipeline.py
```

### 4.7 Cargar desde backup CSV sin volver a scrapear
```bash
python data_pipeline/cargar_desde_backup.py --csv data_pipeline/files/BACKUP_RAW_YYYYMMDD_HHMM.csv
```

---

## 5. Qué hay que revisar con prioridad

1. Validar que los extractores Selenium funcionan con la versión actual de los sites.
2. Confirmar que `data_pipeline/files` contiene los CSV de respaldo y los archivos de seed correctos.
3. Asegurar que `.env` tiene las credenciales PostgreSQL correctas.
4. Revisar si conviene convertir `data_pipeline` en un paquete Python completo (`__init__.py`) para simplificar importaciones.

---

## 6. Recomendaciones rápidas

- Si querés usar el pipeline real, ejecutá `python data_pipeline/pipeline.py` desde la raíz del proyecto.
- Si no necesitás `test_db.py`, ya no queda en el proyecto porque era un duplicado roto.
- Para análisis de links y calidad de dataset, `data_pipeline/scratch_analyze.py` sigue disponible.

---

## 7. Dependencias
Se agregó `requirements.txt` para facilitar la instalación.




## Levantar el proyecto

- Activar entorno
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
.\.venv\Scripts\Activate.ps1

- Levantar el servidor de la api
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload

- Otra terminal levantar el front
cd frontend
npm run dev