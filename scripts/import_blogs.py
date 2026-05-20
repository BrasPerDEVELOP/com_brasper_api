#!/usr/bin/env python
"""
Importa publicaciones de blog desde un CSV a la tabla blog.blog.

Uso desde la raiz del proyecto:

    poetry run python -m scripts.import_blogs /ruta/al/blogs.csv --dry-run
    poetry run python -m scripts.import_blogs /ruta/al/blogs.csv

El import es idempotente por slug: si el slug ya existe, actualiza el registro.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import re
import sys
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.dialects.postgresql import insert

# Permite leer campos HTML grandes con imagenes base64 embebidas.
csv.field_size_limit(sys.maxsize)

# Anade raiz del proyecto al path cuando se ejecuta como script.
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import app.models_registry  # noqa: F401,E402
from app.db.base import AsyncSessionLocal  # noqa: E402
from app.modules.blog.domain.models import Blog  # noqa: E402


REQUIRED_COLUMNS = {
    "title",
    "slug",
    "excerpt",
    "content",
    "category",
    "public_id",
    "read_time",
    "date",
    "language",
}


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def truncate(value: str | None, max_length: int) -> str | None:
    if value is None:
        return None
    return value[:max_length]


def parse_read_time(value: str | None) -> int | None:
    value = clean_text(value)
    if not value:
        return None

    match = re.search(r"\d+", value)
    return int(match.group(0)) if match else None


def parse_date(value: str | None) -> datetime | None:
    value = clean_text(value)
    if not value:
        return None

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.combine(datetime.strptime(value, fmt).date(), time.min, tzinfo=timezone.utc)
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"fecha invalida: {value}") from exc


def row_to_blog_values(row: dict[str, str], row_number: int) -> dict[str, Any]:
    title = clean_text(row.get("title"))
    slug = clean_text(row.get("slug"))
    content = clean_text(row.get("content"))
    language = clean_text(row.get("language"))

    missing = [
        field
        for field, value in {
            "title": title,
            "slug": slug,
            "content": content,
            "language": language,
        }.items()
        if not value
    ]
    if missing:
        raise ValueError(f"fila {row_number}: campos obligatorios vacios: {', '.join(missing)}")

    return {
        "id": uuid4(),
        "title": truncate(title, 255),
        "slug": truncate(slug, 255),
        "excerpt": clean_text(row.get("excerpt")),
        "content": content,
        "category": truncate(clean_text(row.get("category")), 100),
        "public_id": truncate(clean_text(row.get("public_id")), 100),
        "read_time": parse_read_time(row.get("read_time")),
        "date": parse_date(row.get("date")),
        "language": truncate(language, 10),
        "enable": True,
        "deleted": False,
    }


def read_csv(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    valid_rows: list[dict[str, Any]] = []
    errors: list[str] = []

    with path.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        columns = set(reader.fieldnames or [])
        missing_columns = REQUIRED_COLUMNS - columns
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(f"faltan columnas requeridas: {missing}")

        for row_number, row in enumerate(reader, start=2):
            try:
                valid_rows.append(row_to_blog_values(row, row_number))
            except Exception as exc:
                errors.append(str(exc))

    return valid_rows, errors


def chunks(rows: list[dict[str, Any]], batch_size: int):
    for index in range(0, len(rows), batch_size):
        yield rows[index : index + batch_size]


async def import_blogs(path: Path, *, batch_size: int, dry_run: bool) -> None:
    rows, errors = read_csv(path)

    print(f"Archivo: {path}")
    print(f"Filas validas: {len(rows)}")
    print(f"Filas omitidas: {len(errors)}")
    for error in errors[:20]:
        print(f"  - {error}")
    if len(errors) > 20:
        print(f"  ... {len(errors) - 20} errores adicionales")

    if dry_run:
        print("Dry-run activo: no se escribio en la base de datos.")
        return

    if not rows:
        print("No hay filas validas para importar.")
        return

    inserted_or_updated = 0
    async with AsyncSessionLocal() as session:
        for batch in chunks(rows, batch_size):
            stmt = insert(Blog).values(batch)
            excluded = stmt.excluded
            update_values = {
                "title": excluded.title,
                "excerpt": excluded.excerpt,
                "content": excluded.content,
                "category": excluded.category,
                "public_id": excluded.public_id,
                "read_time": excluded.read_time,
                "date": excluded.date,
                "language": excluded.language,
                "enable": excluded.enable,
                "deleted": False,
                "updated_at": datetime.now(timezone.utc),
            }
            stmt = stmt.on_conflict_do_update(
                index_elements=[Blog.slug],
                set_=update_values,
            )
            await session.execute(stmt)
            inserted_or_updated += len(batch)

        await session.commit()

    print(f"Listo. Registros insertados/actualizados: {inserted_or_updated}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Importa blogs desde CSV.")
    parser.add_argument("csv_path", type=Path, help="Ruta del CSV a importar.")
    parser.add_argument("--batch-size", type=int, default=100, help="Cantidad de filas por lote.")
    parser.add_argument("--dry-run", action="store_true", help="Valida el CSV sin insertar datos.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(import_blogs(args.csv_path, batch_size=args.batch_size, dry_run=args.dry_run))
