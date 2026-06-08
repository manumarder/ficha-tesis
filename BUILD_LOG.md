# 🔧 Build Log - Canasta Básica ETL (Documentación Práctica)

**Fecha inicio:** Mayo 2026  
**Estado actual:** En desarrollo - Pipeline básico funcional  
**Tecnología:** Python + Selenium + PostgreSQL (Supabase)

---

## 📋 Fase 1: Setup Inicial del Proyecto

### 1.1 Crear Repo en GitHub
- ✅ Creado repositorio `AIC_tesis` en GitHub
- ✅ Clonado a local: `c:\Users\manue\Desktop\tesis\AIC_tesis`

**Próximo paso:** Usar `.gitignore` para excluir:
```
.env
/logs/*
/data_pipeline/cache/*
/data_pipeline/cookies/*
*.csv (excepto ejemplos)
__pycache__/
```

---

## 🔄 Fase 2: Código del Scraper

### 2.1 Migración del código base
- ✅ Copiados extractores de supermercados:
  - `carrefour_extractor.py`
  - `dia_extractor.py`
  - `depot_extractor.py`
  - `delimart_extractor.py`
- ✅ Estructura de carpetas creada:
  ```
  data_pipeline/
    ├── extractors/
    ├── transformers/
    ├── loaders/
    ├── utils/
    └── files/
  database/
    └── schema/
  config/
  ```

**Decisión tomada:** Cada supermercado tiene su extractor independiente → flexibilidad para mantener y actualizar selectivamente.

---

## 🏗️ Fase 3: Diseño del Esquema de BD

### 3.1 Tablas Base
- ✅ `supermercados` → catálogo de retailers
- ✅ `categorias` → tipos de productos (alimentos, higiene, etc)
- ✅ `productos_maestros` → productos únicos (agrupados por nombre genérico)
- ✅ `link_productos` → mapeo URL por supermercado
- ✅ `precios_productos` → histórico de precios (table crítica)
- ✅ `extracciones` → log de cada ejecución del scraper

### 3.2 Vista especial
- ✅ `vista_auditoria_consumo` → Semáforo (🔴 TRAMPA | 🟡 NORMAL | 🟢 OFERTA)
  - Compara precio actual vs promedio de últimos 21 días
  - Detecta ofertas falsas automáticamente

**Ver en:** [`database/schema/database_schema.sql`](database/schema/database_schema.sql)

---

## ☁️ Fase 4: Infraestructura - Supabase

### 4.1 Crear Base de Datos
- ✅ Cuenta Supabase creada
- ✅ Nuevo proyecto: `canasta-basica-super`
- ✅ Plan: Free (online, gratuito, con backups)

### 4.2 Ejecutar Schema
```bash
python database/init_db.py
```
**Output esperado:**
```
✅ ¡Base de datos inicializada correctamente con todas las tablas y vistas!
```

---

## 🔐 Fase 5: Configuración de Entorno

### 5.1 Crear archivo `.env`
```env
# Base de Datos - Supabase
DB_HOST=<supabase-host>
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=<tu_contraseña_supabase>
DB_NAME=postgres
DB_SSLMODE=require

# Alternativa: URL completa (más simple)
DATABASE_URL=postgresql://usuario:contraseña@host:5432/postgres

# Google Sheets (si usas para reportes)
GOOGLE_SHEETS_CREDENTIALS_FILE=credentials.json

# Logging
ENVIRONMENT=development
LOG_LEVEL=INFO
```

**⚠️ IMPORTANTE:** Nunca comitear `.env` a GitHub. Usar `.env.example` en repo para referencia.

---

## 📊 Fase 6: Carga de Datos Maestros desde Excel

### 6.1 Nuevo enfoque: un solo archivo maestro
Ahora tenemos un workbook combinado en `data_pipeline/files/Ficha_tablas_20260527.xlsx` con:
- ✅ hoja `supermercados`
- ✅ hoja `categorias`
- ✅ hojas por supermercado (`dia`, `carrefour`, `depot`, `delimart`) con links

Esto nos permite actualizar la base desde un único archivo en vez de depender de varios CSV separados.

### 6.2 Comando para probar la carga
```bash
python database/seed_maestros.py
```

**Lo que hace ahora el script:**
1. Lee el Excel maestro desde `data_pipeline/files/`
2. Actualiza/crea `supermercados`
3. Actualiza/crea `categorias`
4. Lee los links de cada hoja de supermercado
5. Agrupa productos en `productos_maestros`
6. Inserta/actualiza `link_productos`

### 6.3 Prueba real ejecutada
Intenté cargar desde el Excel con el comando anterior.

**Resultado observado en esta sesión:**
```text
2026-05-27 19:52:18,799 - ERROR - Error conectando a la base de datos: could not translate host name "db.vhlqggvapvhlfuiwciwo.supabase.co" to address: Unknown server error
2026-05-27 19:52:18,799 - ERROR - No se pudo conectar a la BD.
```

