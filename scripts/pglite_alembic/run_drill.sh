#!/bin/sh
# Drill completo de migraciones 083/084 contra TRES servidores PGlite vacíos.
# Sólo laboratorio local; nunca apuntar a una BD real.
#
#   node .../pglite-socket/dist/scripts/server.js --db=memory:// --port=55433  # A
#   node .../pglite-socket/dist/scripts/server.js --db=memory:// --port=55434  # B
#   node .../pglite-socket/dist/scripts/server.js --db=memory:// --port=55435  # C
#   sh scripts/pglite_alembic/run_drill.sh <out_dir> [python]
#
# A: upgrade con datos históricos + re-run head + downgrade limpio (escenario a)
# B: datos con varios canjes vivos (sólo posibles tras 083) + downgrade (escenario b)
#    + backup lógico de B en head
# C: restauración del backup de B y comparación de checksums
set -u
OUT="${1:?out_dir}"
PY="${2:-.venv/Scripts/python.exe}"
A="${PORT_A:-55433}"; B="${PORT_B:-55434}"; C="${PORT_C:-55435}"
T="scripts/validate_migrations_pglite.py"
D="scripts/pglite_alembic"
mkdir -p "$OUT"
run() { echo; echo "\$ $*"; "$@" 2>&1 | grep -v '^\[0[0-9][0-9]\]' ; return 0; }
q() { port="$1"; shift; echo; echo "-- [$port] $1"; "$PY" "$T" --port "$port" query "$1" 2>&1 | grep -E -v '^  |^Traceback|^\(Background|^The above|^\[SQL|^During|^sqlalchemy\.dialects|^asyncpg\.exceptions|^$' | awk '!seen[$0]++' | head -30; }

IDX="SELECT indexname||' '||indexdef FROM pg_indexes WHERE tablename IN ('coupon_redemptions','coupon_campaign_versions','ai_identity_links') ORDER BY 1"
CONS="SELECT conrelid::regclass||' '||conname||' '||pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid::regclass::text IN ('transaction.coupon_campaign_versions','\"user\".ai_identity_links') ORDER BY 1"
COLS="SELECT table_name||'.'||column_name||' '||data_type||' null='||is_nullable||' def='||coalesce(column_default,'') FROM information_schema.columns WHERE table_schema='transaction' AND column_name IN ('campaign_rules','campaign_version','published_version','coupon_campaign_version') ORDER BY 1"
LIVE="SELECT coupon_id, user_id, count(*) FROM world_cup.coupon_redemptions WHERE deleted=false GROUP BY 1,2 HAVING count(*)>1"
DUP="INSERT INTO world_cup.coupon_redemptions (id, coupon_id, user_id, deleted, enable) VALUES (gen_random_uuid(), '00000000-0000-4000-8400-000000000002', '00000000-0000-4000-8000-000000000001', false, true) RETURNING id"

echo "===== A: upgrade base->082, semilla histórica ====="
run "$PY" "$T" --port "$A" upgrade 082
run "$PY" "$T" --port "$A" sql "$D/seed_pre_083.sql"
run "$PY" "$T" --port "$A" snapshot "$OUT/A_082_seeded.json"
q "$A" "$IDX"
q "$A" "$DUP  /* esperado: UniqueViolation en 082 */"
echo "===== A: upgrade 082->head ====="
run "$PY" "$T" --port "$A" upgrade head
run "$PY" "$T" --port "$A" snapshot "$OUT/A_head.json" --base "$OUT/A_082_seeded.json"
q "$A" "$IDX"
q "$A" "$CONS"
q "$A" "$COLS"
q "$A" "SELECT code, campaign_version, published_version, campaign_rules IS NULL FROM transaction.coupons ORDER BY code"
echo "===== A: re-ejecutar upgrade head (debe ser no-op) ====="
run "$PY" "$T" --port "$A" upgrade head
run "$PY" "$T" --port "$A" snapshot "$OUT/A_head_rerun.json"
run "$PY" "$T" compare "$OUT/A_head.json" "$OUT/A_head_rerun.json"
echo "===== A: escenario (a) datos limpios en head + downgrade 084->083->082 ====="
run "$PY" "$T" --port "$A" sql "$D/seed_post_084_clean.sql"
run "$PY" "$T" --port "$A" snapshot "$OUT/A_head_clean_data.json"
run "$PY" "$T" --port "$A" downgrade 083
q "$A" "SELECT to_regclass('\"user\".ai_identity_links')"
run "$PY" "$T" --port "$A" downgrade 082
run "$PY" "$T" --port "$A" snapshot "$OUT/A_back_to_082.json" --base "$OUT/A_082_seeded.json"
run "$PY" "$T" compare "$OUT/A_082_seeded.json" "$OUT/A_back_to_082.json"
q "$A" "$IDX"
q "$A" "$DUP  /* esperado: UniqueViolation otra vez (restricción repuesta) */"
echo "===== A: re-upgrade 082->head tras downgrade (ida y vuelta) ====="
run "$PY" "$T" --port "$A" upgrade head
run "$PY" "$T" --port "$A" snapshot "$OUT/A_head_again.json"
run "$PY" "$T" compare "$OUT/A_head.json" "$OUT/A_head_again.json"

