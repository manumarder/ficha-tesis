import os
import sys
import re
import urllib.parse
import pandas as pd

# Este script va a leer el CSV de la última extracción masiva (el que generó las 240 fallas),
# va a aplicar tu filtro crítico (ignorar quiebres de stock y aislar páginas muertas/rotas), 
# y va a escupir la interfaz HTML interactiva en la carpeta files/.


def clean_slug(url):
    """Extrae palabras de búsqueda limpias desde el final de la URL."""
    try:
        url = str(url).strip()
        if url.endswith('/p'):
            url = url[:-2]
        slug = url.strip('/').split('/')[-1]
        slug = re.sub(r'-\d+$', '', slug)  # Remueve IDs numéricos finales
        search_term = slug.replace('_', ' ').replace('-', ' ')
        return search_term.strip().lower()
    except:
        return ""

def deducir_super_y_busqueda(url, search_term):
    """
    Analiza el dominio de la URL para deducir el nombre correcto
    del supermercado y retornar su endpoint de búsqueda interno nativo.
    """
    url = str(url).lower()
    encoded_term = urllib.parse.quote(search_term)
    
    if 'carrefour.com.ar' in url:
        return 'Carrefour', f"https://www.carrefour.com.ar/{encoded_term}?_q={encoded_term}&map=ft"
        
    elif 'delimart.com.ar' in url:
        return 'DeliMart', f"https://www.delimart.com.ar/catalogsearch/result/?q={encoded_term}"
        
    elif 'masonline.com.ar' in url:
        return 'Mas Online', f"https://www.masonline.com.ar/{encoded_term}?_q={encoded_term}&map=ft"
        
    elif 'supermercadosdia.com.ar' in url or 'diaonline' in url:
        return 'Dia', f"https://diaonline.supermercadosdia.com.ar/{encoded_term}?_q={encoded_term}&map=ft"
        
    elif 'depotexpress.com.ar' in url or 'depot' in url:
        # Endpoint clásico para búsquedas basadas en query params estándar
        return 'Depot', f"https://www.depotexpress.com.ar/?s={encoded_term}&post_type=product"
        
    return 'Desconocido', f"https://www.google.com/search?q={encoded_term}"

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    fallidos_dir = os.path.join(base_dir, 'files', 'links_fallidos')
    
    if not os.path.exists(fallidos_dir):
        print(f"[ERROR] No existe la carpeta de fallas en: {fallidos_dir}")
        return
        
    candidatos = [
        os.path.join(fallidos_dir, f) 
        for f in os.listdir(fallidos_dir) 
        if f.startswith('LINKS_FALLIDOS_') and f.endswith('.csv')
    ]
    
    if not candidatos:
        print(f"[ERROR] No se encontraron reportes masivos (LINKS_FALLIDOS_*.csv) en: {fallidos_dir}")
        return
        
    ultimo_reporte = max(candidatos, key=os.path.getmtime)
    print(f"📦 Leyendo último reporte masivo de fallas: {os.path.basename(ultimo_reporte)}")
    
    df_raw = pd.read_csv(ultimo_reporte, on_bad_lines='skip')
    
    df_raw['error_type'] = df_raw['error_type'].fillna('exception').astype(str)
    df_raw = df_raw.dropna(subset=['url'])
    df_raw['url'] = df_raw['url'].astype(str)

    # Filtrar excluyendo los no_disponible lógicos
    df_criticos = df_raw[df_raw['error_type'] != 'no_disponible'].drop_duplicates(subset=['url'])
    
    if df_criticos.empty:
        print("✨ ¡Excelente! No hay enlaces críticos o páginas muertas para reparar en este lote.")
        return
        
    input_csv = os.path.join(base_dir, 'files', 'links_a_modificar.csv')
    df_criticos.to_csv(input_csv, index=False)
    
    output_html = os.path.join(base_dir, 'files', 'reparador_links.html')
    rows_html = ""
    
    for idx, row in df_criticos.iterrows():
        old_url = row['url']
        error_type = row['error_type']
        
        nombre_prod = row.get('nombre', '')
        if pd.isna(nombre_prod) or str(nombre_prod).strip() == '':
            search_term = clean_slug(old_url)
        else:
            search_term = str(nombre_prod).strip().lower()
            
        # DEDDUCCIÓN DINÁMICA DE SUPERMERCADO Y URL DE BÚSQUEDA NATIVA
        supermercado, search_url = deducir_super_y_busqueda(old_url, search_term)
        
        rows_html += f"""
        <tr>
            <td class="td-old-url" style="word-break: break-all; font-size: 0.85em;">
                <a href="{old_url}" target="_blank">{old_url}</a>
            </td>
            <td style="font-weight: bold; color: #2c3e50;">{supermercado}</td>
            <td><span class="badge" style="background-color: #e74c3c; color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.8em;">{error_type}</span></td>
            <td>{search_term}</td>
            <td style="text-align:center;">
                <a href="{search_url}" target="_blank" class="btn btn-search">🔍 Buscar en Súper</a>
            </td>
            <td>
                <input type="text" class="new-url-input" placeholder="Pegar nueva URL o escribir 'NO'..." style="width: 100%; padding: 8px;">
            </td>
        </tr>
        """
        
    html_template = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Asistente Reparador de Links - Canasta Básica</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7f6; color: #333; margin: 0; padding: 20px; }}
            .container {{ max-width: 1300px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
            h1 {{ color: #2c3e50; text-align: center; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background-color: #2c3e50; color: white; position: sticky; top: 0; }}
            tr:hover {{ background-color: #f1f1f1; }}
            .btn {{ padding: 8px 12px; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; text-decoration: none; display: inline-block; }}
            .btn-search {{ background-color: #3498db; color: white; font-size: 0.9em; }}
            .btn-search:hover {{ background-color: #2980b9; }}
            .btn-export {{ background-color: #27ae60; color: white; padding: 12px 24px; font-size: 1.1em; display: block; margin: 20px auto; width: fit-content; }}
            .btn-export:hover {{ background-color: #2ecc71; }}
            .header-info {{ background-color: #e8f4f8; padding: 15px; border-left: 4px solid #3498db; margin-bottom: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🛠️ Asistente de Reparación de Links</h1>
            <div class="header-info">
                <p><strong>Instrucciones:</strong></p>
                <ol>
                    <li>Haz clic en <strong>"Buscar en Súper"</strong> para abrir la tienda oficial con el producto ya buscado.</li>
                    <li>Navega en la pestaña nueva y copia la URL correcta del producto.</li>
                    <li>Pega la nueva URL en la columna <strong>"Nueva URL"</strong>.</li>
                    <li>Si el producto ya no existe definitivamente, escribe la palabra <strong>"NO"</strong> para darlo de baja en la DB.</li>
                    <li>Cuando termines, haz clic en el botón <strong>"Exportar Correcciones"</strong> al final de la página.</li>
                </ol>
            </div>
            
            <table id="linksTable">
                <thead>
                    <tr>
                        <th>URL Rota (Actual)</th>
                        <th>Supermercado</th>
                        <th>Tipo Error</th>
                        <th>Término Detectado</th>
                        <th>Buscador Automático</th>
                        <th>Nueva URL (Pegar aquí)</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
            
            <button class="btn btn-export" onclick="exportToCSV()">💾 Exportar Correcciones</button>
        </div>

        <script>
            function exportToCSV() {{
                const table = document.getElementById('linksTable');
                const rows = table.getElementsByTagName('tbody')[0].getElementsByTagName('tr');
                
                let csvContent = "viejo_link,nuevo_link\\n";
                let count = 0;
                
                for (let i = 0; i < rows.length; i++) {{
                    const oldUrlAnchor = rows[i].querySelector('.td-old-url a');
                    const input = rows[i].querySelector('.new-url-input');
                    
                    if (oldUrlAnchor && input) {{
                        const oldUrl = oldUrlAnchor.innerText.trim();
                        const newUrl = input.value.trim();
                        if (newUrl && newUrl !== "") {{
                            csvContent += `"${{oldUrl}}","${{newUrl}}"\\n`;
                            count++;
                        }}
                    }}
                }}
                
                if (count === 0) {{
                    alert("No has ingresado ninguna nueva URL para exportar.");
                    return;
                }}
                
                const blob = new Blob([csvContent], {{ type: 'text/csv;charset=utf-8;' }});
                const link = document.createElement("a");
                const url = URL.createObjectURL(blob);
                link.setAttribute("href", url);
                link.setAttribute("download", "links_corregidos.csv");
                link.style.visibility = 'hidden';
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            }}
        </script>
    </body>
    </html>
    """
    
    with open(output_html, 'w', encoding='utf-8-sig') as f:
        f.write(html_template)
        
    print(f"🎯 Interfaz generada con éxito en: {output_html}")
    print(f"📝 Total de links críticos de la canasta a revisar: {len(df_criticos)}")

if __name__ == "__main__":
    main()