# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sys

# Ensure project root is on sys.path when running as a script
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from waitress import serve

from ytanalyzer.webapp.app import create_app
from ytanalyzer.config import Config


def main():
    app = create_app(Config())
    # Reduce thread count to mitigate SQLite write lock contention
    serve(app, host="127.0.0.1", port=5000, threads=4)


if __name__ == "__main__":
    main()