echo "===== B: 082 + semilla, head, canjes múltiples vivos ====="
run "$PY" "$T" --port "$B" upgrade 082
run "$PY" "$T" --port "$B" sql "$D/seed_pre_083.sql"
run "$PY" "$T" --port "$B" upgrade head
run "$PY" "$T" --port "$B" sql "$D/seed_post_084_clean.sql"
run "$PY" "$T" --port "$B" sql "$D/seed_post_084_multiuse.sql"
q "$B" "$LIVE"
run "$PY" "$T" --port "$B" snapshot "$OUT/B_head_multiuse.json"
echo "===== B: backup lógico en head (antes de intentar downgrade) ====="
run "$PY" "$T" --port "$B" dump "$OUT/backup_B_head"
echo "===== B: escenario (b) downgrade 084->083 y 083->082 ====="
run "$PY" "$T" --port "$B" downgrade 083
run "$PY" "$T" --port "$B" snapshot "$OUT/B_083_after_downgrade.json"
echo "-- downgrade 083->082 (se espera fallo por el UNIQUE de 052) --"
"$PY" "$T" --port "$B" downgrade 082 > "$OUT/B_downgrade_082.log" 2>&1; echo "exit=$?"
grep -E "UniqueViolation|could not create unique index|DETAIL|Key \(" "$OUT/B_downgrade_082.log" | head -5
run "$PY" "$T" --port "$B" current
run "$PY" "$T" --port "$B" snapshot "$OUT/B_after_failed_downgrade.json"
run "$PY" "$T" compare "$OUT/B_083_after_downgrade.json" "$OUT/B_after_failed_downgrade.json"
q "$B" "$IDX"
q "$B" "$COLS"
q "$B" "$LIVE"

echo "===== C: restauración del backup de B ====="
run "$PY" "$T" --port "$C" upgrade head
run "$PY" "$T" --port "$C" restore "$OUT/backup_B_head"
run "$PY" "$T" --port "$C" snapshot "$OUT/C_restored.json"
run "$PY" "$T" compare "$OUT/B_head_multiuse.json" "$OUT/C_restored.json"
for t in transaction.coupons transaction.transactions world_cup.coupon_redemptions transaction.coupon_campaign_versions '"user".ai_identity_links' '"user"."user"'; do
  q "$C" "SELECT '$t', count(*) FROM $t"
done
echo "===== D: robustez — 083 sobre una BD donde el índice 052 ya no existe ====="
D_PORT="${PORT_D:-55436}"
run "$PY" "$T" --port "$D_PORT" upgrade 082
q "$D_PORT" "DROP INDEX world_cup.uq_coupon_redemptions_coupon_user_live"
"$PY" "$T" --port "$D_PORT" upgrade 083 > "$OUT/D_upgrade_083.log" 2>&1; echo "exit=$?"
grep -E "UndefinedObject|does not exist" "$OUT/D_upgrade_083.log" | head -2
run "$PY" "$T" --port "$D_PORT" current
q "$D_PORT" "$COLS"
q "$D_PORT" "SELECT to_regclass('transaction.coupon_campaign_versions')"
echo "-- reintento de upgrade 083 tras el fallo parcial --"
"$PY" "$T" --port "$D_PORT" upgrade 083 > "$OUT/D_upgrade_083_retry.log" 2>&1; echo "exit=$?"
grep -E "DuplicateColumn|already exists" "$OUT/D_upgrade_083_retry.log" | head -2
echo; echo "FIN"
