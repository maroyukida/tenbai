import json
import os
import sys

# Ensure project root is on sys.path
ROOT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(ROOT)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ytanalyzer.webapp.app import create_app
from ytanalyzer.config import Config


def main():
    app = create_app(Config())
    client = app.test_client()

    def check(path: str):
        resp = client.get(path)
        print(f"GET {path} -> {resp.status_code} {resp.content_type}")
        # Print short preview for HTML, JSON summary for JSON
        ctype = resp.headers.get("Content-Type", "")
        if "json" in ctype:
            try:
                data = resp.get_json()
                if isinstance(data, dict):
                    keys = list(data.keys())
                    if "total" in data:
                        print(f"  JSON keys: {keys}; total={data['total']}")
                    else:
                        print(f"  JSON keys: {keys}")
                else:
                    print(f"  JSON type: {type(data).__name__}")
            except Exception as e:
                print(f"  JSON parse error: {e}")
        elif "html" in ctype:
            body = resp.get_data(as_text=True)
            print(f"  HTML bytes: {len(body)}; head: {body[:120].replace('\n',' ')}")
        else:
            print("  (no preview)")

    # Probe key routes
    for p in [
        "/trending",
        "/trending?view=list",
        "/trending.json",
        "/resale/items",
        "/resale/items.json",
    ]:
        try:
            check(p)
        except Exception as e:
            print(f"Error probing {p}: {e}")


if __name__ == "__main__":
    main()
