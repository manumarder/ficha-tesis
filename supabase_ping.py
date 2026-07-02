import os
import sys
import urllib.request
import urllib.error
from urllib.parse import urlparse

# Load local .env if present (for local testing)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    def load_dotenv():
        env_path = os.path.join(os.path.dirname(__file__), ".env")
        if not os.path.exists(env_path):
            return False
        print(f"Loading environment variables from {env_path}")
        with open(env_path, encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
        return True

    load_dotenv()


def get_env(name):
    value = os.environ.get(name, "")
    return value.strip() if value and value.strip() else None


def get_supabase_url():
    supabase_url = get_env("SUPABASE_URL")
    if supabase_url:
        return supabase_url.rstrip("/")

    db_url = get_env("DATABASE_URL") or get_env("SUPABASE_DB_URL")
    if not db_url:
        return None

    parsed = urlparse(db_url)
    hostname = parsed.hostname or ""
    if hostname.endswith(".supabase.co"):
        return f"https://{hostname}"

    return None


def get_api_key_headers():
    key = get_env("SUPABASE_SERVICE_KEY") or get_env("SUPABASE_KEY") or get_env("SUPABASE_ANON_KEY")
    if not key:
        return {}
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }


def run_keepalive():
    supabase_url = get_supabase_url()
    if not supabase_url:
        print("Error: No se encontró SUPABASE_URL ni DATABASE_URL válido.")
        print("Define SUPABASE_URL o DATABASE_URL en tus secrets o .env.")
        sys.exit(1)

    health_url = f"{supabase_url}/auth/v1/health"
    print(f"Using Supabase URL: {supabase_url}")
    print(f"Health endpoint: {health_url}")

    headers = {
        "User-Agent": "supabase-keep-alive/1.0",
        "Accept": "application/json",
    }
    headers.update(get_api_key_headers())

    request = urllib.request.Request(health_url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            status = response.status
            body = response.read(200)
            print(f"HTTP keep-alive response: {status}")
            print(body.decode("utf-8", errors="replace"))
            if 200 <= status < 300:
                print("Keep-alive succeeded.")
                return
            print("Keep-alive returned a non-success status.")
            sys.exit(1)
    except urllib.error.HTTPError as e:
        print(f"HTTP keep-alive failed: {e.code} {e.reason}")
        try:
            error_body = e.read(200)
            print(error_body.decode("utf-8", errors="replace"))
        except Exception:
            pass
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"HTTP keep-alive network error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"HTTP keep-alive unexpected error: {type(e).__name__} {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_keepalive()
