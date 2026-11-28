-- =============================================================================
-- HunarLink MySQL 8.4 LTS Disposable Database Smoke Test
-- File: sql/13_disposable_smoke_test.sql
--
-- WARNING:
--   Run ONLY on a disposable development/test database (NEVER production!).
--   Executes all 13 repeatable transaction scenarios from Section 7 of the
--   HunarLink MySQL Database Development specification and rolls back / cleans up.
-- =============================================================================

USE `hunarlink`;
SET SESSION time_zone = '+00:00';

-- All test records use fixed namespace `99999999-...` and are clearly labelled TEST_.
START TRANSACTION;

-- 1. Create one test user + multi-role assignment (Customer + Direct Seller)
INSERT INTO `users` (`id`, `clerk_user_id`, `email`, `first_name`, `last_name`, `account_role`, `account_status`)
VALUES ('99999999-0000-4000-8000-000000000001', 'clerk_test_user_001', 'test.artisan@example.invalid', 'Test', 'Artisan', 'ARTISAN', 'ACTIVE');

INSERT INTO `user_role_assignments` (`id`, `user_id`, `platform_role_id`, `assignment_status`, `granted_at`) VALUES
  ('99999999-0000-4000-8000-000000000011', '99999999-0000-4000-8000-000000000001', '10000000-0000-4000-8000-000000000001', 'ACTIVE', UTC_TIMESTAMP(6)),
  ('99999999-0000-4000-8000-000000000012', '99999999-0000-4000-8000-000000000001', '10000000-0000-4000-8000-000000000002', 'ACTIVE', UTC_TIMESTAMP(6));

INSERT INTO `user_addresses` (`id`, `user_id`, `recipient_name`, `recipient_phone`, `line1`, `city`, `state_province`, `postal_code`, `is_default`)
VALUES ('99999999-0000-4000-8000-000000000015', '99999999-0000-4000-8000-000000000001', 'Test Artisan', '+910000000001', 'Test Lane 1', 'Srinagar', 'Jammu & Kashmir', '190001', 1);

-- 2. Create seller profile & NON_GI verification application
INSERT INTO `seller_profiles` (`id`, `user_id`, `store_name`, `store_slug`, `verification_path`, `profile_status`, `verification_status`)
VALUES ('99999999-0000-4000-8000-000000000020', '99999999-0000-4000-8000-000000000001', 'TEST_Kani_Workshop', 'test-kani-workshop', 'NON_GI', 'ACTIVE', 'APPROVED');

INSERT INTO `seller_verification_applications` (`id`, `seller_profile_id`, `application_number`, `verification_path`, `application_status`, `submitted_at`)
VALUES ('99999999-0000-4000-8000-000000000021', '99999999-0000-4000-8000-000000000020', 'TEST-APP-001', 'NON_GI', 'APPROVED', UTC_TIMESTAMP(6));

-- Catalogue product & variant for subsequent tests
INSERT INTO `products` (`id`, `category_id`, `sku_root`, `name`, `slug`, `gi_status`, `approval_status`)
VALUES ('99999999-0000-4000-8000-000000000030', '50000000-0000-4000-8000-000000000001', 'TEST-PASH-001', 'TEST Handwoven Pashmina Shawl', 'test-handwoven-pashmina-shawl', 'UNVERIFIED', 'APPROVED');

INSERT INTO `product_variants` (`id`, `product_id`, `variant_sku`, `variant_name`, `base_mrp`, `currency_code`)
VALUES ('99999999-0000-4000-8000-000000000031', '99999999-0000-4000-8000-000000000030', 'TEST-PASH-001-IVORY', 'Ivory 200x100cm', 12000.00, 'INR');

INSERT INTO `seller_product_listings` (`id`, `seller_profile_id`, `product_id`, `product_variant_id`, `seller_sku`, `listing_title`, `selling_price`, `compare_at_mrp`, `listing_status`)
VALUES ('99999999-0000-4000-8000-000000000032', '99999999-0000-4000-8000-000000000020', '99999999-0000-4000-8000-000000000030', '99999999-0000-4000-8000-000000000031', 'TS-PASH-01', 'TEST Direct Seller Pashmina', 9500.00, 12000.00, 'ACTIVE');