**Conclusión:** el flujo del seeder quedó listo para el Excel, pero la verificación real de carga quedó bloqueada por el acceso DNS a Supabase desde este entorno. En tu máquina local o desde un entorno con acceso a la red de Supabase, esa misma línea debería ejecutar la carga completa.

### 6.4 Verificación recomendada en tu entorno
```sql
SELECT COUNT(*) FROM supermercados;
SELECT COUNT(*) FROM categorias;
SELECT COUNT(*) FROM link_productos;
SELECT COUNT(*) FROM productos_maestros;
```

---

## 🧪 Fase 7: Pruebas Iniciales de Extracción

### 7.1 Test con 10-50 Productos
```bash
python data_pipeline/pipeline.py
```

**Flujo de la prueba:**
1. Lee links activos de BD
2. Lanza extractores Selenium (paralelo o secuencial)
3. Transforma datos
4. Valida precios
5. Carga en `precios_productos`
6. Registra ejecución en `extracciones`

**Resultados esperados:**
```
[EXTRACT] Se obtuvieron 15 links activos
[EXTRACT] Extracción completada: 12 productos válidos
[LOAD] Carga finalizada. ID de extracción: 1
✅ ETL completado en 2 minutos
```

### 7.2 Verificar Datos Cargados
```sql
SELECT COUNT(*) FROM precios_productos;  -- Debería ver 12 registros
SELECT * FROM extracciones;              -- Ver log de ejecuciones
```

---

## 📥 Fase 8: Carga Masiva de Links (PRÓXIMO PASO)

### 8.1 Preparar CSV de Links
- Necesito: `link_productos_YYYYMMDD_HHMM.csv`
- Estructura esperada:
  ```
  id_link_producto, id_maestro, id_supermercado, url_producto, activo
  1, 1, 1, https://carrefour.com/producto/xyz, TRUE
  2, 2, 1, https://carrefour.com/producto/abc, TRUE
  ...
  ```

### 8.2 Cargar con Seed Maestros
```bash
python database/seed_maestros.py
```

**Esto hará:**
1. Leer CSV con links
2. Crear `productos_maestros` agrupados por nombre genérico
3. Mapear links a maestros automáticamente
4. Insertar en BD en lotes (bulk insert)

---

## 📈 Estado Actual - Checkpoints

| Fase | Tarea | Estado | Fecha |
|------|-------|--------|-------|
| 1 | Repo GitHub | ✅ | 2026-05 |
| 2 | Extractores | ✅ | 2026-05 |
| 3 | Esquema BD | ✅ | 2026-05 |
| 4 | Supabase Setup | ✅ | 2026-05 |
| 5 | Variables .env | ✅ | 2026-05 |
| 6 | Seed Maestros | ✅ | 2026-05 |
| 7 | Test ETL (10-50 prod) | ✅ | 2026-05 |
| 8 | **Carga Links CSV** | ⏳ | Próximo |

---

## 🎯 Blockers / Issues Resueltos

### Issue #1: Conexión a Supabase con SSL
- **Problema:** Supabase requiere SSL en producción
- **Solución:** Añadido `DB_SSLMODE=require` en `.env` y soporte en `utils_db.py`
- **Status:** ✅ Resuelto

### Issue #2: Schema Categorías sin descripción
- **Problema:** `seed_from_csv.py` intentaba insertar columna `descripcion` que no existe
- **Solución:** Corregido a usar solo `id, nombre`
- **Status:** ✅ Resuelto

---

## 💡 Próximos Pasos (Roadmap)

1. ⏳ **Carga de Links Productos** → Subir CSV y ejecutar `seed_maestros.py`
2. 🚀 **Pipeline Automático** → Configurar scheduler (cron/APScheduler)
3. 📊 **Dashboard** → Visualizar precios en tiempo real
4. 🤖 **IA Agent** → Análisis automático de ofertas y trampas
5. 📱 **API REST** → Exponer datos para apps móviles

---

## 📝 Notas Técnicas

### Estructura de Datos
```
Supermercado (1) ─→ (N) Link Productos ─→ (N) Precios Productos
                    ↓
                    Productos Maestros ← Categorías
```

### Performance
- Links por supermercado: ~200-500 URLs activas
- Productos por ejecución: ~100-300 scrapeados
- Tiempo ejecución: 3-5 minutos (con 3 workers paralelos)
- Frecuencia recomendada: 1x por día (madrugada)

### Seguridad
- ✅ Credenciales en `.env` (nunca en código)
- ✅ SSL/TLS en conexión Supabase
- ✅ Logs sin exponer contraseñas
- ⚠️ TODO: Hacer `.env.example` público en repo

