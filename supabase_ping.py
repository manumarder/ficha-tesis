import os
import psycopg2
import sys

# Intentamos cargar el archivo .env local si existe (para cuando probás en tu PC)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # Si no está instalada, en GitHub no pasa nada porque usa las variables de entorno directas

def run_ping():
    # Buscamos primero la URL completa. Si no está, la armamos con los datos del .env
    db_url = os.environ.get("DATABASE_URL")
    
    if not db_url:
        # Si no tenés DATABASE_URL armada, usamos los componentes individuales de tu .env
        user = os.environ.get("DB_USER")
        password = os.environ.get("DB_PASSWORD")
        host = os.environ.get("DB_HOST")
        port = os.environ.get("DB_PORT", "5432")
        name = os.environ.get("DB_NAME", "postgres")
        
        if all([user, password, host, name]):
            db_url = f"postgresql://{user}:{password}@{host}:{port}/{name}"
        else:
            print("Error: No se encontraron las credenciales de la Base de Datos en el entorno.")
            sys.exit(1)
        
    try:
        # Intentamos la conexión a Supabase
        connection = psycopg2.connect(db_url)
        cursor = connection.cursor()
        
        # Consulta rápida de actividad
        cursor.execute("SELECT 1;")
        result = cursor.fetchone()
        
        print(f"¡Ping exitoso! Conectado a {host or 'Supabase'}. Respuesta: {result}")
        
        cursor.close()
        connection.close()
        
    except Exception as e:
        print(f"Error al conectar con la Base de Datos: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_ping()