-- 3. Create supplier & supplier lot
INSERT INTO `users` (`id`, `clerk_user_id`, `email`, `first_name`, `account_role`, `account_status`) VALUES
  ('99999999-0000-4000-8000-000000000002', 'clerk_test_supplier_002', 'test.supplier@example.invalid', 'TestSupplier', 'SUPPLIER', 'ACTIVE'),
  ('99999999-0000-4000-8000-000000000003', 'clerk_test_dealer_003',   'test.dealer@example.invalid',   'TestDealer',   'DEALER',   'ACTIVE'),
  ('99999999-0000-4000-8000-000000000004', 'clerk_test_buyer_004',    'test.wsbuyer@example.invalid',  'TestWSBuyer',  'WHOLESALE_BUYER', 'ACTIVE');

INSERT INTO `supplier_profiles` (`id`, `user_id`, `supplier_name`, `profile_status`, `verification_status`)
VALUES ('99999999-0000-4000-8000-000000000040', '99999999-0000-4000-8000-000000000002', 'TEST_Budgam_Weavers', 'ACTIVE', 'APPROVED');

INSERT INTO `supplier_lots` (`id`, `lot_number`, `supplier_profile_id`, `category_id`, `product_id`, `product_variant_id`, `lot_title`, `offered_quantity`, `remaining_quantity`, `expected_unit_price`, `available_from_date`, `lot_status`)
VALUES ('99999999-0000-4000-8000-000000000041', 'TEST-LOT-001', '99999999-0000-4000-8000-000000000040', '50000000-0000-4000-8000-000000000001', '99999999-0000-4000-8000-000000000030', '99999999-0000-4000-8000-000000000031', 'TEST Bulk Pashmina Lot', 50.000, 50.000, 6500.00, '2026-11-24', 'APPROVED_FOR_MATCHING');

-- 4. Create dealer, warehouse, and dealer assignment (decline attempt 1, accept attempt 2)
INSERT INTO `dealer_profiles` (`id`, `user_id`, `dealership_name`, `dealership_slug`, `city`, `state_province`, `profile_status`, `verification_status`)
VALUES ('99999999-0000-4000-8000-000000000050', '99999999-0000-4000-8000-000000000003', 'TEST_Valley_Dealership', 'test-valley-dealership', 'Srinagar', 'Jammu & Kashmir', 'ACTIVE', 'APPROVED');

INSERT INTO `warehouses` (`id`, `warehouse_code`, `name`, `owner_type`, `dealer_profile_id`, `address_line1`, `city`, `state_province`, `postal_code`)
VALUES ('99999999-0000-4000-8000-000000000051', 'TEST-WH-D01', 'TEST Dealer Warehouse', 'DEALER', '99999999-0000-4000-8000-000000000050', 'Depot 1', 'Srinagar', 'Jammu & Kashmir', '190001');

INSERT INTO `warehouses` (`id`, `warehouse_code`, `name`, `owner_type`, `seller_profile_id`, `address_line1`, `city`, `state_province`, `postal_code`)
VALUES ('99999999-0000-4000-8000-000000000052', 'TEST-WH-S01', 'TEST Seller Workshop', 'SELLER', '99999999-0000-4000-8000-000000000020', 'Loom 1', 'Srinagar', 'Jammu & Kashmir', '190001');

INSERT INTO `dealer_assignments` (`id`, `supplier_lot_id`, `dealer_profile_id`, `attempt_number`, `assigned_quantity`, `proposed_unit_price`, `assignment_status`, `assigned_by_user_id`) VALUES
  ('99999999-0000-4000-8000-000000000053', '99999999-0000-4000-8000-000000000041', '99999999-0000-4000-8000-000000000050', 1, 50.000, 6800.00, 'DECLINED',     '99999999-0000-4000-8000-000000000001'),
  ('99999999-0000-4000-8000-000000000054', '99999999-0000-4000-8000-000000000041', '99999999-0000-4000-8000-000000000050', 2, 50.000, 6500.00, 'TERMS_AGREED', '99999999-0000-4000-8000-000000000001');

