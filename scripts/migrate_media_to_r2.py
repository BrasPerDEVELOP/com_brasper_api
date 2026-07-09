"""Migra archivos locales de media/ al bucket Cloudflare R2.

Ejecutar desde la raíz del proyecto:
  python -m scripts.migrate_media_to_r2
  python -m scripts.migrate_media_to_r2 --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from app.shared.services.file_service import file_service


async def migrate_media(source_dir: Path, dry_run: bool = False) -> int:
    if not source_dir.exists():
        print(f"No existe la carpeta {source_dir}")
        return 0

    files = [path for path in source_dir.rglob("*") if path.is_file()]
    if not files:
        print(f"No hay archivos en {source_dir}")
        return 0

    uploaded = 0
    for local_path in sorted(files):
        key = str(local_path.relative_to(source_dir)).replace("\\", "/")
        if dry_run:
            print(f"[dry-run] {local_path} -> r2://{key}")
            uploaded += 1
            continue

        await file_service.upload_local_file(local_path, key)
        print(f"Subido: {key}")
        uploaded += 1

    return uploaded


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrar media/ local a Cloudflare R2")
    parser.add_argument(
        "--source",
        default="media",
        help="Carpeta local con archivos (default: media)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo listar archivos que se subirían",
    )
    args = parser.parse_args()

    count = asyncio.run(migrate_media(Path(args.source), dry_run=args.dry_run))
    action = "Se subirían" if args.dry_run else "Subidos"
    print(f"{action} {count} archivo(s).")


if __name__ == "__main__":
    main()
