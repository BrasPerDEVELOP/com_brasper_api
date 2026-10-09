-- Datos SINTÉTICOS que SÓLO son posibles tras 083: varios canjes VIVOS del
-- mismo cupón por el mismo usuario (PROMO3X per_user_limit=3). Rompen la
-- restricción antigua uq_coupon_redemptions_coupon_user_live (052).
BEGIN;
INSERT INTO transaction.transactions (id, deleted, enable, created_at, updated_at, status, user_id, tax_rate_id, commission_id, origin_amount, destination_amount, code, coupon_id, bank_account_destination_id, commission_result, total_to_send, coupon_discount_code, coupon_discount_percentage, coupon_discount_commission, coupon_campaign_version) VALUES
 ('00000000-0000-4000-8500-000000000013', false, true, '2026-10-08T15:00:00Z', '2026-10-08T15:00:00Z', 'completed', '00000000-0000-4000-8000-000000000001', '00000000-0000-4000-8300-000000000001', '00000000-0000-4000-8300-000000000002', 600.00, 390.72, 'TX-0013', '00000000-0000-4000-8400-000000000002', '00000000-0000-4000-8200-000000000001', 15.00, 585.00, 'PROMO3X', 10.0000, 1.50, 1),
 ('00000000-0000-4000-8500-000000000014', false, true, '2026-10-09T09:00:00Z', '2026-10-09T09:00:00Z', 'pending',   '00000000-0000-4000-8000-000000000001', '00000000-0000-4000-8300-000000000001', '00000000-0000-4000-8300-000000000002', 450.00, 293.04, 'TX-0014', '00000000-0000-4000-8400-000000000002', '00000000-0000-4000-8200-000000000001', 11.25, 438.75, 'PROMO3X', 10.0000, 1.13, 1);
INSERT INTO world_cup.coupon_redemptions (id, coupon_id, user_id, transaction_id, deleted, enable, created_at, updated_at) VALUES
 ('00000000-0000-4000-8600-000000000008', '00000000-0000-4000-8400-000000000002', '00000000-0000-4000-8000-000000000001', '00000000-0000-4000-8500-000000000013', false, true, '2026-10-08T15:00:00Z', '2026-10-08T15:00:00Z'),
 ('00000000-0000-4000-8600-000000000009', '00000000-0000-4000-8400-000000000002', '00000000-0000-4000-8000-000000000001', '00000000-0000-4000-8500-000000000014', false, true, '2026-10-09T09:00:00Z', '2026-10-09T09:00:00Z');
UPDATE transaction.coupons SET used_count = used_count + 2 WHERE id = '00000000-0000-4000-8400-000000000002';
COMMIT;
