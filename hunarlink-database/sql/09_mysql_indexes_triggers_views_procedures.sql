-- =============================================================================
-- HunarLink MySQL 8.4 LTS Schema Objects
-- File: sql/09_mysql_indexes_triggers_views_procedures.sql
-- Purpose:
--   1. Targeted MySQL FULLTEXT and operational query indexes.
--   2. Safety triggers (append-only audit_logs, cumulative refund cap,
--      Non-GI LLM block, wholesale quote-dealer/RFQ integrity check).
--   3. Operational read views.
--   4. Atomic stock & goods-receipt stored procedures.
--
-- TRANSACTION RULE (CRITICAL):
--   None of the stored procedures below execute START TRANSACTION, COMMIT,
--   or ROLLBACK. The calling FastAPI/SQLAlchemy unit-of-work owns the
--   transaction boundary so multi-step checkout and goods-receipt flows stay
--   atomic and rollback-safe.
-- =============================================================================

USE `hunarlink`;

-- -----------------------------------------------------------------------------
-- 1. TARGETED INDEXES (MySQL 8.4 InnoDB FULLTEXT & Query-Pattern Indexes)
-- -----------------------------------------------------------------------------
ALTER TABLE `products`
  ADD FULLTEXT INDEX `ft_products_search` (`name`, `short_description`, `description`);

CREATE INDEX `idx_retail_orders_placed_at` ON `retail_orders` (`placed_at` DESC);
CREATE INDEX `idx_wholesale_orders_created_at` ON `wholesale_orders` (`created_at` DESC);
CREATE INDEX `idx_payments_created_at` ON `payments` (`created_at` DESC);
CREATE INDEX `idx_supplier_lots_available_dates` ON `supplier_lots` (`lot_status`, `available_from_date`, `available_until_date`);
CREATE INDEX `idx_dealer_quotes_valid_until` ON `dealer_quotes` (`quote_status`, `valid_until`);

-- -----------------------------------------------------------------------------
-- 2. SAFETY TRIGGERS
-- -----------------------------------------------------------------------------
DELIMITER //

-- 2a. Enforce immutable append-only audit_logs (block UPDATE)
CREATE TRIGGER `trg_audit_logs_no_update`
BEFORE UPDATE ON `audit_logs`
FOR EACH ROW
BEGIN
  SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'audit_logs is append-only; UPDATE is prohibited.';
END//

-- 2b. Enforce immutable append-only audit_logs (block DELETE)
CREATE TRIGGER `trg_audit_logs_no_delete`
BEFORE DELETE ON `audit_logs`
FOR EACH ROW
BEGIN
  SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'audit_logs is append-only; DELETE is prohibited.';
END//

-- 2c. Enforce Non-GI seller applications NEVER invoke GI LLM verification runs
CREATE TRIGGER `trg_gi_runs_block_non_gi`
BEFORE INSERT ON `gi_verification_runs`
FOR EACH ROW
BEGIN
  DECLARE v_path VARCHAR(16);
  IF NEW.`target_type` = 'SELLER_APPLICATION' THEN
    SELECT `verification_path`
      INTO v_path
      FROM `seller_verification_applications`
     WHERE `id` = NEW.`seller_application_id`;
    IF v_path IS NULL OR v_path <> 'GI' THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Non-GI seller verification applications must use Admin manual review and cannot create gi_verification_runs.';
    END IF;
  END IF;
END//

-- 2d. Enforce cumulative refunds never exceed captured payment amount (INSERT)
CREATE TRIGGER `trg_refunds_before_insert_cap`
BEFORE INSERT ON `refunds`
FOR EACH ROW
BEGIN
  DECLARE v_captured DECIMAL(14,2) DEFAULT 0.00;
  DECLARE v_existing DECIMAL(14,2) DEFAULT 0.00;

  SELECT `captured_amount`
    INTO v_captured
    FROM `payments`
   WHERE `id` = NEW.`payment_id`;

  IF v_captured IS NULL OR v_captured <= 0.00 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Cannot create refund: payment has no captured amount.';
  END IF;

  SELECT COALESCE(SUM(`amount`), 0.00)
    INTO v_existing
    FROM `refunds`
   WHERE `payment_id` = NEW.`payment_id`
     AND `refund_status` IN ('REQUESTED', 'PENDING_PROVIDER', 'PROCESSED');

  IF (v_existing + NEW.`amount`) > v_captured THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Cumulative refund amount exceeds captured payment amount.';
  END IF;
