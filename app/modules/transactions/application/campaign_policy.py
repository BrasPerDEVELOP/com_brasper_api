"""Deterministic coupon discount and eligibility used by transaction registration.

``discount_for`` also validates the 0–100 % range for traditional coupons. The campaign
branch (``campaign_rules``) is dormant: campaign administration moved to com_brasper_ia
and the API no longer creates or publishes campaign rules.
"""
from math import isfinite

from .schemas.campaign_schema import CampaignRules


def discount_for(coupon, amount: float, commission: float, *, completed: int, pending: int) -> float:
    percentage = float(coupon.discount_percentage)
    if not isfinite(percentage) or not 0 <= percentage <= 100:
        raise ValueError("El porcentaje del cupón debe estar entre 0 y 100")
    saving = round(commission * percentage / 100, 2)
    raw = getattr(coupon, "campaign_rules", None)
    if raw:
        rules = CampaignRules.model_validate(raw)
        if amount < rules.minimum_amount or (rules.maximum_amount is not None and amount > rules.maximum_amount):
            raise ValueError("El monto no cumple las condiciones de la campaña")
        if rules.segment == "first_transfer" and (completed or pending):
            raise ValueError("Primer envío ya realizado o reservado por una operación pendiente")
        if rules.segment == "returning" and completed < 1:
            raise ValueError("Esta campaña requiere un envío completado")
        if rules.maximum_discount is not None:
            saving = min(saving, round(rules.maximum_discount, 2))
    return min(max(saving, 0), round(commission, 2))


def validate_campaign_dates(start, end):
    if start is None or end is None or start.tzinfo is None or end.tzinfo is None or end <= start:
        raise ValueError("La campaña necesita inicio y fin con zona horaria y fin posterior al inicio")


def discount_state(coupon_id, status) -> str | None:
    """Lifecycle of a coupon/campaign discount on an operation.

    ``quoted`` belongs to quotes only (never stored); a registered operation is
    ``reserved`` while pending, ``consumed`` once completed and ``released`` when
    it failed (the usage registry gave the quota back exactly once).
    """
    if not coupon_id:
        return None
    value = getattr(status, "value", status)
    if value == "completed":
        return "consumed"
    if value == "failed":
        return "released"
    return "reserved"
