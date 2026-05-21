import os
import sys
import pandas as pd
from urllib.parse import urlparse
import re
import unicodedata

def clean_product_name(url):
    try:
        path = urlparse(url).path.strip('/')
        segments = path.split('/')
        if segments[-1] == 'p' and len(segments) > 1:
            filename = segments[-2]
        else:
            filename = segments[-1]
        filename = filename.replace('.html', '')
        name = filename.replace('_', ' ').replace('-', ' ')
        name = re.sub(r'\b\d{5,}\b', '', name) 
        name = " ".join(name.split()).title()
        return name if len(name) > 2 else "Producto Desconocido"
    except:
        return "Producto Desconocido"

def normalize(s):
    s = str(s).lower().strip().rstrip('.')
    sinonimos = {
        'shampoo': 'champu',
        'toallitas': 'toallitas femeninas',
        'tomate': 'tomate perita',
        'piedritas / arena sanitaria para gatos': 'arena sanitaria para gatos'
    }
    s_norm = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    return sinonimos.get(s_norm, s_norm)

excel_path = r"c:\Users\manue\Desktop\tesis\AIC_tesis\data_pipeline\files\Links_productos_Fichá.xlsx"

xls = pd.ExcelFile(excel_path)
print("Hojas encontradas:", xls.sheet_names)

all_links = []

for sheet in xls.sheet_names:
    if normalize(sheet) == 'categorias':
        continue
    df = pd.read_excel(xls, sheet_name=sheet)
    print(f"Leyendo hoja '{sheet}'. Columnas: {list(df.columns)}")
    for _, row in df.iterrows():
        # Sometimes column names have trailing spaces
        # Let's search for columns that contain 'Producto' and 'Link'
        cat_col = next((col for col in df.columns if 'producto' in col.lower()), None)
        link_col = next((col for col in df.columns if 'link' in col.lower()), None)
        
        if not cat_col or not link_col:
             continue

        cat = row.get(cat_col)
        url = row.get(link_col)
        if pd.isna(cat) or pd.isna(url):
            continue
        
        all_links.append({
            'supermercado': sheet,
            'categoria': normalize(cat),
            'categoria_orig': str(cat).strip(),
            'url': url,
            'producto_maestro': clean_product_name(url)
        })

df_links = pd.DataFrame(all_links)

print("\n--- Resumen por Supermercado ---")
if len(df_links) > 0:
    print(df_links['supermercado'].value_counts())

    print("\n--- Resumen por Supermercado y Categoría (Conteo de Links) ---")
    summary = df_links.groupby(['supermercado', 'categoria_orig']).size().reset_index(name='conteo')
    pivot_summary = summary.pivot(index='categoria_orig', columns='supermercado', values='conteo').fillna(0).astype(int)
    
    # We also want to know which categories exist globally, in case a supermarket is missing it completely
    todas_categorias = sorted(df_links['categoria_orig'].unique())
    print(f"\nTotal de categorías únicas: {len(todas_categorias)}")
    
    # Reindex to make sure all categories are present
    pivot_summary = pivot_summary.reindex(todas_categorias, fill_value=0)
    
    print("\n--- Alertas (Pocos o 0 links) ---")
    alertas = []
    for index, row in pivot_summary.iterrows():
        for col in pivot_summary.columns:
            val = row[col]
            if val == 0:
                alertas.append(f"- '{col}' NO TIENE links para la categoría '{index}'.")
            elif val < 2:
                alertas.append(f"- '{col}' tiene muy pocos links ({val}) para la categoría '{index}'.")
    
    if alertas:
        for a in alertas:
            print(a)
    else:
        print("No se detectaron alertas.")
else:
    print("No se encontraron links.")

print("\n--- Resumen de Productos Maestros ---")
if len(df_links) > 0:
    maestros_count = df_links.groupby('producto_maestro').size().reset_index(name='conteo_total')
    print(f"Total de links válidos: {len(df_links)}")
    print(f"Total de productos maestros únicos detectados: {len(maestros_count)}")
    print(f"Promedio de links por producto maestro: {len(df_links) / len(maestros_count):.2f}")