END//

-- 2e. Enforce cumulative refunds never exceed captured payment amount (UPDATE)
CREATE TRIGGER `trg_refunds_before_update_cap`
BEFORE UPDATE ON `refunds`
FOR EACH ROW
BEGIN
  DECLARE v_captured DECIMAL(14,2) DEFAULT 0.00;
  DECLARE v_other DECIMAL(14,2) DEFAULT 0.00;

  IF NEW.`refund_status` IN ('REQUESTED', 'PENDING_PROVIDER', 'PROCESSED') THEN
    SELECT `captured_amount`
      INTO v_captured
      FROM `payments`
     WHERE `id` = NEW.`payment_id`;

    SELECT COALESCE(SUM(`amount`), 0.00)
      INTO v_other
      FROM `refunds`
     WHERE `payment_id` = NEW.`payment_id`
       AND `id` <> OLD.`id`
       AND `refund_status` IN ('REQUESTED', 'PENDING_PROVIDER', 'PROCESSED');

    IF (v_other + NEW.`amount`) > v_captured THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Updated cumulative refund amount exceeds captured payment amount.';
    END IF;
  END IF;
END//

-- 2f. Enforce wholesale order accepted quote belongs to the buyer's RFQ and selected dealer
CREATE TRIGGER `trg_wholesale_orders_validate_quote`
BEFORE INSERT ON `wholesale_orders`
FOR EACH ROW
BEGIN
  DECLARE v_quote_rfq CHAR(36) CHARACTER SET ascii COLLATE ascii_bin;
  DECLARE v_quote_dealer CHAR(36) CHARACTER SET ascii COLLATE ascii_bin;
  DECLARE v_quote_status VARCHAR(32);
  DECLARE v_rfq_buyer CHAR(36) CHARACTER SET ascii COLLATE ascii_bin;

  IF NEW.`dealer_quote_id` IS NOT NULL THEN
    SELECT `wholesale_rfq_id`, `dealer_profile_id`, `quote_status`
      INTO v_quote_rfq, v_quote_dealer, v_quote_status
      FROM `dealer_quotes`
     WHERE `id` = NEW.`dealer_quote_id`;

    SELECT `wholesale_buyer_profile_id`
      INTO v_rfq_buyer
      FROM `wholesale_rfqs`
     WHERE `id` = v_quote_rfq;

    IF v_quote_status NOT IN ('ACCEPTED', 'CONVERTED_TO_ORDER') THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Wholesale order quote must be ACCEPTED before order creation.';
    END IF;

    IF v_quote_rfq <> NEW.`wholesale_rfq_id`
       OR v_quote_dealer <> NEW.`dealer_profile_id`
       OR v_rfq_buyer <> NEW.`wholesale_buyer_profile_id` THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Accepted quotation does not match the buyer RFQ and selected dealer.';
    END IF;
  END IF;
END//

DELIMITER ;

-- -----------------------------------------------------------------------------
-- 3. OPERATIONAL VIEWS
-- -----------------------------------------------------------------------------

CREATE OR REPLACE VIEW `vw_active_user_roles` AS
SELECT
  u.`id` AS `user_id`,
  u.`clerk_user_id`,
  u.`email`,
  u.`account_role`,
  u.`account_status`,
  pr.`code` AS `role_code`,
  pr.`name` AS `role_name`,
  ura.`assignment_status`,
  ura.`granted_at`
FROM `users` u
INNER JOIN `user_role_assignments` ura ON ura.`user_id` = u.`id`
INNER JOIN `platform_roles` pr ON pr.`id` = ura.`platform_role_id`
WHERE ura.`assignment_status` = 'ACTIVE';

