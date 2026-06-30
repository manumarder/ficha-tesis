import streamlit as st
import requests
import pandas as pd

# ==========================================
# CONFIGURACIÓN DE PÁGINA E IDENTIDAD VISUAL
# ==========================================
st.set_page_config(
    page_title="Fichá - Auditor de Precios Inteligente",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuración del Backend local de FastAPI
BACKEND_URL = "http://127.0.0.1:8000"

# Inyección de CSS Avanzado para Estética Glassmorphism y Tipografía Montserrat/Outfit
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');
    
    /* Configuración global de fuentes */
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    /* Estilo para las Tarjetas de Métricas Principales */
    .metric-card {
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 24px;
        text-align: center;
        backdrop-filter: blur(12px);
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.2);
        transition: transform 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-4px);
        border-color: rgba(46, 213, 115, 0.4);
    }
    
    /* Títulos con Degradé Corporativo (Match con el Logo) */
    .gradient-text {
        background: -webkit-linear-gradient(45deg, #2ed573, #1e90ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
    }
    
    /* Ajustes estéticos para las pestañas (Tabs) */
    .stTabs [data-baseweb="tab"] {
        font-size: 16px;
        font-weight: 600;
        padding: 12px 24px;
        border-radius: 8px 8px 0px 0px;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# LOGICA DE CONSUMO DE MICROSERVICIOS (API)
# ==========================================
@st.cache_data(ttl=300) # Caché inteligente de 5 minutos para no saturar Supabase
def fetch_api(endpoint: str, params: dict = None):
    try:
        response = requests.get(f"{BACKEND_URL}{endpoint}", params=params, timeout=15)
        if response.status_code == 200:
            return response.json()
        # Si la API devuelve un error, lo pasamos para que el frontend lo sepa
        return {"error": f"Error en el backend: {response.status_code}", "detail": response.text}
    except Exception as e:
        # Si hay un error de conexión, también lo notificamos
        return {"error": f"No se pudo conectar al backend: {e}"}

# ==========================================
# RENDERIZADO DEL ENTORNO WEB
# ==========================================

# Encabezado Principal de Alto Impacto
col_logo, col_titulo = st.columns([1, 4])
with col_titulo:
    st.markdown('<h1 class="gradient-text" style="font-size: 48px; margin-bottom: 0px;">FICHÁ</h1>', unsafe_allow_html=True)
    st.markdown('<p style="font-size: 18px; color: #a4b0be; margin-top: 0px;"><b>Auditor de Precios Inteligente</b> — Transparencia Retail en Corrientes Capital</p>', unsafe_allow_html=True)

st.markdown("---")

# Fila Superior: Tarjetas de Métricas de Control de Gestión (Simuladas/API)
m1, m2, m3, m4 = st.columns(4)
with m1:
    st.markdown('<div class="metric-card"><h4 style="margin:0;color:#747d8c;">Cadenas Auditadas</h4><h2 style="margin:10px 0 0 0;color:#1e90ff;">4 Activas</h2><p style="margin:0;font-size:12px;color:#57606f;">Carrefour • Día • Depot • Delimart</p></div>', unsafe_allow_html=True)
with m2:
    st.markdown('<div class="metric-card"><h4 style="margin:0;color:#747d8c;">Catálogo Base</h4><h2 style="margin:10px 0 0 0;color:#f1f2f6;">2.202 Links</h2><p style="margin:0;font-size:12px;color:#57606f;">Sincronización DataOps Diaria</p></div>', unsafe_allow_html=True)
with m3:
    st.markdown('<div class="metric-card"><h4 style="margin:0;color:#747d8c;">Oportunidades de Compra</h4><h2 style="margin:10px 0 0 0;color:#2ed573;">🟢 Reales</h2><p style="margin:0;font-size:12px;color:#57606f;">Ahorro neto vs Histórico de 21d</p></div>', unsafe_allow_html=True)
with m4:
    st.markdown('<div class="metric-card"><h4 style="margin:0;color:#747d8c;">Alertas de Variación</h4><h2 style="margin:10px 0 0 0;color:#ff4757;">🔴 Fraudes</h2><p style="margin:0;font-size:12px;color:#57606f;">Inflado artificial de precio normal</p></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Segmentación de Secciones mediante Pestañas Avanzadas
tab_buscador, tab_canasta, tab_oportunidades, tab_fraudes = st.tabs([
    "🔍 Buscador de Góndola", 
    "🛒 Armador de Canastas", 
    "🟢 Oportunidades Reales", 
    "🔴 Alertas de Fraude"
])

# ------------------------------------------
# PESTAÑA 1: BUSCADOR INTELIGENTE
# ------------------------------------------
with tab_buscador:
    st.markdown("### Buscar Productos en la Ciudad")
    busqueda = st.text_input("¿Qué artículo estás buscando?", placeholder="Ej: Aceite de Girasol, Yerba Mate...", key="input_search")
    
    if busqueda:
        with st.spinner("Escaneando series de tiempo relacionales..."):
            res = fetch_api("/api/buscar", params={"q": busqueda})
            if res and not res.get("error"):
                if not res.get("data"):
                    st.info("No se encontraron registros vigentes para ese criterio en las góndolas de Corrientes.")
                else:
                    df = pd.DataFrame(res["data"])
                    # Rellenar nulos
                    df["ahorro_real_pct"] = df["ahorro_real_pct"].fillna(0.0)
                    df["precio_descuento"] = df["precio_descuento"].fillna(df["precio_normal"])
                    
                    # Formatear la tabla para visualización limpia
                    df_show = df[["semaforo", "supermercado", "nombre_generico", "precio_final", "precio_normal", "ahorro_real_pct"]].copy()
                    df_show.columns = ["Alerta", "Supermercado", "Producto", "Precio de Venta", "Precio Lista Base", "Ahorro Real (%)"]
                    
                    st.dataframe(
                        df_show.style.format({
                            "Precio de Venta": "${:,.2f}",
                            "Precio Lista Base": "${:,.2f}",
                            "Ahorro Real (%)": "{:.2f}%"
                        }),
                        use_container_width=True,
                        hide_index=True
                    )
            else:
                st.error(f"No se pudo conectar con el motor de búsqueda. Detalle: {res.get('error', 'Error desconocido')}")

# ------------------------------------------
# PESTAÑA 2: ARMADOR DE CANASTAS (OPTIMIZADOR PRESUPUESTARIO)
# ------------------------------------------
with tab_canasta:
    st.markdown("### Algoritmo de Optimización de Canasta Familiar")
    st.caption("Seleccioná múltiples bienes de la canasta para calcular en qué sucursal de la ciudad el costo consolidado final es menor.")
    
    with st.spinner("Cargando catálogo de productos..."):
        res_prod = fetch_api("/api/productos")

    if res_prod and not res_prod.get("error"):
        productos_seleccionados = st.multiselect(
            "Construí tu lista de compras:",
            options=res_prod["data"],
            placeholder="Escribí para filtrar el catálogo..."
        )
        
        if st.button("Comparar Canasta", disabled=not productos_seleccionados, use_container_width=True):
            if productos_seleccionados:
                with st.spinner("Procesando combinatoria matricial en el Backend..."):
                    try:
                        # Hacemos una petición POST al endpoint de la canasta
                        response = requests.post(f"{BACKEND_URL}/api/comparar-canasta", json={"productos": productos_seleccionados}, timeout=30)
                        if response.status_code == 200:
                            data_canasta = response.json()
                            
                            if data_canasta.get("totales"):
                                # Mostrar ganadores absolutos en tarjetas estéticas
                                st.markdown("#### Costo Total por Supermercado")
                                cols_super = st.columns(len(data_canasta["totales"]))
                                
                                for idx, (superm, total) in enumerate(data_canasta["totales"].items()):
                                    with cols_super[idx]:
                                        # Resaltar al más barato (el primero, debido al ORDER BY de la API)
                                        border_color = "#2ed573" if idx == 0 else "rgba(255,255,255,0.08)"
                                        badge_winner = "🏆 ¡MÁS ECONÓMICO!" if idx == 0 else ""
                                        
                                        st.markdown(f"""
                                            <div style="border: 2px solid {border_color}; padding: 16px; border-radius: 12px; text-align: center; background: rgba(255,255,255,0.02);">
                                                <p style="margin:0; font-size: 14px; color:#a4b0be;">{superm}</p>
                                                <h2 style="margin:5px 0; color:#fff;">${total:,.2f}</h2>
                                                <span style="font-size:11px; color:#2ed573; font-weight:bold;">{badge_winner}</span>
                                            </div>
                                        """, unsafe_allow_html=True)
                                
                                # Mostrar el desglose comparativo de productos en formato de matriz pivot
                                if data_canasta.get("items"):
                                    st.markdown("<br>#### 📋 Comparativa Detallada de Artículos", unsafe_allow_html=True)
                                    df_items = pd.DataFrame(data_canasta["items"])
                                    if not df_items.empty:
                                        # Formatear el precio y semáforo para mostrar
                                        df_items["precio_formateado"] = df_items["precio_efectivo"].map(lambda x: f"${x:,.2f}") + " " + df_items["semaforo"]
                                        
                                        # Pivotar para colocar supermercados como columnas y productos como filas
                                        df_pivot = df_items.pivot(index="nombre_generico", columns="supermercado", values="precio_formateado")
                                        df_pivot.index.name = "Producto Seleccionado"
                                        df_pivot = df_pivot.fillna("❌ Sin Stock")
                                        
                                        st.dataframe(df_pivot, use_container_width=True)

                                # Mostrar gráfico de barras comparativo básico
                                st.markdown("<br>", unsafe_allow_html=True)
                                df_chart = pd.DataFrame(list(data_canasta["totales"].items()), columns=["Supermercado", "Costo Canasta Total"])
                                st.bar_chart(df_chart.set_index("Supermercado"))
                            else:
                                st.warning(data_canasta.get("mensaje", "No se pudieron consolidar precios para calcular los totales."))
                        else:
                            st.error(f"El backend devolvió un error: {response.status_code} - {response.text}")
                    except Exception as e:
                        st.error(f"Falla de red con la capa de microservicios: {e}")
    else:
        st.error(f"No se pudo conectar con el catálogo unificado del Backend. Detalle: {res_prod.get('error', 'Error desconocido')}")

# ------------------------------------------
# PESTAÑA 3: OPORTUNIDADES REALES
# ------------------------------------------
with tab_oportunidades:
    st.markdown("### Descuentos Genuinos Detectados en la Ciudad 🟢")
    st.caption("Artículos cuyo precio final es estrictamente inferior al promedio móvil de su historial de 21 días.")
    
    with st.spinner("Cargando matriz Oro de oportunidades..."):
        res_reales = fetch_api("/api/ofertas-reales")
        if res_reales and not res_reales.get("error"):
            if res_reales.get("data"):
                df_reales = pd.DataFrame(res_reales["data"])
                # Rellenar nulos
                df_reales["ahorro_real_pct"] = df_reales["ahorro_real_pct"].fillna(0.0)
                df_reales["ahorro_nominal_pct"] = df_reales["ahorro_nominal_pct"].fillna(0.0)
                
                df_reales_show = df_reales[["supermercado", "nombre_generico", "precio_descuento", "promedio_normal_21d", "ahorro_real_pct", "ahorro_nominal_pct"]].copy()
                df_reales_show.columns = ["Supermercado", "Producto Maestro", "Precio Hoy", "Promedio Móvil (21d)", "Ahorro Real (%)", "Ahorro de Cartel (%)"]
                
                st.dataframe(
                    df_reales_show.style.format({
                        "Precio Hoy": "${:,.2f}",
                        "Promedio Móvil (21d)": "${:,.2f}",
                        "Ahorro Real (%)": "{:.2f}%",
                        "Ahorro de Cartel (%)": "{:.2f}%"
                    }),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("No se registran ofertas reales en el actual ciclo de precios.")
        else:
            st.error(f"No se pudo obtener la lista de ofertas. Detalle: {res_reales.get('error', 'Error desconocido')}")

# ------------------------------------------
# PESTAÑA 4: ALERTAS DE FRAUDE COMERCIAL
# ------------------------------------------
with tab_fraudes:
    st.markdown("### Ofertas Trampa Identificadas Diariamente 🔴")
    st.caption("Productos publicitados que sufrieron incrementos artificiales en su precio de lista normal para simular rebajas engañosas.")
    
    with st.spinner("Extrayendo historial de infracciones..."):
        res_trampas = fetch_api("/api/alertas-trampa")
        if res_trampas and not res_trampas.get("error"):
            if res_trampas.get("data"):
                df_trampas = pd.DataFrame(res_trampas["data"])
                # Rellenar nulos
                df_trampas["ahorro_real_pct"] = df_trampas["ahorro_real_pct"].fillna(0.0)
                # Calcular sobrecargo sobre el promedio histórico verdadero
                df_trampas["sobrecargo_pct"] = ((df_trampas["precio_normal"] / df_trampas["promedio_normal_21d"].replace(0, 1)) - 1) * 100
                
                df_trampas_show = df_trampas[["supermercado", "nombre_generico", "precio_normal", "precio_descuento", "promedio_normal_21d", "sobrecargo_pct"]].copy()
                df_trampas_show.columns = ["Supermercado Infraccionado", "Producto", "Precio Lista Inflado", "Precio Descuento Falso", "Promedio Histórico Verdadero", "Sobrecargo Lista (%)"]
                
                st.dataframe(
                    df_trampas_show.style.format({
                        "Precio Lista Inflado": "${:,.2f}",
                        "Precio Descuento Falso": "${:,.2f}",
                        "Promedio Histórico Verdadero": "${:,.2f}",
                        "Sobrecargo Lista (%)": "{:.2f}%"
                    }),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.success("¡Excelente! No se detectaron anomalías distributivas ni fraudes de cartelería en la última corrida.")
        else:
            st.error(f"No se pudo obtener la lista de alertas. Detalle: {res_trampas.get('error', 'Error desconocido')}")