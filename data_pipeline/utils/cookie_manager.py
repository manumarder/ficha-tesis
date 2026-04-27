"""
Módulo centralizado para manejo de cookies de todos los supermercados
Organiza y gestiona las cookies en un directorio único
"""
import os
import pickle
import logging
from pathlib import Path
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


class CookieManager:
    """Gestor centralizado de cookies para todos los supermercados"""
    
    def __init__(self, base_dir: str):
        """
        Inicializa el gestor de cookies
        
        Args:
            base_dir: Directorio base del proyecto (donde está main.py)
        """
        self.base_dir = Path(base_dir)
        self.cookies_dir = self.base_dir / 'cookies'
        self.cookies_dir.mkdir(exist_ok=True)
        
        logger.info(f"[COOKIES] Directorio de cookies: {self.cookies_dir}")
    
    def get_cookie_path(self, supermarket: str) -> Path:
        """
        Obtiene la ruta del archivo de cookies para un supermercado
        
        Args:
            supermarket: Nombre del supermercado (ej: 'carrefour', 'masonline')
            
        Returns:
            Path al archivo de cookies
        """
        return self.cookies_dir / f"{supermarket}_cookies.pkl"
    
    def save_cookies(self, supermarket: str, cookies: List[Dict]) -> bool:
        """
        Guarda las cookies de un supermercado
        
        Args:
            supermarket: Nombre del supermercado
            cookies: Lista de cookies a guardar
            
        Returns:
            True si se guardó correctamente, False en caso contrario
        """
        try:
            cookie_path = self.get_cookie_path(supermarket)
            with open(cookie_path, 'wb') as f:
                pickle.dump(cookies, f)
            logger.debug(f"[COOKIES] Cookies de {supermarket} guardadas en {cookie_path}")
            return True
        except Exception as e:
            logger.error(f"[COOKIES] Error guardando cookies de {supermarket}: {e}")
            return False
    
    def load_cookies(self, supermarket: str) -> Optional[List[Dict]]:
        """
        Carga las cookies de un supermercado
        
        Args:
            supermarket: Nombre del supermercado
            
        Returns:
            Lista de cookies o None si no existen o hay error
        """
        cookie_path = self.get_cookie_path(supermarket)
        
        if not cookie_path.exists():
            logger.debug(f"[COOKIES] No hay cookies guardadas para {supermarket}")
            return None
        
        try:
            with open(cookie_path, 'rb') as f:
                cookies = pickle.load(f)
            logger.debug(f"[COOKIES] Cookies de {supermarket} cargadas desde {cookie_path}")
            return cookies
        except Exception as e:
            logger.error(f"[COOKIES] Error cargando cookies de {supermarket}: {e}")
            return None
    
    def delete_cookies(self, supermarket: str) -> bool:
        """
        Elimina las cookies de un supermercado
        
        Args:
            supermarket: Nombre del supermercado
            
        Returns:
            True si se eliminaron correctamente, False en caso contrario
        """
        cookie_path = self.get_cookie_path(supermarket)
        
        if not cookie_path.exists():
            return True
        
        try:
            cookie_path.unlink()
            logger.info(f"[COOKIES] Cookies de {supermarket} eliminadas")
            return True
        except Exception as e:
            logger.error(f"[COOKIES] Error eliminando cookies de {supermarket}: {e}")
            return False
    
    def cookies_exist(self, supermarket: str) -> bool:
        """
        Verifica si existen cookies guardadas para un supermercado
        
        Args:
            supermarket: Nombre del supermercado
            
        Returns:
            True si existen cookies, False en caso contrario
        """
        return self.get_cookie_path(supermarket).exists()
    
    def migrate_old_cookies(self) -> Dict[str, bool]:
        """
        Migra cookies antiguas desde ubicaciones dispersas al directorio centralizado
        
        Returns:
            Diccionario con el resultado de la migración por supermercado
        """
        results = {}
        
        # Mapeo de ubicaciones antiguas a nuevas
        old_locations = {
            'carrefour': [
                self.base_dir / 'carrefour_cookies.pkl',
                self.base_dir / 'files' / 'carrefour_cookies.pkl',
            ],
            'masonline': [
                self.base_dir / 'masonline_cookies.pkl',
            ],
            'dia': [
                self.base_dir / 'dia_cookies.pkl',
            ]
        }
        
        for supermarket, old_paths in old_locations.items():
            migrated = False
            new_path = self.get_cookie_path(supermarket)
            
            # Si ya existe en la nueva ubicación, no migrar
            if new_path.exists():
                results[supermarket] = True
                continue
            
            # Buscar en ubicaciones antiguas
            for old_path in old_paths:
                if old_path.exists():
                    try:
                        # Copiar cookies
                        with open(old_path, 'rb') as f:
                            cookies = pickle.load(f)
                        
                        self.save_cookies(supermarket, cookies)
                        logger.info(f"[COOKIES] Migradas cookies de {supermarket} desde {old_path}")
                        migrated = True
                        
                        # Opcional: eliminar archivo antiguo
                        # old_path.unlink()
                        break
                    except Exception as e:
                        logger.warning(f"[COOKIES] Error migrando cookies de {supermarket} desde {old_path}: {e}")
            
            results[supermarket] = migrated
        
        return results