CREATE OR REPLACE VIEW `vw_seller_verification_queue` AS
SELECT
  sva.`id` AS `application_id`,
  sva.`application_number`,
  sp.`id` AS `seller_profile_id`,
  sp.`store_name`,
  sva.`verification_path`,
  sva.`application_status`,
  sva.`claimed_gi_code`,
  sva.`submitted_at`,
  sp.`verification_status` AS `seller_verification_status`
FROM `seller_verification_applications` sva
INNER JOIN `seller_profiles` sp ON sp.`id` = sva.`seller_profile_id`
WHERE sva.`application_status` IN ('SUBMITTED', 'UNDER_REVIEW', 'NEEDS_MORE_INFO');

CREATE OR REPLACE VIEW `vw_product_gi_summary` AS
SELECT
  p.`id` AS `product_id`,
  p.`sku_root`,
  p.`name` AS `product_name`,
  c.`name` AS `category_name`,
  p.`gi_status` AS `product_gi_status`,
  p.`approval_status`,
  pgc.`id` AS `latest_claim_id`,
  pgc.`claimed_gi_code`,
  pgc.`claim_status`
FROM `products` p
INNER JOIN `categories` c ON c.`id` = p.`category_id`
LEFT JOIN `product_gi_claims` pgc ON pgc.`product_id` = p.`id`;

CREATE OR REPLACE VIEW `vw_warehouse_stock_health` AS
SELECT
  ws.`id` AS `warehouse_stock_id`,
  w.`warehouse_code`,
  w.`owner_type`,
  p.`sku_root`,
  pv.`variant_sku`,
  ws.`available_quantity`,
  ws.`reserved_quantity`,
  ws.`damaged_quantity`,
  (ws.`available_quantity` + ws.`reserved_quantity` + ws.`damaged_quantity`) AS `total_physical_quantity`,
  ws.`reorder_threshold`,
  IF(ws.`available_quantity` <= ws.`reorder_threshold`, 1, 0) AS `is_low_stock`
FROM `warehouse_stock` ws
INNER JOIN `warehouses` w ON w.`id` = ws.`warehouse_id`
INNER JOIN `products` p ON p.`id` = ws.`product_id`
INNER JOIN `product_variants` pv ON pv.`id` = ws.`product_variant_id`;

CREATE OR REPLACE VIEW `vw_dealer_procurement_pipeline` AS
SELECT
  sl.`id` AS `supplier_lot_id`,
  sl.`lot_number`,
  sp.`supplier_name`,
  sl.`lot_title`,
  sl.`offered_quantity`,
  sl.`remaining_quantity`,
  sl.`lot_status`,
  da.`id` AS `dealer_assignment_id`,
  dp.`dealership_name`,
  da.`assignment_status`,
  spo.`id` AS `supplier_po_id`,
  spo.`po_number`,
  spo.`po_status`,
  spo.`settlement_status`
FROM `supplier_lots` sl
INNER JOIN `supplier_profiles` sp ON sp.`id` = sl.`supplier_profile_id`
LEFT JOIN `dealer_assignments` da ON da.`supplier_lot_id` = sl.`id`
LEFT JOIN `dealer_profiles` dp ON dp.`id` = da.`dealer_profile_id`
LEFT JOIN `supplier_purchase_orders` spo ON spo.`dealer_assignment_id` = da.`id`;

CREATE OR REPLACE VIEW `vw_payment_reconciliation_overview` AS
SELECT
  pay.`id` AS `payment_id`,
  pay.`payment_reference`,
  pay.`payment_purpose`,
  pay.`payment_method`,
  pay.`provider_name`,
  pay.`provider_order_id`,
  pay.`provider_payment_id`,
  pay.`amount`,
  pay.`captured_amount`,
  pay.`currency_code`,
  pay.`payment_status`,
  COALESCE(ref.`total_refunded`, 0.00) AS `total_refunded_amount`,
  (pay.`captured_amount` - COALESCE(ref.`total_refunded`, 0.00)) AS `net_settled_amount`,
  pay.`captured_at`,
  pay.`created_at`
FROM `payments` pay
LEFT JOIN (
  SELECT
    `payment_id`,
    SUM(`amount`) AS `total_refunded`
  FROM `refunds`
  WHERE `refund_status` IN ('REQUESTED', 'PENDING_PROVIDER', 'PROCESSED')
  GROUP BY `payment_id`
) ref ON ref.`payment_id` = pay.`id`;