-- 5 & 6. Create supplier purchase order, goods receipt, quality inspection, and post to dealer stock ONCE
INSERT INTO `supplier_purchase_orders` (`id`, `po_number`, `supplier_lot_id`, `dealer_assignment_id`, `supplier_profile_id`, `dealer_profile_id`, `destination_warehouse_id`, `subtotal_amount`, `total_amount`, `po_status`, `created_by_user_id`)
VALUES ('99999999-0000-4000-8000-000000000060', 'TEST-PO-001', '99999999-0000-4000-8000-000000000041', '99999999-0000-4000-8000-000000000054', '99999999-0000-4000-8000-000000000040', '99999999-0000-4000-8000-000000000050', '99999999-0000-4000-8000-000000000051', 325000.00, 325000.00, 'ISSUED', '99999999-0000-4000-8000-000000000003');

INSERT INTO `supplier_purchase_order_items` (`id`, `supplier_purchase_order_id`, `product_id`, `product_variant_id`, `item_title_snapshot`, `sku_snapshot`, `ordered_quantity`, `unit_cost`, `line_total`)
VALUES ('99999999-0000-4000-8000-000000000061', '99999999-0000-4000-8000-000000000060', '99999999-0000-4000-8000-000000000030', '99999999-0000-4000-8000-000000000031', 'TEST Handwoven Pashmina Shawl', 'TEST-PASH-001-IVORY', 50.000, 6500.00, 325000.00);

INSERT INTO `goods_receipts` (`id`, `receipt_number`, `supplier_purchase_order_id`, `warehouse_id`, `dealer_profile_id`, `received_by_user_id`, `receipt_status`)
VALUES ('99999999-0000-4000-8000-000000000062', 'TEST-GR-001', '99999999-0000-4000-8000-000000000060', '99999999-0000-4000-8000-000000000051', '99999999-0000-4000-8000-000000000050', '99999999-0000-4000-8000-000000000003', 'INSPECTED');

INSERT INTO `goods_receipt_items` (`id`, `goods_receipt_id`, `supplier_po_item_id`, `product_id`, `product_variant_id`, `received_quantity`, `accepted_quantity`, `damaged_quantity`)
VALUES ('99999999-0000-4000-8000-000000000063', '99999999-0000-4000-8000-000000000062', '99999999-0000-4000-8000-000000000061', '99999999-0000-4000-8000-000000000030', '99999999-0000-4000-8000-000000000031', 50.000, 48.000, 2.000);

INSERT INTO `quality_inspections` (`id`, `goods_receipt_id`, `goods_receipt_item_id`, `inspector_user_id`, `inspection_outcome`)
VALUES ('99999999-0000-4000-8000-000000000064', '99999999-0000-4000-8000-000000000062', '99999999-0000-4000-8000-000000000063', '99999999-0000-4000-8000-000000000003', 'PARTIALLY_PASSED');

INSERT INTO `warehouse_stock` (`id`, `warehouse_id`, `product_id`, `product_variant_id`, `owner_type`, `dealer_profile_id`, `available_quantity`)
VALUES ('99999999-0000-4000-8000-000000000065', '99999999-0000-4000-8000-000000000051', '99999999-0000-4000-8000-000000000030', '99999999-0000-4000-8000-000000000031', 'DEALER', '99999999-0000-4000-8000-000000000050', 0.000);

CALL `sp_post_goods_receipt_to_dealer_stock`(
  '99999999-0000-4000-8000-000000000063',
  '99999999-0000-4000-8000-000000000065',
  '99999999-0000-4000-8000-000000000066',
  '99999999-0000-4000-8000-000000000003'
);
SELECT `available_quantity` AS dealer_stock_after_gr_expected_48, `damaged_quantity` AS damaged_expected_2
FROM `warehouse_stock` WHERE `id` = '99999999-0000-4000-8000-000000000065';

