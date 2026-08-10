"""soft_delete_aware_user_uniques

Revision ID: 063
Revises: 062
Create Date: 2026-08-10 12:00:00.000000

El borrado de usuarios es lógico (`deleted = true`), pero `email`,
`document_number` y `(document_type, document_number)` tenían restricciones
únicas incondicionales. La fila borrada seguía ocupando el índice, así que tras
"eliminar" un cliente era imposible volver a registrarlo con su mismo correo o
documento: el alta fallaba con 409 «Conflicto de datos».

Se reemplazan por índices únicos **parciales** que solo miran las filas vivas
(`WHERE deleted = false`), que es el patrón que corresponde a un borrado lógico.

Además se marcan como borradas las identificaciones de usuarios ya borrados: sin
ese backfill el índice parcial de `user_identifications` no las excluiría y el
documento seguiría bloqueado.

NOTA: si en la tabla hubiera duplicados entre filas NO borradas, la creación del
índice fallará. Es el comportamiento correcto —esos duplicados son datos rotos
que hay que resolver a mano—, pero conviene revisarlo antes de aplicar:

    SELECT email, count(*) FROM "user"."user"
    WHERE deleted = false AND email IS NOT NULL
    GROUP BY email HAVING count(*) > 1;
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "063"
down_revision: Union[str, None] = "062"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "user"


def upgrade() -> None:
    # 1) Las identificaciones de usuarios ya borrados quedan marcadas también.
    #    El borrado del usuario nunca las tocó, así que hoy siguen bloqueando el
    #    documento aunque el usuario esté fuera de circulación.
    op.execute(
        sa.text(
            """
            UPDATE "user".user_identifications AS ui
            SET deleted = true
            FROM "user"."user" AS u
            WHERE ui.user_id = u.id
              AND u.deleted = true
              AND ui.deleted = false
            """
        )
    )

    # 2) `email` y `document_number`: la constraint la creó SQLAlchemy con el
    #    nombre por defecto de PostgreSQL. Se eliminan de forma tolerante porque
    #    su nombre exacto depende de cómo se creó la tabla en cada entorno.
    op.execute(sa.text('ALTER TABLE "user"."user" DROP CONSTRAINT IF EXISTS user_email_key'))
    op.execute(
        sa.text('ALTER TABLE "user"."user" DROP CONSTRAINT IF EXISTS user_document_number_key')
    )
    op.execute(sa.text('DROP INDEX IF EXISTS "user".user_email_key'))
    op.execute(sa.text('DROP INDEX IF EXISTS "user".user_document_number_key'))

    op.execute(
        sa.text(
            """
            CREATE UNIQUE INDEX uq_user_email_alive
            ON "user"."user" (email)
            WHERE deleted = false AND email IS NOT NULL
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE UNIQUE INDEX uq_user_document_number_alive
            ON "user"."user" (document_number)
            WHERE deleted = false AND document_number IS NOT NULL
            """
        )
    )

    # 3) Identificaciones: misma idea sobre el par (tipo, número).
    op.execute(
        sa.text(
            'ALTER TABLE "user".user_identifications '
            "DROP CONSTRAINT IF EXISTS uq_user_identifications_type_number"
        )
    )
    op.execute(
        sa.text(
            """
            CREATE UNIQUE INDEX uq_user_identifications_type_number_alive
            ON "user".user_identifications (document_type, document_number)
            WHERE deleted = false
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text('DROP INDEX IF EXISTS "user".uq_user_identifications_type_number_alive'))
    op.execute(sa.text('DROP INDEX IF EXISTS "user".uq_user_email_alive'))
    op.execute(sa.text('DROP INDEX IF EXISTS "user".uq_user_document_number_alive'))

    # Al volver atrás, las restricciones incondicionales solo se pueden recrear
    # si no quedan duplicados entre filas borradas y vivas.
    op.create_unique_constraint(
        "uq_user_identifications_type_number",
        "user_identifications",
        ["document_type", "document_number"],
        schema=schema,
    )
    op.create_unique_constraint("user_email_key", "user", ["email"], schema=schema)
    op.create_unique_constraint(
        "user_document_number_key", "user", ["document_number"], schema=schema
    )
