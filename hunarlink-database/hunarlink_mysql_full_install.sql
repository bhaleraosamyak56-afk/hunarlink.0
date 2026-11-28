-- =============================================================================
-- HunarLink MySQL 8.4 LTS Complete Single-File Installer
-- File: hunarlink_mysql_full_install.sql
-- Generated directly from sql/00_create_database.sql through sql/10_seed_reference_data.sql
--
-- Usage (fresh development database only):
--   mysql -u root -p < hunarlink_mysql_full_install.sql
--   mysql -u root -p < sql/11_validation_queries.sql
--
-- Note: sql/12_create_database_users.example.sql is intentionally excluded;
--       edit its passwords before running it separately.
-- =============================================================================


-- >>> BEGIN 00_create_database.sql <<<

-- =============================================================================
-- HunarLink MySQL 8.4 LTS Database Bootstrap
-- File: sql/00_create_database.sql
-- Purpose: Create the `hunarlink` database with UTF-8 (utf8mb4) defaults.
-- Target: MySQL 8.0.21+ (MySQL 8.4 LTS preferred), InnoDB storage engine.
-- Safety: Fresh-install bootstrap only. Never run DROP DATABASE on live data.
-- =============================================================================

CREATE DATABASE IF NOT EXISTS `hunarlink`
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_0900_ai_ci;

USE `hunarlink`;

-- Enforce strict SQL validation during schema installation
SET SESSION sql_mode = 'STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION';
SET SESSION time_zone = '+00:00';

-- >>> END 00_create_database.sql <<<


-- >>> BEGIN 01_identity_and_admin_access.sql <<<

-- =============================================================================
-- HunarLink MySQL 8.4 LTS Schema
-- File: sql/01_identity_and_admin_access.sql
-- Module A: Identity and Admin Access (10 tables)
-- Tables:
--   1. users
--   2. platform_roles
--   3. user_role_assignments
--   4. user_addresses
--   5. admin_profiles
--   6. admin_roles
--   7. admin_permissions
--   8. admin_user_roles
--   9. admin_role_permissions
--  10. admin_credentials
-- Rules:
--   - Clerk is identity only (`clerk_user_id` unique external key).
--   - Never store Clerk passwords or secrets in MySQL.
--   - One user may hold multiple approved platform roles.
--   - Account status, platform role, business profile status, and verification
--     status remain separate concepts.
-- =============================================================================

USE `hunarlink`;

