"""Cálculo puro de cotización (tramo, cupón y descuento sobre la comisión), sin rutas HTTP.

La API principal ya no cotiza para la plataforma IA ni administra campañas: la ruta
``POST /brasper/ai/quotes`` y ``quote_for_client`` se retiraron (las campañas viven solo
en com_brasper_ia). ``calculate`` e ``inverse_quote`` se conservan como referencia
determinista que las pruebas de integridad C1 comparan con el registro de operaciones
(misma selección de tramo y misma precisión ``normalize_amount``). Sin consumidores en
producción; no exponerlas de nuevo sin decisión del responsable de la API.
"""
from math import isfinite

from app.modules.coin.domain.commission_selection import normalize_amount, select_commission
from app.modules.transactions.domain.enums import ExchangeRateScope
from app.modules.transactions.application.campaign_policy import discount_for


def calculate(amount, rate, commissions, coupons, uses, history, origin, destination, now):
    amount = normalize_amount(amount)
    commission = select_commission(amount, commissions)
    gross = round(amount * float(commission.percentage) / 100, 2)
    if not isfinite(gross) or gross < 0 or gross > amount:
        raise ValueError("Comisión no válida")
    choices = []
    for coupon in coupons:
        if not coupon.is_active or coupon.lifecycle_status != "ACTIVE" or coupon.used_count >= coupon.max_uses:
            continue
        if coupon.start_date and coupon.start_date > now or coupon.end_date and coupon.end_date < now:
            continue
        scopes = coupon.exchange_rate_scopes
        if scopes:
            if not ExchangeRateScope.matches_pair(scopes, origin, destination):
                continue
        elif (coupon.origin_currency is not None and coupon.origin_currency != origin or
              coupon.destination_currency is not None and coupon.destination_currency != destination):
            continue
        if coupon.per_user_limit and uses.get(coupon.id, 0) >= coupon.per_user_limit:
            continue
        try:
            saving = discount_for(coupon, amount, gross, completed=history.completed_transfers,
                                  pending=history.pending_transfers)
        except ValueError:
            continue
        rules = coupon.campaign_rules or {}
        choices.append((rules.get("priority", 0), saving, str(coupon.id), coupon))
    selected = max(choices, key=lambda c: c[:3]) if choices else None
    coupon, saving = (selected[3], selected[1]) if selected else (None, 0)
    net = round(gross - saving, 2)
    total = round(amount - net, 2)
    return {"amount_send": amount, "amount_receive": round(total * rate, 2), "rate": rate,
            "commission": net, "commission_gross": gross, "commission_rate": float(commission.percentage),
            "total_to_send": total, "coupon_code": coupon.code if coupon else None,
            "coupon_id": str(coupon.id) if coupon else None, "coupon_savings_amount": saving,
            "campaign_version": coupon.published_version if coupon else None,
            "campaign_rules": coupon.campaign_rules if coupon else None,
            "origin_currency": origin.value, "destination_currency": destination.value,
            "eligibility_checked_at": now.isoformat(), "reserved": False,
            # C1: a quote never reserves; registration reserves, completion consumes.
            "discount_state": "quoted" if coupon else None}


def inverse_quote(target, rate, commissions, coupons, compute):
    # Campaign thresholds can make receipt amounts non-monotonic. Solve every
    # linear branch and inspect boundaries instead of assuming binary-search order.
    amounts = {target / rate, 0.01}
    for commission in commissions:
        c = float(commission.percentage) / 100
        amounts.update(float(v) for v in (commission.min_amount, commission.max_amount) if v is not None)
        for coupon in [None, *coupons]:
            p = float(coupon.discount_percentage) / 100 if coupon else 0
            rules = coupon.campaign_rules or {} if coupon else {}
            if not isfinite(p) or not 0 <= p <= 1:
                continue
            coefficient = 1 - c * (1 - p)
            if coefficient > 0:
                amounts.add(target / rate / coefficient)
            amounts.update(float(rules[k]) for k in ("minimum_amount", "maximum_amount") if rules.get(k) is not None)
            cap = rules.get("maximum_discount")
            if cap is not None:
                if c * p > 0:
                    amounts.add(float(cap) / (c * p))
                if 1 - c > 0:
                    amounts.add((target / rate - float(cap)) / (1 - c))
    choices = []
    for value in amounts:
        for offset in (-0.02, -0.01, 0, 0.01, 0.02):
            amount = normalize_amount(value + offset)
            if not 0 < amount <= 1_000_000_000:
                continue
            try:
                choices.append(compute(amount))
            except ValueError:
                continue
    if not choices:
        raise ValueError("No hay una cotización para ese monto")
    result = min(choices, key=lambda q: (abs(q["amount_receive"] - target), q["amount_send"]))
    if abs(result["amount_receive"] - target) > max(0.02, rate * 0.02):
        raise ValueError("El monto solicitado coincide con un cambio de tramo; un asesor debe revisarlo")
    return result