-- -----------------------------------------------------------------------------
-- 4. CALLER-MANAGED TRANSACTION STORED PROCEDURES
--    Caller (FastAPI / SQLAlchemy) MUST open and commit/rollback the transaction.
-- -----------------------------------------------------------------------------
DELIMITER //

-- 4a. Reserve available warehouse stock atomically using FOR UPDATE row lock
CREATE PROCEDURE `sp_reserve_warehouse_stock` (
  IN p_reservation_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin,
  IN p_tx_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin,
  IN p_warehouse_stock_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin,
  IN p_scope VARCHAR(32),
  IN p_retail_order_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin,
  IN p_wholesale_order_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin,
  IN p_actor_user_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin,
  IN p_quantity DECIMAL(14,3),
  IN p_expires_at DATETIME(6)
)
BEGIN
  DECLARE v_available DECIMAL(14,3);
  DECLARE v_reserved DECIMAL(14,3);
  DECLARE v_damaged DECIMAL(14,3);
  DECLARE v_warehouse_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin;
  DECLARE v_variant_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin;

  IF p_quantity IS NULL OR p_quantity <= 0.000 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Reservation quantity must be positive.';
  END IF;

  SELECT `available_quantity`, `reserved_quantity`, `damaged_quantity`, `warehouse_id`, `product_variant_id`
    INTO v_available, v_reserved, v_damaged, v_warehouse_id, v_variant_id
    FROM `warehouse_stock`
   WHERE `id` = p_warehouse_stock_id
   FOR UPDATE;

  IF v_warehouse_id IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Warehouse stock record not found.';
  END IF;

  IF v_available < p_quantity THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Insufficient available stock for reservation.';
  END IF;

  UPDATE `warehouse_stock`
     SET `available_quantity` = `available_quantity` - p_quantity,
         `reserved_quantity` = `reserved_quantity` + p_quantity,
         `version` = `version` + 1
   WHERE `id` = p_warehouse_stock_id;

  INSERT INTO `stock_reservations` (
    `id`, `warehouse_stock_id`, `reservation_scope`,
    `retail_order_id`, `wholesale_order_id`, `reserved_by_user_id`,
    `reserved_quantity`, `reservation_status`, `expires_at`
  ) VALUES (
    p_reservation_id, p_warehouse_stock_id, p_scope,
    p_retail_order_id, p_wholesale_order_id, p_actor_user_id,
    p_quantity, 'ACTIVE', p_expires_at
  );

  INSERT INTO `inventory_transactions` (
    `id`, `warehouse_stock_id`, `warehouse_id`, `product_variant_id`,
    `movement_type`, `quantity_delta`,
    `available_after`, `reserved_after`, `damaged_after`,
    `reference_type`, `reference_id`, `actor_user_id`, `reason`
  ) VALUES (
    p_tx_id, p_warehouse_stock_id, v_warehouse_id, v_variant_id,
    'RESERVE', -p_quantity,
    v_available - p_quantity, v_reserved + p_quantity, v_damaged,
    p_scope, COALESCE(p_retail_order_id, p_wholesale_order_id), p_actor_user_id,
    'Stock reserved for order checkout'
  );
END//

