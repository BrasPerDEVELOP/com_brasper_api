-- Equivalente en SQL puro de las migraciones 072 y 073, para correr desde
-- pgAdmin cuando no se puede usar alembic contra ese servidor.
--
--   072  transaction.transactions.commission_accounting_id  <- tramo por rango
--   073  accounting_commision / accounting_destination_amount / accounting_tax_final
--
-- Reglas (ver los docstrings de ambas migraciones para el detalle):
--   * El par de monedas sale del tax_rate de la transaccion.
--   * El rango se evalua contra origin_amount, con corte superior EXCLUSIVO
--     (min_amount <= origin_amount < max_amount), la convencion que fijo la 069.
--   * accounting_commision          = ROUND(origin_amount * percentage / 100, 2)
--   * accounting_destination_amount = ROUND(origin_amount - accounting_commision, 2)
--       -> resta en MONEDA DE ORIGEN, sin aplicar tasa.
--   * accounting_tax_final          = ROUND(accounting_commision * 0.18, 2)  (IGV anadido)
--
-- Ambos pasos son idempotentes. Despues de correrlo, marcar la version:
--   alembic stamp 073


-- ===========================================================================
-- PASO 0 -- Solo lectura. Que tramo le tocaria a cada transaccion.
-- Correr esto primero y revisar el reparto antes de escribir.
-- ===========================================================================

WITH resolved AS (
    SELECT
        t.id,
        t.origin_amount,
        (
            SELECT ca.id
            FROM coin.commission_accounting AS ca
            JOIN coin.tax_rate AS tr ON tr.id = t.tax_rate_id
            WHERE ca.deleted IS FALSE
              AND ca.coin_a = tr.coin_a
              AND ca.coin_b = tr.coin_b
              AND (ca.min_amount IS NULL OR t.origin_amount >= ca.min_amount)
              AND (ca.max_amount IS NULL OR t.origin_amount <  ca.max_amount)
            ORDER BY ca.min_amount NULLS FIRST, ca.max_amount NULLS LAST
            LIMIT 1
        ) AS ca_id
    FROM transaction.transactions AS t
)
SELECT
    COALESCE(ca.coin_a::text || '->' || ca.coin_b::text, '(sin tramo)') AS par,
    ca.min_amount,
    ca.max_amount,
    ca.percentage                                                      AS pct,
    COUNT(*)                                                           AS transacciones,
    MIN(r.origin_amount)                                               AS origin_min,
    MAX(r.origin_amount)                                               AS origin_max
FROM resolved AS r
LEFT JOIN coin.commission_accounting AS ca ON ca.id = r.ca_id
GROUP BY 1, 2, 3, 4
ORDER BY 1, ca.min_amount NULLS FIRST;


-- ===========================================================================
-- PASOS 1 y 2 -- Escritura. Seleccionar desde BEGIN hasta COMMIT y ejecutar.
-- Para ensayar sin guardar: cambiar COMMIT por ROLLBACK.
-- ===========================================================================

BEGIN;

-- Paso 1 (migracion 072): vincular el tramo. Solo filas con la FK en NULL.
WITH resolved AS (
    SELECT
        t.id AS transaction_id,
        (
            SELECT ca.id
            FROM coin.commission_accounting AS ca
            JOIN coin.tax_rate AS tr ON tr.id = t.tax_rate_id
            WHERE ca.deleted IS FALSE
              AND ca.coin_a = tr.coin_a
              AND ca.coin_b = tr.coin_b
              AND (ca.min_amount IS NULL OR t.origin_amount >= ca.min_amount)
              AND (ca.max_amount IS NULL OR t.origin_amount <  ca.max_amount)
            ORDER BY ca.min_amount NULLS FIRST, ca.max_amount NULLS LAST
            LIMIT 1
        ) AS commission_accounting_id
    FROM transaction.transactions AS t
    WHERE t.commission_accounting_id IS NULL
)
UPDATE transaction.transactions AS t
SET commission_accounting_id = r.commission_accounting_id
FROM resolved AS r
WHERE r.transaction_id = t.id
  AND r.commission_accounting_id IS NOT NULL;

-- Paso 2 (migracion 073): calcular los tres importes contables.
WITH computed AS (
    SELECT
        t.id AS transaction_id,
        ROUND(t.origin_amount * ca.percentage / 100, 2) AS commision
    FROM transaction.transactions AS t
    JOIN coin.commission_accounting AS ca
      ON ca.id = t.commission_accounting_id
    WHERE ca.deleted IS FALSE
)
UPDATE transaction.transactions AS t
SET accounting_commision          = c.commision,
    accounting_destination_amount = ROUND(t.origin_amount - c.commision, 2),
    accounting_tax_final          = ROUND(c.commision * 0.18, 2)
FROM computed AS c
WHERE c.transaction_id = t.id;

-- Verificacion antes de confirmar.
SELECT
    COUNT(*)                                                        AS total,
    COUNT(commission_accounting_id)                                 AS con_tramo,
    COUNT(*) - COUNT(commission_accounting_id)                      AS sin_tramo,
    COUNT(accounting_commision)                                     AS con_importes,
    COUNT(*) FILTER (
        WHERE accounting_commision IS NOT NULL
          AND ROUND(accounting_commision + accounting_destination_amount, 2)
              <> ROUND(origin_amount, 2)
    )                                                               AS descuadres
FROM transaction.transactions;

COMMIT;


-- ===========================================================================
-- Muestra para revisar a ojo despues de confirmar.
-- ===========================================================================

-- SELECT t.origin_amount, ca.percentage AS pct, t.accounting_commision,
--        t.accounting_destination_amount, t.accounting_tax_final
-- FROM transaction.transactions t
-- JOIN coin.commission_accounting ca ON ca.id = t.commission_accounting_id
-- ORDER BY t.origin_amount
-- LIMIT 25;
