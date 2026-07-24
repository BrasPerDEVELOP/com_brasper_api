"""Operaciones limitadas que el bot Brasper puede ejecutar sobre la fuente oficial."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.coin.domain.enums import Currency
from app.modules.transactions.domain.models import Bank, Transaction
from app.modules.users.domain.models import User, UserIdentification
from app.modules.brasper.application.ai_schemas import (
    AIClientDTO,
    AIClientLookupDTO,
    AIClientUpsertCmd,
    AIClientUpsertDTO,
    AIDepositAccountDTO,
)


def normalize_name(value: str) -> str:
    return " ".join((value or "").casefold().split())


class BrasperAIService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _is_first_transfer(self, user_id: UUID) -> bool:
        count = await self.session.scalar(select(func.count(Transaction.id)).where(
            Transaction.user_id == user_id,
            Transaction.deleted.is_(False),
        ))
        return int(count or 0) == 0

    async def _client_dto(self, user: User) -> AIClientDTO:
        return AIClientDTO(
            id=user.id,
            names=user.names,
            lastnames=user.lastnames,
            code_phone=user.code_phone,
            phone=str(user.phone) if user.phone is not None else None,
            document_type=user.document_type,
            document_verified=bool(user.document_number or user.identifications),
            is_first_transfer=await self._is_first_transfer(user.id),
        )

    def _active_clients(self):
        return select(User).options(selectinload(User.identifications)).where(
            User.role == "client",
            User.deleted.is_(False),
            User.enable.is_(True),
        )

    async def lookup_client(self, *, code_phone: str | None, phone: int | None,
                            full_name: str | None) -> AIClientLookupDTO:
        stmt = self._active_clients()
        if phone is not None:
            stmt = stmt.where(User.phone == phone)
            if code_phone:
                stmt = stmt.where(User.code_phone == code_phone)
        elif full_name:
            normalized = normalize_name(full_name)
            # PostgreSQL normaliza espacios; la comparación conserva tildes para
            # evitar coincidencias demasiado amplias por nombre.
            db_name = func.lower(func.regexp_replace(
                func.concat_ws(" ", User.names, User.lastnames), r"\s+", " ", "g"
            ))
            stmt = stmt.where(db_name == normalized)
        else:
            raise ValueError("Debes enviar teléfono o nombre completo")

        users = list((await self.session.scalars(stmt.limit(2))).all())
        if len(users) != 1:
            return AIClientLookupDTO(found=False, ambiguous=len(users) > 1)
        return AIClientLookupDTO(found=True, client=await self._client_dto(users[0]))

    async def _find_by_document(self, cmd: AIClientUpsertCmd) -> User | None:
        stmt = (
            self._active_clients()
            .outerjoin(UserIdentification, UserIdentification.user_id == User.id)
            .where(or_(
                (User.document_type == cmd.document_type.value) &
                (User.document_number == cmd.document_number),
                (UserIdentification.document_type == cmd.document_type.value) &
                (UserIdentification.document_number == cmd.document_number),
            ))
        )
        return (await self.session.scalars(stmt.limit(1))).first()

    async def _find_by_phone(self, cmd: AIClientUpsertCmd) -> User | None:
        stmt = self._active_clients().where(
            User.code_phone == cmd.code_phone.value,
            User.phone == cmd.phone,
        )
        return (await self.session.scalars(stmt.limit(1))).first()

    async def upsert_client(self, cmd: AIClientUpsertCmd) -> AIClientUpsertDTO:
        by_document = await self._find_by_document(cmd)
        by_phone = await self._find_by_phone(cmd)
        if by_document and by_phone and by_document.id != by_phone.id:
            raise ValueError("El documento y el teléfono pertenecen a clientes distintos")

        user = by_document or by_phone
        created = user is None
        if user is None:
            user = User(role="client", is_agent=False, enable=True, deleted=False)
            self.session.add(user)

        user.names = cmd.names
        user.lastnames = cmd.lastnames
        user.document_type = cmd.document_type.value
        user.document_number = cmd.document_number
        user.code_phone = cmd.code_phone.value
        user.phone = cmd.phone
        if cmd.email is not None:
            user.email = str(cmd.email)

        primary = next((item for item in user.identifications
                        if item.document_type == cmd.document_type.value and
                        item.document_number == cmd.document_number), None)
        if primary is None:
            primary = next((item for item in user.identifications if item.is_primary), None)
        if primary is None:
            primary = UserIdentification(position=0)
            user.identifications.insert(0, primary)
        for item in user.identifications:
            item.is_primary = item is primary
        primary.document_type = cmd.document_type.value
        primary.document_number = cmd.document_number

        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ValueError("El documento, teléfono o correo ya pertenece a otro cliente") from exc
        await self.session.refresh(user)
        return AIClientUpsertDTO(
            id=user.id,
            created=created,
            is_first_transfer=await self._is_first_transfer(user.id),
        )

    async def deposit_accounts(self, currency: str) -> list[AIDepositAccountDTO]:
        try:
            currency_value = Currency(currency.upper())
        except ValueError as exc:
            raise ValueError("Moneda no soportada; usa PEN, BRL o USD") from exc
        stmt = select(Bank).where(
            Bank.currency == currency_value,
            Bank.deleted.is_(False),
            Bank.enable.is_(True),
        ).order_by(Bank.bank, Bank.company)
        banks = list((await self.session.scalars(stmt)).all())
        return [AIDepositAccountDTO(
            id=item.id,
            currency=item.currency.value.upper(),
            country=item.country.value.upper(),
            bank=item.bank,
            company=item.company,
            account=item.account,
            pix=item.pix,
        ) for item in banks]
