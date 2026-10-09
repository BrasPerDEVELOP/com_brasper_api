-- Datos SINTÉTICOS que usan las columnas/tablas nuevas de 083/084 SIN violar
-- la restricción antigua (máx. 1 canje vivo por cupón/usuario).
BEGIN;
UPDATE transaction.coupons
   SET campaign_rules = '{"first_shipment_only": true, "channels": ["web","whatsapp"]}'::jsonb,
       campaign_version = 2, published_version = 2
 WHERE id = '00000000-0000-4000-8400-000000000001';
UPDATE transaction.coupons
   SET campaign_rules = '{"per_user_limit": 3, "min_origin_amount": 200}'::jsonb,
       published_version = 1
 WHERE id = '00000000-0000-4000-8400-000000000002';
INSERT INTO transaction.coupon_campaign_versions (id, coupon_id, version, payload, created_at, updated_at) VALUES
 ('00000000-0000-4000-8700-000000000001', '00000000-0000-4000-8400-000000000001', 1, '{"first_shipment_only": true}'::jsonb, '2026-10-08T10:00:00Z', '2026-10-08T10:00:00Z'),
 ('00000000-0000-4000-8700-000000000002', '00000000-0000-4000-8400-000000000001', 2, '{"first_shipment_only": true, "channels": ["web","whatsapp"]}'::jsonb, '2026-10-08T11:00:00Z', '2026-10-08T11:00:00Z'),
 ('00000000-0000-4000-8700-000000000003', '00000000-0000-4000-8400-000000000002', 1, '{"per_user_limit": 3, "min_origin_amount": 200}'::jsonb, '2026-10-08T12:00:00Z', '2026-10-08T12:00:00Z');
UPDATE transaction.transactions SET coupon_campaign_version = 1
 WHERE id = '00000000-0000-4000-8500-000000000009';
INSERT INTO "user".ai_identity_links (id, user_id, channel, subject_hash, token_hash, grant_hash, expires_at, consumed_at, grant_expires_at, deleted, enable, created_at, updated_at) VALUES
 ('00000000-0000-4000-8800-000000000001', '00000000-0000-4000-8000-000000000001', 'whatsapp', repeat('a',64), repeat('1',64), repeat('f',64), '2026-10-09T01:10:00Z', '2026-10-09T01:05:00Z', '2026-10-10T01:05:00Z', false, true, '2026-10-09T01:00:00Z', '2026-10-09T01:05:00Z'),
 ('00000000-0000-4000-8800-000000000002', '00000000-0000-4000-8000-000000000002', 'telegram', repeat('b',64), repeat('2',64), NULL,          '2026-10-09T01:10:00Z', NULL, NULL, false, true, '2026-10-09T01:00:00Z', '2026-10-09T01:00:00Z'),
 ('00000000-0000-4000-8800-000000000003', '00000000-0000-4000-8000-000000000001', 'webchat',  repeat('c',64), repeat('3',64), NULL,          '2026-10-08T01:10:00Z', NULL, NULL, true,  false, '2026-10-08T01:00:00Z', '2026-10-08T02:00:00Z');
COMMIT;
