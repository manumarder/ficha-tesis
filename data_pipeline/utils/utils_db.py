"""
Implementación local de ConexionBaseDatos para reemplazar etl_modular
"""
import pymysql
from sqlalchemy import create_engine, text
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class ConexionBaseDatos:
    """Clase para manejar conexiones a base de datos MySQL/Postgres"""
    
    def __init__(self, host, user, password, database, port=None, database_url='', ssl_mode='prefer'):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.port = port
        self.database_url = database_url
        self.ssl_mode = ssl_mode
        self.connection = None
        self.engine = None
        
    def connect_db(self):
        """Establece conexión con la base de datos (Soporta MySQL y Postgres via port)"""
        try:
            # Determinamos si es Postgres o MySQL basado en el puerto
            # default mysql: 3306, postgres: 5432
            is_postgres = str(self.port) == '5432'
            
            if self.database_url:
                # Soporte explícito para URLs de conexión, útil para Supabase.
                # Si la URL ya trae '?sslmode=require', no la reescribimos innecesariamente.
                url = self.database_url
                if 'sslmode=' not in url and self.ssl_mode:
                    url = f"{url}?sslmode={self.ssl_mode}"
                self.engine = create_engine(url)
                self.connection = self.engine.raw_connection()
                db_type = "PostgreSQL" if "postgres" in url else "MySQL"
                logger.info(f"Conexión a base de datos {db_type} establecida correctamente")
                return True

            if is_postgres:
                import psycopg2
                # Conexión directa con psycopg2
                self.connection = psycopg2.connect(
                    host=self.host,
                    user=self.user,
                    password=self.password,
                    database=self.database,
                    port=self.port,
                    sslmode=self.ssl_mode
                )
                # Engine de SQLAlchemy para Postgres
                connection_string = f"postgresql+psycopg2://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
                self.engine = create_engine(connection_string, connect_args={"sslmode": self.ssl_mode})
            else:
                # Conexión directa con pymysql
                self.connection = pymysql.connect(
                    host=self.host,
                    user=self.user,
                    password=self.password,
                    database=self.database,
                    port=int(self.port) if self.port else 3306,
                    charset='utf8mb4'
                )
                # Engine de SQLAlchemy para MySQL
                port_str = f":{self.port}" if self.port else ""
                connection_string = f"mysql+pymysql://{self.user}:{self.password}@{self.host}{port_str}/{self.database}"
                self.engine = create_engine(connection_string)
            
            db_type = "PostgreSQL" if is_postgres else "MySQL"
            logger.info(f"Conexión a base de datos {db_type} establecida correctamente")
            return True
            
        except Exception as e:
            logger.error(f"Error conectando a la base de datos: {e}")
            return False
    
    def insert_append(self, table_name, df):
        """Inserta datos usando append (sin reemplazar)"""
        try:
            if self.engine is None:
                logger.error("No hay conexión activa a la base de datos")
                return False

            # method='multi' junta varias filas por INSERT; sin chunksize (~2500 filas) una sola
            # sentencia supera el límite de placeholders del driver (error gkpj / truncated params).
            chunk_size = 400

            df.to_sql(
                name=table_name,
                con=self.engine,
                if_exists='append',
                index=False,
                method='multi',
                chunksize=chunk_size,
            )

            logger.info(f"Datos insertados correctamente en {table_name}: {len(df)} registros")
            return True

        except Exception as e:
            logger.error(f"Error insertando datos: {e}")
            return False
    
    def execute_query(self, query, params=None):
        """Ejecuta una consulta SQL"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, params)
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Error ejecutando consulta: {e}")
            return None
    
    def close_connections(self):
        """Cierra las conexiones"""
        try:
            if self.connection:
                self.connection.close()
                logger.info("Conexión pymysql cerrada")
                
            if self.engine:
                self.engine.dispose()
                logger.info("Engine SQLAlchemy cerrado")
                
        except Exception as e:
            logger.error(f"Error cerrando conexiones: {e}")