-- 4b. Release an active stock reservation back to available stock
CREATE PROCEDURE `sp_release_stock_reservation` (
  IN p_reservation_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin,
  IN p_tx_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin,
  IN p_actor_user_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin,
  IN p_reason VARCHAR(500)
)
BEGIN
  DECLARE v_stock_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin;
  DECLARE v_qty DECIMAL(14,3);
  DECLARE v_status VARCHAR(20);
  DECLARE v_scope VARCHAR(32);
  DECLARE v_ref_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin;
  DECLARE v_available DECIMAL(14,3);
  DECLARE v_reserved DECIMAL(14,3);
  DECLARE v_damaged DECIMAL(14,3);
  DECLARE v_warehouse_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin;
  DECLARE v_variant_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin;

  SELECT `warehouse_stock_id`, `reserved_quantity`, `reservation_status`,
         `reservation_scope`, COALESCE(`retail_order_id`, `wholesale_order_id`)
    INTO v_stock_id, v_qty, v_status, v_scope, v_ref_id
    FROM `stock_reservations`
   WHERE `id` = p_reservation_id
   FOR UPDATE;

  IF v_stock_id IS NULL OR v_status <> 'ACTIVE' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Active stock reservation not found.';
  END IF;

  SELECT `available_quantity`, `reserved_quantity`, `damaged_quantity`, `warehouse_id`, `product_variant_id`
    INTO v_available, v_reserved, v_damaged, v_warehouse_id, v_variant_id
    FROM `warehouse_stock`
   WHERE `id` = v_stock_id
   FOR UPDATE;

  IF v_reserved < v_qty THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Reserved balance is less than reservation quantity.';
  END IF;

  UPDATE `warehouse_stock`
     SET `available_quantity` = `available_quantity` + v_qty,
         `reserved_quantity` = `reserved_quantity` - v_qty,
         `version` = `version` + 1
   WHERE `id` = v_stock_id;

  UPDATE `stock_reservations`
     SET `reservation_status` = 'RELEASED',
         `resolved_at` = CURRENT_TIMESTAMP(6)
   WHERE `id` = p_reservation_id;

  INSERT INTO `inventory_transactions` (
    `id`, `warehouse_stock_id`, `warehouse_id`, `product_variant_id`,
    `movement_type`, `quantity_delta`,
    `available_after`, `reserved_after`, `damaged_after`,
    `reference_type`, `reference_id`, `actor_user_id`, `reason`
  ) VALUES (
    p_tx_id, v_stock_id, v_warehouse_id, v_variant_id,
    'RELEASE_RESERVATION', v_qty,
    v_available + v_qty, v_reserved - v_qty, v_damaged,
    v_scope, v_ref_id, p_actor_user_id,
    COALESCE(p_reason, 'Reservation released')
  );
END//

-- 4c. Consume an active stock reservation when payment is verified / order fulfilled
CREATE PROCEDURE `sp_consume_stock_reservation` (
  IN p_reservation_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin,
  IN p_tx_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin,
  IN p_actor_user_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin,
  IN p_reason VARCHAR(500)
)
BEGIN
  DECLARE v_stock_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin;
  DECLARE v_qty DECIMAL(14,3);
  DECLARE v_status VARCHAR(20);
  DECLARE v_scope VARCHAR(32);
  DECLARE v_ref_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin;
  DECLARE v_available DECIMAL(14,3);
  DECLARE v_reserved DECIMAL(14,3);
  DECLARE v_damaged DECIMAL(14,3);
  DECLARE v_warehouse_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin;
  DECLARE v_variant_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin;

  SELECT `warehouse_stock_id`, `reserved_quantity`, `reservation_status`,
         `reservation_scope`, COALESCE(`retail_order_id`, `wholesale_order_id`)
    INTO v_stock_id, v_qty, v_status, v_scope, v_ref_id
    FROM `stock_reservations`
   WHERE `id` = p_reservation_id
   FOR UPDATE;

  IF v_stock_id IS NULL OR v_status <> 'ACTIVE' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Active stock reservation not found for consumption.';
  END IF;

  SELECT `available_quantity`, `reserved_quantity`, `damaged_quantity`, `warehouse_id`, `product_variant_id`
    INTO v_available, v_reserved, v_damaged, v_warehouse_id, v_variant_id
    FROM `warehouse_stock`
   WHERE `id` = v_stock_id
   FOR UPDATE;

  IF v_reserved < v_qty THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Reserved stock balance underflow prevented.';
  END IF;

  UPDATE `warehouse_stock`
     SET `reserved_quantity` = `reserved_quantity` - v_qty,
         `version` = `version` + 1
   WHERE `id` = v_stock_id;

  UPDATE `stock_reservations`
     SET `reservation_status` = 'CONSUMED',
         `resolved_at` = CURRENT_TIMESTAMP(6)
   WHERE `id` = p_reservation_id;

  INSERT INTO `inventory_transactions` (
    `id`, `warehouse_stock_id`, `warehouse_id`, `product_variant_id`,
    `movement_type`, `quantity_delta`,
    `available_after`, `reserved_after`, `damaged_after`,
    `reference_type`, `reference_id`, `actor_user_id`, `reason`
  ) VALUES (
    p_tx_id, v_stock_id, v_warehouse_id, v_variant_id,
    'CONSUME_RESERVATION', -v_qty,
    v_available, v_reserved - v_qty, v_damaged,
    v_scope, v_ref_id, p_actor_user_id,
    COALESCE(p_reason, 'Reservation consumed on confirmed order')
  );
