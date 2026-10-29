"""
Launch the read-only dashboard on 127.0.0.1 (never 0.0.0.0).

    .venv/Scripts/python.exe main.py web [--port 8000]
    .venv/Scripts/python.exe -m web [--port 8000]
"""

import argparse

import uvicorn

HOST = '127.0.0.1'
DEFAULT_PORT = 8000


def serve(port: int = DEFAULT_PORT) -> None:
    from web.app import create_app
    uvicorn.run(create_app(), host=HOST, port=port, log_level='info')


def main() -> None:
    parser = argparse.ArgumentParser(description='Alpha Farm dashboard (read-only, 127.0.0.1)')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT)
    serve(parser.parse_args().port)