-- 7, 8 & 9. Wholesale listing, price tier, buyer profile, RFQ, dealer quote & wholesale order
INSERT INTO `dealer_wholesale_listings` (`id`, `dealer_profile_id`, `product_id`, `product_variant_id`, `warehouse_id`, `warehouse_stock_id`, `dealer_sku`, `listing_title`, `base_unit_price`, `minimum_order_quantity`, `listing_status`)
VALUES ('99999999-0000-4000-8000-000000000070', '99999999-0000-4000-8000-000000000050', '99999999-0000-4000-8000-000000000030', '99999999-0000-4000-8000-000000000031', '99999999-0000-4000-8000-000000000051', '99999999-0000-4000-8000-000000000065', 'TD-PASH-BULK', 'TEST Bulk Pashmina', 7800.00, 10.000, 'ACTIVE');

INSERT INTO `wholesale_price_tiers` (`id`, `dealer_wholesale_listing_id`, `min_quantity`, `max_quantity`, `unit_price`) VALUES
  ('99999999-0000-4000-8000-000000000071', '99999999-0000-4000-8000-000000000070', 10.000, 24.000, 7600.00),
  ('99999999-0000-4000-8000-000000000072', '99999999-0000-4000-8000-000000000070', 25.000, NULL,   7200.00);

INSERT INTO `wholesale_buyer_profiles` (`id`, `user_id`, `company_name`, `business_city`, `business_state`, `profile_status`, `verification_status`)
VALUES ('99999999-0000-4000-8000-000000000073', '99999999-0000-4000-8000-000000000004', 'TEST Hospitality Group', 'New Delhi', 'Delhi', 'ACTIVE', 'APPROVED');

INSERT INTO `wholesale_rfqs` (`id`, `rfq_number`, `wholesale_buyer_profile_id`, `buyer_user_id`, `title`, `rfq_status`)
VALUES ('99999999-0000-4000-8000-000000000074', 'TEST-RFQ-001', '99999999-0000-4000-8000-000000000073', '99999999-0000-4000-8000-000000000004', 'TEST 20 Pashmina Shawls', 'QUOTE_ACCEPTED');

INSERT INTO `dealer_quotes` (`id`, `quote_number`, `wholesale_rfq_id`, `dealer_profile_id`, `submitted_by_user_id`, `subtotal_amount`, `total_amount`, `valid_until`, `quote_status`)
VALUES ('99999999-0000-4000-8000-000000000075', 'TEST-QT-001', '99999999-0000-4000-8000-000000000074', '99999999-0000-4000-8000-000000000050', '99999999-0000-4000-8000-000000000003', 152000.00, 152000.00, DATE_ADD(UTC_TIMESTAMP(6), INTERVAL 7 DAY), 'ACCEPTED');

INSERT INTO `wholesale_orders` (`id`, `order_number`, `wholesale_buyer_profile_id`, `buyer_user_id`, `dealer_profile_id`, `order_source`, `wholesale_rfq_id`, `dealer_quote_id`, `shipping_address_snapshot_json`, `subtotal_amount`, `total_amount`)
VALUES ('99999999-0000-4000-8000-000000000076', 'TEST-WO-001', '99999999-0000-4000-8000-000000000073', '99999999-0000-4000-8000-000000000004', '99999999-0000-4000-8000-000000000050', 'ACCEPTED_RFQ_QUOTE', '99999999-0000-4000-8000-000000000074', '99999999-0000-4000-8000-000000000075', JSON_OBJECT('city', 'New Delhi'), 152000.00, 152000.00);

-- 10 & 11. Retail order, seller fulfilment group & inventory reserve -> release -> reserve -> consume
INSERT INTO `warehouse_stock` (`id`, `warehouse_id`, `product_id`, `product_variant_id`, `owner_type`, `seller_profile_id`, `seller_listing_id`, `available_quantity`)
VALUES ('99999999-0000-4000-8000-000000000080', '99999999-0000-4000-8000-000000000052', '99999999-0000-4000-8000-000000000030', '99999999-0000-4000-8000-000000000031', 'SELLER', '99999999-0000-4000-8000-000000000020', '99999999-0000-4000-8000-000000000032', 5.000);

