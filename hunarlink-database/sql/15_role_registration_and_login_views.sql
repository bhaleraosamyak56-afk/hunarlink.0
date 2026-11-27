-- ============================================================================
-- HunarLink — Module 15: Per-Role Registered vs Logged-In Separation & Audit Logs
-- Target: MySQL 8.0 / 8.4 LTS (strictly additive — zero changes to 00-14 tables)
-- ============================================================================
-- Creates:
--   1. `user_login_logs` table (tracks REGISTER vs LOGIN events per role_code)
--   2. Dedicated MySQL Views separating Registered Users vs Logged-In Users
--      for each role (`CUSTOMER`, `DIRECT_SELLER`, `ADMIN`, `WHOLESALE_BUYER`/`DEALER`/`SUPPLIER`)
-- ============================================================================

USE `hunarlink`;

-- 1. Role-aware Registration & Login Audit Log
CREATE TABLE IF NOT EXISTS `user_login_logs` (
    `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `role_code` VARCHAR(50) NOT NULL,
    `auth_event_type` VARCHAR(24) NOT NULL,
    `auth_method` VARCHAR(32) NOT NULL,
    `email` VARCHAR(255) NOT NULL,
    `ip_address` VARCHAR(64) NULL,
    `user_agent` VARCHAR(500) NULL,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`id`),
    KEY `idx_ull_user_role_event` (`user_id`, `role_code`, `auth_event_type`),
    KEY `idx_ull_role_event_time` (`role_code`, `auth_event_type`, `created_at`),
    KEY `idx_ull_created_at` (`created_at`),
    CONSTRAINT `fk_ull_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 2. Buyers (`CUSTOMER`) — All Registered vs Actually Logged-In
CREATE OR REPLACE VIEW `vw_registered_buyers` AS
SELECT
    u.`id` AS `user_id`,
    u.`clerk_user_id`,
    u.`email`,
    COALESCE(u.`display_name`, CONCAT_WS(' ', u.`first_name`, u.`last_name`)) AS `display_name`,
    u.`phone`,
    u.`account_status`,
    pr.`code` AS `role_code`,
    u.`created_at` AS `registered_at`,
    COALESCE(ll.`last_event_login_at`, u.`last_login_at`) AS `last_login_at`,
    COALESCE(ll.`login_count`, 0) AS `login_count`,
    CASE
        WHEN COALESCE(ll.`last_event_login_at`, u.`last_login_at`) IS NOT NULL THEN 1
        ELSE 0
    END AS `has_logged_in`
FROM `users` u
INNER JOIN `user_role_assignments` ura
    ON ura.`user_id` = u.`id` AND ura.`assignment_status` = 'ACTIVE'
INNER JOIN `platform_roles` pr
    ON pr.`id` = ura.`platform_role_id` AND pr.`code` = 'CUSTOMER' AND pr.`is_active` = 1
LEFT JOIN (
    SELECT
        `user_id`,
        COUNT(*) AS `login_count`,
        MAX(`created_at`) AS `last_event_login_at`
    FROM `user_login_logs`
    WHERE `auth_event_type` = 'LOGIN' AND `role_code` = 'CUSTOMER'
    GROUP BY `user_id`
) ll ON ll.`user_id` = u.`id`;

CREATE OR REPLACE VIEW `vw_logged_in_buyers` AS
SELECT *
FROM `vw_registered_buyers`
WHERE `has_logged_in` = 1;

-- 3. Artisans (`DIRECT_SELLER`) — All Registered/Seeded vs Actually Logged-In
CREATE OR REPLACE VIEW `vw_registered_artisans` AS
SELECT
    u.`id` AS `user_id`,
    u.`clerk_user_id`,
    u.`email`,
    COALESCE(u.`display_name`, CONCAT_WS(' ', u.`first_name`, u.`last_name`)) AS `display_name`,
    u.`phone`,
    u.`account_status`,
    pr.`code` AS `role_code`,
    sp.`id` AS `seller_profile_id`,
    sp.`store_name`,
    sp.`workshop_district`,
    sp.`verification_path`,
    sp.`verification_status`,
    sp.`profile_status`,
    u.`created_at` AS `registered_at`,
    COALESCE(ll.`last_event_login_at`, u.`last_login_at`) AS `last_login_at`,
    COALESCE(ll.`login_count`, 0) AS `login_count`,
    CASE
        WHEN COALESCE(ll.`last_event_login_at`, u.`last_login_at`) IS NOT NULL THEN 1
        ELSE 0
    END AS `has_logged_in`
FROM `users` u
INNER JOIN `user_role_assignments` ura
    ON ura.`user_id` = u.`id` AND ura.`assignment_status` = 'ACTIVE'
INNER JOIN `platform_roles` pr
    ON pr.`id` = ura.`platform_role_id` AND pr.`code` = 'DIRECT_SELLER' AND pr.`is_active` = 1
LEFT JOIN `seller_profiles` sp
    ON sp.`user_id` = u.`id`
LEFT JOIN (
    SELECT
        `user_id`,
        COUNT(*) AS `login_count`,
        MAX(`created_at`) AS `last_event_login_at`
    FROM `user_login_logs`
    WHERE `auth_event_type` = 'LOGIN' AND `role_code` = 'DIRECT_SELLER'
    GROUP BY `user_id`
) ll ON ll.`user_id` = u.`id`;

CREATE OR REPLACE VIEW `vw_logged_in_artisans` AS
SELECT *
FROM `vw_registered_artisans`
WHERE `has_logged_in` = 1;

-- 4. Admins (`ADMIN`) — All DB-Provisioned vs Actually Logged-In
CREATE OR REPLACE VIEW `vw_registered_admins` AS
SELECT
    u.`id` AS `user_id`,
    ac.`id` AS `admin_credential_id`,
    ac.`email`,
    COALESCE(u.`display_name`, CONCAT_WS(' ', u.`first_name`, u.`last_name`)) AS `display_name`,
    u.`account_status`,
    ac.`is_active`,
    ap.`department`,
    ac.`created_at` AS `registered_at`,
    COALESCE(ll.`last_event_login_at`, ac.`last_login_at`, u.`last_login_at`) AS `last_login_at`,
    COALESCE(ll.`login_count`, 0) AS `login_count`,
    CASE
        WHEN COALESCE(ll.`last_event_login_at`, ac.`last_login_at`, u.`last_login_at`) IS NOT NULL THEN 1
        ELSE 0
    END AS `has_logged_in`
FROM `admin_credentials` ac
INNER JOIN `users` u
    ON u.`id` = ac.`user_id`
LEFT JOIN `admin_profiles` ap
    ON ap.`user_id` = u.`id`
LEFT JOIN (
    SELECT
        `user_id`,
        COUNT(*) AS `login_count`,
        MAX(`created_at`) AS `last_event_login_at`
    FROM `user_login_logs`
    WHERE `auth_event_type` = 'LOGIN' AND `role_code` = 'ADMIN'
    GROUP BY `user_id`
) ll ON ll.`user_id` = u.`id`;

CREATE OR REPLACE VIEW `vw_logged_in_admins` AS
SELECT *
FROM `vw_registered_admins`
WHERE `has_logged_in` = 1;

-- 5. Wholesale / Dealers / Suppliers — All Registered vs Actually Logged-In
CREATE OR REPLACE VIEW `vw_registered_wholesale_accounts` AS
SELECT
    u.`id` AS `user_id`,
    u.`clerk_user_id`,
    u.`email`,
    COALESCE(u.`display_name`, CONCAT_WS(' ', u.`first_name`, u.`last_name`)) AS `display_name`,
    u.`phone`,
    u.`account_status`,
    pr.`code` AS `role_code`,
    u.`created_at` AS `registered_at`,
    COALESCE(ll.`last_event_login_at`, u.`last_login_at`) AS `last_login_at`,
    COALESCE(ll.`login_count`, 0) AS `login_count`,
    CASE
        WHEN COALESCE(ll.`last_event_login_at`, u.`last_login_at`) IS NOT NULL THEN 1
        ELSE 0
    END AS `has_logged_in`
FROM `users` u
INNER JOIN `user_role_assignments` ura
    ON ura.`user_id` = u.`id` AND ura.`assignment_status` = 'ACTIVE'
INNER JOIN `platform_roles` pr
    ON pr.`id` = ura.`platform_role_id`
   AND pr.`code` IN ('WHOLESALE_BUYER', 'DEALER', 'SUPPLIER')
   AND pr.`is_active` = 1
LEFT JOIN (
    SELECT
        `user_id`,
        `role_code`,
        COUNT(*) AS `login_count`,
        MAX(`created_at`) AS `last_event_login_at`
    FROM `user_login_logs`
    WHERE `auth_event_type` = 'LOGIN'
    GROUP BY `user_id`, `role_code`
) ll ON ll.`user_id` = u.`id` AND ll.`role_code` = pr.`code`;

CREATE OR REPLACE VIEW `vw_logged_in_wholesale_accounts` AS
SELECT *
FROM `vw_registered_wholesale_accounts`
WHERE `has_logged_in` = 1;

-- 6. Unified Summary by Role (Registered vs Logged-In vs Never-Logged-In)
CREATE OR REPLACE VIEW `vw_user_role_activity_summary` AS
SELECT
    pr.`code` AS `role_code`,
    pr.`name` AS `role_name`,
    COUNT(DISTINCT ura.`user_id`) AS `registered_users`,
    COUNT(DISTINCT CASE
        WHEN COALESCE(ll.`last_event_login_at`, u.`last_login_at`) IS NOT NULL THEN ura.`user_id`
        ELSE NULL
    END) AS `logged_in_users`,
    COUNT(DISTINCT CASE
        WHEN COALESCE(ll.`last_event_login_at`, u.`last_login_at`) IS NULL THEN ura.`user_id`
        ELSE NULL
    END) AS `registered_only_never_logged_in`,
    COALESCE(SUM(COALESCE(ll.`login_count`, 0)), 0) AS `total_login_events`,
    MAX(COALESCE(ll.`last_event_login_at`, u.`last_login_at`)) AS `latest_login_at`
FROM `platform_roles` pr
LEFT JOIN `user_role_assignments` ura
    ON ura.`platform_role_id` = pr.`id` AND ura.`assignment_status` = 'ACTIVE'
LEFT JOIN `users` u
    ON u.`id` = ura.`user_id`
LEFT JOIN (
    SELECT
        `user_id`,
        `role_code`,
        COUNT(*) AS `login_count`,
        MAX(`created_at`) AS `last_event_login_at`
    FROM `user_login_logs`
    WHERE `auth_event_type` = 'LOGIN'
    GROUP BY `user_id`, `role_code`
) ll ON ll.`user_id` = u.`id` AND ll.`role_code` = pr.`code`
WHERE pr.`is_active` = 1
GROUP BY pr.`code`, pr.`name`;
