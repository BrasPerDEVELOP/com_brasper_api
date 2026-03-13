# app/modules/transactions/domain/enums.py
"""Enums para el módulo de transacciones."""
import enum


class TransactionType(str, enum.Enum):
    """Tipo de transacción."""
    deposit = "deposit"
    withdrawal = "withdrawal"
    transfer = "transfer"


class TransactionStatus(str, enum.Enum):
    """Estado de la transacción."""
    pending = "pending"
    completed = "completed"
    failed = "failed"
    checked = "checked"  # Solo cuando checked=True (checklist)


class BankCountry(str, enum.Enum):
    """País/región para agrupar bancos (PE, BR)."""
    pe = "pe"
    br = "br"


class AccountFlowType(str, enum.Enum):
    """Cuenta origen o cuenta destino."""
    origin = "origin"  # cuenta origen
    destination = "destination"  # cuenta destino


class SocialActor(str, enum.Enum):
    naturalPerson = "naturalPerson"
    legalEntity = "legalEntity"
    generalAspect = "generalAspect"
