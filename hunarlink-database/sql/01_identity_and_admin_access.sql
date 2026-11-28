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
