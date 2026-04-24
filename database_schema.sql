-- Extensiones necesarias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Tabla de Supermercados
CREATE TABLE IF NOT EXISTS supermercados (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    url_base VARCHAR(255),
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Tabla de Categorías
CREATE TABLE IF NOT EXISTS categorias (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    descripcion TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Tabla de Productos Maestros (Centralización)
CREATE TABLE IF NOT EXISTS productos_maestros (
    id SERIAL PRIMARY KEY,
    nombre_generico VARCHAR(255) NOT NULL,
    marca VARCHAR(100),
    id_categoria INTEGER REFERENCES categorias(id) ON DELETE SET NULL,
    sku_referencia VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. Tabla de Links de Productos (Mapeo por Supermercado)
CREATE TABLE IF NOT EXISTS link_productos (
    id SERIAL PRIMARY KEY,
    id_maestro INTEGER REFERENCES productos_maestros(id) ON DELETE CASCADE,
    id_supermercado INTEGER REFERENCES supermercados(id) ON DELETE CASCADE,
    url_producto TEXT NOT NULL,
    nombre_especifico_retail VARCHAR(255),
    codigo_interno_retail VARCHAR(100),
    activo BOOLEAN DEFAULT TRUE,
    ultima_sincronizacion TIMESTAMP WITH TIME ZONE
);

-- 5. Tabla de Extracciones (Logs de Scraping)
CREATE TABLE IF NOT EXISTS extracciones (
    id SERIAL PRIMARY KEY,
    fecha_ejecucion TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    estado VARCHAR(50), -- 'exitoso', 'fallido'
    items_procesados INTEGER DEFAULT 0,
    error_log TEXT
);

-- 6. Tabla de Precios de Productos (Histórico y Auditoría)
CREATE TABLE IF NOT EXISTS precios_productos (
    id SERIAL PRIMARY KEY,
    id_link INTEGER REFERENCES link_productos(id) ON DELETE CASCADE,
    id_extraccion INTEGER REFERENCES extracciones(id) ON DELETE CASCADE,
    precio_normal DECIMAL(12, 2) NOT NULL,
    precio_descuento DECIMAL(12, 2),
    precio_final DECIMAL(12, 2) GENERATED ALWAYS AS (LEAST(precio_normal, COALESCE(precio_descuento, precio_normal))) STORED,
    
    -- Auditoría técnica
    es_oferta_real BOOLEAN DEFAULT FALSE,
    alerta_trampa BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 7. VISTA DE AUDITORÍA (El "Semáforo" de la Tesis)
-- Esta vista hace la magia: compara el precio de hoy con el promedio de los últimos 21 días
CREATE OR REPLACE VIEW vista_auditoria_consumo AS
WITH historico AS (
    SELECT 
        p.id,
        m.nombre_generico,
        s.nombre AS supermercado,
        p.precio_final,
        p.precio_normal,
        p.precio_descuento,
        p.created_at,
        AVG(p.precio_final) OVER (
            PARTITION BY m.id 
            ORDER BY p.created_at 
            ROWS BETWEEN 21 PRECEDING AND 1 PRECEDING
        ) AS promedio_historico
    FROM precios_productos p
    JOIN link_productos l ON p.id_link = l.id
    JOIN productos_maestros m ON l.id_maestro = m.id
    JOIN supermercados s ON l.id_supermercado = s.id
)
SELECT 
    *,
    CASE 
        -- ROJO: El precio normal subió más del 15% respecto al promedio y pusieron un "descuento"
        WHEN precio_normal > (promedio_historico * 1.15) AND precio_descuento IS NOT NULL THEN '🔴 ROJO - OFERTA TRAMPA'
        -- VERDE: El precio final es al menos un 10% menor al promedio histórico real
        WHEN precio_final < (promedio_historico * 0.90) THEN '🟢 VERDE - DESCUENTO REAL'
        -- AMARILLO: El precio está en el rango normal
        ELSE '🟡 AMARILLO - PRECIO ESTÁNDAR'
    END AS semaforo_auditoria
FROM historico;