END//

-- 4d. Post accepted goods-receipt item into dealer sellable inventory EXACTLY ONCE
CREATE PROCEDURE `sp_post_goods_receipt_to_dealer_stock` (
  IN p_goods_receipt_item_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin,
  IN p_warehouse_stock_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin,
  IN p_tx_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin,
  IN p_actor_user_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin
)
BEGIN
  DECLARE v_accepted DECIMAL(14,3);
  DECLARE v_damaged DECIMAL(14,3);
  DECLARE v_posted TINYINT(1);
  DECLARE v_gr_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin;
  DECLARE v_available DECIMAL(14,3);
  DECLARE v_reserved DECIMAL(14,3);
  DECLARE v_curr_damaged DECIMAL(14,3);
  DECLARE v_warehouse_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin;
  DECLARE v_variant_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin;
  DECLARE v_owner_type VARCHAR(20);
  DECLARE v_inspections INT DEFAULT 0;

  SELECT `goods_receipt_id`, `accepted_quantity`, `damaged_quantity`, `inventory_posted`
    INTO v_gr_id, v_accepted, v_damaged, v_posted
    FROM `goods_receipt_items`
   WHERE `id` = p_goods_receipt_item_id
   FOR UPDATE;

  IF v_gr_id IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Goods receipt item not found.';
  END IF;

  IF v_posted = 1 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Goods receipt item has already been posted to dealer inventory.';
  END IF;

  SELECT COUNT(*)
    INTO v_inspections
    FROM `quality_inspections`
   WHERE `goods_receipt_id` = v_gr_id
     AND (`goods_receipt_item_id` IS NULL OR `goods_receipt_item_id` = p_goods_receipt_item_id)
     AND `inspection_outcome` IN ('PASSED', 'PARTIALLY_PASSED');

  IF v_inspections = 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Quality inspection must pass before posting accepted goods into dealer inventory.';
  END IF;

  SELECT `available_quantity`, `reserved_quantity`, `damaged_quantity`, `warehouse_id`, `product_variant_id`, `owner_type`
    INTO v_available, v_reserved, v_curr_damaged, v_warehouse_id, v_variant_id, v_owner_type
    FROM `warehouse_stock`
   WHERE `id` = p_warehouse_stock_id
   FOR UPDATE;

  IF v_warehouse_id IS NULL OR v_owner_type <> 'DEALER' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Target stock row must belong to a DEALER warehouse.';
  END IF;

  UPDATE `warehouse_stock`
     SET `available_quantity` = `available_quantity` + v_accepted,
         `damaged_quantity` = `damaged_quantity` + v_damaged,
         `version` = `version` + 1
   WHERE `id` = p_warehouse_stock_id;

  UPDATE `goods_receipt_items`
     SET `inventory_posted` = 1
   WHERE `id` = p_goods_receipt_item_id;

  INSERT INTO `inventory_transactions` (
    `id`, `warehouse_stock_id`, `warehouse_id`, `product_variant_id`,
    `goods_receipt_item_id`, `movement_type`, `quantity_delta`,
    `available_after`, `reserved_after`, `damaged_after`,
    `reference_type`, `reference_id`, `actor_user_id`, `reason`
  ) VALUES (
    p_tx_id, p_warehouse_stock_id, v_warehouse_id, v_variant_id,
    p_goods_receipt_item_id, 'GOODS_RECEIPT_ACCEPT', v_accepted,
    v_available + v_accepted, v_reserved, v_curr_damaged + v_damaged,
    'GOODS_RECEIPT_ITEM', p_goods_receipt_item_id, p_actor_user_id,
    'Accepted inspected goods posted into dealer sellable stock'
  );
END//

DELIMITER ;