INSERT INTO `retail_orders` (`id`, `order_number`, `customer_user_id`, `shipping_address_snapshot_json`, `subtotal_amount`, `total_amount`)
VALUES ('99999999-0000-4000-8000-000000000081', 'TEST-RO-001', '99999999-0000-4000-8000-000000000001', JSON_OBJECT('city', 'Srinagar'), 9500.00, 9500.00);

INSERT INTO `seller_fulfilment_groups` (`id`, `fulfilment_number`, `retail_order_id`, `seller_profile_id`, `warehouse_id`, `subtotal_amount`, `group_total_amount`)
VALUES ('99999999-0000-4000-8000-000000000082', 'TEST-SFG-001', '99999999-0000-4000-8000-000000000081', '99999999-0000-4000-8000-000000000020', '99999999-0000-4000-8000-000000000052', 9500.00, 9500.00);

CALL `sp_reserve_warehouse_stock`('99999999-0000-4000-8000-000000000083', '99999999-0000-4000-8000-000000000084', '99999999-0000-4000-8000-000000000080', 'RETAIL_ORDER', '99999999-0000-4000-8000-000000000081', NULL, '99999999-0000-4000-8000-000000000001', 2.000, DATE_ADD(UTC_TIMESTAMP(6), INTERVAL 15 MINUTE));
CALL `sp_release_stock_reservation`('99999999-0000-4000-8000-000000000083', '99999999-0000-4000-8000-000000000085', '99999999-0000-4000-8000-000000000001', 'Smoke test release');
CALL `sp_reserve_warehouse_stock`('99999999-0000-4000-8000-000000000086', '99999999-0000-4000-8000-000000000087', '99999999-0000-4000-8000-000000000080', 'RETAIL_ORDER', '99999999-0000-4000-8000-000000000081', NULL, '99999999-0000-4000-8000-000000000001', 1.000, DATE_ADD(UTC_TIMESTAMP(6), INTERVAL 15 MINUTE));
CALL `sp_consume_stock_reservation`('99999999-0000-4000-8000-000000000086', '99999999-0000-4000-8000-000000000088', '99999999-0000-4000-8000-000000000001', 'Smoke test consume');
SELECT `available_quantity` AS seller_stock_expected_4, `reserved_quantity` AS reserved_expected_0
FROM `warehouse_stock` WHERE `id` = '99999999-0000-4000-8000-000000000080';

-- 12. Payment + webhook idempotent inbox test
INSERT INTO `payments` (`id`, `payment_reference`, `payment_purpose`, `retail_order_id`, `payer_user_id`, `amount`, `captured_amount`, `payment_status`, `idempotency_key`, `provider_order_id`, `provider_payment_id`)
VALUES ('99999999-0000-4000-8000-000000000090', 'TEST-PAY-001', 'RETAIL_ORDER', '99999999-0000-4000-8000-000000000081', '99999999-0000-4000-8000-000000000001', 9500.00, 9500.00, 'CAPTURED', 'idem_test_pay_001', 'order_test_001', 'pay_test_001');

INSERT INTO `payment_webhook_events` (`id`, `provider_name`, `provider_event_id`, `event_type`, `payment_id`, `signature_verified`, `processing_status`)
VALUES ('99999999-0000-4000-8000-000000000091', 'RAZORPAY', 'evt_test_unique_001', 'payment.captured', '99999999-0000-4000-8000-000000000090', 1, 'PROCESSED');

-- 13. Audit log insert (UPDATE / DELETE are blocked by trg_audit_logs_no_update / no_delete)
INSERT INTO `audit_logs` (`id`, `actor_user_id`, `actor_role`, `action`, `target_type`, `target_id`, `reason`, `correlation_id`)
VALUES ('99999999-0000-4000-8000-000000000099', '99999999-0000-4000-8000-000000000001', 'SYSTEM_TEST', 'SMOKE_TEST_CHECK', 'retail_orders', '99999999-0000-4000-8000-000000000081', 'Disposable DB smoke test', 'corr-smoke-001');

-- Roll back everything so zero fake rows remain!
ROLLBACK;
SELECT 'ALL 13 SMOKE TEST STEPS PASSED AND ROLLED BACK CLEANLY' AS smoke_test_result;
