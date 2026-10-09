"""Driver E2E (laboratorio) de la vinculación de identidad del chat: API + bot + PGlite.

Pasos (todo local, 127.0.0.1, datos sintéticos):
  1. Arranca PGlite (``pglite-socket``, ``--db=memory://``) en ``--pg-port``.
  2. Migra a ``head`` con ``scripts/validate_migrations_pglite.py``.
  3. Arranca el arnés ``scripts/e2e_identity_link_pglite.py`` (app real, uvicorn :8010).
  4. Ejecuta ``com_brasper_ia/backend/tests/identity_e2e.py`` con el venv del bot.
  5. Apaga el arnés y PGlite (siempre, también ante errores).

El secreto de integración y la contraseña de la cuenta de servicio son valores
aleatorios sintéticos generados aquí y pasados a ambos procesos por variables
(``E2E_SHARED_SECRET``, ``E2E_SERVICE_USERNAME``/``E2E_SERVICE_PASSWORD``); no se
imprimen ni se guardan.

Uso (desde la raíz de com_brasper_api)::

    .venv/Scripts/python.exe scripts/e2e_identity_link_driver.py \
        --pglite <carpeta con node_modules/@electric-sql/pglite-socket> [--auth-required 0|1]

``--auth-required 0`` (por defecto) corre como ``ENVIRONMENT=development``;
``1`` reproduce la configuración obligatoria fuera de desarrollo.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BOT = ROOT.parent / "com_brasper_ia"


def wait_port(port: int, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket() as s:
            s.settimeout(0.5)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.3)
    return False


def port_free(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) != 0


def stop(proc: subprocess.Popen | None, name: str) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(10)
    except subprocess.TimeoutExpired:
        proc.kill()
    print(f"[driver] {name} detenido", flush=True)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--pglite", required=True, help="carpeta con node_modules/@electric-sql/pglite-socket")
    p.add_argument("--pg-port", type=int, default=55450)
    p.add_argument("--api-port", type=int, default=8010)
    p.add_argument("--bot-repo", default=str(DEFAULT_BOT))
    p.add_argument("--auth-required", choices=["0", "1"], default="0")
    p.add_argument("--logs", default=None, help="carpeta para logs y results.json (por defecto, temporal)")
    args = p.parse_args()

    for port in (args.pg_port, args.api_port):
        if not port_free(port):
            print(f"[driver] el puerto {port} está ocupado; aborto", file=sys.stderr)
            return 2
    logs = Path(args.logs or tempfile.mkdtemp(prefix="e2e_identity_"))
    logs.mkdir(parents=True, exist_ok=True)
    api_py = ROOT / ".venv" / "Scripts" / "python.exe"
    bot_repo = Path(args.bot_repo)
    bot_py = bot_repo / ".venv" / "Scripts" / "python.exe"
    server_js = Path(args.pglite) / "node_modules/@electric-sql/pglite-socket/dist/scripts/server.js"
    env = {**os.environ, "E2E_SHARED_SECRET": secrets.token_urlsafe(32), "PYTHONIOENCODING": "utf-8",
           "E2E_AUTH_REQUIRED": args.auth_required, "E2E_API_BASE": f"http://127.0.0.1:{args.api_port}",
           "E2E_RESULTS": str(logs / f"results_auth{args.auth_required}.json"),
           # Cuenta de servicio sintética: el arnés la siembra con hash real y el bot entra por /auth/login.
           "E2E_SERVICE_USERNAME": "svcbrasperiae2e", "E2E_SERVICE_PASSWORD": secrets.token_urlsafe(24)}

    pg = api = None
    code = 1
    try:
        pg = subprocess.Popen(["node", str(server_js), "--db=memory://", f"--port={args.pg_port}"],
                              stdout=open(logs / "pglite.log", "w"), stderr=subprocess.STDOUT)
        if not wait_port(args.pg_port, 30):
            raise RuntimeError("PGlite no arrancó")
        print(f"[driver] PGlite :{args.pg_port}", flush=True)
        mig = subprocess.run([str(api_py), "scripts/validate_migrations_pglite.py", "--port", str(args.pg_port),
                              "upgrade", "head"], cwd=ROOT, capture_output=True, text=True, timeout=600,
                             encoding="utf-8", errors="replace")
        (logs / "migrate.log").write_text(mig.stdout + mig.stderr, encoding="utf-8")
        last = (mig.stdout.strip().splitlines() or [""])[-1]
        print(f"[driver] migración: {last}", flush=True)
        if mig.returncode != 0 or '"084"' not in last:
            raise RuntimeError("migración a head falló (ver migrate.log)")

        api = subprocess.Popen([str(api_py), "scripts/e2e_identity_link_pglite.py", "--pg-port", str(args.pg_port),
                                "--port", str(args.api_port)], cwd=ROOT, env=env,
                               stdout=open(logs / f"api_auth{args.auth_required}.log", "w", encoding="utf-8"),
                               stderr=subprocess.STDOUT)
        deadline = time.time() + 60
        while True:
            try:
                with urlopen(f"http://127.0.0.1:{args.api_port}/health", timeout=2) as r:
                    if json.load(r).get("status") == "ok":
                        break
            except OSError:
                pass
            if time.time() > deadline or api.poll() is not None:
                raise RuntimeError("el arnés de la API no arrancó (ver api_auth*.log)")
            time.sleep(0.5)
        print(f"[driver] API real en http://127.0.0.1:{args.api_port} (AUTH_REQUIRED={args.auth_required})",
              flush=True)

        bot = subprocess.run([str(bot_py), "tests/identity_e2e.py"], cwd=bot_repo / "backend", env=env,
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
        out = bot.stdout + bot.stderr
        (logs / f"bot_auth{args.auth_required}.log").write_text(out, encoding="utf-8")
        print(out, flush=True)
        code = bot.returncode
    except Exception as exc:  # noqa: BLE001
        print(f"[driver] ERROR: {exc}", file=sys.stderr, flush=True)
        code = 1
    finally:
        if api is not None and api.poll() is None:
            try:
                from urllib.request import Request
                urlopen(Request(f"http://127.0.0.1:{args.api_port}/__e2e/shutdown", method="POST",
                                headers={"X-E2E-Control": env["E2E_SHARED_SECRET"]}), timeout=3)
                api.wait(10)
            except Exception:  # noqa: BLE001
                pass
        stop(api, "arnés API")
        stop(pg, "PGlite")
        freed = port_free(args.pg_port) and port_free(args.api_port)
        print(f"[driver] puertos liberados: {freed}", flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
