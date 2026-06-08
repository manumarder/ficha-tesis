import os
import sys
import socket
import ssl
from urllib.parse import urlparse

# Cargar .env si existe
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def test_dns(host: str):
    print('\n[DNS] Resolviendo:', host)
    try:
        print('  ->', socket.gethostbyname(host))
        return True
    except Exception as e:
        print('  -> ERROR:', type(e).__name__, e)
        return False


def test_tcp(host: str, port: int, timeout=10):
    print('\n[TCP] Probando conexión:', host, port)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            print('  -> OK: TCP connect succeeded')
            return True
    except Exception as e:
        print('  -> ERROR:', type(e).__name__, e)
        return False


def test_ssl(host: str, port: int, timeout=10):
    print('\n[SSL] Probando TLS:', host, port)
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host):
                print('  -> OK: TLS handshake succeeded')
                return True
    except Exception as e:
        print('  -> ERROR:', type(e).__name__, e)
        return False


print('=== DIAGNÓSTICO DE CONEXIÓN SUPABASE ===')
print('Python:', sys.version)

url = os.getenv('DATABASE_URL', '').strip()
print('\nDATABASE_URL:', url or '(vacía)')

if url:
    p = urlparse(url)
    print('  scheme=', p.scheme)
    print('  hostname=', p.hostname)
    print('  port=', p.port)
    print('  username=', p.username)
    print('  database=', p.path.lstrip('/'))

host = (urlparse(url).hostname if url else '').strip() or os.getenv('DB_HOST', '').strip()
port = (urlparse(url).port if url else None) or int(os.getenv('DB_PORT', 0) or 0)
user = (urlparse(url).username if url else '').strip() or os.getenv('DB_USER', '').strip()
password = (urlparse(url).password if url else '').strip() or os.getenv('DB_PASSWORD', '').strip()

print('\nVariables usadas por el script:')
print('  DB_HOST=', host)
print('  DB_PORT=', port)
print('  DB_USER=', user)
print('  DB_PASSWORD=', '***' if password else '(vacía)')

if host and port:
    test_dns(host)
    test_tcp(host, port)
    test_ssl(host, port)
else:
    print('\nNo hay host/port para probar. Completa .env con DATABASE_URL o DB_HOST/DB_PORT.')

print('\n=== FIN DEL DIAGNÓSTICO ===')
