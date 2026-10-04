"""Local HTTP entry point for the iqAudi360 dashboard backend.

Run ``python backend.py`` to serve the existing Flask dashboard on localhost.
This file deliberately starts no scans and makes no outbound requests.
"""

from __future__ import annotations

import argparse
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from flask import Flask, jsonify

from strix.gui.app import create_app


def _version() -> str:
    """Return the installed package version, with a source-tree fallback."""
    try:
        return version("iqaudi360")
    except PackageNotFoundError:
        return "1.6.2"


def create_backend() -> Flask:
    """Create the dashboard application with a lightweight health endpoint."""
    app = create_app()

    @app.get("/api/health")
    def health() -> Any:
        return jsonify({"status": "ok", "service": "iqaudi360", "version": _version()})

    return app


def main() -> None:
    """Start the backend, binding only to localhost unless explicitly changed."""
    parser = argparse.ArgumentParser(description="Run the iqAudi360 local backend.")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind.")
    parser.add_argument("--port", type=int, default=5050, help="TCP port to bind.")
    parser.add_argument("--debug", action="store_true", help="Enable Flask debug mode.")
    args = parser.parse_args()

    create_backend().run(
        host=args.host,
        port=args.port,
        debug=args.debug,
        threaded=True,
        use_reloader=False,
    )


if __name__ == "__main__":
    main()