-- 1. users
CREATE TABLE IF NOT EXISTS `users` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `clerk_user_id` VARCHAR(128) NOT NULL,
  `email` VARCHAR(255) NOT NULL,
  `email_verified` TINYINT(1) NOT NULL DEFAULT 0,
  `phone` VARCHAR(32) NULL,
  `phone_verified` TINYINT(1) NOT NULL DEFAULT 0,
  `first_name` VARCHAR(100) NOT NULL,
  `last_name` VARCHAR(100) NULL,
  `display_name` VARCHAR(160) NULL,
  `avatar_storage_key` VARCHAR(512) NULL,
  `preferred_locale` VARCHAR(16) NOT NULL DEFAULT 'en-IN',
  `preferred_currency` CHAR(3) NOT NULL DEFAULT 'INR',
  `account_role` ENUM('BUYER', 'ARTISAN', 'ADMIN', 'WHOLESALE_BUYER', 'DEALER', 'SUPPLIER', 'DEACTIVATED') NOT NULL DEFAULT 'BUYER',
  `account_status` ENUM('PENDING_VERIFICATION', 'ACTIVE', 'SUSPENDED', 'DEACTIVATED') NOT NULL DEFAULT 'ACTIVE',
  `suspended_reason` VARCHAR(500) NULL,
  `last_login_at` DATETIME(6) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_users_clerk_user_id` (`clerk_user_id`),
  UNIQUE KEY `uq_users_email` (`email`),
  KEY `idx_users_account_role` (`account_role`),
  KEY `idx_users_account_status` (`account_status`),
  KEY `idx_users_created_at` (`created_at`),
  CONSTRAINT `chk_users_email_verified` CHECK (`email_verified` IN (0, 1)),
  CONSTRAINT `chk_users_phone_verified` CHECK (`phone_verified` IN (0, 1)),
  CONSTRAINT `chk_users_currency_len` CHECK (CHAR_LENGTH(`preferred_currency`) = 3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 2. platform_roles
CREATE TABLE IF NOT EXISTS `platform_roles` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `code` VARCHAR(50) NOT NULL,
  `name` VARCHAR(100) NOT NULL,
  `description` VARCHAR(500) NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_platform_roles_code` (`code`),
  CONSTRAINT `chk_platform_roles_active` CHECK (`is_active` IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 3. user_role_assignments
-- MySQL partial uniqueness via generated column: prevents duplicate ACTIVE role
-- assignments for the same (user_id, platform_role_id) while allowing history.
CREATE TABLE IF NOT EXISTS `user_role_assignments` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `platform_role_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `assignment_status` ENUM('PENDING', 'ACTIVE', 'SUSPENDED', 'REVOKED') NOT NULL DEFAULT 'PENDING',
  `active_role_guard` TINYINT(1) GENERATED ALWAYS AS (IF(`assignment_status` = 'ACTIVE', 1, NULL)) STORED,
  `granted_by_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `granted_at` DATETIME(6) NULL,
  `revoked_by_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `revoked_at` DATETIME(6) NULL,
  `status_reason` VARCHAR(500) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_user_role_active` (`user_id`, `platform_role_id`, `active_role_guard`),
  KEY `idx_ura_user_status` (`user_id`, `assignment_status`),
  KEY `idx_ura_role_id` (`platform_role_id`),
  KEY `idx_ura_granted_by` (`granted_by_user_id`),
  KEY `idx_ura_revoked_by` (`revoked_by_user_id`),
  CONSTRAINT `fk_ura_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_ura_role` FOREIGN KEY (`platform_role_id`) REFERENCES `platform_roles` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_ura_granted_by` FOREIGN KEY (`granted_by_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `fk_ura_revoked_by` FOREIGN KEY (`revoked_by_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 4. user_addresses
-- MySQL partial uniqueness via generated column: enforces at most ONE active
-- default address per user.
CREATE TABLE IF NOT EXISTS `user_addresses` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `address_label` VARCHAR(50) NOT NULL DEFAULT 'HOME',
  `recipient_name` VARCHAR(160) NOT NULL,
  `recipient_phone` VARCHAR(32) NOT NULL,
  `line1` VARCHAR(255) NOT NULL,
  `line2` VARCHAR(255) NULL,
  `landmark` VARCHAR(160) NULL,
  `city` VARCHAR(100) NOT NULL,
  `district` VARCHAR(100) NULL,
  `state_province` VARCHAR(100) NOT NULL,
  `postal_code` VARCHAR(20) NOT NULL,
  `country_code` CHAR(2) NOT NULL DEFAULT 'IN',
  `is_default` TINYINT(1) NOT NULL DEFAULT 0,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `default_address_guard` TINYINT(1) GENERATED ALWAYS AS (IF(`is_default` = 1 AND `is_active` = 1, 1, NULL)) STORED,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_user_single_default_address` (`user_id`, `default_address_guard`),
  KEY `idx_user_addresses_user_active` (`user_id`, `is_active`),
  KEY `idx_user_addresses_postal` (`postal_code`),
  CONSTRAINT `fk_user_addresses_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_user_addresses_default` CHECK (`is_default` IN (0, 1)),
  CONSTRAINT `chk_user_addresses_active` CHECK (`is_active` IN (0, 1)),
  CONSTRAINT `chk_user_addresses_country` CHECK (CHAR_LENGTH(`country_code`) = 2)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 5. admin_profiles
-- Provisioned ONLY after a real Clerk identity is verified; never seed a fake admin.
CREATE TABLE IF NOT EXISTS `admin_profiles` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `employee_code` VARCHAR(64) NULL,
  `department` VARCHAR(100) NULL,
  `job_title` VARCHAR(120) NULL,
  `admin_status` ENUM('ACTIVE', 'SUSPENDED', 'REVOKED') NOT NULL DEFAULT 'ACTIVE',
  `mfa_required` TINYINT(1) NOT NULL DEFAULT 1,
  `provisioned_by_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_admin_profiles_user_id` (`user_id`),
  UNIQUE KEY `uq_admin_profiles_employee_code` (`employee_code`),
  KEY `idx_admin_profiles_status` (`admin_status`),
  KEY `idx_admin_profiles_provisioned_by` (`provisioned_by_user_id`),
  CONSTRAINT `fk_admin_profiles_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_admin_profiles_provisioned_by` FOREIGN KEY (`provisioned_by_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `chk_admin_profiles_mfa` CHECK (`mfa_required` IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 6. admin_roles
CREATE TABLE IF NOT EXISTS `admin_roles` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `code` VARCHAR(64) NOT NULL,
  `name` VARCHAR(120) NOT NULL,
  `description` VARCHAR(500) NULL,
  `is_system_role` TINYINT(1) NOT NULL DEFAULT 1,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_admin_roles_code` (`code`),
  CONSTRAINT `chk_admin_roles_system` CHECK (`is_system_role` IN (0, 1)),
  CONSTRAINT `chk_admin_roles_active` CHECK (`is_active` IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 7. admin_permissions
CREATE TABLE IF NOT EXISTS `admin_permissions` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `code` VARCHAR(100) NOT NULL,
  `module_name` VARCHAR(64) NOT NULL,
  `description` VARCHAR(500) NULL,
  `is_high_risk` TINYINT(1) NOT NULL DEFAULT 0,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_admin_permissions_code` (`code`),
  KEY `idx_admin_permissions_module` (`module_name`),
  CONSTRAINT `chk_admin_permissions_high_risk` CHECK (`is_high_risk` IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 8. admin_user_roles
CREATE TABLE IF NOT EXISTS `admin_user_roles` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `admin_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `admin_role_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `assigned_by_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `active_assignment_guard` TINYINT(1) GENERATED ALWAYS AS (IF(`is_active` = 1, 1, NULL)) STORED,
  `assigned_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `revoked_at` DATETIME(6) NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_admin_user_role_active` (`admin_profile_id`, `admin_role_id`, `active_assignment_guard`),
  KEY `idx_aur_admin_role` (`admin_role_id`),
  KEY `idx_aur_assigned_by` (`assigned_by_user_id`),
  CONSTRAINT `fk_aur_admin_profile` FOREIGN KEY (`admin_profile_id`) REFERENCES `admin_profiles` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_aur_admin_role` FOREIGN KEY (`admin_role_id`) REFERENCES `admin_roles` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_aur_assigned_by` FOREIGN KEY (`assigned_by_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `chk_aur_active` CHECK (`is_active` IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 9. admin_role_permissions
CREATE TABLE IF NOT EXISTS `admin_role_permissions` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `admin_role_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `admin_permission_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_admin_role_permission` (`admin_role_id`, `admin_permission_id`),
  KEY `idx_arp_permission` (`admin_permission_id`),
  CONSTRAINT `fk_arp_role` FOREIGN KEY (`admin_role_id`) REFERENCES `admin_roles` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `fk_arp_permission` FOREIGN KEY (`admin_permission_id`) REFERENCES `admin_permissions` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 10. admin_credentials (Dedicated allowlisted Email + PBKDF2-SHA256 Admin vault)
CREATE TABLE IF NOT EXISTS `admin_credentials` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `email` VARCHAR(255) NOT NULL,
  `password_hash` VARCHAR(255) NOT NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `last_login_at` DATETIME(6) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_admin_credentials_user_id` (`user_id`),
  UNIQUE KEY `uq_admin_credentials_email` (`email`),
  KEY `idx_admin_credentials_active` (`is_active`),
  CONSTRAINT `fk_admin_credentials_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_admin_credentials_active` CHECK (`is_active` IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- >>> END 01_identity_and_admin_access.sql <<<


-- >>> BEGIN 02_sellers_and_verification.sql <<<

-- =============================================================================
-- HunarLink MySQL 8.4 LTS Schema
-- File: sql/02_sellers_and_verification.sql
-- Module B (Part 1): Seller Profiles, Verification & GI Reference Records (5 tables)
-- Tables:
--   10. seller_profiles
--   11. seller_verification_applications
--   12. seller_documents
--   13. seller_verification_history
--   14. gi_reference_records
-- Note: Product-level GI claim tables (`product_gi_claims`, `gi_claim_documents`,
--       `gi_verification_runs`) follow in 03_catalog_and_gi_products.sql right
--       after `products` so every foreign key resolves in strict execution order.
-- Rules:
--   - Verification path (`GI` vs `NON_GI`) is separate from platform role.
--   - Seller verification is separate from product-level GI verification.
--   - Never seed fictional official GI reference records.
-- =============================================================================

USE `hunarlink`;

-- 10. seller_profiles
CREATE TABLE IF NOT EXISTS `seller_profiles` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `store_name` VARCHAR(160) NOT NULL,
  `store_slug` VARCHAR(180) NOT NULL,
  `legal_business_name` VARCHAR(200) NULL,
  `business_type` ENUM('INDIVIDUAL_ARTISAN', 'PROPRIETORSHIP', 'PARTNERSHIP', 'COOPERATIVE', 'PRIVATE_LIMITED', 'LLP') NOT NULL DEFAULT 'INDIVIDUAL_ARTISAN',
  `craft_specialty` VARCHAR(160) NULL,
  `workshop_district` VARCHAR(100) NULL,
  `workshop_state` VARCHAR(100) NOT NULL DEFAULT 'Jammu & Kashmir',
  `tax_id_masked` VARCHAR(64) NULL,
  `gstin` VARCHAR(20) NULL,
  `verification_path` ENUM('GI', 'NON_GI') NOT NULL DEFAULT 'NON_GI',
  `profile_status` ENUM('DRAFT', 'ACTIVE', 'SUSPENDED', 'TERMINATED') NOT NULL DEFAULT 'DRAFT',
  `verification_status` ENUM('UNVERIFIED', 'SUBMITTED', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'REVOKED') NOT NULL DEFAULT 'UNVERIFIED',
  `claimed_gi_authorized_user_no` VARCHAR(120) NULL,
  `bio` TEXT NULL,
  `average_rating` DECIMAL(3,2) NOT NULL DEFAULT 0.00,
  `total_reviews` INT UNSIGNED NOT NULL DEFAULT 0,
  `approved_at` DATETIME(6) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_seller_profiles_user_id` (`user_id`),
  UNIQUE KEY `uq_seller_profiles_slug` (`store_slug`),
  KEY `idx_seller_profiles_status` (`profile_status`, `verification_status`),
  KEY `idx_seller_profiles_path` (`verification_path`),
  CONSTRAINT `fk_seller_profiles_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_seller_profiles_rating` CHECK (`average_rating` >= 0.00 AND `average_rating` <= 5.00)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 11. seller_verification_applications
CREATE TABLE IF NOT EXISTS `seller_verification_applications` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `seller_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `application_number` VARCHAR(64) NOT NULL,
  `verification_path` ENUM('GI', 'NON_GI') NOT NULL,
  `application_status` ENUM('DRAFT', 'SUBMITTED', 'UNDER_REVIEW', 'NEEDS_MORE_INFO', 'APPROVED', 'REJECTED', 'WITHDRAWN') NOT NULL DEFAULT 'DRAFT',
  `claimed_gi_code` VARCHAR(120) NULL,
  `claimed_craft_cluster` VARCHAR(160) NULL,
  `submitted_metadata` JSON NULL,
  `submitted_at` DATETIME(6) NULL,
  `assigned_reviewer_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `reviewed_by_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `reviewed_at` DATETIME(6) NULL,
  `review_decision_notes` TEXT NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_sva_application_number` (`application_number`),
  KEY `idx_sva_seller_status` (`seller_profile_id`, `application_status`),
  KEY `idx_sva_path_status` (`verification_path`, `application_status`),
  KEY `idx_sva_assigned_reviewer` (`assigned_reviewer_user_id`),
  KEY `idx_sva_reviewed_by` (`reviewed_by_user_id`),
  CONSTRAINT `fk_sva_seller` FOREIGN KEY (`seller_profile_id`) REFERENCES `seller_profiles` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_sva_assigned_reviewer` FOREIGN KEY (`assigned_reviewer_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `fk_sva_reviewed_by` FOREIGN KEY (`reviewed_by_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 12. seller_documents
-- Private object storage keys only; raw bytes live in private object storage.
CREATE TABLE IF NOT EXISTS `seller_documents` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `seller_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `application_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `document_type` ENUM('IDENTITY_PROOF', 'BUSINESS_REGISTRATION', 'TAX_CERTIFICATE', 'GI_AUTHORIZED_USER_CERT', 'WORKSHOP_PROOF', 'ARTISAN_PORTRAIT', 'BANK_PROOF', 'OTHER') NOT NULL,
  `storage_key` VARCHAR(512) NOT NULL,
  `original_filename` VARCHAR(255) NOT NULL,
  `detected_mime_type` VARCHAR(120) NOT NULL,
  `file_size_bytes` BIGINT UNSIGNED NOT NULL,
  `sha256_hash` CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `scan_status` ENUM('PENDING_SCAN', 'CLEAN', 'INFECTED', 'SCAN_ERROR') NOT NULL DEFAULT 'PENDING_SCAN',
  `verification_status` ENUM('PENDING', 'ACCEPTED', 'REJECTED') NOT NULL DEFAULT 'PENDING',
  `uploaded_by_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `reviewed_by_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `review_notes` VARCHAR(500) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_seller_documents_storage_key` (`storage_key`),
  KEY `idx_seller_docs_seller` (`seller_profile_id`, `document_type`),
  KEY `idx_seller_docs_app` (`application_id`),
  KEY `idx_seller_docs_hash` (`sha256_hash`),
  KEY `idx_seller_docs_uploaded_by` (`uploaded_by_user_id`),
  KEY `idx_seller_docs_reviewed_by` (`reviewed_by_user_id`),
  CONSTRAINT `fk_seller_docs_seller` FOREIGN KEY (`seller_profile_id`) REFERENCES `seller_profiles` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_seller_docs_app` FOREIGN KEY (`application_id`) REFERENCES `seller_verification_applications` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_seller_docs_uploaded_by` FOREIGN KEY (`uploaded_by_user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_seller_docs_reviewed_by` FOREIGN KEY (`reviewed_by_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `chk_seller_docs_size` CHECK (`file_size_bytes` > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 13. seller_verification_history
CREATE TABLE IF NOT EXISTS `seller_verification_history` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `application_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `seller_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `from_status` VARCHAR(40) NULL,
  `to_status` VARCHAR(40) NOT NULL,
  `actor_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `reason` VARCHAR(1000) NULL,
  `correlation_id` VARCHAR(100) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_svh_app_created` (`application_id`, `created_at`),
  KEY `idx_svh_seller` (`seller_profile_id`),
  KEY `idx_svh_actor` (`actor_user_id`),
  CONSTRAINT `fk_svh_app` FOREIGN KEY (`application_id`) REFERENCES `seller_verification_applications` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_svh_seller` FOREIGN KEY (`seller_profile_id`) REFERENCES `seller_profiles` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_svh_actor` FOREIGN KEY (`actor_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 14. gi_reference_records
-- Stores verified, versioned official GI registry reference records imported
-- from trusted official sources. Never seed fictional registry entries.
CREATE TABLE IF NOT EXISTS `gi_reference_records` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `gi_registration_number` VARCHAR(100) NOT NULL,
  `gi_name` VARCHAR(255) NOT NULL,
  `craft_class` VARCHAR(120) NULL,
  `authorized_geographic_area` VARCHAR(255) NOT NULL,
  `state_region` VARCHAR(120) NOT NULL,
  `source_authority` VARCHAR(255) NOT NULL,
  `source_url` VARCHAR(512) NULL,
  `dataset_version` VARCHAR(64) NOT NULL,
  `reference_payload` JSON NULL,
  `valid_from` DATE NULL,
  `valid_until` DATE NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `imported_by_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_gi_ref_number_version` (`gi_registration_number`, `dataset_version`),
  KEY `idx_gi_ref_active_region` (`is_active`, `state_region`),
  KEY `idx_gi_ref_imported_by` (`imported_by_user_id`),
  CONSTRAINT `fk_gi_ref_imported_by` FOREIGN KEY (`imported_by_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `chk_gi_ref_active` CHECK (`is_active` IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- >>> END 02_sellers_and_verification.sql <<<


-- >>> BEGIN 03_catalog_and_gi_products.sql <<<

-- =============================================================================
-- HunarLink MySQL 8.4 LTS Schema
-- File: sql/03_catalog_and_gi_products.sql
-- Module B (Part 2) & Module C: Product Catalogue & Product GI Verification (9 tables)
-- Tables:
--   15. categories
--   16. brands
--   17. products
--   18. product_variants
--   19. product_images
--   20. product_gi_claims
--   21. gi_claim_documents
--   22. gi_verification_runs
--   23. seller_product_listings
-- Note: `dealer_wholesale_listings` is created in 06_wholesale_marketplace.sql
--       after `dealer_profiles`, `warehouses`, and `warehouse_stock` exist.
-- Rules:
--   - Shared product catalogue is separate from seller/dealer listings.
--   - Product GI status is separate from seller verification status.
--   - LLM verification run is an assessment only, never automatic legal proof.
-- =============================================================================

USE `hunarlink`;

-- 15. categories
CREATE TABLE IF NOT EXISTS `categories` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `parent_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `code` VARCHAR(64) NOT NULL,
  `name` VARCHAR(120) NOT NULL,
  `slug` VARCHAR(140) NOT NULL,
  `description` TEXT NULL,
  `is_gi_eligible_category` TINYINT(1) NOT NULL DEFAULT 0,
  `display_order` INT NOT NULL DEFAULT 0,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_categories_code` (`code`),
  UNIQUE KEY `uq_categories_slug` (`slug`),
  KEY `idx_categories_parent` (`parent_id`),
  KEY `idx_categories_active_order` (`is_active`, `display_order`),
  CONSTRAINT `fk_categories_parent` FOREIGN KEY (`parent_id`) REFERENCES `categories` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `chk_categories_gi_eligible` CHECK (`is_gi_eligible_category` IN (0, 1)),
  CONSTRAINT `chk_categories_active` CHECK (`is_active` IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 16. brands
CREATE TABLE IF NOT EXISTS `brands` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `name` VARCHAR(140) NOT NULL,
  `slug` VARCHAR(160) NOT NULL,
  `description` TEXT NULL,
  `origin_region` VARCHAR(120) NULL,
  `logo_storage_key` VARCHAR(512) NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_brands_slug` (`slug`),
  KEY `idx_brands_active` (`is_active`),
  CONSTRAINT `chk_brands_active` CHECK (`is_active` IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 17. products
CREATE TABLE IF NOT EXISTS `products` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `category_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `brand_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `created_by_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `sku_root` VARCHAR(80) NOT NULL,
  `name` VARCHAR(220) NOT NULL,
  `slug` VARCHAR(240) NOT NULL,
  `short_description` VARCHAR(500) NULL,
  `description` MEDIUMTEXT NULL,
  `craft_technique` VARCHAR(120) NULL,
  `origin_district` VARCHAR(100) NULL,
  `material_composition` VARCHAR(255) NULL,
  `gi_status` ENUM('NOT_APPLICABLE', 'UNVERIFIED', 'PENDING_REVIEW', 'GI_VERIFIED', 'GI_REJECTED', 'GI_REVOKED') NOT NULL DEFAULT 'UNVERIFIED',
  `approval_status` ENUM('DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'REJECTED', 'ARCHIVED') NOT NULL DEFAULT 'DRAFT',
  `attributes_json` JSON NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_products_sku_root` (`sku_root`),
  UNIQUE KEY `uq_products_slug` (`slug`),
  KEY `idx_products_category` (`category_id`),
  KEY `idx_products_brand` (`brand_id`),
  KEY `idx_products_created_by` (`created_by_user_id`),
  KEY `idx_products_status` (`approval_status`, `gi_status`, `is_active`),
  CONSTRAINT `fk_products_category` FOREIGN KEY (`category_id`) REFERENCES `categories` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_products_brand` FOREIGN KEY (`brand_id`) REFERENCES `brands` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `fk_products_created_by` FOREIGN KEY (`created_by_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `chk_products_active` CHECK (`is_active` IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 18. product_variants
CREATE TABLE IF NOT EXISTS `product_variants` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `product_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `variant_sku` VARCHAR(100) NOT NULL,
  `variant_name` VARCHAR(160) NOT NULL,
  `option_values_json` JSON NULL,
  `unit_of_measure` VARCHAR(32) NOT NULL DEFAULT 'PCS',
  `weight_grams` DECIMAL(10,2) NULL,
  `dimensions_cm_json` JSON NULL,
  `base_mrp` DECIMAL(14,2) NOT NULL,
  `currency_code` CHAR(3) NOT NULL DEFAULT 'INR',
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_product_variants_sku` (`variant_sku`),
  KEY `idx_product_variants_product` (`product_id`, `is_active`),
  CONSTRAINT `fk_product_variants_product` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_pv_mrp` CHECK (`base_mrp` > 0.00),
  CONSTRAINT `chk_pv_weight` CHECK (`weight_grams` IS NULL OR `weight_grams` >= 0.00),
  CONSTRAINT `chk_pv_currency` CHECK (CHAR_LENGTH(`currency_code`) = 3),
  CONSTRAINT `chk_pv_active` CHECK (`is_active` IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 19. product_images
CREATE TABLE IF NOT EXISTS `product_images` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `product_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `product_variant_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `storage_key` VARCHAR(512) NOT NULL,
  `alt_text` VARCHAR(255) NULL,
  `sort_order` INT NOT NULL DEFAULT 0,
  `is_primary` TINYINT(1) NOT NULL DEFAULT 0,
  `primary_image_guard` TINYINT(1) GENERATED ALWAYS AS (IF(`is_primary` = 1, 1, NULL)) STORED,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_product_images_primary` (`product_id`, `primary_image_guard`),
  KEY `idx_product_images_product` (`product_id`, `sort_order`),
  KEY `idx_product_images_variant` (`product_variant_id`),
  CONSTRAINT `fk_product_images_product` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `fk_product_images_variant` FOREIGN KEY (`product_variant_id`) REFERENCES `product_variants` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `chk_product_images_primary` CHECK (`is_primary` IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 20. product_gi_claims
-- Separate from seller verification: approving a GI seller NEVER auto-verifies
-- every product of that seller.
CREATE TABLE IF NOT EXISTS `product_gi_claims` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `product_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `seller_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `gi_reference_record_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `claimed_gi_code` VARCHAR(120) NOT NULL,
  `claimed_origin_location` VARCHAR(200) NOT NULL,
  `claim_statement` TEXT NULL,
  `claim_status` ENUM('DRAFT', 'SUBMITTED', 'ASSESSED_NEEDS_REVIEW', 'APPROVED', 'REJECTED', 'REVOKED') NOT NULL DEFAULT 'DRAFT',
  `reviewed_by_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `reviewed_at` DATETIME(6) NULL,
  `review_notes` TEXT NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_pgc_product_status` (`product_id`, `claim_status`),
  KEY `idx_pgc_seller` (`seller_profile_id`),
  KEY `idx_pgc_reference` (`gi_reference_record_id`),
  KEY `idx_pgc_reviewed_by` (`reviewed_by_user_id`),
  CONSTRAINT `fk_pgc_product` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_pgc_seller` FOREIGN KEY (`seller_profile_id`) REFERENCES `seller_profiles` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_pgc_reference` FOREIGN KEY (`gi_reference_record_id`) REFERENCES `gi_reference_records` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `fk_pgc_reviewed_by` FOREIGN KEY (`reviewed_by_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 21. gi_claim_documents
CREATE TABLE IF NOT EXISTS `gi_claim_documents` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `product_gi_claim_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `document_type` ENUM('GI_TAG_PHOTO', 'LAB_PURITY_REPORT', 'ORIGIN_CERTIFICATE', 'WORKSHOP_LOOM_PROOF', 'OTHER') NOT NULL,
  `storage_key` VARCHAR(512) NOT NULL,
  `original_filename` VARCHAR(255) NOT NULL,
  `detected_mime_type` VARCHAR(120) NOT NULL,
  `file_size_bytes` BIGINT UNSIGNED NOT NULL,
  `sha256_hash` CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `scan_status` ENUM('PENDING_SCAN', 'CLEAN', 'INFECTED', 'SCAN_ERROR') NOT NULL DEFAULT 'PENDING_SCAN',
  `uploaded_by_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_gi_claim_docs_storage_key` (`storage_key`),
  KEY `idx_gcd_claim` (`product_gi_claim_id`),
  KEY `idx_gcd_hash` (`sha256_hash`),
  KEY `idx_gcd_uploaded_by` (`uploaded_by_user_id`),
  CONSTRAINT `fk_gcd_claim` FOREIGN KEY (`product_gi_claim_id`) REFERENCES `product_gi_claims` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_gcd_uploaded_by` FOREIGN KEY (`uploaded_by_user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_gcd_size` CHECK (`file_size_bytes` > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 22. gi_verification_runs
-- Traceable evidence assessment record for GI claims ONLY (never NON_GI).
-- `is_legal_proof` is constrained to 0 so an LLM run is never treated as legal proof.
CREATE TABLE IF NOT EXISTS `gi_verification_runs` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `target_type` ENUM('SELLER_APPLICATION', 'PRODUCT_GI_CLAIM') NOT NULL,
  `seller_application_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `product_gi_claim_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `gi_reference_record_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `provider_name` VARCHAR(80) NOT NULL,
  `model_version` VARCHAR(120) NOT NULL,
  `prompt_version` VARCHAR(64) NOT NULL,
  `dataset_version` VARCHAR(64) NOT NULL,
  `input_sha256` CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `evidence_reference_ids` JSON NOT NULL,
  `assessment_outcome` ENUM('LIKELY_MATCH', 'NEEDS_HUMAN_REVIEW', 'CONFLICT_DETECTED', 'INSUFFICIENT_EVIDENCE', 'ERROR') NOT NULL,
  `confidence_score` DECIMAL(5,2) NULL,
  `structured_findings_json` JSON NOT NULL,
  `is_legal_proof` TINYINT(1) NOT NULL DEFAULT 0,
  `is_mock_provider` TINYINT(1) NOT NULL DEFAULT 0,
  `human_review_decision` ENUM('PENDING', 'APPROVED', 'REJECTED', 'ESCALATED') NOT NULL DEFAULT 'PENDING',
  `human_reviewed_by_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `human_reviewed_at` DATETIME(6) NULL,
  `human_review_notes` TEXT NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_gvr_seller_app` (`seller_application_id`),
  KEY `idx_gvr_product_claim` (`product_gi_claim_id`),
  KEY `idx_gvr_reference` (`gi_reference_record_id`),
  KEY `idx_gvr_review_status` (`human_review_decision`, `created_at`),
  KEY `idx_gvr_reviewer` (`human_reviewed_by_user_id`),
  CONSTRAINT `fk_gvr_seller_app` FOREIGN KEY (`seller_application_id`) REFERENCES `seller_verification_applications` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_gvr_product_claim` FOREIGN KEY (`product_gi_claim_id`) REFERENCES `product_gi_claims` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_gvr_reference` FOREIGN KEY (`gi_reference_record_id`) REFERENCES `gi_reference_records` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `fk_gvr_reviewer` FOREIGN KEY (`human_reviewed_by_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `chk_gvr_not_legal_proof` CHECK (`is_legal_proof` = 0),
  CONSTRAINT `chk_gvr_is_mock` CHECK (`is_mock_provider` IN (0, 1)),
  CONSTRAINT `chk_gvr_confidence` CHECK (`confidence_score` IS NULL OR (`confidence_score` >= 0.00 AND `confidence_score` <= 100.00)),
  CONSTRAINT `chk_gvr_single_target` CHECK (
    (`target_type` = 'SELLER_APPLICATION' AND `seller_application_id` IS NOT NULL AND `product_gi_claim_id` IS NULL)
    OR (`target_type` = 'PRODUCT_GI_CLAIM' AND `product_gi_claim_id` IS NOT NULL AND `seller_application_id` IS NULL)
  )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 23. seller_product_listings
-- Retail offers published by approved Direct Sellers against shared catalogue variants.
CREATE TABLE IF NOT EXISTS `seller_product_listings` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `seller_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `product_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `product_variant_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `seller_sku` VARCHAR(100) NOT NULL,
  `listing_title` VARCHAR(220) NOT NULL,
  `selling_price` DECIMAL(14,2) NOT NULL,
  `compare_at_mrp` DECIMAL(14,2) NULL,
  `currency_code` CHAR(3) NOT NULL DEFAULT 'INR',
  `min_order_qty` INT UNSIGNED NOT NULL DEFAULT 1,
  `max_order_qty` INT UNSIGNED NULL,
  `dispatch_lead_days` SMALLINT UNSIGNED NOT NULL DEFAULT 3,
  `listing_status` ENUM('DRAFT', 'PENDING_APPROVAL', 'ACTIVE', 'PAUSED', 'REJECTED', 'ARCHIVED') NOT NULL DEFAULT 'DRAFT',
  `published_at` DATETIME(6) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_spl_seller_sku` (`seller_profile_id`, `seller_sku`),
  KEY `idx_spl_product_status` (`product_id`, `listing_status`),
  KEY `idx_spl_variant_status` (`product_variant_id`, `listing_status`),
  KEY `idx_spl_seller_status` (`seller_profile_id`, `listing_status`),
  CONSTRAINT `fk_spl_seller` FOREIGN KEY (`seller_profile_id`) REFERENCES `seller_profiles` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_spl_product` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_spl_variant` FOREIGN KEY (`product_variant_id`) REFERENCES `product_variants` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_spl_price` CHECK (`selling_price` > 0.00),
  CONSTRAINT `chk_spl_mrp` CHECK (`compare_at_mrp` IS NULL OR `compare_at_mrp` >= `selling_price`),
  CONSTRAINT `chk_spl_qty` CHECK (`min_order_qty` >= 1 AND (`max_order_qty` IS NULL OR `max_order_qty` >= `min_order_qty`)),
  CONSTRAINT `chk_spl_currency` CHECK (CHAR_LENGTH(`currency_code`) = 3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- >>> END 03_catalog_and_gi_products.sql <<<


-- >>> BEGIN 04_suppliers_dealers_and_procurement.sql <<<

-- =============================================================================
-- HunarLink MySQL 8.4 LTS Schema
-- File: sql/04_suppliers_dealers_and_procurement.sql
-- Module D: Suppliers, Dealers & Procurement (20 tables)
-- Tables:
--   24. supplier_profiles
--   25. supplier_verification_applications
--   26. supplier_documents
--   27. supplier_verification_history
--   28. supplier_lots
--   29. supplier_lot_documents
--   30. supplier_lot_status_history
--   31. dealer_profiles
--   32. dealer_documents
--   33. dealer_categories
--   34. warehouses
--   35. dealer_assignment_recommendations
--   36. dealer_assignments
--   37. dealer_assignment_history
--   38. supplier_purchase_orders
--   39. supplier_purchase_order_status_history
--   40. supplier_purchase_order_items
--   41. goods_receipts
--   42. goods_receipt_items
--   43. quality_inspections
-- Rules:
--   - A supplier lot is an offered supply quantity, NOT a catalogue listing.
--   - A dealer assignment is an invitation; it does NOT transfer ownership or stock.
--   - A purchase order is created ONLY after dealer acceptance & commercial agreement.
--   - Received/accepted qty enters dealer stock ONLY after goods receipt & inspection.
--   - Supplier purchase orders stay strictly separate from retail/wholesale orders.
-- =============================================================================

USE `hunarlink`;

-- 24. supplier_profiles
CREATE TABLE IF NOT EXISTS `supplier_profiles` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `supplier_name` VARCHAR(180) NOT NULL,
  `legal_entity_name` VARCHAR(200) NULL,
  `supplier_type` ENUM('PRODUCER', 'ARTISAN_COOPERATIVE', 'WEAVER_CLUSTER', 'MANUFACTURER', 'AGGREGATOR') NOT NULL DEFAULT 'PRODUCER',
  `craft_cluster` VARCHAR(140) NULL,
  `district` VARCHAR(100) NULL,
  `state_province` VARCHAR(100) NOT NULL DEFAULT 'Jammu & Kashmir',
  `gstin` VARCHAR(20) NULL,
  `profile_status` ENUM('DRAFT', 'ACTIVE', 'SUSPENDED', 'TERMINATED') NOT NULL DEFAULT 'DRAFT',
  `verification_status` ENUM('UNVERIFIED', 'SUBMITTED', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'REVOKED') NOT NULL DEFAULT 'UNVERIFIED',
  `monthly_capacity_units` INT UNSIGNED NULL,
  `approved_at` DATETIME(6) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_supplier_profiles_user_id` (`user_id`),
  KEY `idx_supplier_profiles_status` (`profile_status`, `verification_status`),
  CONSTRAINT `fk_supplier_profiles_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 25. supplier_verification_applications
CREATE TABLE IF NOT EXISTS `supplier_verification_applications` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `supplier_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `application_number` VARCHAR(64) NOT NULL,
  `application_status` ENUM('DRAFT', 'SUBMITTED', 'UNDER_REVIEW', 'NEEDS_MORE_INFO', 'APPROVED', 'REJECTED', 'WITHDRAWN') NOT NULL DEFAULT 'DRAFT',
  `submitted_metadata` JSON NULL,
  `submitted_at` DATETIME(6) NULL,
  `reviewed_by_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `reviewed_at` DATETIME(6) NULL,
  `review_notes` TEXT NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_sup_va_app_number` (`application_number`),
  KEY `idx_sup_va_supplier_status` (`supplier_profile_id`, `application_status`),
  KEY `idx_sup_va_reviewed_by` (`reviewed_by_user_id`),
  CONSTRAINT `fk_sup_va_supplier` FOREIGN KEY (`supplier_profile_id`) REFERENCES `supplier_profiles` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_sup_va_reviewed_by` FOREIGN KEY (`reviewed_by_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 26. supplier_documents
CREATE TABLE IF NOT EXISTS `supplier_documents` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `supplier_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `application_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `document_type` ENUM('IDENTITY_PROOF', 'BUSINESS_REGISTRATION', 'TAX_CERTIFICATE', 'WORKSHOP_PROOF', 'BANK_PROOF', 'QUALITY_CERT', 'OTHER') NOT NULL,
  `storage_key` VARCHAR(512) NOT NULL,
  `original_filename` VARCHAR(255) NOT NULL,
  `detected_mime_type` VARCHAR(120) NOT NULL,
  `file_size_bytes` BIGINT UNSIGNED NOT NULL,
  `sha256_hash` CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `scan_status` ENUM('PENDING_SCAN', 'CLEAN', 'INFECTED', 'SCAN_ERROR') NOT NULL DEFAULT 'PENDING_SCAN',
  `verification_status` ENUM('PENDING', 'ACCEPTED', 'REJECTED') NOT NULL DEFAULT 'PENDING',
  `uploaded_by_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_supplier_docs_storage_key` (`storage_key`),
  KEY `idx_sup_docs_supplier` (`supplier_profile_id`),
  KEY `idx_sup_docs_app` (`application_id`),
  KEY `idx_sup_docs_hash` (`sha256_hash`),
  KEY `idx_sup_docs_uploaded_by` (`uploaded_by_user_id`),
  CONSTRAINT `fk_sup_docs_supplier` FOREIGN KEY (`supplier_profile_id`) REFERENCES `supplier_profiles` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_sup_docs_app` FOREIGN KEY (`application_id`) REFERENCES `supplier_verification_applications` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_sup_docs_uploaded_by` FOREIGN KEY (`uploaded_by_user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_sup_docs_size` CHECK (`file_size_bytes` > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 27. supplier_verification_history
CREATE TABLE IF NOT EXISTS `supplier_verification_history` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `application_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `supplier_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `from_status` VARCHAR(40) NULL,
  `to_status` VARCHAR(40) NOT NULL,
  `actor_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `reason` VARCHAR(1000) NULL,
  `correlation_id` VARCHAR(100) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_sup_vh_app` (`application_id`, `created_at`),
  KEY `idx_sup_vh_supplier` (`supplier_profile_id`),
  KEY `idx_sup_vh_actor` (`actor_user_id`),
  CONSTRAINT `fk_sup_vh_app` FOREIGN KEY (`application_id`) REFERENCES `supplier_verification_applications` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_sup_vh_supplier` FOREIGN KEY (`supplier_profile_id`) REFERENCES `supplier_profiles` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_sup_vh_actor` FOREIGN KEY (`actor_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 28. supplier_lots
CREATE TABLE IF NOT EXISTS `supplier_lots` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `lot_number` VARCHAR(64) NOT NULL,
  `supplier_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `category_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `product_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `product_variant_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `lot_title` VARCHAR(220) NOT NULL,
  `lot_description` TEXT NULL,
  `offered_quantity` DECIMAL(14,3) NOT NULL,
  `remaining_quantity` DECIMAL(14,3) NOT NULL,
  `unit_of_measure` VARCHAR(32) NOT NULL DEFAULT 'PCS',
  `expected_unit_price` DECIMAL(14,2) NOT NULL,
  `currency_code` CHAR(3) NOT NULL DEFAULT 'INR',
  `is_gi_claimed` TINYINT(1) NOT NULL DEFAULT 0,
  `available_from_date` DATE NOT NULL,
  `available_until_date` DATE NULL,
  `origin_location` VARCHAR(160) NULL,
  `lot_status` ENUM('DRAFT', 'SUBMITTED', 'UNDER_REVIEW', 'APPROVED_FOR_MATCHING', 'ASSIGNED', 'PARTIALLY_PROCURED', 'PROCURED', 'REJECTED', 'EXPIRED', 'CANCELLED') NOT NULL DEFAULT 'DRAFT',
  `reviewed_by_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `reviewed_at` DATETIME(6) NULL,
  `review_notes` TEXT NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_supplier_lots_number` (`lot_number`),
  KEY `idx_sl_supplier_status` (`supplier_profile_id`, `lot_status`),
  KEY `idx_sl_category_status` (`category_id`, `lot_status`),
  KEY `idx_sl_product` (`product_id`),
  KEY `idx_sl_variant` (`product_variant_id`),
  KEY `idx_sl_reviewed_by` (`reviewed_by_user_id`),
  CONSTRAINT `fk_sl_supplier` FOREIGN KEY (`supplier_profile_id`) REFERENCES `supplier_profiles` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_sl_category` FOREIGN KEY (`category_id`) REFERENCES `categories` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_sl_product` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `fk_sl_variant` FOREIGN KEY (`product_variant_id`) REFERENCES `product_variants` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `fk_sl_reviewed_by` FOREIGN KEY (`reviewed_by_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `chk_sl_offered_qty` CHECK (`offered_quantity` > 0.000),
  CONSTRAINT `chk_sl_remaining_qty` CHECK (`remaining_quantity` >= 0.000 AND `remaining_quantity` <= `offered_quantity`),
  CONSTRAINT `chk_sl_price` CHECK (`expected_unit_price` > 0.00),
  CONSTRAINT `chk_sl_gi_claimed` CHECK (`is_gi_claimed` IN (0, 1)),
  CONSTRAINT `chk_sl_dates` CHECK (`available_until_date` IS NULL OR `available_until_date` >= `available_from_date`),
  CONSTRAINT `chk_sl_currency` CHECK (CHAR_LENGTH(`currency_code`) = 3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 29. supplier_lot_documents
CREATE TABLE IF NOT EXISTS `supplier_lot_documents` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `supplier_lot_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `document_type` ENUM('LOT_PHOTO', 'QUALITY_REPORT', 'GI_CERTIFICATE', 'PACKING_LIST', 'OTHER') NOT NULL,
  `storage_key` VARCHAR(512) NOT NULL,
  `original_filename` VARCHAR(255) NOT NULL,
  `detected_mime_type` VARCHAR(120) NOT NULL,
  `file_size_bytes` BIGINT UNSIGNED NOT NULL,
  `sha256_hash` CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `scan_status` ENUM('PENDING_SCAN', 'CLEAN', 'INFECTED', 'SCAN_ERROR') NOT NULL DEFAULT 'PENDING_SCAN',
  `uploaded_by_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_sld_storage_key` (`storage_key`),
  KEY `idx_sld_lot` (`supplier_lot_id`),
  KEY `idx_sld_hash` (`sha256_hash`),
  KEY `idx_sld_uploaded_by` (`uploaded_by_user_id`),
  CONSTRAINT `fk_sld_lot` FOREIGN KEY (`supplier_lot_id`) REFERENCES `supplier_lots` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_sld_uploaded_by` FOREIGN KEY (`uploaded_by_user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_sld_size` CHECK (`file_size_bytes` > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 30. supplier_lot_status_history
CREATE TABLE IF NOT EXISTS `supplier_lot_status_history` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `supplier_lot_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `from_status` VARCHAR(40) NULL,
  `to_status` VARCHAR(40) NOT NULL,
  `actor_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `reason` VARCHAR(1000) NULL,
  `correlation_id` VARCHAR(100) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_slsh_lot_created` (`supplier_lot_id`, `created_at`),
  KEY `idx_slsh_actor` (`actor_user_id`),
  CONSTRAINT `fk_slsh_lot` FOREIGN KEY (`supplier_lot_id`) REFERENCES `supplier_lots` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_slsh_actor` FOREIGN KEY (`actor_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 31. dealer_profiles
CREATE TABLE IF NOT EXISTS `dealer_profiles` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `dealership_name` VARCHAR(180) NOT NULL,
  `dealership_slug` VARCHAR(200) NOT NULL,
  `legal_entity_name` VARCHAR(200) NULL,
  `gstin` VARCHAR(20) NULL,
  `city` VARCHAR(100) NOT NULL,
  `state_province` VARCHAR(100) NOT NULL,
  `country_code` CHAR(2) NOT NULL DEFAULT 'IN',
  `monthly_procurement_capacity` DECIMAL(14,2) NULL,
  `currency_code` CHAR(3) NOT NULL DEFAULT 'INR',
  `reliability_rating` DECIMAL(3,2) NOT NULL DEFAULT 0.00,
  `profile_status` ENUM('DRAFT', 'ACTIVE', 'SUSPENDED', 'TERMINATED') NOT NULL DEFAULT 'DRAFT',
  `verification_status` ENUM('UNVERIFIED', 'SUBMITTED', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'REVOKED') NOT NULL DEFAULT 'UNVERIFIED',
  `approved_at` DATETIME(6) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_dealer_profiles_user_id` (`user_id`),
  UNIQUE KEY `uq_dealer_profiles_slug` (`dealership_slug`),
  KEY `idx_dealer_profiles_status` (`profile_status`, `verification_status`),
  KEY `idx_dealer_profiles_city` (`city`, `state_province`),
  CONSTRAINT `fk_dealer_profiles_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_dp_rating` CHECK (`reliability_rating` >= 0.00 AND `reliability_rating` <= 5.00),
  CONSTRAINT `chk_dp_capacity` CHECK (`monthly_procurement_capacity` IS NULL OR `monthly_procurement_capacity` >= 0.00),
  CONSTRAINT `chk_dp_currency` CHECK (CHAR_LENGTH(`currency_code`) = 3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 32. dealer_documents
CREATE TABLE IF NOT EXISTS `dealer_documents` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `dealer_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `document_type` ENUM('BUSINESS_REGISTRATION', 'GST_CERTIFICATE', 'WAREHOUSE_LEASE', 'BANK_PROOF', 'IDENTITY_PROOF', 'OTHER') NOT NULL,
  `storage_key` VARCHAR(512) NOT NULL,
  `original_filename` VARCHAR(255) NOT NULL,
  `detected_mime_type` VARCHAR(120) NOT NULL,
  `file_size_bytes` BIGINT UNSIGNED NOT NULL,
  `sha256_hash` CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `scan_status` ENUM('PENDING_SCAN', 'CLEAN', 'INFECTED', 'SCAN_ERROR') NOT NULL DEFAULT 'PENDING_SCAN',
  `verification_status` ENUM('PENDING', 'ACCEPTED', 'REJECTED') NOT NULL DEFAULT 'PENDING',
  `uploaded_by_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_dealer_docs_storage_key` (`storage_key`),
  KEY `idx_dealer_docs_dealer` (`dealer_profile_id`),
  KEY `idx_dealer_docs_hash` (`sha256_hash`),
  KEY `idx_dealer_docs_uploaded_by` (`uploaded_by_user_id`),
  CONSTRAINT `fk_dealer_docs_dealer` FOREIGN KEY (`dealer_profile_id`) REFERENCES `dealer_profiles` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_dealer_docs_uploaded_by` FOREIGN KEY (`uploaded_by_user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_dealer_docs_size` CHECK (`file_size_bytes` > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 33. dealer_categories
CREATE TABLE IF NOT EXISTS `dealer_categories` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `dealer_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `category_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `is_approved` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_dealer_category` (`dealer_profile_id`, `category_id`),
  KEY `idx_dc_category` (`category_id`),
  CONSTRAINT `fk_dc_dealer` FOREIGN KEY (`dealer_profile_id`) REFERENCES `dealer_profiles` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `fk_dc_category` FOREIGN KEY (`category_id`) REFERENCES `categories` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_dc_approved` CHECK (`is_approved` IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 34. warehouses
CREATE TABLE IF NOT EXISTS `warehouses` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `warehouse_code` VARCHAR(64) NOT NULL,
  `name` VARCHAR(160) NOT NULL,
  `owner_type` ENUM('SELLER', 'DEALER', 'PLATFORM') NOT NULL,
  `seller_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `dealer_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `address_line1` VARCHAR(255) NOT NULL,
  `address_line2` VARCHAR(255) NULL,
  `city` VARCHAR(100) NOT NULL,
  `state_province` VARCHAR(100) NOT NULL,
  `postal_code` VARCHAR(20) NOT NULL,
  `country_code` CHAR(2) NOT NULL DEFAULT 'IN',
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_warehouses_code` (`warehouse_code`),
  KEY `idx_wh_seller` (`seller_profile_id`),
  KEY `idx_wh_dealer` (`dealer_profile_id`),
  KEY `idx_wh_active` (`is_active`, `owner_type`),
  CONSTRAINT `fk_wh_seller` FOREIGN KEY (`seller_profile_id`) REFERENCES `seller_profiles` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_wh_dealer` FOREIGN KEY (`dealer_profile_id`) REFERENCES `dealer_profiles` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_wh_owner` CHECK (
    (`owner_type` = 'SELLER' AND `seller_profile_id` IS NOT NULL AND `dealer_profile_id` IS NULL)
    OR (`owner_type` = 'DEALER' AND `dealer_profile_id` IS NOT NULL AND `seller_profile_id` IS NULL)
    OR (`owner_type` = 'PLATFORM' AND `seller_profile_id` IS NULL AND `dealer_profile_id` IS NULL)
  ),
  CONSTRAINT `chk_wh_active` CHECK (`is_active` IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 35. dealer_assignment_recommendations
CREATE TABLE IF NOT EXISTS `dealer_assignment_recommendations` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `supplier_lot_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `dealer_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `rank_position` SMALLINT UNSIGNED NOT NULL,
  `match_score` DECIMAL(5,2) NOT NULL,
  `scoring_factors_json` JSON NULL,
  `generated_by_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_dar_lot_dealer` (`supplier_lot_id`, `dealer_profile_id`),
  KEY `idx_dar_lot_rank` (`supplier_lot_id`, `rank_position`),
  KEY `idx_dar_dealer` (`dealer_profile_id`),
  KEY `idx_dar_generated_by` (`generated_by_user_id`),
  CONSTRAINT `fk_dar_lot` FOREIGN KEY (`supplier_lot_id`) REFERENCES `supplier_lots` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_dar_dealer` FOREIGN KEY (`dealer_profile_id`) REFERENCES `dealer_profiles` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_dar_generated_by` FOREIGN KEY (`generated_by_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `chk_dar_score` CHECK (`match_score` >= 0.00 AND `match_score` <= 100.00)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 36. dealer_assignments
-- Invitation only; never transfers ownership or adds inventory.
CREATE TABLE IF NOT EXISTS `dealer_assignments` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `supplier_lot_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `dealer_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `recommendation_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `attempt_number` INT UNSIGNED NOT NULL DEFAULT 1,
  `assigned_quantity` DECIMAL(14,3) NOT NULL,
  `proposed_unit_price` DECIMAL(14,2) NULL,
  `currency_code` CHAR(3) NOT NULL DEFAULT 'INR',
  `assignment_status` ENUM('INVITED', 'ACCEPTED', 'DECLINED', 'TERMS_AGREED', 'EXPIRED', 'CANCELLED', 'PO_CREATED') NOT NULL DEFAULT 'INVITED',
  `active_invitation_guard` TINYINT(1) GENERATED ALWAYS AS (IF(`assignment_status` IN ('INVITED', 'ACCEPTED', 'TERMS_AGREED'), 1, NULL)) STORED,
  `assigned_by_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `expires_at` DATETIME(6) NULL,
  `responded_at` DATETIME(6) NULL,
  `response_notes` TEXT NULL,
  `agreed_terms_json` JSON NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_da_lot_dealer_active` (`supplier_lot_id`, `dealer_profile_id`, `active_invitation_guard`),
  KEY `idx_da_dealer_status` (`dealer_profile_id`, `assignment_status`),
  KEY `idx_da_lot_status` (`supplier_lot_id`, `assignment_status`),
  KEY `idx_da_recommendation` (`recommendation_id`),
  KEY `idx_da_assigned_by` (`assigned_by_user_id`),
  CONSTRAINT `fk_da_lot` FOREIGN KEY (`supplier_lot_id`) REFERENCES `supplier_lots` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_da_dealer` FOREIGN KEY (`dealer_profile_id`) REFERENCES `dealer_profiles` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_da_recommendation` FOREIGN KEY (`recommendation_id`) REFERENCES `dealer_assignment_recommendations` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `fk_da_assigned_by` FOREIGN KEY (`assigned_by_user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_da_qty` CHECK (`assigned_quantity` > 0.000),
  CONSTRAINT `chk_da_price` CHECK (`proposed_unit_price` IS NULL OR `proposed_unit_price` > 0.00),
  CONSTRAINT `chk_da_currency` CHECK (CHAR_LENGTH(`currency_code`) = 3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 37. dealer_assignment_history
CREATE TABLE IF NOT EXISTS `dealer_assignment_history` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `dealer_assignment_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `from_status` VARCHAR(40) NULL,
  `to_status` VARCHAR(40) NOT NULL,
  `actor_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `notes` VARCHAR(1000) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_dah_assignment` (`dealer_assignment_id`, `created_at`),
  KEY `idx_dah_actor` (`actor_user_id`),
  CONSTRAINT `fk_dah_assignment` FOREIGN KEY (`dealer_assignment_id`) REFERENCES `dealer_assignments` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_dah_actor` FOREIGN KEY (`actor_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 38. supplier_purchase_orders
-- Created ONLY after dealer accepts assignment & commercial terms are agreed.
CREATE TABLE IF NOT EXISTS `supplier_purchase_orders` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `po_number` VARCHAR(64) NOT NULL,
  `supplier_lot_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `dealer_assignment_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `supplier_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `dealer_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `destination_warehouse_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `currency_code` CHAR(3) NOT NULL DEFAULT 'INR',
  `subtotal_amount` DECIMAL(14,2) NOT NULL,
  `tax_amount` DECIMAL(14,2) NOT NULL DEFAULT 0.00,
  `freight_amount` DECIMAL(14,2) NOT NULL DEFAULT 0.00,
  `total_amount` DECIMAL(14,2) NOT NULL,
  `payment_terms` VARCHAR(160) NULL,
  `payment_due_date` DATE NULL,
  `settlement_status` ENUM('UNPAID', 'PARTIALLY_SETTLED', 'SETTLED', 'DISPUTED') NOT NULL DEFAULT 'UNPAID',
  `po_status` ENUM('DRAFT', 'ISSUED', 'CONFIRMED_BY_SUPPLIER', 'IN_TRANSIT', 'PARTIALLY_RECEIVED', 'RECEIVED', 'INSPECTED', 'CLOSED', 'CANCELLED') NOT NULL DEFAULT 'DRAFT',
  `expected_delivery_date` DATE NULL,
  `created_by_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_spo_po_number` (`po_number`),
  UNIQUE KEY `uq_spo_assignment` (`dealer_assignment_id`),
  KEY `idx_spo_supplier_status` (`supplier_profile_id`, `po_status`),
  KEY `idx_spo_dealer_status` (`dealer_profile_id`, `po_status`),
  KEY `idx_spo_lot` (`supplier_lot_id`),
  KEY `idx_spo_warehouse` (`destination_warehouse_id`),
  KEY `idx_spo_created_by` (`created_by_user_id`),
  CONSTRAINT `fk_spo_lot` FOREIGN KEY (`supplier_lot_id`) REFERENCES `supplier_lots` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_spo_assignment` FOREIGN KEY (`dealer_assignment_id`) REFERENCES `dealer_assignments` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_spo_supplier` FOREIGN KEY (`supplier_profile_id`) REFERENCES `supplier_profiles` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_spo_dealer` FOREIGN KEY (`dealer_profile_id`) REFERENCES `dealer_profiles` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_spo_warehouse` FOREIGN KEY (`destination_warehouse_id`) REFERENCES `warehouses` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_spo_created_by` FOREIGN KEY (`created_by_user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_spo_amounts` CHECK (`subtotal_amount` >= 0.00 AND `tax_amount` >= 0.00 AND `freight_amount` >= 0.00 AND `total_amount` > 0.00),
  CONSTRAINT `chk_spo_currency` CHECK (CHAR_LENGTH(`currency_code`) = 3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 39. supplier_purchase_order_status_history
CREATE TABLE IF NOT EXISTS `supplier_purchase_order_status_history` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `supplier_purchase_order_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `from_status` VARCHAR(40) NULL,
  `to_status` VARCHAR(40) NOT NULL,
  `actor_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `reason` VARCHAR(1000) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_sposh_po` (`supplier_purchase_order_id`, `created_at`),
  KEY `idx_sposh_actor` (`actor_user_id`),
  CONSTRAINT `fk_sposh_po` FOREIGN KEY (`supplier_purchase_order_id`) REFERENCES `supplier_purchase_orders` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_sposh_actor` FOREIGN KEY (`actor_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 40. supplier_purchase_order_items
CREATE TABLE IF NOT EXISTS `supplier_purchase_order_items` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `supplier_purchase_order_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `product_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `product_variant_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `item_title_snapshot` VARCHAR(220) NOT NULL,
  `sku_snapshot` VARCHAR(100) NOT NULL,
  `ordered_quantity` DECIMAL(14,3) NOT NULL,
  `unit_of_measure` VARCHAR(32) NOT NULL DEFAULT 'PCS',
  `unit_cost` DECIMAL(14,2) NOT NULL,
  `tax_amount` DECIMAL(14,2) NOT NULL DEFAULT 0.00,
  `line_total` DECIMAL(14,2) NOT NULL,
  `currency_code` CHAR(3) NOT NULL DEFAULT 'INR',
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_spoi_po` (`supplier_purchase_order_id`),
  KEY `idx_spoi_product` (`product_id`),
  KEY `idx_spoi_variant` (`product_variant_id`),
  CONSTRAINT `fk_spoi_po` FOREIGN KEY (`supplier_purchase_order_id`) REFERENCES `supplier_purchase_orders` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_spoi_product` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_spoi_variant` FOREIGN KEY (`product_variant_id`) REFERENCES `product_variants` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_spoi_qty` CHECK (`ordered_quantity` > 0.000),
  CONSTRAINT `chk_spoi_cost` CHECK (`unit_cost` > 0.00 AND `tax_amount` >= 0.00 AND `line_total` > 0.00),
  CONSTRAINT `chk_spoi_currency` CHECK (CHAR_LENGTH(`currency_code`) = 3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 41. goods_receipts
CREATE TABLE IF NOT EXISTS `goods_receipts` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `receipt_number` VARCHAR(64) NOT NULL,
  `supplier_purchase_order_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `warehouse_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `dealer_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `received_by_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `received_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `receipt_status` ENUM('RECEIVED_PENDING_INSPECTION', 'INSPECTED', 'POSTED_TO_INVENTORY', 'REJECTED') NOT NULL DEFAULT 'RECEIVED_PENDING_INSPECTION',
  `carrier_reference` VARCHAR(120) NULL,
  `notes` TEXT NULL,
  `posted_to_inventory_at` DATETIME(6) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_gr_receipt_number` (`receipt_number`),
  KEY `idx_gr_po` (`supplier_purchase_order_id`),
  KEY `idx_gr_warehouse` (`warehouse_id`),
  KEY `idx_gr_dealer_status` (`dealer_profile_id`, `receipt_status`),
  KEY `idx_gr_received_by` (`received_by_user_id`),
  CONSTRAINT `fk_gr_po` FOREIGN KEY (`supplier_purchase_order_id`) REFERENCES `supplier_purchase_orders` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_gr_warehouse` FOREIGN KEY (`warehouse_id`) REFERENCES `warehouses` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_gr_dealer` FOREIGN KEY (`dealer_profile_id`) REFERENCES `dealer_profiles` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_gr_received_by` FOREIGN KEY (`received_by_user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 42. goods_receipt_items
CREATE TABLE IF NOT EXISTS `goods_receipt_items` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `goods_receipt_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `supplier_po_item_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `product_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `product_variant_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `received_quantity` DECIMAL(14,3) NOT NULL,
  `accepted_quantity` DECIMAL(14,3) NOT NULL DEFAULT 0.000,
  `rejected_quantity` DECIMAL(14,3) NOT NULL DEFAULT 0.000,
  `damaged_quantity` DECIMAL(14,3) NOT NULL DEFAULT 0.000,
  `inventory_posted` TINYINT(1) NOT NULL DEFAULT 0,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_gri_receipt` (`goods_receipt_id`),
  KEY `idx_gri_po_item` (`supplier_po_item_id`),
  KEY `idx_gri_product` (`product_id`),
  KEY `idx_gri_variant` (`product_variant_id`),
  CONSTRAINT `fk_gri_receipt` FOREIGN KEY (`goods_receipt_id`) REFERENCES `goods_receipts` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_gri_po_item` FOREIGN KEY (`supplier_po_item_id`) REFERENCES `supplier_purchase_order_items` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_gri_product` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_gri_variant` FOREIGN KEY (`product_variant_id`) REFERENCES `product_variants` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_gri_quantities` CHECK (
    `received_quantity` >= 0.000
    AND `accepted_quantity` >= 0.000
    AND `rejected_quantity` >= 0.000
    AND `damaged_quantity` >= 0.000
    AND (`accepted_quantity` + `rejected_quantity` + `damaged_quantity`) <= `received_quantity`
  ),
  CONSTRAINT `chk_gri_posted` CHECK (`inventory_posted` IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 43. quality_inspections
CREATE TABLE IF NOT EXISTS `quality_inspections` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `goods_receipt_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `goods_receipt_item_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `inspector_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `inspection_outcome` ENUM('PASSED', 'PARTIALLY_PASSED', 'FAILED') NOT NULL,
  `checklist_results_json` JSON NULL,
  `notes` TEXT NULL,
  `inspected_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_qi_receipt` (`goods_receipt_id`),
  KEY `idx_qi_receipt_item` (`goods_receipt_item_id`),
  KEY `idx_qi_inspector` (`inspector_user_id`),
  CONSTRAINT `fk_qi_receipt` FOREIGN KEY (`goods_receipt_id`) REFERENCES `goods_receipts` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_qi_receipt_item` FOREIGN KEY (`goods_receipt_item_id`) REFERENCES `goods_receipt_items` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_qi_inspector` FOREIGN KEY (`inspector_user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- >>> END 04_suppliers_dealers_and_procurement.sql <<<


-- >>> BEGIN 05_inventory_and_retail.sql <<<

-- =============================================================================
-- HunarLink MySQL 8.4 LTS Schema
-- File: sql/05_inventory_and_retail.sql
-- Module E: Inventory and Retail Commerce (10 tables)
-- Tables:
--   44. warehouse_stock
--   45. inventory_transactions
--   46. carts
--   47. cart_items
--   48. wishlists
--   49. wishlist_items
--   50. retail_orders
--   51. seller_fulfilment_groups
--   52. retail_order_items
--   53. retail_order_status_history
-- Rules:
--   - Separate available, reserved, and damaged stock quantities (all >= 0).
--   - Accepted goods receipt updates dealer stock EXACTLY ONCE (enforced by
--     generated unique guard on inventory_transactions).
--   - One multi-seller retail order splits into separate seller_fulfilment_groups.
--   - Order items store immutable price/title/SKU/tax/discount snapshots.
-- =============================================================================

USE `hunarlink`;

-- 44. warehouse_stock
CREATE TABLE IF NOT EXISTS `warehouse_stock` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `warehouse_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `product_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `product_variant_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `owner_type` ENUM('SELLER', 'DEALER', 'PLATFORM') NOT NULL,
  `seller_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `dealer_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `seller_listing_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `available_quantity` DECIMAL(14,3) NOT NULL DEFAULT 0.000,
  `reserved_quantity` DECIMAL(14,3) NOT NULL DEFAULT 0.000,
  `damaged_quantity` DECIMAL(14,3) NOT NULL DEFAULT 0.000,
  `reorder_threshold` DECIMAL(14,3) NOT NULL DEFAULT 0.000,
  `version` BIGINT UNSIGNED NOT NULL DEFAULT 1,
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_ws_warehouse_variant_owner` (`warehouse_id`, `product_variant_id`, `owner_type`),
  KEY `idx_ws_product` (`product_id`),
  KEY `idx_ws_variant` (`product_variant_id`),
  KEY `idx_ws_seller` (`seller_profile_id`),
  KEY `idx_ws_dealer` (`dealer_profile_id`),
  KEY `idx_ws_seller_listing` (`seller_listing_id`),
  CONSTRAINT `fk_ws_warehouse` FOREIGN KEY (`warehouse_id`) REFERENCES `warehouses` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_ws_product` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_ws_variant` FOREIGN KEY (`product_variant_id`) REFERENCES `product_variants` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_ws_seller` FOREIGN KEY (`seller_profile_id`) REFERENCES `seller_profiles` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_ws_dealer` FOREIGN KEY (`dealer_profile_id`) REFERENCES `dealer_profiles` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_ws_seller_listing` FOREIGN KEY (`seller_listing_id`) REFERENCES `seller_product_listings` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `chk_ws_non_negative` CHECK (`available_quantity` >= 0.000 AND `reserved_quantity` >= 0.000 AND `damaged_quantity` >= 0.000 AND `reorder_threshold` >= 0.000),
  CONSTRAINT `chk_ws_owner_match` CHECK (
    (`owner_type` = 'SELLER' AND `seller_profile_id` IS NOT NULL AND `dealer_profile_id` IS NULL)
    OR (`owner_type` = 'DEALER' AND `dealer_profile_id` IS NOT NULL AND `seller_profile_id` IS NULL)
    OR (`owner_type` = 'PLATFORM' AND `seller_profile_id` IS NULL AND `dealer_profile_id` IS NULL)
  )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 45. inventory_transactions
-- Immutable ledger of every stock movement. Generated column guarantees each
-- goods_receipt_item can post accepted dealer stock AT MOST ONCE.
CREATE TABLE IF NOT EXISTS `inventory_transactions` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `warehouse_stock_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `warehouse_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `product_variant_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `goods_receipt_item_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `movement_type` ENUM('OPENING_BALANCE', 'GOODS_RECEIPT_ACCEPT', 'GOODS_RECEIPT_DAMAGED', 'RESERVE', 'RELEASE_RESERVATION', 'CONSUME_RESERVATION', 'RETURN_RESTOCK', 'DAMAGE_WRITE_OFF', 'MANUAL_ADJUSTMENT') NOT NULL,
  `quantity_delta` DECIMAL(14,3) NOT NULL,
  `available_after` DECIMAL(14,3) NOT NULL,
  `reserved_after` DECIMAL(14,3) NOT NULL,
  `damaged_after` DECIMAL(14,3) NOT NULL,
  `reference_type` VARCHAR(64) NULL,
  `reference_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `goods_receipt_post_guard` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin GENERATED ALWAYS AS (
    IF(`movement_type` = 'GOODS_RECEIPT_ACCEPT' AND `goods_receipt_item_id` IS NOT NULL, `goods_receipt_item_id`, NULL)
  ) STORED,
  `actor_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `reason` VARCHAR(500) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_inv_tx_single_gr_post` (`goods_receipt_post_guard`),
  KEY `idx_inv_tx_stock_created` (`warehouse_stock_id`, `created_at`),
  KEY `idx_inv_tx_warehouse` (`warehouse_id`),
  KEY `idx_inv_tx_variant` (`product_variant_id`),
  KEY `idx_inv_tx_gr_item` (`goods_receipt_item_id`),
  KEY `idx_inv_tx_ref` (`reference_type`, `reference_id`),
  KEY `idx_inv_tx_actor` (`actor_user_id`),
  CONSTRAINT `fk_inv_tx_stock` FOREIGN KEY (`warehouse_stock_id`) REFERENCES `warehouse_stock` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_inv_tx_warehouse` FOREIGN KEY (`warehouse_id`) REFERENCES `warehouses` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_inv_tx_variant` FOREIGN KEY (`product_variant_id`) REFERENCES `product_variants` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_inv_tx_gr_item` FOREIGN KEY (`goods_receipt_item_id`) REFERENCES `goods_receipt_items` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_inv_tx_actor` FOREIGN KEY (`actor_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `chk_inv_tx_balances` CHECK (`available_after` >= 0.000 AND `reserved_after` >= 0.000 AND `damaged_after` >= 0.000)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 46. carts
CREATE TABLE IF NOT EXISTS `carts` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `cart_status` ENUM('ACTIVE', 'CONVERTED', 'ABANDONED') NOT NULL DEFAULT 'ACTIVE',
  `active_cart_guard` TINYINT(1) GENERATED ALWAYS AS (IF(`cart_status` = 'ACTIVE', 1, NULL)) STORED,
  `currency_code` CHAR(3) NOT NULL DEFAULT 'INR',
  `applied_coupon_code` VARCHAR(64) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_carts_user_active` (`user_id`, `active_cart_guard`),
  KEY `idx_carts_user_status` (`user_id`, `cart_status`),
  CONSTRAINT `fk_carts_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_carts_currency` CHECK (CHAR_LENGTH(`currency_code`) = 3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 47. cart_items
CREATE TABLE IF NOT EXISTS `cart_items` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `cart_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `seller_listing_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `product_variant_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `quantity` INT UNSIGNED NOT NULL DEFAULT 1,
  `unit_price_snapshot` DECIMAL(14,2) NOT NULL,
  `currency_code` CHAR(3) NOT NULL DEFAULT 'INR',
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_cart_items_cart_listing` (`cart_id`, `seller_listing_id`),
  KEY `idx_ci_listing` (`seller_listing_id`),
  KEY `idx_ci_variant` (`product_variant_id`),
  CONSTRAINT `fk_ci_cart` FOREIGN KEY (`cart_id`) REFERENCES `carts` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `fk_ci_listing` FOREIGN KEY (`seller_listing_id`) REFERENCES `seller_product_listings` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_ci_variant` FOREIGN KEY (`product_variant_id`) REFERENCES `product_variants` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_ci_qty` CHECK (`quantity` >= 1),
  CONSTRAINT `chk_ci_price` CHECK (`unit_price_snapshot` > 0.00),
  CONSTRAINT `chk_ci_currency` CHECK (CHAR_LENGTH(`currency_code`) = 3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 48. wishlists
CREATE TABLE IF NOT EXISTS `wishlists` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `name` VARCHAR(100) NOT NULL DEFAULT 'Saved Crafts',
  `is_default` TINYINT(1) NOT NULL DEFAULT 1,
  `default_wishlist_guard` TINYINT(1) GENERATED ALWAYS AS (IF(`is_default` = 1, 1, NULL)) STORED,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_wishlists_user_default` (`user_id`, `default_wishlist_guard`),
  KEY `idx_wishlists_user` (`user_id`),
  CONSTRAINT `fk_wishlists_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_wishlists_default` CHECK (`is_default` IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 49. wishlist_items
CREATE TABLE IF NOT EXISTS `wishlist_items` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `wishlist_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `product_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `product_variant_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `seller_listing_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_wishlist_items_unique` (`wishlist_id`, `product_id`),
  KEY `idx_wi_product` (`product_id`),
  KEY `idx_wi_variant` (`product_variant_id`),
  KEY `idx_wi_listing` (`seller_listing_id`),
  CONSTRAINT `fk_wi_wishlist` FOREIGN KEY (`wishlist_id`) REFERENCES `wishlists` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `fk_wi_product` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_wi_variant` FOREIGN KEY (`product_variant_id`) REFERENCES `product_variants` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `fk_wi_listing` FOREIGN KEY (`seller_listing_id`) REFERENCES `seller_product_listings` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 50. retail_orders
-- Customer order header. Payment status is tracked separately from fulfilment status.
CREATE TABLE IF NOT EXISTS `retail_orders` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `order_number` VARCHAR(64) NOT NULL,
  `customer_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `shipping_address_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `shipping_address_snapshot_json` JSON NOT NULL,
  `currency_code` CHAR(3) NOT NULL DEFAULT 'INR',
  `subtotal_amount` DECIMAL(14,2) NOT NULL,
  `discount_amount` DECIMAL(14,2) NOT NULL DEFAULT 0.00,
  `tax_amount` DECIMAL(14,2) NOT NULL DEFAULT 0.00,
  `shipping_fee` DECIMAL(14,2) NOT NULL DEFAULT 0.00,
  `total_amount` DECIMAL(14,2) NOT NULL,
  `coupon_code_snapshot` VARCHAR(64) NULL,
  `payment_method` ENUM('RAZORPAY_STANDARD', 'COD') NOT NULL DEFAULT 'RAZORPAY_STANDARD',
  `payment_status` ENUM('PENDING', 'AUTHORIZED', 'PAID', 'FAILED', 'PARTIALLY_REFUNDED', 'REFUNDED', 'COD_PENDING', 'COD_COLLECTED') NOT NULL DEFAULT 'PENDING',
  `fulfilment_status` ENUM('PENDING_PAYMENT', 'CONFIRMED', 'PROCESSING', 'PARTIALLY_SHIPPED', 'SHIPPED', 'DELIVERED', 'CANCELLED', 'RETURNED') NOT NULL DEFAULT 'PENDING_PAYMENT',
  `placed_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `confirmed_at` DATETIME(6) NULL,
  `cancelled_at` DATETIME(6) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_retail_orders_number` (`order_number`),
  KEY `idx_ro_customer_created` (`customer_user_id`, `created_at`),
  KEY `idx_ro_statuses` (`payment_status`, `fulfilment_status`),
  KEY `idx_ro_shipping_addr` (`shipping_address_id`),
  CONSTRAINT `fk_ro_customer` FOREIGN KEY (`customer_user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_ro_shipping_addr` FOREIGN KEY (`shipping_address_id`) REFERENCES `user_addresses` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `chk_ro_amounts` CHECK (`subtotal_amount` >= 0.00 AND `discount_amount` >= 0.00 AND `tax_amount` >= 0.00 AND `shipping_fee` >= 0.00 AND `total_amount` >= 0.00),
  CONSTRAINT `chk_ro_currency` CHECK (CHAR_LENGTH(`currency_code`) = 3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 51. seller_fulfilment_groups
-- Multi-seller retail checkout splits cleanly into one fulfilment group per seller.
CREATE TABLE IF NOT EXISTS `seller_fulfilment_groups` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `fulfilment_number` VARCHAR(64) NOT NULL,
  `retail_order_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `seller_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `warehouse_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `currency_code` CHAR(3) NOT NULL DEFAULT 'INR',
  `subtotal_amount` DECIMAL(14,2) NOT NULL,
  `discount_amount` DECIMAL(14,2) NOT NULL DEFAULT 0.00,
  `tax_amount` DECIMAL(14,2) NOT NULL DEFAULT 0.00,
  `shipping_fee` DECIMAL(14,2) NOT NULL DEFAULT 0.00,
  `group_total_amount` DECIMAL(14,2) NOT NULL,
  `fulfilment_status` ENUM('PENDING_PAYMENT', 'CONFIRMED', 'PACKED', 'SHIPPED', 'OUT_FOR_DELIVERY', 'DELIVERED', 'CANCELLED', 'RETURNED') NOT NULL DEFAULT 'PENDING_PAYMENT',
  `seller_notes` VARCHAR(500) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_sfg_number` (`fulfilment_number`),
  UNIQUE KEY `uq_sfg_order_seller` (`retail_order_id`, `seller_profile_id`),
  KEY `idx_sfg_seller_status` (`seller_profile_id`, `fulfilment_status`),
  KEY `idx_sfg_warehouse` (`warehouse_id`),
  CONSTRAINT `fk_sfg_order` FOREIGN KEY (`retail_order_id`) REFERENCES `retail_orders` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_sfg_seller` FOREIGN KEY (`seller_profile_id`) REFERENCES `seller_profiles` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_sfg_warehouse` FOREIGN KEY (`warehouse_id`) REFERENCES `warehouses` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `chk_sfg_amounts` CHECK (`subtotal_amount` >= 0.00 AND `discount_amount` >= 0.00 AND `tax_amount` >= 0.00 AND `shipping_fee` >= 0.00 AND `group_total_amount` >= 0.00),
  CONSTRAINT `chk_sfg_currency` CHECK (CHAR_LENGTH(`currency_code`) = 3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 52. retail_order_items
-- Stores immutable snapshots so future catalogue edits never alter historical orders.
CREATE TABLE IF NOT EXISTS `retail_order_items` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `retail_order_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `seller_fulfilment_group_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `seller_listing_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `product_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `product_variant_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `product_name_snapshot` VARCHAR(220) NOT NULL,
  `sku_snapshot` VARCHAR(100) NOT NULL,
  `gi_status_snapshot` VARCHAR(40) NOT NULL,
  `quantity` INT UNSIGNED NOT NULL,
  `unit_price_snapshot` DECIMAL(14,2) NOT NULL,
  `discount_amount_snapshot` DECIMAL(14,2) NOT NULL DEFAULT 0.00,
  `tax_amount_snapshot` DECIMAL(14,2) NOT NULL DEFAULT 0.00,
  `line_total_amount` DECIMAL(14,2) NOT NULL,
  `currency_code` CHAR(3) NOT NULL DEFAULT 'INR',
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_roi_order` (`retail_order_id`),
  KEY `idx_roi_group` (`seller_fulfilment_group_id`),
  KEY `idx_roi_listing` (`seller_listing_id`),
  KEY `idx_roi_product` (`product_id`),
  KEY `idx_roi_variant` (`product_variant_id`),
  CONSTRAINT `fk_roi_order` FOREIGN KEY (`retail_order_id`) REFERENCES `retail_orders` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_roi_group` FOREIGN KEY (`seller_fulfilment_group_id`) REFERENCES `seller_fulfilment_groups` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_roi_listing` FOREIGN KEY (`seller_listing_id`) REFERENCES `seller_product_listings` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_roi_product` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_roi_variant` FOREIGN KEY (`product_variant_id`) REFERENCES `product_variants` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_roi_qty` CHECK (`quantity` >= 1),
  CONSTRAINT `chk_roi_amounts` CHECK (`unit_price_snapshot` > 0.00 AND `discount_amount_snapshot` >= 0.00 AND `tax_amount_snapshot` >= 0.00 AND `line_total_amount` >= 0.00),
  CONSTRAINT `chk_roi_currency` CHECK (CHAR_LENGTH(`currency_code`) = 3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 53. retail_order_status_history
CREATE TABLE IF NOT EXISTS `retail_order_status_history` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `retail_order_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `seller_fulfilment_group_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `status_scope` ENUM('ORDER_FULFILMENT', 'SELLER_FULFILMENT', 'PAYMENT_SYNC') NOT NULL DEFAULT 'ORDER_FULFILMENT',
  `from_status` VARCHAR(40) NULL,
  `to_status` VARCHAR(40) NOT NULL,
  `actor_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `reason` VARCHAR(1000) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_rosh_order_created` (`retail_order_id`, `created_at`),
  KEY `idx_rosh_group` (`seller_fulfilment_group_id`),
  KEY `idx_rosh_actor` (`actor_user_id`),
  CONSTRAINT `fk_rosh_order` FOREIGN KEY (`retail_order_id`) REFERENCES `retail_orders` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_rosh_group` FOREIGN KEY (`seller_fulfilment_group_id`) REFERENCES `seller_fulfilment_groups` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_rosh_actor` FOREIGN KEY (`actor_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- >>> END 05_inventory_and_retail.sql <<<


-- >>> BEGIN 06_wholesale_marketplace.sql <<<

-- =============================================================================
-- HunarLink MySQL 8.4 LTS Schema
-- File: sql/06_wholesale_marketplace.sql
-- Module C (Dealer Wholesale Listing) & Module F: Wholesale Marketplace (14 tables)
-- Tables:
--   54. dealer_wholesale_listings
--   55. wholesale_buyer_profiles
--   56. wholesale_price_tiers
--   57. wholesale_carts
--   58. wholesale_cart_items
--   59. wholesale_rfqs
--   60. wholesale_rfq_items
--   61. rfq_dealer_invitations
--   62. dealer_quotes
--   63. dealer_quote_items
--   64. wholesale_orders
--   65. wholesale_order_items
--   66. wholesale_order_status_history
--   67. stock_reservations
-- Rules:
--   - Supports MOQ, bulk availability, and quantity-based price tiers.
--   - Buyer creates an RFQ; dealers submit quotes; buyer accepts a valid quote.
--   - In v1, one wholesale order is fulfilled by one dealer.
--   - Accepted quote must belong to the buyer's RFQ and selected dealer.
-- =============================================================================

USE `hunarlink`;

-- 54. dealer_wholesale_listings
CREATE TABLE IF NOT EXISTS `dealer_wholesale_listings` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `dealer_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `product_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `product_variant_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `warehouse_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `warehouse_stock_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `dealer_sku` VARCHAR(100) NOT NULL,
  `listing_title` VARCHAR(220) NOT NULL,
  `base_unit_price` DECIMAL(14,2) NOT NULL,
  `currency_code` CHAR(3) NOT NULL DEFAULT 'INR',
  `minimum_order_quantity` DECIMAL(14,3) NOT NULL,
  `order_quantity_increment` DECIMAL(14,3) NOT NULL DEFAULT 1.000,
  `lead_time_days` SMALLINT UNSIGNED NOT NULL DEFAULT 14,
  `listing_status` ENUM('DRAFT', 'PENDING_APPROVAL', 'ACTIVE', 'PAUSED', 'REJECTED', 'ARCHIVED') NOT NULL DEFAULT 'DRAFT',
  `published_at` DATETIME(6) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_dwl_dealer_sku` (`dealer_profile_id`, `dealer_sku`),
  KEY `idx_dwl_product_status` (`product_id`, `listing_status`),
  KEY `idx_dwl_variant_status` (`product_variant_id`, `listing_status`),
  KEY `idx_dwl_warehouse` (`warehouse_id`),
  KEY `idx_dwl_stock` (`warehouse_stock_id`),
  CONSTRAINT `fk_dwl_dealer` FOREIGN KEY (`dealer_profile_id`) REFERENCES `dealer_profiles` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_dwl_product` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_dwl_variant` FOREIGN KEY (`product_variant_id`) REFERENCES `product_variants` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_dwl_warehouse` FOREIGN KEY (`warehouse_id`) REFERENCES `warehouses` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_dwl_stock` FOREIGN KEY (`warehouse_stock_id`) REFERENCES `warehouse_stock` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `chk_dwl_price` CHECK (`base_unit_price` > 0.00),
  CONSTRAINT `chk_dwl_moq` CHECK (`minimum_order_quantity` > 0.000 AND `order_quantity_increment` > 0.000),
  CONSTRAINT `chk_dwl_currency` CHECK (CHAR_LENGTH(`currency_code`) = 3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 55. wholesale_buyer_profiles
CREATE TABLE IF NOT EXISTS `wholesale_buyer_profiles` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `company_name` VARCHAR(200) NOT NULL,
  `buyer_segment` ENUM('RETAIL_BOUTIQUE', 'HOSPITALITY', 'INTERIOR_STUDIO', 'EXPORTER', 'CORPORATE_GIFTING', 'OTHER') NOT NULL DEFAULT 'RETAIL_BOUTIQUE',
  `gstin` VARCHAR(20) NULL,
  `business_city` VARCHAR(100) NOT NULL,
  `business_state` VARCHAR(100) NOT NULL,
  `country_code` CHAR(2) NOT NULL DEFAULT 'IN',
  `profile_status` ENUM('DRAFT', 'ACTIVE', 'SUSPENDED', 'TERMINATED') NOT NULL DEFAULT 'DRAFT',
  `verification_status` ENUM('UNVERIFIED', 'SUBMITTED', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'REVOKED') NOT NULL DEFAULT 'UNVERIFIED',
  `approved_at` DATETIME(6) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_wbp_user_id` (`user_id`),
  KEY `idx_wbp_status` (`profile_status`, `verification_status`),
  CONSTRAINT `fk_wbp_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 56. wholesale_price_tiers
CREATE TABLE IF NOT EXISTS `wholesale_price_tiers` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `dealer_wholesale_listing_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `min_quantity` DECIMAL(14,3) NOT NULL,
  `max_quantity` DECIMAL(14,3) NULL,
  `unit_price` DECIMAL(14,2) NOT NULL,
  `currency_code` CHAR(3) NOT NULL DEFAULT 'INR',
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_wpt_listing_min_qty` (`dealer_wholesale_listing_id`, `min_quantity`),
  KEY `idx_wpt_listing_active` (`dealer_wholesale_listing_id`, `is_active`),
  CONSTRAINT `fk_wpt_listing` FOREIGN KEY (`dealer_wholesale_listing_id`) REFERENCES `dealer_wholesale_listings` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `chk_wpt_qty` CHECK (`min_quantity` > 0.000 AND (`max_quantity` IS NULL OR `max_quantity` >= `min_quantity`)),
  CONSTRAINT `chk_wpt_price` CHECK (`unit_price` > 0.00),
  CONSTRAINT `chk_wpt_currency` CHECK (CHAR_LENGTH(`currency_code`) = 3),
  CONSTRAINT `chk_wpt_active` CHECK (`is_active` IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 57. wholesale_carts
CREATE TABLE IF NOT EXISTS `wholesale_carts` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `wholesale_buyer_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `cart_status` ENUM('ACTIVE', 'CONVERTED', 'ABANDONED') NOT NULL DEFAULT 'ACTIVE',
  `active_cart_guard` TINYINT(1) GENERATED ALWAYS AS (IF(`cart_status` = 'ACTIVE', 1, NULL)) STORED,
  `currency_code` CHAR(3) NOT NULL DEFAULT 'INR',
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_wc_buyer_active` (`wholesale_buyer_profile_id`, `active_cart_guard`),
  KEY `idx_wc_user` (`user_id`),
  CONSTRAINT `fk_wc_buyer` FOREIGN KEY (`wholesale_buyer_profile_id`) REFERENCES `wholesale_buyer_profiles` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_wc_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_wc_currency` CHECK (CHAR_LENGTH(`currency_code`) = 3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 58. wholesale_cart_items
CREATE TABLE IF NOT EXISTS `wholesale_cart_items` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `wholesale_cart_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `dealer_wholesale_listing_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `product_variant_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `quantity` DECIMAL(14,3) NOT NULL,
  `tier_unit_price_snapshot` DECIMAL(14,2) NOT NULL,
  `currency_code` CHAR(3) NOT NULL DEFAULT 'INR',
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_wci_cart_listing` (`wholesale_cart_id`, `dealer_wholesale_listing_id`),
  KEY `idx_wci_listing` (`dealer_wholesale_listing_id`),
  KEY `idx_wci_variant` (`product_variant_id`),
  CONSTRAINT `fk_wci_cart` FOREIGN KEY (`wholesale_cart_id`) REFERENCES `wholesale_carts` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `fk_wci_listing` FOREIGN KEY (`dealer_wholesale_listing_id`) REFERENCES `dealer_wholesale_listings` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_wci_variant` FOREIGN KEY (`product_variant_id`) REFERENCES `product_variants` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_wci_qty` CHECK (`quantity` > 0.000),
  CONSTRAINT `chk_wci_price` CHECK (`tier_unit_price_snapshot` > 0.00),
  CONSTRAINT `chk_wci_currency` CHECK (CHAR_LENGTH(`currency_code`) = 3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 59. wholesale_rfqs
CREATE TABLE IF NOT EXISTS `wholesale_rfqs` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `rfq_number` VARCHAR(64) NOT NULL,
  `wholesale_buyer_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `buyer_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `delivery_address_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `title` VARCHAR(220) NOT NULL,
  `requirements_notes` TEXT NULL,
  `target_delivery_date` DATE NULL,
  `currency_code` CHAR(3) NOT NULL DEFAULT 'INR',
  `rfq_status` ENUM('DRAFT', 'OPEN', 'QUOTES_RECEIVED', 'QUOTE_ACCEPTED', 'EXPIRED', 'CANCELLED', 'CLOSED') NOT NULL DEFAULT 'DRAFT',
  `expires_at` DATETIME(6) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_wrfq_number` (`rfq_number`),
  KEY `idx_wrfq_buyer_status` (`wholesale_buyer_profile_id`, `rfq_status`),
  KEY `idx_wrfq_user` (`buyer_user_id`),
  KEY `idx_wrfq_delivery_addr` (`delivery_address_id`),
  CONSTRAINT `fk_wrfq_buyer` FOREIGN KEY (`wholesale_buyer_profile_id`) REFERENCES `wholesale_buyer_profiles` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_wrfq_user` FOREIGN KEY (`buyer_user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_wrfq_delivery_addr` FOREIGN KEY (`delivery_address_id`) REFERENCES `user_addresses` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `chk_wrfq_currency` CHECK (CHAR_LENGTH(`currency_code`) = 3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 60. wholesale_rfq_items
CREATE TABLE IF NOT EXISTS `wholesale_rfq_items` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `wholesale_rfq_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `category_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `product_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `product_variant_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `item_description` VARCHAR(300) NOT NULL,
  `requested_quantity` DECIMAL(14,3) NOT NULL,
  `unit_of_measure` VARCHAR(32) NOT NULL DEFAULT 'PCS',
  `target_unit_price` DECIMAL(14,2) NULL,
  `requires_gi_verified` TINYINT(1) NOT NULL DEFAULT 0,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_wrfqi_rfq` (`wholesale_rfq_id`),
  KEY `idx_wrfqi_category` (`category_id`),
  KEY `idx_wrfqi_product` (`product_id`),
  KEY `idx_wrfqi_variant` (`product_variant_id`),
  CONSTRAINT `fk_wrfqi_rfq` FOREIGN KEY (`wholesale_rfq_id`) REFERENCES `wholesale_rfqs` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `fk_wrfqi_category` FOREIGN KEY (`category_id`) REFERENCES `categories` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_wrfqi_product` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `fk_wrfqi_variant` FOREIGN KEY (`product_variant_id`) REFERENCES `product_variants` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `chk_wrfqi_qty` CHECK (`requested_quantity` > 0.000),
  CONSTRAINT `chk_wrfqi_price` CHECK (`target_unit_price` IS NULL OR `target_unit_price` > 0.00),
  CONSTRAINT `chk_wrfqi_gi` CHECK (`requires_gi_verified` IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 61. rfq_dealer_invitations
CREATE TABLE IF NOT EXISTS `rfq_dealer_invitations` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `wholesale_rfq_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `dealer_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `invited_by_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `invitation_status` ENUM('INVITED', 'VIEWED', 'QUOTED', 'DECLINED', 'EXPIRED') NOT NULL DEFAULT 'INVITED',
  `invited_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `responded_at` DATETIME(6) NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_rdi_rfq_dealer` (`wholesale_rfq_id`, `dealer_profile_id`),
  KEY `idx_rdi_dealer_status` (`dealer_profile_id`, `invitation_status`),
  KEY `idx_rdi_invited_by` (`invited_by_user_id`),
  CONSTRAINT `fk_rdi_rfq` FOREIGN KEY (`wholesale_rfq_id`) REFERENCES `wholesale_rfqs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_rdi_dealer` FOREIGN KEY (`dealer_profile_id`) REFERENCES `dealer_profiles` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_rdi_invited_by` FOREIGN KEY (`invited_by_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 62. dealer_quotes
CREATE TABLE IF NOT EXISTS `dealer_quotes` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `quote_number` VARCHAR(64) NOT NULL,
  `wholesale_rfq_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `rfq_invitation_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `dealer_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `submitted_by_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `currency_code` CHAR(3) NOT NULL DEFAULT 'INR',
  `subtotal_amount` DECIMAL(14,2) NOT NULL,
  `discount_amount` DECIMAL(14,2) NOT NULL DEFAULT 0.00,
  `tax_amount` DECIMAL(14,2) NOT NULL DEFAULT 0.00,
  `shipping_fee` DECIMAL(14,2) NOT NULL DEFAULT 0.00,
  `total_amount` DECIMAL(14,2) NOT NULL,
  `lead_time_days` SMALLINT UNSIGNED NOT NULL DEFAULT 14,
  `valid_until` DATETIME(6) NOT NULL,
  `quote_status` ENUM('DRAFT', 'SUBMITTED', 'ACCEPTED', 'REJECTED', 'WITHDRAWN', 'EXPIRED', 'CONVERTED_TO_ORDER') NOT NULL DEFAULT 'DRAFT',
  `terms_notes` TEXT NULL,
  `accepted_at` DATETIME(6) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_dq_number` (`quote_number`),
  KEY `idx_dq_rfq_status` (`wholesale_rfq_id`, `quote_status`),
  KEY `idx_dq_dealer_status` (`dealer_profile_id`, `quote_status`),
  KEY `idx_dq_invitation` (`rfq_invitation_id`),
  KEY `idx_dq_submitted_by` (`submitted_by_user_id`),
  CONSTRAINT `fk_dq_rfq` FOREIGN KEY (`wholesale_rfq_id`) REFERENCES `wholesale_rfqs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_dq_invitation` FOREIGN KEY (`rfq_invitation_id`) REFERENCES `rfq_dealer_invitations` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `fk_dq_dealer` FOREIGN KEY (`dealer_profile_id`) REFERENCES `dealer_profiles` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_dq_submitted_by` FOREIGN KEY (`submitted_by_user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_dq_amounts` CHECK (`subtotal_amount` >= 0.00 AND `discount_amount` >= 0.00 AND `tax_amount` >= 0.00 AND `shipping_fee` >= 0.00 AND `total_amount` > 0.00),
  CONSTRAINT `chk_dq_currency` CHECK (CHAR_LENGTH(`currency_code`) = 3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 63. dealer_quote_items
CREATE TABLE IF NOT EXISTS `dealer_quote_items` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `dealer_quote_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `wholesale_rfq_item_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `dealer_wholesale_listing_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `product_variant_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `item_title_snapshot` VARCHAR(220) NOT NULL,
  `quoted_quantity` DECIMAL(14,3) NOT NULL,
  `unit_price` DECIMAL(14,2) NOT NULL,
  `tax_amount` DECIMAL(14,2) NOT NULL DEFAULT 0.00,
  `line_total` DECIMAL(14,2) NOT NULL,
  `currency_code` CHAR(3) NOT NULL DEFAULT 'INR',
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_dqi_quote` (`dealer_quote_id`),
  KEY `idx_dqi_rfq_item` (`wholesale_rfq_item_id`),
  KEY `idx_dqi_listing` (`dealer_wholesale_listing_id`),
  KEY `idx_dqi_variant` (`product_variant_id`),
  CONSTRAINT `fk_dqi_quote` FOREIGN KEY (`dealer_quote_id`) REFERENCES `dealer_quotes` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `fk_dqi_rfq_item` FOREIGN KEY (`wholesale_rfq_item_id`) REFERENCES `wholesale_rfq_items` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `fk_dqi_listing` FOREIGN KEY (`dealer_wholesale_listing_id`) REFERENCES `dealer_wholesale_listings` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `fk_dqi_variant` FOREIGN KEY (`product_variant_id`) REFERENCES `product_variants` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_dqi_qty` CHECK (`quoted_quantity` > 0.000),
  CONSTRAINT `chk_dqi_amounts` CHECK (`unit_price` > 0.00 AND `tax_amount` >= 0.00 AND `line_total` > 0.00),
  CONSTRAINT `chk_dqi_currency` CHECK (CHAR_LENGTH(`currency_code`) = 3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 64. wholesale_orders
-- One dealer per wholesale order in v1; strictly separate from retail & supplier POs.
CREATE TABLE IF NOT EXISTS `wholesale_orders` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `order_number` VARCHAR(64) NOT NULL,
  `wholesale_buyer_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `buyer_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `dealer_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `order_source` ENUM('DIRECT_BULK', 'ACCEPTED_RFQ_QUOTE') NOT NULL,
  `wholesale_rfq_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `dealer_quote_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `shipping_address_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `shipping_address_snapshot_json` JSON NOT NULL,
  `currency_code` CHAR(3) NOT NULL DEFAULT 'INR',
  `subtotal_amount` DECIMAL(14,2) NOT NULL,
  `discount_amount` DECIMAL(14,2) NOT NULL DEFAULT 0.00,
  `tax_amount` DECIMAL(14,2) NOT NULL DEFAULT 0.00,
  `shipping_fee` DECIMAL(14,2) NOT NULL DEFAULT 0.00,
  `total_amount` DECIMAL(14,2) NOT NULL,
  `payment_method` ENUM('RAZORPAY_STANDARD', 'COD', 'BANK_TRANSFER_VERIFIED') NOT NULL DEFAULT 'RAZORPAY_STANDARD',
  `payment_status` ENUM('PENDING', 'AUTHORIZED', 'PAID', 'FAILED', 'PARTIALLY_REFUNDED', 'REFUNDED', 'COD_PENDING', 'COD_COLLECTED') NOT NULL DEFAULT 'PENDING',
  `fulfilment_status` ENUM('PENDING_PAYMENT', 'CONFIRMED', 'PROCESSING', 'SHIPPED', 'DELIVERED', 'CANCELLED', 'RETURNED') NOT NULL DEFAULT 'PENDING_PAYMENT',
  `confirmed_at` DATETIME(6) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_wo_number` (`order_number`),
  UNIQUE KEY `uq_wo_dealer_quote` (`dealer_quote_id`),
  KEY `idx_wo_buyer_created` (`wholesale_buyer_profile_id`, `created_at`),
  KEY `idx_wo_buyer_user` (`buyer_user_id`),
  KEY `idx_wo_dealer_status` (`dealer_profile_id`, `fulfilment_status`),
  KEY `idx_wo_rfq` (`wholesale_rfq_id`),
  KEY `idx_wo_shipping_addr` (`shipping_address_id`),
  KEY `idx_wo_statuses` (`payment_status`, `fulfilment_status`),
  CONSTRAINT `fk_wo_buyer_profile` FOREIGN KEY (`wholesale_buyer_profile_id`) REFERENCES `wholesale_buyer_profiles` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_wo_buyer_user` FOREIGN KEY (`buyer_user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_wo_dealer` FOREIGN KEY (`dealer_profile_id`) REFERENCES `dealer_profiles` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_wo_rfq` FOREIGN KEY (`wholesale_rfq_id`) REFERENCES `wholesale_rfqs` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_wo_quote` FOREIGN KEY (`dealer_quote_id`) REFERENCES `dealer_quotes` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_wo_shipping_addr` FOREIGN KEY (`shipping_address_id`) REFERENCES `user_addresses` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `chk_wo_amounts` CHECK (`subtotal_amount` >= 0.00 AND `discount_amount` >= 0.00 AND `tax_amount` >= 0.00 AND `shipping_fee` >= 0.00 AND `total_amount` > 0.00),
  CONSTRAINT `chk_wo_source_quote` CHECK (
    (`order_source` = 'DIRECT_BULK' AND `dealer_quote_id` IS NULL)
    OR (`order_source` = 'ACCEPTED_RFQ_QUOTE' AND `wholesale_rfq_id` IS NOT NULL AND `dealer_quote_id` IS NOT NULL)
  ),
  CONSTRAINT `chk_wo_currency` CHECK (CHAR_LENGTH(`currency_code`) = 3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 65. wholesale_order_items
CREATE TABLE IF NOT EXISTS `wholesale_order_items` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `wholesale_order_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `dealer_wholesale_listing_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `dealer_quote_item_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `product_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `product_variant_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `product_name_snapshot` VARCHAR(220) NOT NULL,
  `sku_snapshot` VARCHAR(100) NOT NULL,
  `quantity` DECIMAL(14,3) NOT NULL,
  `unit_price_snapshot` DECIMAL(14,2) NOT NULL,
  `discount_amount_snapshot` DECIMAL(14,2) NOT NULL DEFAULT 0.00,
  `tax_amount_snapshot` DECIMAL(14,2) NOT NULL DEFAULT 0.00,
  `line_total_amount` DECIMAL(14,2) NOT NULL,
  `currency_code` CHAR(3) NOT NULL DEFAULT 'INR',
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_woi_order` (`wholesale_order_id`),
  KEY `idx_woi_listing` (`dealer_wholesale_listing_id`),
  KEY `idx_woi_quote_item` (`dealer_quote_item_id`),
  KEY `idx_woi_product` (`product_id`),
  KEY `idx_woi_variant` (`product_variant_id`),
  CONSTRAINT `fk_woi_order` FOREIGN KEY (`wholesale_order_id`) REFERENCES `wholesale_orders` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_woi_listing` FOREIGN KEY (`dealer_wholesale_listing_id`) REFERENCES `dealer_wholesale_listings` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `fk_woi_quote_item` FOREIGN KEY (`dealer_quote_item_id`) REFERENCES `dealer_quote_items` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `fk_woi_product` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_woi_variant` FOREIGN KEY (`product_variant_id`) REFERENCES `product_variants` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_woi_qty` CHECK (`quantity` > 0.000),
  CONSTRAINT `chk_woi_amounts` CHECK (`unit_price_snapshot` > 0.00 AND `discount_amount_snapshot` >= 0.00 AND `tax_amount_snapshot` >= 0.00 AND `line_total_amount` > 0.00),
  CONSTRAINT `chk_woi_currency` CHECK (CHAR_LENGTH(`currency_code`) = 3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 66. wholesale_order_status_history
CREATE TABLE IF NOT EXISTS `wholesale_order_status_history` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `wholesale_order_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `status_scope` ENUM('ORDER_FULFILMENT', 'PAYMENT_SYNC') NOT NULL DEFAULT 'ORDER_FULFILMENT',
  `from_status` VARCHAR(40) NULL,
  `to_status` VARCHAR(40) NOT NULL,
  `actor_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `reason` VARCHAR(1000) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_wosh_order_created` (`wholesale_order_id`, `created_at`),
  KEY `idx_wosh_actor` (`actor_user_id`),
  CONSTRAINT `fk_wosh_order` FOREIGN KEY (`wholesale_order_id`) REFERENCES `wholesale_orders` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_wosh_actor` FOREIGN KEY (`actor_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 67. stock_reservations
-- Holds inventory during checkout for either a retail or wholesale order.
CREATE TABLE IF NOT EXISTS `stock_reservations` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `warehouse_stock_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `reservation_scope` ENUM('RETAIL_ORDER', 'WHOLESALE_ORDER') NOT NULL,
  `retail_order_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `wholesale_order_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `reserved_by_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `reserved_quantity` DECIMAL(14,3) NOT NULL,
  `reservation_status` ENUM('ACTIVE', 'RELEASED', 'CONSUMED', 'EXPIRED') NOT NULL DEFAULT 'ACTIVE',
  `expires_at` DATETIME(6) NOT NULL,
  `resolved_at` DATETIME(6) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_sr_stock_status` (`warehouse_stock_id`, `reservation_status`),
  KEY `idx_sr_retail_order` (`retail_order_id`),
  KEY `idx_sr_wholesale_order` (`wholesale_order_id`),
  KEY `idx_sr_user` (`reserved_by_user_id`),
  KEY `idx_sr_expires` (`reservation_status`, `expires_at`),
  CONSTRAINT `fk_sr_stock` FOREIGN KEY (`warehouse_stock_id`) REFERENCES `warehouse_stock` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_sr_retail_order` FOREIGN KEY (`retail_order_id`) REFERENCES `retail_orders` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_sr_wholesale_order` FOREIGN KEY (`wholesale_order_id`) REFERENCES `wholesale_orders` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_sr_user` FOREIGN KEY (`reserved_by_user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_sr_qty` CHECK (`reserved_quantity` > 0.000),
  CONSTRAINT `chk_sr_scope_target` CHECK (
    (`reservation_scope` = 'RETAIL_ORDER' AND `retail_order_id` IS NOT NULL AND `wholesale_order_id` IS NULL)
    OR (`reservation_scope` = 'WHOLESALE_ORDER' AND `wholesale_order_id` IS NOT NULL AND `retail_order_id` IS NULL)
  )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- >>> END 06_wholesale_marketplace.sql <<<


-- >>> BEGIN 07_payments_shipping_returns_reviews.sql <<<

-- =============================================================================
-- HunarLink MySQL 8.4 LTS Schema
-- File: sql/07_payments_shipping_returns_reviews.sql
-- Module G: Payments, Shipping, Returns & Reviews (13 tables)
-- Tables:
--   68. payments
--   69. payment_attempts
--   70. payment_status_history
--   71. payment_webhook_events
--   72. refunds
--   73. payouts
--   74. shipments
--   75. shipment_items
--   76. tracking_events
--   77. return_requests
--   78. return_status_history
--   79. return_items
--   80. product_reviews
-- Rules:
--   - Payment status is strictly separate from order fulfilment status.
--   - Supports RETAIL_ORDER, WHOLESALE_ORDER, and SUPPLIER_PROCUREMENT separately.
--   - Never store card numbers, CVV, UPI PINs, or gateway secrets.
--   - Cumulative refunds can never exceed captured payment amount.
--   - Webhook inbox guarantees idempotent processing via unique provider_event_id.
-- =============================================================================

USE `hunarlink`;

-- 68. payments
CREATE TABLE IF NOT EXISTS `payments` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `payment_reference` VARCHAR(64) NOT NULL,
  `payment_purpose` ENUM('RETAIL_ORDER', 'WHOLESALE_ORDER', 'SUPPLIER_PROCUREMENT') NOT NULL,
  `retail_order_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `wholesale_order_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `supplier_purchase_order_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `payer_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `payment_method` ENUM('RAZORPAY_STANDARD', 'COD', 'BANK_TRANSFER_OFFLINE') NOT NULL DEFAULT 'RAZORPAY_STANDARD',
  `provider_name` VARCHAR(40) NOT NULL DEFAULT 'RAZORPAY',
  `amount` DECIMAL(14,2) NOT NULL,
  `captured_amount` DECIMAL(14,2) NOT NULL DEFAULT 0.00,
  `currency_code` CHAR(3) NOT NULL DEFAULT 'INR',
  `payment_status` ENUM('CREATED', 'ORDER_CREATED', 'CHECKOUT_OPENED', 'AUTHORIZED', 'CAPTURED', 'FAILED', 'CANCELLED', 'REFUND_PENDING', 'PARTIALLY_REFUNDED', 'REFUNDED', 'RECONCILIATION_REQUIRED', 'COD_PENDING', 'COD_COLLECTED') NOT NULL DEFAULT 'CREATED',
  `idempotency_key` VARCHAR(128) NOT NULL,
  `provider_order_id` VARCHAR(128) NULL,
  `provider_payment_id` VARCHAR(128) NULL,
  `provider_receipt` VARCHAR(80) NULL,
  `authorized_at` DATETIME(6) NULL,
  `captured_at` DATETIME(6) NULL,
  `failed_at` DATETIME(6) NULL,
  `failure_code` VARCHAR(100) NULL,
  `failure_reason` VARCHAR(500) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_payments_reference` (`payment_reference`),
  UNIQUE KEY `uq_payments_idempotency_key` (`idempotency_key`),
  UNIQUE KEY `uq_payments_provider_order_id` (`provider_order_id`),
  UNIQUE KEY `uq_payments_provider_payment_id` (`provider_payment_id`),
  KEY `idx_payments_retail_order` (`retail_order_id`),
  KEY `idx_payments_wholesale_order` (`wholesale_order_id`),
  KEY `idx_payments_supplier_po` (`supplier_purchase_order_id`),
  KEY `idx_payments_payer_status` (`payer_user_id`, `payment_status`),
  KEY `idx_payments_purpose_status` (`payment_purpose`, `payment_status`),
  CONSTRAINT `fk_payments_payer` FOREIGN KEY (`payer_user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_payments_retail_order` FOREIGN KEY (`retail_order_id`) REFERENCES `retail_orders` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_payments_wholesale_order` FOREIGN KEY (`wholesale_order_id`) REFERENCES `wholesale_orders` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_payments_supplier_po` FOREIGN KEY (`supplier_purchase_order_id`) REFERENCES `supplier_purchase_orders` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_payments_amounts` CHECK (`amount` > 0.00 AND `captured_amount` >= 0.00 AND `captured_amount` <= `amount`),
  CONSTRAINT `chk_payments_currency` CHECK (CHAR_LENGTH(`currency_code`) = 3),
  CONSTRAINT `chk_payments_single_target` CHECK (
    (`payment_purpose` = 'RETAIL_ORDER' AND `retail_order_id` IS NOT NULL AND `wholesale_order_id` IS NULL AND `supplier_purchase_order_id` IS NULL)
    OR (`payment_purpose` = 'WHOLESALE_ORDER' AND `wholesale_order_id` IS NOT NULL AND `retail_order_id` IS NULL AND `supplier_purchase_order_id` IS NULL)
    OR (`payment_purpose` = 'SUPPLIER_PROCUREMENT' AND `supplier_purchase_order_id` IS NOT NULL AND `retail_order_id` IS NULL AND `wholesale_order_id` IS NULL)
  )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 69. payment_attempts
CREATE TABLE IF NOT EXISTS `payment_attempts` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `payment_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `payer_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `attempt_number` INT UNSIGNED NOT NULL DEFAULT 1,
  `idempotency_key` VARCHAR(128) NOT NULL,
  `provider_order_id` VARCHAR(128) NULL,
  `provider_payment_id` VARCHAR(128) NULL,
  `amount` DECIMAL(14,2) NOT NULL,
  `currency_code` CHAR(3) NOT NULL DEFAULT 'INR',
  `attempt_status` ENUM('INITIATED', 'ORDER_CREATED', 'CHECKOUT_OPENED', 'PENDING_VERIFICATION', 'AUTHORIZED', 'CAPTURED', 'FAILED', 'CANCELLED', 'RECONCILIATION_REQUIRED') NOT NULL DEFAULT 'INITIATED',
  `failure_code` VARCHAR(100) NULL,
  `failure_description` VARCHAR(500) NULL,
  `safe_metadata_json` JSON NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_pa_idempotency_key` (`idempotency_key`),
  UNIQUE KEY `uq_pa_provider_order_id` (`provider_order_id`),
  KEY `idx_pa_payment_attempt` (`payment_id`, `attempt_number`),
  KEY `idx_pa_payer` (`payer_user_id`),
  KEY `idx_pa_provider_payment` (`provider_payment_id`),
  KEY `idx_pa_status` (`attempt_status`),
  CONSTRAINT `fk_pa_payment` FOREIGN KEY (`payment_id`) REFERENCES `payments` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_pa_payer` FOREIGN KEY (`payer_user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_pa_amount` CHECK (`amount` > 0.00),
  CONSTRAINT `chk_pa_currency` CHECK (CHAR_LENGTH(`currency_code`) = 3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 70. payment_status_history
CREATE TABLE IF NOT EXISTS `payment_status_history` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `payment_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `from_status` VARCHAR(40) NULL,
  `to_status` VARCHAR(40) NOT NULL,
  `event_source` ENUM('CREATE_ORDER', 'VERIFY_CALLBACK', 'WEBHOOK', 'RECONCILIATION', 'REFUND', 'COD_COLLECTION', 'ADMIN') NOT NULL,
  `actor_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `provider_event_ref` VARCHAR(128) NULL,
  `notes` VARCHAR(500) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_psh_payment_created` (`payment_id`, `created_at`),
  KEY `idx_psh_actor` (`actor_user_id`),
  CONSTRAINT `fk_psh_payment` FOREIGN KEY (`payment_id`) REFERENCES `payments` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_psh_actor` FOREIGN KEY (`actor_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 71. payment_webhook_events
-- Durable inbox for signed webhooks; unique provider_event_id guarantees idempotency.
CREATE TABLE IF NOT EXISTS `payment_webhook_events` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `provider_name` VARCHAR(40) NOT NULL DEFAULT 'RAZORPAY',
  `provider_event_id` VARCHAR(128) NOT NULL,
  `event_type` VARCHAR(100) NOT NULL,
  `payment_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `provider_order_id` VARCHAR(128) NULL,
  `provider_payment_id` VARCHAR(128) NULL,
  `signature_verified` TINYINT(1) NOT NULL DEFAULT 0,
  `processing_status` ENUM('RECEIVED', 'PROCESSED', 'DUPLICATE_IGNORED', 'IGNORED_OUT_OF_ORDER', 'FAILED') NOT NULL DEFAULT 'RECEIVED',
  `safe_payload_summary_json` JSON NULL,
  `error_summary` VARCHAR(500) NULL,
  `received_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `processed_at` DATETIME(6) NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_pwe_provider_event_id` (`provider_name`, `provider_event_id`),
  KEY `idx_pwe_event_type_status` (`event_type`, `processing_status`),
  KEY `idx_pwe_payment` (`payment_id`),
  KEY `idx_pwe_provider_order` (`provider_order_id`),
  KEY `idx_pwe_provider_payment` (`provider_payment_id`),
  CONSTRAINT `fk_pwe_payment` FOREIGN KEY (`payment_id`) REFERENCES `payments` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `chk_pwe_sig_verified` CHECK (`signature_verified` IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 72. refunds
CREATE TABLE IF NOT EXISTS `refunds` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `refund_reference` VARCHAR(64) NOT NULL,
  `payment_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `provider_refund_id` VARCHAR(128) NULL,
  `idempotency_key` VARCHAR(128) NOT NULL,
  `amount` DECIMAL(14,2) NOT NULL,
  `currency_code` CHAR(3) NOT NULL DEFAULT 'INR',
  `refund_type` ENUM('FULL', 'PARTIAL') NOT NULL,
  `refund_status` ENUM('REQUESTED', 'PENDING_PROVIDER', 'PROCESSED', 'FAILED', 'CANCELLED') NOT NULL DEFAULT 'REQUESTED',
  `reason` VARCHAR(500) NOT NULL,
  `initiated_by_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `approved_by_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `processed_at` DATETIME(6) NULL,
  `failure_reason` VARCHAR(500) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_refunds_reference` (`refund_reference`),
  UNIQUE KEY `uq_refunds_idempotency` (`idempotency_key`),
  UNIQUE KEY `uq_refunds_provider_id` (`provider_refund_id`),
  KEY `idx_refunds_payment_status` (`payment_id`, `refund_status`),
  KEY `idx_refunds_initiated_by` (`initiated_by_user_id`),
  KEY `idx_refunds_approved_by` (`approved_by_user_id`),
  CONSTRAINT `fk_refunds_payment` FOREIGN KEY (`payment_id`) REFERENCES `payments` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_refunds_initiated_by` FOREIGN KEY (`initiated_by_user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_refunds_approved_by` FOREIGN KEY (`approved_by_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `chk_refunds_amount` CHECK (`amount` > 0.00),
  CONSTRAINT `chk_refunds_currency` CHECK (CHAR_LENGTH(`currency_code`) = 3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 73. payouts
-- Tracks seller/dealer/supplier settlement obligations separately from customer Checkout.
CREATE TABLE IF NOT EXISTS `payouts` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `payout_reference` VARCHAR(64) NOT NULL,
  `recipient_type` ENUM('DIRECT_SELLER', 'DEALER', 'SUPPLIER') NOT NULL,
  `recipient_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `seller_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `dealer_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `supplier_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `retail_order_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `wholesale_order_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `supplier_purchase_order_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `gross_amount` DECIMAL(14,2) NOT NULL,
  `platform_fee_amount` DECIMAL(14,2) NOT NULL DEFAULT 0.00,
  `tax_withheld_amount` DECIMAL(14,2) NOT NULL DEFAULT 0.00,
  `net_payout_amount` DECIMAL(14,2) NOT NULL,
  `currency_code` CHAR(3) NOT NULL DEFAULT 'INR',
  `payout_status` ENUM('OBLIGATION_RECORDED', 'APPROVED', 'PROCESSING', 'SETTLED', 'ON_HOLD', 'FAILED', 'CANCELLED') NOT NULL DEFAULT 'OBLIGATION_RECORDED',
  `settlement_reference` VARCHAR(128) NULL,
  `settled_at` DATETIME(6) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_payouts_reference` (`payout_reference`),
  KEY `idx_payouts_recipient` (`recipient_type`, `recipient_user_id`, `payout_status`),
  KEY `idx_payouts_seller` (`seller_profile_id`),
  KEY `idx_payouts_dealer` (`dealer_profile_id`),
  KEY `idx_payouts_supplier` (`supplier_profile_id`),
  KEY `idx_payouts_retail_order` (`retail_order_id`),
  KEY `idx_payouts_wholesale_order` (`wholesale_order_id`),
  KEY `idx_payouts_supplier_po` (`supplier_purchase_order_id`),
  CONSTRAINT `fk_payouts_user` FOREIGN KEY (`recipient_user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_payouts_seller` FOREIGN KEY (`seller_profile_id`) REFERENCES `seller_profiles` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_payouts_dealer` FOREIGN KEY (`dealer_profile_id`) REFERENCES `dealer_profiles` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_payouts_supplier` FOREIGN KEY (`supplier_profile_id`) REFERENCES `supplier_profiles` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_payouts_retail_order` FOREIGN KEY (`retail_order_id`) REFERENCES `retail_orders` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_payouts_wholesale_order` FOREIGN KEY (`wholesale_order_id`) REFERENCES `wholesale_orders` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_payouts_supplier_po` FOREIGN KEY (`supplier_purchase_order_id`) REFERENCES `supplier_purchase_orders` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_payouts_amounts` CHECK (`gross_amount` > 0.00 AND `platform_fee_amount` >= 0.00 AND `tax_withheld_amount` >= 0.00 AND `net_payout_amount` >= 0.00),
  CONSTRAINT `chk_payouts_currency` CHECK (CHAR_LENGTH(`currency_code`) = 3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 74. shipments
CREATE TABLE IF NOT EXISTS `shipments` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `shipment_number` VARCHAR(64) NOT NULL,
  `shipment_scope` ENUM('RETAIL_FULFILMENT', 'WHOLESALE_ORDER', 'SUPPLIER_PROCUREMENT') NOT NULL,
  `retail_order_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `seller_fulfilment_group_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `wholesale_order_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `supplier_purchase_order_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `origin_warehouse_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `carrier_name` VARCHAR(100) NULL,
  `tracking_number` VARCHAR(128) NULL,
  `shipment_status` ENUM('LABEL_CREATED', 'PICKED_UP', 'IN_TRANSIT', 'OUT_FOR_DELIVERY', 'DELIVERED', 'DELIVERY_FAILED', 'RETURNED_TO_ORIGIN', 'CANCELLED') NOT NULL DEFAULT 'LABEL_CREATED',
  `dispatched_at` DATETIME(6) NULL,
  `delivered_at` DATETIME(6) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_shipments_number` (`shipment_number`),
  KEY `idx_shipments_tracking` (`carrier_name`, `tracking_number`),
  KEY `idx_shipments_retail` (`retail_order_id`),
  KEY `idx_shipments_sfg` (`seller_fulfilment_group_id`),
  KEY `idx_shipments_wholesale` (`wholesale_order_id`),
  KEY `idx_shipments_po` (`supplier_purchase_order_id`),
  KEY `idx_shipments_warehouse` (`origin_warehouse_id`),
  CONSTRAINT `fk_shipments_retail` FOREIGN KEY (`retail_order_id`) REFERENCES `retail_orders` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_shipments_sfg` FOREIGN KEY (`seller_fulfilment_group_id`) REFERENCES `seller_fulfilment_groups` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_shipments_wholesale` FOREIGN KEY (`wholesale_order_id`) REFERENCES `wholesale_orders` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_shipments_po` FOREIGN KEY (`supplier_purchase_order_id`) REFERENCES `supplier_purchase_orders` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_shipments_warehouse` FOREIGN KEY (`origin_warehouse_id`) REFERENCES `warehouses` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 75. shipment_items
CREATE TABLE IF NOT EXISTS `shipment_items` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `shipment_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `retail_order_item_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `wholesale_order_item_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `supplier_po_item_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `shipped_quantity` DECIMAL(14,3) NOT NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_si_shipment` (`shipment_id`),
  KEY `idx_si_retail_item` (`retail_order_item_id`),
  KEY `idx_si_wholesale_item` (`wholesale_order_item_id`),
  KEY `idx_si_po_item` (`supplier_po_item_id`),
  CONSTRAINT `fk_si_shipment` FOREIGN KEY (`shipment_id`) REFERENCES `shipments` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_si_retail_item` FOREIGN KEY (`retail_order_item_id`) REFERENCES `retail_order_items` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_si_wholesale_item` FOREIGN KEY (`wholesale_order_item_id`) REFERENCES `wholesale_order_items` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_si_po_item` FOREIGN KEY (`supplier_po_item_id`) REFERENCES `supplier_purchase_order_items` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_si_qty` CHECK (`shipped_quantity` > 0.000)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 76. tracking_events
CREATE TABLE IF NOT EXISTS `tracking_events` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `shipment_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `provider_event_id` VARCHAR(128) NULL,
  `event_status` VARCHAR(80) NOT NULL,
  `location_name` VARCHAR(160) NULL,
  `event_description` VARCHAR(500) NULL,
  `occurred_at` DATETIME(6) NOT NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_te_shipment_provider_event` (`shipment_id`, `provider_event_id`),
  KEY `idx_te_shipment_occurred` (`shipment_id`, `occurred_at`),
  CONSTRAINT `fk_te_shipment` FOREIGN KEY (`shipment_id`) REFERENCES `shipments` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 77. return_requests
CREATE TABLE IF NOT EXISTS `return_requests` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `return_number` VARCHAR(64) NOT NULL,
  `order_scope` ENUM('RETAIL_ORDER', 'WHOLESALE_ORDER') NOT NULL,
  `retail_order_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `seller_fulfilment_group_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `wholesale_order_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `payment_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `requested_by_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `reason_code` VARCHAR(64) NOT NULL,
  `reason_details` TEXT NULL,
  `return_status` ENUM('REQUESTED', 'APPROVED', 'REJECTED', 'PICKUP_SCHEDULED', 'RECEIVED', 'INSPECTED', 'REFUND_INITIATED', 'CLOSED', 'CANCELLED') NOT NULL DEFAULT 'REQUESTED',
  `requested_refund_amount` DECIMAL(14,2) NULL,
  `currency_code` CHAR(3) NOT NULL DEFAULT 'INR',
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_rr_number` (`return_number`),
  KEY `idx_rr_user_status` (`requested_by_user_id`, `return_status`),
  KEY `idx_rr_retail` (`retail_order_id`),
  KEY `idx_rr_sfg` (`seller_fulfilment_group_id`),
  KEY `idx_rr_wholesale` (`wholesale_order_id`),
  KEY `idx_rr_payment` (`payment_id`),
  CONSTRAINT `fk_rr_user` FOREIGN KEY (`requested_by_user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_rr_retail` FOREIGN KEY (`retail_order_id`) REFERENCES `retail_orders` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_rr_sfg` FOREIGN KEY (`seller_fulfilment_group_id`) REFERENCES `seller_fulfilment_groups` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_rr_wholesale` FOREIGN KEY (`wholesale_order_id`) REFERENCES `wholesale_orders` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_rr_payment` FOREIGN KEY (`payment_id`) REFERENCES `payments` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_rr_refund_amount` CHECK (`requested_refund_amount` IS NULL OR `requested_refund_amount` > 0.00),
  CONSTRAINT `chk_rr_currency` CHECK (CHAR_LENGTH(`currency_code`) = 3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 78. return_status_history
CREATE TABLE IF NOT EXISTS `return_status_history` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `return_request_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `from_status` VARCHAR(40) NULL,
  `to_status` VARCHAR(40) NOT NULL,
  `actor_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `notes` VARCHAR(1000) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_rsh_return_created` (`return_request_id`, `created_at`),
  KEY `idx_rsh_actor` (`actor_user_id`),
  CONSTRAINT `fk_rsh_return` FOREIGN KEY (`return_request_id`) REFERENCES `return_requests` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_rsh_actor` FOREIGN KEY (`actor_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 79. return_items
CREATE TABLE IF NOT EXISTS `return_items` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `return_request_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `retail_order_item_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `wholesale_order_item_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `return_quantity` DECIMAL(14,3) NOT NULL,
  `item_condition` ENUM('UNOPENED', 'OPENED_GOOD', 'DAMAGED', 'DEFECTIVE', 'WRONG_ITEM') NOT NULL DEFAULT 'OPENED_GOOD',
  `restock_approved` TINYINT(1) NOT NULL DEFAULT 0,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_ri_return` (`return_request_id`),
  KEY `idx_ri_retail_item` (`retail_order_item_id`),
  KEY `idx_ri_wholesale_item` (`wholesale_order_item_id`),
  CONSTRAINT `fk_ri_return` FOREIGN KEY (`return_request_id`) REFERENCES `return_requests` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_ri_retail_item` FOREIGN KEY (`retail_order_item_id`) REFERENCES `retail_order_items` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_ri_wholesale_item` FOREIGN KEY (`wholesale_order_item_id`) REFERENCES `wholesale_order_items` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_ri_qty` CHECK (`return_quantity` > 0.000),
  CONSTRAINT `chk_ri_restock` CHECK (`restock_approved` IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 80. product_reviews
CREATE TABLE IF NOT EXISTS `product_reviews` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `product_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `product_variant_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `seller_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `reviewer_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `retail_order_item_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `rating` TINYINT UNSIGNED NOT NULL,
  `title` VARCHAR(160) NULL,
  `review_body` TEXT NULL,
  `is_verified_purchase` TINYINT(1) NOT NULL DEFAULT 0,
  `moderation_status` ENUM('PENDING', 'PUBLISHED', 'HIDDEN', 'REJECTED') NOT NULL DEFAULT 'PUBLISHED',
  `seller_reply` TEXT NULL,
  `seller_replied_at` DATETIME(6) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_pr_order_item_reviewer` (`retail_order_item_id`, `reviewer_user_id`),
  KEY `idx_pr_product_status` (`product_id`, `moderation_status`),
  KEY `idx_pr_variant` (`product_variant_id`),
  KEY `idx_pr_seller` (`seller_profile_id`),
  KEY `idx_pr_reviewer` (`reviewer_user_id`),
  CONSTRAINT `fk_pr_product` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_pr_variant` FOREIGN KEY (`product_variant_id`) REFERENCES `product_variants` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `fk_pr_seller` FOREIGN KEY (`seller_profile_id`) REFERENCES `seller_profiles` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `fk_pr_reviewer` FOREIGN KEY (`reviewer_user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_pr_order_item` FOREIGN KEY (`retail_order_item_id`) REFERENCES `retail_order_items` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `chk_pr_rating` CHECK (`rating` BETWEEN 1 AND 5),
  CONSTRAINT `chk_pr_verified` CHECK (`is_verified_purchase` IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- >>> END 07_payments_shipping_returns_reviews.sql <<<


-- >>> BEGIN 08_promotions_notifications_and_admin_operations.sql <<<

-- =============================================================================
-- HunarLink MySQL 8.4 LTS Schema
-- File: sql/08_promotions_notifications_and_admin_operations.sql
-- Module H: Platform Operations, Promotions, Support & Immutable Audit (15 tables)
-- Tables:
--   81. coupons
--   82. coupon_usage
--   83. promotions
--   84. promotion_products
--   85. promotion_categories
--   86. notifications
--   87. support_tickets
--   88. support_ticket_messages
--   89. audit_logs
--   90. admin_action_requests
--   91. platform_settings
--   92. announcements
--   93. product_approval_history
--   94. dealer_status_history
--   95. supplier_status_history
-- Rules:
--   - `audit_logs` is append-only (protected by BEFORE UPDATE / BEFORE DELETE
--     triggers in 09_mysql_indexes_triggers_views_procedures.sql and least-privilege
--     grants in 12_create_database_users.example.sql).
--   - High-risk Admin actions support dual-control approval via `admin_action_requests`.
-- =============================================================================

USE `hunarlink`;

-- 81. coupons
CREATE TABLE IF NOT EXISTS `coupons` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `code` VARCHAR(64) NOT NULL,
  `description` VARCHAR(255) NULL,
  `discount_type` ENUM('PERCENTAGE', 'FIXED_AMOUNT') NOT NULL,
  `discount_value` DECIMAL(14,2) NOT NULL,
  `max_discount_amount` DECIMAL(14,2) NULL,
  `min_order_amount` DECIMAL(14,2) NOT NULL DEFAULT 0.00,
  `currency_code` CHAR(3) NOT NULL DEFAULT 'INR',
  `applicable_scope` ENUM('RETAIL', 'WHOLESALE', 'BOTH') NOT NULL DEFAULT 'RETAIL',
  `max_total_redemptions` INT UNSIGNED NULL,
  `max_per_user` INT UNSIGNED NOT NULL DEFAULT 1,
  `starts_at` DATETIME(6) NOT NULL,
  `ends_at` DATETIME(6) NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_by_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_coupons_code` (`code`),
  KEY `idx_coupons_active_dates` (`is_active`, `starts_at`, `ends_at`),
  KEY `idx_coupons_created_by` (`created_by_user_id`),
  CONSTRAINT `fk_coupons_created_by` FOREIGN KEY (`created_by_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `chk_coupons_value` CHECK (`discount_value` > 0.00 AND `min_order_amount` >= 0.00),
  CONSTRAINT `chk_coupons_pct` CHECK (`discount_type` <> 'PERCENTAGE' OR `discount_value` <= 100.00),
  CONSTRAINT `chk_coupons_active` CHECK (`is_active` IN (0, 1)),
  CONSTRAINT `chk_coupons_currency` CHECK (CHAR_LENGTH(`currency_code`) = 3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 82. coupon_usage
CREATE TABLE IF NOT EXISTS `coupon_usage` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `coupon_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `retail_order_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `wholesale_order_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `discount_applied` DECIMAL(14,2) NOT NULL,
  `currency_code` CHAR(3) NOT NULL DEFAULT 'INR',
  `used_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_cu_coupon_user` (`coupon_id`, `user_id`),
  KEY `idx_cu_user` (`user_id`),
  KEY `idx_cu_retail_order` (`retail_order_id`),
  KEY `idx_cu_wholesale_order` (`wholesale_order_id`),
  CONSTRAINT `fk_cu_coupon` FOREIGN KEY (`coupon_id`) REFERENCES `coupons` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_cu_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_cu_retail_order` FOREIGN KEY (`retail_order_id`) REFERENCES `retail_orders` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_cu_wholesale_order` FOREIGN KEY (`wholesale_order_id`) REFERENCES `wholesale_orders` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_cu_discount` CHECK (`discount_applied` >= 0.00),
  CONSTRAINT `chk_cu_currency` CHECK (CHAR_LENGTH(`currency_code`) = 3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 83. promotions
CREATE TABLE IF NOT EXISTS `promotions` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `code` VARCHAR(64) NOT NULL,
  `name` VARCHAR(160) NOT NULL,
  `description` TEXT NULL,
  `promotion_type` ENUM('PERCENTAGE_OFF', 'FIXED_OFF', 'FREE_SHIPPING', 'BUNDLE') NOT NULL,
  `discount_value` DECIMAL(14,2) NOT NULL DEFAULT 0.00,
  `currency_code` CHAR(3) NOT NULL DEFAULT 'INR',
  `starts_at` DATETIME(6) NOT NULL,
  `ends_at` DATETIME(6) NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_by_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_promotions_code` (`code`),
  KEY `idx_promotions_active_dates` (`is_active`, `starts_at`, `ends_at`),
  KEY `idx_promotions_created_by` (`created_by_user_id`),
  CONSTRAINT `fk_promotions_created_by` FOREIGN KEY (`created_by_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `chk_promotions_value` CHECK (`discount_value` >= 0.00),
  CONSTRAINT `chk_promotions_active` CHECK (`is_active` IN (0, 1)),
  CONSTRAINT `chk_promotions_currency` CHECK (CHAR_LENGTH(`currency_code`) = 3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 84. promotion_products
CREATE TABLE IF NOT EXISTS `promotion_products` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `promotion_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `product_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_pp_promo_product` (`promotion_id`, `product_id`),
  KEY `idx_pp_product` (`product_id`),
  CONSTRAINT `fk_pp_promo` FOREIGN KEY (`promotion_id`) REFERENCES `promotions` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `fk_pp_product` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 85. promotion_categories
CREATE TABLE IF NOT EXISTS `promotion_categories` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `promotion_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `category_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_pc_promo_category` (`promotion_id`, `category_id`),
  KEY `idx_pc_category` (`category_id`),
  CONSTRAINT `fk_pc_promo` FOREIGN KEY (`promotion_id`) REFERENCES `promotions` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `fk_pc_category` FOREIGN KEY (`category_id`) REFERENCES `categories` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 86. notifications
CREATE TABLE IF NOT EXISTS `notifications` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `channel` ENUM('IN_APP', 'EMAIL', 'SMS', 'WEBHOOK') NOT NULL DEFAULT 'IN_APP',
  `notification_type` VARCHAR(80) NOT NULL,
  `title` VARCHAR(200) NOT NULL,
  `body` TEXT NOT NULL,
  `reference_type` VARCHAR(64) NULL,
  `reference_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `is_read` TINYINT(1) NOT NULL DEFAULT 0,
  `read_at` DATETIME(6) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_notif_user_read` (`user_id`, `is_read`, `created_at`),
  CONSTRAINT `fk_notif_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `chk_notif_read` CHECK (`is_read` IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 87. support_tickets
CREATE TABLE IF NOT EXISTS `support_tickets` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `ticket_number` VARCHAR(64) NOT NULL,
  `requester_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `assigned_admin_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `category` ENUM('ORDER_ISSUE', 'PAYMENT_ISSUE', 'RETURN_DISPUTE', 'GI_VERIFICATION', 'PROCUREMENT', 'ACCOUNT_ACCESS', 'OTHER') NOT NULL DEFAULT 'OTHER',
  `priority` ENUM('LOW', 'MEDIUM', 'HIGH', 'URGENT') NOT NULL DEFAULT 'MEDIUM',
  `ticket_status` ENUM('OPEN', 'IN_PROGRESS', 'WAITING_ON_USER', 'RESOLVED', 'CLOSED') NOT NULL DEFAULT 'OPEN',
  `subject` VARCHAR(220) NOT NULL,
  `retail_order_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `wholesale_order_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `supplier_purchase_order_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `resolved_at` DATETIME(6) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_st_ticket_number` (`ticket_number`),
  KEY `idx_st_requester_status` (`requester_user_id`, `ticket_status`),
  KEY `idx_st_admin_status` (`assigned_admin_profile_id`, `ticket_status`),
  KEY `idx_st_retail` (`retail_order_id`),
  KEY `idx_st_wholesale` (`wholesale_order_id`),
  KEY `idx_st_po` (`supplier_purchase_order_id`),
  CONSTRAINT `fk_st_requester` FOREIGN KEY (`requester_user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_st_admin` FOREIGN KEY (`assigned_admin_profile_id`) REFERENCES `admin_profiles` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `fk_st_retail` FOREIGN KEY (`retail_order_id`) REFERENCES `retail_orders` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `fk_st_wholesale` FOREIGN KEY (`wholesale_order_id`) REFERENCES `wholesale_orders` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `fk_st_po` FOREIGN KEY (`supplier_purchase_order_id`) REFERENCES `supplier_purchase_orders` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 88. support_ticket_messages
CREATE TABLE IF NOT EXISTS `support_ticket_messages` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `support_ticket_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `sender_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `is_internal_note` TINYINT(1) NOT NULL DEFAULT 0,
  `message_body` TEXT NOT NULL,
  `attachment_storage_key` VARCHAR(512) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_stm_ticket_created` (`support_ticket_id`, `created_at`),
  KEY `idx_stm_sender` (`sender_user_id`),
  CONSTRAINT `fk_stm_ticket` FOREIGN KEY (`support_ticket_id`) REFERENCES `support_tickets` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `fk_stm_sender` FOREIGN KEY (`sender_user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_stm_internal` CHECK (`is_internal_note` IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 89. audit_logs
-- Append-only immutable audit log. Never store passwords, secrets, or raw tokens.
CREATE TABLE IF NOT EXISTS `audit_logs` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `actor_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `actor_role` VARCHAR(64) NOT NULL,
  `action` VARCHAR(120) NOT NULL,
  `target_type` VARCHAR(80) NOT NULL,
  `target_id` VARCHAR(128) NOT NULL,
  `reason` VARCHAR(1000) NULL,
  `previous_values_json` JSON NULL,
  `new_values_json` JSON NULL,
  `correlation_id` VARCHAR(100) NOT NULL,
  `ip_address` VARCHAR(45) NULL,
  `user_agent` VARCHAR(255) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_audit_actor_created` (`actor_user_id`, `created_at`),
  KEY `idx_audit_target` (`target_type`, `target_id`),
  KEY `idx_audit_action_created` (`action`, `created_at`),
  KEY `idx_audit_correlation` (`correlation_id`),
  CONSTRAINT `fk_audit_actor` FOREIGN KEY (`actor_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 90. admin_action_requests
-- Dual-control maker/checker approval workflow for high-risk Admin operations.
CREATE TABLE IF NOT EXISTS `admin_action_requests` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `request_type` VARCHAR(100) NOT NULL,
  `target_type` VARCHAR(80) NOT NULL,
  `target_id` VARCHAR(128) NOT NULL,
  `requested_payload_json` JSON NOT NULL,
  `request_reason` VARCHAR(1000) NOT NULL,
  `requested_by_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `approval_status` ENUM('PENDING', 'APPROVED', 'REJECTED', 'EXECUTED', 'CANCELLED', 'EXPIRED') NOT NULL DEFAULT 'PENDING',
  `reviewed_by_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `review_reason` VARCHAR(1000) NULL,
  `reviewed_at` DATETIME(6) NULL,
  `executed_at` DATETIME(6) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_aar_status_created` (`approval_status`, `created_at`),
  KEY `idx_aar_requested_by` (`requested_by_user_id`),
  KEY `idx_aar_reviewed_by` (`reviewed_by_user_id`),
  CONSTRAINT `fk_aar_requested_by` FOREIGN KEY (`requested_by_user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_aar_reviewed_by` FOREIGN KEY (`reviewed_by_user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_aar_dual_control` CHECK (`reviewed_by_user_id` IS NULL OR `reviewed_by_user_id` <> `requested_by_user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 91. platform_settings
CREATE TABLE IF NOT EXISTS `platform_settings` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `setting_key` VARCHAR(100) NOT NULL,
  `setting_value_json` JSON NOT NULL,
  `description` VARCHAR(500) NULL,
  `is_sensitive` TINYINT(1) NOT NULL DEFAULT 0,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `updated_by_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_platform_settings_key` (`setting_key`),
  KEY `idx_ps_updated_by` (`updated_by_user_id`),
  CONSTRAINT `fk_ps_updated_by` FOREIGN KEY (`updated_by_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `chk_ps_sensitive` CHECK (`is_sensitive` IN (0, 1)),
  CONSTRAINT `chk_ps_active` CHECK (`is_active` IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 92. announcements
CREATE TABLE IF NOT EXISTS `announcements` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `title` VARCHAR(200) NOT NULL,
  `body` TEXT NOT NULL,
  `audience_role_code` VARCHAR(50) NULL,
  `severity` ENUM('INFO', 'NOTICE', 'WARNING', 'MAINTENANCE') NOT NULL DEFAULT 'INFO',
  `starts_at` DATETIME(6) NOT NULL,
  `ends_at` DATETIME(6) NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_by_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_ann_active_dates` (`is_active`, `starts_at`, `ends_at`),
  KEY `idx_ann_created_by` (`created_by_user_id`),
  CONSTRAINT `fk_ann_created_by` FOREIGN KEY (`created_by_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `chk_ann_active` CHECK (`is_active` IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 93. product_approval_history
CREATE TABLE IF NOT EXISTS `product_approval_history` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `product_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `seller_listing_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `dealer_wholesale_listing_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `from_status` VARCHAR(40) NULL,
  `to_status` VARCHAR(40) NOT NULL,
  `actor_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `reason` VARCHAR(1000) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_pah_product_created` (`product_id`, `created_at`),
  KEY `idx_pah_seller_listing` (`seller_listing_id`),
  KEY `idx_pah_dealer_listing` (`dealer_wholesale_listing_id`),
  KEY `idx_pah_actor` (`actor_user_id`),
  CONSTRAINT `fk_pah_product` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_pah_seller_listing` FOREIGN KEY (`seller_listing_id`) REFERENCES `seller_product_listings` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `fk_pah_dealer_listing` FOREIGN KEY (`dealer_wholesale_listing_id`) REFERENCES `dealer_wholesale_listings` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `fk_pah_actor` FOREIGN KEY (`actor_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 94. dealer_status_history
CREATE TABLE IF NOT EXISTS `dealer_status_history` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `dealer_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `status_field` ENUM('PROFILE_STATUS', 'VERIFICATION_STATUS') NOT NULL,
  `from_status` VARCHAR(40) NULL,
  `to_status` VARCHAR(40) NOT NULL,
  `actor_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `reason` VARCHAR(1000) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_dsh_dealer_created` (`dealer_profile_id`, `created_at`),
  KEY `idx_dsh_actor` (`actor_user_id`),
  CONSTRAINT `fk_dsh_dealer` FOREIGN KEY (`dealer_profile_id`) REFERENCES `dealer_profiles` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_dsh_actor` FOREIGN KEY (`actor_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 95. supplier_status_history
CREATE TABLE IF NOT EXISTS `supplier_status_history` (
  `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `supplier_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `status_field` ENUM('PROFILE_STATUS', 'VERIFICATION_STATUS') NOT NULL,
  `from_status` VARCHAR(40) NULL,
  `to_status` VARCHAR(40) NOT NULL,
  `actor_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
  `reason` VARCHAR(1000) NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_ssh_supplier_created` (`supplier_profile_id`, `created_at`),
  KEY `idx_ssh_actor` (`actor_user_id`),
  CONSTRAINT `fk_ssh_supplier` FOREIGN KEY (`supplier_profile_id`) REFERENCES `supplier_profiles` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_ssh_actor` FOREIGN KEY (`actor_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- >>> END 08_promotions_notifications_and_admin_operations.sql <<<


-- >>> BEGIN 09_mysql_indexes_triggers_views_procedures.sql <<<

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

-- >>> END 09_mysql_indexes_triggers_views_procedures.sql <<<


-- >>> BEGIN 10_seed_reference_data.sql <<<

-- =============================================================================
-- HunarLink MySQL 8.4 LTS Safe Reference Seed Data
-- File: sql/10_seed_reference_data.sql
-- Purpose: Insert ONLY safe platform reference data:
--   - 6 platform roles
--   - 6 admin roles
--   - 16 fine-grained admin permissions & role-permission mappings
--   - 6 core Kashmiri handicraft categories
--   - Non-secret default platform settings
--
-- STRICT SAFETY RULE:
--   DO NOT seed fake users, fake Super Admins, fake sellers, fake suppliers,
--   fake dealers, fake payment credentials, or fictional official GI reference
--   records. Provision the first Super Admin only after verifying a real Clerk
--   user identity.
-- =============================================================================

USE `hunarlink`;

-- -----------------------------------------------------------------------------
-- 1. Platform Roles (6 roles)
-- -----------------------------------------------------------------------------
INSERT INTO `platform_roles` (`id`, `code`, `name`, `description`, `is_active`) VALUES
  ('10000000-0000-4000-8000-000000000001', 'CUSTOMER',        'Customer',            'Individual retail buyer purchasing crafts from approved direct sellers.', 1),
  ('10000000-0000-4000-8000-000000000002', 'DIRECT_SELLER',   'Direct Seller',       'Approved artisan or workshop selling products directly to retail customers.', 1),
  ('10000000-0000-4000-8000-000000000003', 'SUPPLIER',        'Supplier / Producer', 'Producer or artisan cluster submitting supply lots for dealer procurement.', 1),
  ('10000000-0000-4000-8000-000000000004', 'DEALER',          'Dealer',              'Approved wholesale dealer procuring lots and fulfilling bulk B2B orders.', 1),
  ('10000000-0000-4000-8000-000000000005', 'WHOLESALE_BUYER', 'Wholesale Buyer',     'Verified B2B buyer purchasing bulk lots or requesting dealer quotations.', 1),
  ('10000000-0000-4000-8000-000000000006', 'ADMIN',           'Admin',               'Authorized platform operator with role-scoped administrative permissions.', 1)
ON DUPLICATE KEY UPDATE
  `name` = VALUES(`name`),
  `description` = VALUES(`description`),
  `is_active` = VALUES(`is_active`);

-- -----------------------------------------------------------------------------
-- 2. Admin Roles (6 roles)
-- -----------------------------------------------------------------------------
INSERT INTO `admin_roles` (`id`, `code`, `name`, `description`, `is_system_role`, `is_active`) VALUES
  ('20000000-0000-4000-8000-000000000001', 'SUPER_ADMIN',         'Super Administrator',  'Full administrative governance including RBAC, settings, and escalations.', 1, 1),
  ('20000000-0000-4000-8000-000000000002', 'GI_VERIFIER',         'GI & Craft Verifier',  'Reviews GI evidence runs, Non-GI seller applications, and product GI claims.', 1, 1),
  ('20000000-0000-4000-8000-000000000003', 'PROCUREMENT_MANAGER', 'Procurement Manager',  'Reviews supplier lots, ranks dealers, and oversees procurement workflow.', 1, 1),
  ('20000000-0000-4000-8000-000000000004', 'FINANCE_ADMIN',       'Finance Administrator','Monitors payments, reconciliation, refunds, and settlement ledgers.', 1, 1),
  ('20000000-0000-4000-8000-000000000005', 'CATALOG_MODERATOR',   'Catalogue Moderator',  'Approves products, seller listings, and guardrail review cases.', 1, 1),
  ('20000000-0000-4000-8000-000000000006', 'SUPPORT_LEAD',        'Support Lead',         'Handles customer/seller tickets and return escalations.', 1, 1)
ON DUPLICATE KEY UPDATE
  `name` = VALUES(`name`),
  `description` = VALUES(`description`),
  `is_active` = VALUES(`is_active`);

-- -----------------------------------------------------------------------------
-- 3. Admin Permissions (16 fine-grained permissions)
-- -----------------------------------------------------------------------------
INSERT INTO `admin_permissions` (`id`, `code`, `module_name`, `description`, `is_high_risk`) VALUES
  ('30000000-0000-4000-8000-000000000001', 'users.read',           'identity',    'View user accounts and assigned platform roles.', 0),
  ('30000000-0000-4000-8000-000000000002', 'users.manage',         'identity',    'Suspend, reactivate, or update user role assignments.', 1),
  ('30000000-0000-4000-8000-000000000003', 'sellers.review',       'sellers',     'Review and decide Non-GI and GI seller onboarding applications.', 0),
  ('30000000-0000-4000-8000-000000000004', 'gi.review',            'gi',          'Review GI evidence assessments and approve/reject product GI claims.', 1),
  ('30000000-0000-4000-8000-000000000005', 'catalog.approve',      'catalog',     'Approve or reject products and seller/dealer listings.', 0),
  ('30000000-0000-4000-8000-000000000006', 'procurement.read',     'procurement', 'Inspect supplier lots, dealer assignments, POs, and receipts.', 0),
  ('30000000-0000-4000-8000-000000000007', 'procurement.manage',   'procurement', 'Approve supplier lots and assign suitable dealers.', 0),
  ('30000000-0000-4000-8000-000000000008', 'payments.read',        'payments',    'View payments, webhook events, and reconciliation records.', 0),
  ('30000000-0000-4000-8000-000000000009', 'payments.refund',      'payments',    'Initiate and approve full or partial customer payment refunds.', 1),
  ('30000000-0000-4000-8000-000000000010', 'payouts.manage',       'payments',    'Manage seller, dealer, and supplier settlement obligations.', 1),
  ('30000000-0000-4000-8000-000000000011', 'guardrails.read',      'guardrails',  'Inspect seller input guardrail checks and review cases.', 0),
  ('30000000-0000-4000-8000-000000000012', 'guardrails.decide',    'guardrails',  'Approve, reject, or override guardrail review cases with mandatory reason.', 1),
  ('30000000-0000-4000-8000-000000000013', 'support.manage',       'operations',  'Respond to support tickets and oversee returns.', 0),
  ('30000000-0000-4000-8000-000000000014', 'settings.manage',      'operations',  'Modify platform-wide operational settings.', 1),
  ('30000000-0000-4000-8000-000000000015', 'audit.read',           'operations',  'Read immutable audit logs and security histories.', 0),
  ('30000000-0000-4000-8000-000000000016', 'rbac.manage',          'identity',    'Assign or revoke Admin roles and permissions.', 1)
ON DUPLICATE KEY UPDATE
  `description` = VALUES(`description`),
  `is_high_risk` = VALUES(`is_high_risk`);

-- -----------------------------------------------------------------------------
-- 4. Admin Role -> Permission Mappings
-- -----------------------------------------------------------------------------
-- SUPER_ADMIN receives all 16 permissions
INSERT IGNORE INTO `admin_role_permissions` (`id`, `admin_role_id`, `admin_permission_id`)
SELECT
  CONCAT('40000000-0000-4000-8000-', LPAD(ROW_NUMBER() OVER (ORDER BY `code`), 12, '0')),
  '20000000-0000-4000-8000-000000000001',
  `id`
FROM `admin_permissions`;

-- Scoped role permissions
INSERT IGNORE INTO `admin_role_permissions` (`id`, `admin_role_id`, `admin_permission_id`) VALUES
  ('41000000-0000-4000-8000-000000000001', '20000000-0000-4000-8000-000000000002', '30000000-0000-4000-8000-000000000003'),
  ('41000000-0000-4000-8000-000000000002', '20000000-0000-4000-8000-000000000002', '30000000-0000-4000-8000-000000000004'),
  ('41000000-0000-4000-8000-000000000003', '20000000-0000-4000-8000-000000000002', '30000000-0000-4000-8000-000000000011'),
  ('41000000-0000-4000-8000-000000000004', '20000000-0000-4000-8000-000000000002', '30000000-0000-4000-8000-000000000012'),
  ('41000000-0000-4000-8000-000000000005', '20000000-0000-4000-8000-000000000003', '30000000-0000-4000-8000-000000000006'),
  ('41000000-0000-4000-8000-000000000006', '20000000-0000-4000-8000-000000000003', '30000000-0000-4000-8000-000000000007'),
  ('41000000-0000-4000-8000-000000000007', '20000000-0000-4000-8000-000000000003', '30000000-0000-4000-8000-000000000011'),
  ('41000000-0000-4000-8000-000000000008', '20000000-0000-4000-8000-000000000004', '30000000-0000-4000-8000-000000000008'),
  ('41000000-0000-4000-8000-000000000009', '20000000-0000-4000-8000-000000000004', '30000000-0000-4000-8000-000000000009'),
  ('41000000-0000-4000-8000-000000000010', '20000000-0000-4000-8000-000000000004', '30000000-0000-4000-8000-000000000010'),
  ('41000000-0000-4000-8000-000000000011', '20000000-0000-4000-8000-000000000004', '30000000-0000-4000-8000-000000000015'),
  ('41000000-0000-4000-8000-000000000012', '20000000-0000-4000-8000-000000000005', '30000000-0000-4000-8000-000000000005'),
  ('41000000-0000-4000-8000-000000000013', '20000000-0000-4000-8000-000000000005', '30000000-0000-4000-8000-000000000011'),
  ('41000000-0000-4000-8000-000000000014', '20000000-0000-4000-8000-000000000005', '30000000-0000-4000-8000-000000000012'),
  ('41000000-0000-4000-8000-000000000015', '20000000-0000-4000-8000-000000000006', '30000000-0000-4000-8000-000000000001'),
  ('41000000-0000-4000-8000-000000000016', '20000000-0000-4000-8000-000000000006', '30000000-0000-4000-8000-000000000013');

-- -----------------------------------------------------------------------------
-- 5. Core Craft Categories (Reference Taxonomy Only)
-- -----------------------------------------------------------------------------
INSERT INTO `categories` (`id`, `parent_id`, `code`, `name`, `slug`, `description`, `is_gi_eligible_category`, `display_order`, `is_active`) VALUES
  ('50000000-0000-4000-8000-000000000001', NULL, 'PASHMINA',     'Pashmina & Kani Shawls', 'pashmina-kani-shawls', 'Hand-spun Kashmiri Pashmina, Kani Jamawar, and Sozni shawls.', 1, 1, 1),
  ('50000000-0000-4000-8000-000000000002', NULL, 'WALNUT_WOOD',  'Walnut Woodcarving',     'walnut-woodcarving',   'Seasoned Juglans Regia hand-carved furniture, screens, and decor.', 1, 2, 1),
  ('50000000-0000-4000-8000-000000000003', NULL, 'SILK_CARPETS', 'Hand-Knotted Carpets',   'hand-knotted-carpets', 'Kashmiri silk-on-silk and wool hand-knotted carpets.', 1, 3, 1),
  ('50000000-0000-4000-8000-000000000004', NULL, 'PAPIER_MACHE', 'Papier-Mache Art',       'papier-mache-art',     'Sakhta and Naqashi lacquered papier-mache craftwork.', 1, 4, 1),
  ('50000000-0000-4000-8000-000000000005', NULL, 'SOZNI',        'Sozni Embroidery',       'sozni-embroidery',     'Fine Kashmiri needlework textiles and stoles.', 1, 5, 1),
  ('50000000-0000-4000-8000-000000000006', NULL, 'COPPERWARE',   'Copperware & Crewels',   'copperware-crewels',   'Hand-engraved Kandkari copperware and traditional crewel textiles.', 0, 6, 1)
ON DUPLICATE KEY UPDATE
  `name` = VALUES(`name`),
  `description` = VALUES(`description`),
  `is_active` = VALUES(`is_active`);

-- -----------------------------------------------------------------------------
-- 6. Safe Default Platform Settings (Non-Secret Operational Defaults)
-- -----------------------------------------------------------------------------
INSERT INTO `platform_settings` (`id`, `setting_key`, `setting_value_json`, `description`, `is_sensitive`, `is_active`) VALUES
  ('60000000-0000-4000-8000-000000000001', 'default_currency',                 JSON_OBJECT('currency', 'INR'),              'Default transaction currency for initial India release.', 0, 1),
  ('60000000-0000-4000-8000-000000000002', 'payment_capture_policy',           JSON_OBJECT('mode', 'AUTO_CAPTURE_REQUIRED'), 'Online fulfilment requires verified CAPTURED payment.', 0, 1),
  ('60000000-0000-4000-8000-000000000003', 'gi_llm_enabled',                   JSON_OBJECT('enabled', false),                'GI LLM assessment remains behind provider flag until official GI dataset is loaded.', 0, 1),
  ('60000000-0000-4000-8000-000000000004', 'cod_enabled',                      JSON_OBJECT('enabled', true),                 'Allow Cash on Delivery on eligible retail orders without creating Razorpay orders.', 0, 1),
  ('60000000-0000-4000-8000-000000000005', 'stock_reservation_ttl_minutes',    JSON_OBJECT('minutes', 15),                   'Default checkout reservation hold window in minutes.', 0, 1)
ON DUPLICATE KEY UPDATE
  `description` = VALUES(`description`);

-- >>> END 10_seed_reference_data.sql <<<
