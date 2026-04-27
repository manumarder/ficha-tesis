import os
from dotenv import load_dotenv
from dataclasses import dataclass, field

# Cargar variables de entorno desde el archivo .env (si existe)
load_dotenv()

@dataclass
class DatabaseSettings:
    host: str = os.getenv("DB_HOST", "localhost")
    port: int = int(os.getenv("DB_PORT", 5432))
    user: str = os.getenv("DB_USER", "postgres")
    password: str = os.getenv("DB_PASSWORD", "")
    name: str = os.getenv("DB_NAME", "canasta_basica_super")

@dataclass
class GCPSettings:
    project_id: str = os.getenv("GCP_PROJECT_ID", "")
    credentials_path: str = os.getenv("GCP_CREDENTIALS_PATH", "")

@dataclass
class AppSettings:
    environment: str = os.getenv("ENVIRONMENT", "development")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    
    db: DatabaseSettings = field(default_factory=DatabaseSettings)
    gcp: GCPSettings = field(default_factory=GCPSettings)

# Instancia global de configuración para usar en toda la app
# Ejemplo de uso: 
# from config.settings import settings
# print(settings.db.host)
settings = AppSettings()
