-- ============================================================================
-- HunarLink — Module 16: DPDP Act 2023 Consents, Review Privacy & Signed QRs
-- Target: MySQL 8.0 / 8.4 LTS (strictly additive — zero changes to 00-13 tables)
-- ============================================================================

USE `hunarlink`;

CREATE TABLE IF NOT EXISTS `user_consents` (
    `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `consent_scope` VARCHAR(64) NOT NULL,
    `policy_version` VARCHAR(32) NOT NULL DEFAULT '2026-11-v1',
    `granted` TINYINT(1) NOT NULL DEFAULT 0,
    `source_surface` VARCHAR(64) NULL,
    `ip_hash` VARCHAR(64) NULL,
    `user_agent` VARCHAR(255) NULL,
    `granted_at` DATETIME(6) NULL,
    `withdrawn_at` DATETIME(6) NULL,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_uc_user_scope` (`user_id`, `consent_scope`),
    KEY `idx_uc_scope_granted` (`consent_scope`, `granted`),
    CONSTRAINT `fk_uc_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Idempotent additive column for anonymous product reviews
SET @pr_anon_exists := (
    SELECT COUNT(*)
    FROM `information_schema`.`COLUMNS`
    WHERE `TABLE_SCHEMA` = DATABASE()
      AND `TABLE_NAME` = 'product_reviews'
      AND `COLUMN_NAME` = 'is_anonymous'
);
SET @pr_anon_sql := IF(
    @pr_anon_exists = 0,
    'ALTER TABLE `product_reviews` ADD COLUMN `is_anonymous` TINYINT(1) NOT NULL DEFAULT 0',
    'SELECT 1'
);
PREPARE stmt_pr_anon FROM @pr_anon_sql;
EXECUTE stmt_pr_anon;
DEALLOCATE PREPARE stmt_pr_anon;
