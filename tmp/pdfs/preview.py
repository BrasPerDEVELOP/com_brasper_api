import json
from pathlib import Path
from types import SimpleNamespace
import psycopg2
from psycopg2.extras import RealDictCursor
from app.core.settings import get_settings
from app.modules.billing.infrastructure.branded_pdf import render_boleta

connection = psycopg2.connect(get_settings().database_url.replace('postgresql+asyncpg://', 'postgresql://'))
connection.set_session(readonly=True)
with connection.cursor(cursor_factory=RealDictCursor) as cur:
    cur.execute('''SELECT i.*, u.document_type AS profile_type, u.document_number AS profile_number
      FROM billing.invoices i
      JOIN "transaction".transactions t ON t.id = i.transaction_id
      JOIN "user"."user" u ON u.id = t.user_id
      WHERE i.file_name = %s AND NOT i.deleted''', ('20611936428-03-BB02-00000002',))
    data = dict(cur.fetchone())
connection.close()
data['full_number'] = f"{data['series']}-{data['number']:08d}"
Path('tmp/pdfs/invoice.json').write_text(json.dumps(data, default=str), encoding='utf-8')
source = Path(r'C:\Users\rodri\Downloads\20611936428-03-BB02-00000002.pdf').read_bytes()
pdf = render_boleta(SimpleNamespace(**data), source, profile_document_type=data['profile_type'], profile_document_number=data['profile_number'])
Path('output/pdf').mkdir(parents=True, exist_ok=True)
Path('output/pdf/20611936428-03-BB02-00000002-brasper.pdf').write_bytes(pdf)
print(f'PDF generado: {len(pdf)} bytes; documento registrado: {bool(data["profile_number"])}')
