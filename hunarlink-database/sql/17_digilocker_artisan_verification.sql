-- ============================================================================
-- HunarLink — Module 17: DigiLocker Artisan Card Authentication & Fetch
-- Target: MySQL 8.0 / 8.4 LTS (strictly additive — zero changes to 00-13 tables)
-- ============================================================================

USE `hunarlink`;

CREATE TABLE IF NOT EXISTS `digilocker_verifications` (
    `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `state_token` VARCHAR(128) NOT NULL,
    `pkce_verifier` VARCHAR(255) NULL,
    `mode` VARCHAR(16) NOT NULL DEFAULT 'SANDBOX',
    `status` VARCHAR(24) NOT NULL DEFAULT 'INITIATED',
    `issuer_id` VARCHAR(128) NULL,
    `issuer_name` VARCHAR(255) NULL,
    `doc_type` VARCHAR(64) NULL,
    `doc_uri` VARCHAR(255) NULL,
    `artisan_card_number` VARCHAR(100) NULL,
    `card_holder_name` VARCHAR(160) NULL,
    `craft_category` VARCHAR(160) NULL,
    `district` VARCHAR(120) NULL,
    `issued_date` VARCHAR(32) NULL,
    `file_scan_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
    `raw_claims_json` JSON NULL,
    `return_to` VARCHAR(255) NULL,
    `expires_at` DATETIME(6) NOT NULL,
    `fetched_at` DATETIME(6) NULL,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_dlv_state_token` (`state_token`),
    KEY `idx_dlv_user_id` (`user_id`),
    CONSTRAINT `fk_dlv_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
