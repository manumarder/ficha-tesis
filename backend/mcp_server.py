import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Cargar variables de entorno (.env) que tenés en la raíz
load_dotenv()

# Inicializar el servidor FastMCP oficial de la Tesis
mcp = FastMCP("Fichá Analítica Regional")

def obtener_conexion_db():
    """Establece una conexión directa con la base de datos relacional de Supabase."""
    # Nota: Asegurate de que estos nombres coincidan con los de tu archivo .env
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT", 5432)
    )

# --- 1. RECURSO REAL (Conexión a tu vista_auditoria_consumo) ---
@mcp.resource("views://auditoria_consumo")
def obtener_vista_auditoria() -> str:
    """
    Consulta en tiempo real la vista 'public.vista_auditoria_consumo' 
    para exponer alertas de desvíos, semáforos e indicadores analíticos al LLM.
    """
    conn = None
    try:
        conn = obtener_conexion_db()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Traemos un límite prudente para no desbordar el contexto de tokens del LLM
            cur.execute("""
                SELECT nombre_generico, supermercado, precio_normal, precio_descuento, semaforo, clasificacion, ahorro_real_pct
                FROM public.vista_auditoria_consumo
                ORDER BY created_at DESC
                LIMIT 50;
            """)
            resultados = cur.fetchall()
            return json.dumps(resultados, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Error al consultar la vista de auditoría: {str(e)}"}, ensure_ascii=False)
    finally:
        if conn:
            conn.close()

# --- 2. HERRAMIENTA REAL (Buscador parametrizado sobre tu tabla precios_productos) ---
@mcp.tool()
def buscar_precios_producto(termino_busqueda: str) -> str:
    """
    Busca de manera automática el precio actual de un producto en la tabla precios_productos 
    aplicando filtros analíticos sobre los supermercados de Corrientes Capital.
    """
    conn = None
    try:
        conn = obtener_conexion_db()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Nueva consulta optimizada: Trae solo el registro más reciente de cada link de producto
            query = """
                SELECT DISTINCT ON (lp.id)
                    pm.nombre_generico,
                    s.nombre AS supermercado,
                    pp.precio_normal,
                    pp.precio_descuento,
                    pp.precio_final,
                    pp.alerta_trampa,
                    pp.es_oferta_real,
                    pp.created_at
                FROM public.precios_productos pp
                JOIN public.link_productos lp ON lp.id = pp.id_link
                JOIN public.productos_maestros pm ON pm.id = lp.id_maestro
                JOIN public.supermercados s ON s.id = lp.id_supermercado
                WHERE pm.nombre_generico ILIKE %s AND lp.activo = true
                ORDER BY lp.id, pp.created_at DESC
            """
            # El ILIKE con %s busca coincidencias parciales (ej: 'fernet' encuentra 'Fernet Branca 750ml')
            cur.execute(query, (f"%{termino_busqueda}%",))
            resultados = cur.fetchall()
            
            if not resultados:
                return f"Se encontraron 0 registros en la base de datos para el criterio: '{termino_busqueda}'."
            
            # Formateamos la respuesta en un texto claro que el LLM pueda interpretar al instante
            respuesta = f"Resultados de base de datos en tiempo real para '{termino_busqueda}':\n\n"
            for i, res in enumerate(resultados, 1):
                alerta = "🚨 ¡Alerta Trampa!" if res['alerta_trampa'] else "✅ Estable"
                oferta = "⭐ Oferta Real" if res['es_oferta_real'] else "Precio Regular"
                respuesta += (
                    f"{i}. {res['nombre_generico']} en {res['supermercado']}:\n"
                    f"   - Precio Final Computado: ${res['precio_final']:,}\n"
                    f"   - Precio Normal: ${res['precio_normal']:,} | Descuento: ${res['precio_descuento'] or 0:,}\n"
                    f"   - Estado: {alerta} | Clasificación: {oferta}\n\n"
                )
            return respuesta

    except Exception as e:
        return f"Error crítico al ejecutar la consulta en la base de datos de la tesis: {str(e)}"
    finally:
        if conn:
            conn.close()

# --- 3. HERRAMIENTA REAL: OPTIMIZADOR DE CANASTAS POR ID MAESTRO (OPCIÓN A) ---
@mcp.tool()
def optimizar_canasta(items_json: str) -> str:
    """
    Calcula el costo total acumulado de una lista de compras por supermercado en Corrientes Capital.
    Recibe un JSON string con los IDs maestros exactos y cantidades, ej: [{"id_maestro": 12, "cantidad": 3}, {"id_maestro": 45, "cantidad": 1}]
    """
    conn = None
    try:
        items = json.loads(items_json)
        if not items:
            return "La lista de compras está vacía."
            
        conn = obtener_conexion_db()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            
            totales_supermercados = {}
            
            for item in items:
                id_maestro = item.get("id_maestro")
                cantidad = item.get("cantidad", 1)
                
                if not id_maestro:
                    continue
                
                # Query seguro y unívoco: Filtra directamente por el ID de productos_maestros
                # Trae el más barato de cada supermercado si es que hay múltiples links asignados
                query = """
                    SELECT DISTINCT ON (lp.id_supermercado)
                        s.nombre AS supermercado,
                        pm.nombre_generico,
                        pp.precio_final
                    FROM public.precios_productos pp
                    JOIN public.link_productos lp ON lp.id = pp.id_link
                    JOIN public.productos_maestros pm ON pm.id = lp.id_maestro
                    JOIN public.supermercados s ON s.id = lp.id_supermercado
                    WHERE pm.id = %s AND lp.activo = true
                    ORDER BY lp.id_supermercado, pp.precio_final ASC, pp.created_at DESC
                """
                cur.execute(query, (id_maestro,))
                filas = cur.fetchall()
                
                for fila in filas:
                    super_nom = fila["supermercado"]
                    prod_real = fila["nombre_generico"]
                    costo_parcial = float(fila["precio_final"]) * cantidad
                    
                    if super_nom not in totales_supermercados:
                        totales_supermercados[super_nom] = {"total": 0.0, "productos_encontrados": []}
                        
                    totales_supermercados[super_nom]["total"] += costo_parcial
                    totales_supermercados[super_nom]["productos_encontrados"].append(f"{prod_real} (x{cantidad})")
            
            if not totales_supermercados:
                return "No se encontraron los IDs maestros solicitados en ninguna sucursal activa."
                
            # Ordenamos el ranking del más barato al más caro
            ranking = sorted(totales_supermercados.items(), key=lambda x: x[1]["total"])
            
            respuesta = "📊 COMPARATIVA DE CANASTA EN TIEMPO REAL (Filtro por ID Maestro):\n\n"
            for i, (super_nom, info) in enumerate(ranking, 1):
                medalla = "🥇 MEJOR OPCIÓN" if i == 1 else "❌" if i == len(ranking) else "⚖️"
                respuesta += (
                    f"{i}. {super_nom} {medalla}:\n"
                    f"   - COSTO TOTAL: ${info['total']:,.2f}\n"
                    f"   - Items procesados:\n     • " + "\n     • ".join(info['productos_encontrados']) + "\n\n"
                )
            return respuesta

    except Exception as e:
        return f"Error analítico en la agregación por ID: {str(e)}"
    finally:
        if conn:
            conn.close()
            
if __name__ == "__main__":
    mcp.run()