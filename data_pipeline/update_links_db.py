import os
import sys
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Este script toma el archivo links_corregidos.csv generado por el botón del HTML
# (que debés guardar dentro de la carpeta files/), se conecta a tu base de datos cloud 
# de Supabase PostgreSQL utilizando la variable de entorno nativa de tu .env (DATABASE_URL) 
# y actualiza el catálogo masivamente.

def main():
    load_dotenv()
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    files_dir = os.path.join(base_dir, 'files')
    a_modificar_csv = os.path.join(files_dir, 'links_a_modificar.csv')
    
    # Localizar el archivo descargado desde la interfaz web
    candidatos = [
        os.path.join(files_dir, f) 
        for f in os.listdir(files_dir) 
        if f.startswith('links_corregidos') and f.endswith('.csv')
    ]
    
    if not candidatos:
        print(f"[ERROR] No se encontró el archivo 'links_corregidos.csv' en: {files_dir}")
        print("💡 Recuerda descargar el archivo desde el HTML y guardarlo en esa carpeta.")
        return
        
    correcciones_csv = max(candidatos, key=os.path.getmtime)
    print(f"🚀 Procesando correcciones desde: {os.path.basename(correcciones_csv)}")
    
    df_correcciones = pd.read_csv(correcciones_csv)
    
    # Levantamos la URL de conexión de Supabase desde tu .env existente
    supabase_url = os.getenv('DATABASE_URL')
    if not supabase_url:
        print("[ERROR] Variable DATABASE_URL no encontrada en el archivo .env")
        return
        
    # Adaptación para compatibilidad de SQLAlchemy con cadenas postgresql://
    if supabase_url.startswith("postgresql://"):
        supabase_url = supabase_url.replace("postgresql://", "postgresql+psycopg2://", 1)
        
    engine = create_engine(supabase_url)
    total_modificados = 0
    
    try:
        with engine.begin() as conn:
            for _, row in df_correcciones.iterrows():
                viejo = str(row['viejo_link']).strip()
                nuevo = str(row['nuevo_link']).strip()
                
                if not viejo or not nuevo or viejo == 'nan' or nuevo == 'nan':
                    continue
                
                # Caso A: El usuario determinó la baja definitiva escribiendo "NO"
                if nuevo.upper() == 'NO':
                    res = conn.execute(
                        text("SELECT id FROM link_productos WHERE url_producto = :link"),
                        {"link": viejo}
                    ).fetchone()
                    
                    if res:
                        id_link = res[0]
                        conn.execute(
                            text("UPDATE link_productos SET url_producto = :nuevo, activo = false WHERE id = :id"),
                            {"nuevo": f"BAJA_{id_link}", "id": id_link}
                        )
                        total_modificados += 1
                        print(f"🗑️ [BAJA] Discontinuado: ...{viejo[-25:]}")
                
                # Caso B: El usuario ingresó una nueva URL válida de reemplazo
                else:
                    conn.execute(
                        text("UPDATE link_productos SET url_producto = :nuevo, activo = true WHERE url_producto = :link"),
                        {"nuevo": nuevo, "link": viejo}
                    )
                    total_modificados += 1
                    print(f"🔄 [REEMPLAZO] Actualizado: ...{viejo[-25:]} ➡️ ...{nuevo[-25:]}")
                    
    except Exception as e:
        print(f"❌ [ERROR SYSTEM] Error en la transacción SQL: {e}")
        return
    finally:
        engine.dispose()
        
    print(f"\n✨ [ÉXITO] Saneamiento completado. {total_modificados} registros modificados en Supabase Cloud.")
    
    # Limpieza preventiva del archivo puente
    if os.path.exists(a_modificar_csv):
        os.remove(a_modificar_csv)

if __name__ == "__main__":
    main()