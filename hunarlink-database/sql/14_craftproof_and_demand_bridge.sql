-- ============================================================================
-- HunarLink — Module 14: CraftProof AI Passports, Claims, Evidence & Demand Bridge
-- Target: MySQL 8.0 / 8.4 LTS (strictly additive — zero changes to 00-13 tables)
-- ============================================================================
-- Trust Invariant (enforced both in application layer and MySQL CHECK constraints):
--   AI/LLM advisories (`actor_type = 'AI_ADVISORY'`) NEVER set a claim status
--   to `HUMAN_VERIFIED` or `THIRD_PARTY_VERIFIED` and are ALWAYS `is_legal_proof = 0`.
-- ============================================================================

USE `hunarlink`;

-- 1. Digital Craft Passport (1-to-1 per seller_product_listings)
CREATE TABLE IF NOT EXISTS `craft_passports` (
    `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `passport_code` VARCHAR(40) NOT NULL,
    `listing_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `product_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `seller_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `public_slug` VARCHAR(260) NOT NULL,
    `overall_trust_level` ENUM(
        'SELLER_DECLARED',
        'EVIDENCE_SUBMITTED',
        'UNDER_REVIEW',
        'HUMAN_VERIFIED',
        'THIRD_PARTY_VERIFIED',
        'NOT_ESTABLISHED',
        'REJECTED'
    ) NOT NULL DEFAULT 'SELLER_DECLARED',
    `materials_summary` TEXT NULL,
    `manufacturing_process` TEXT NULL,
    `origin_location` VARCHAR(180) NULL,
    `craft_days_estimated` SMALLINT UNSIGNED NULL,
    `artisan_story` TEXT NULL,
    `fair_craft_breakdown_json` JSON NULL,
    `serial_number` VARCHAR(48) NULL,
    `first_scanned_at` DATETIME(6) NULL,
    `scan_count` INT NOT NULL DEFAULT 0,
    `is_public` TINYINT(1) NOT NULL DEFAULT 1,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_craft_passports_code` (`passport_code`),
    UNIQUE KEY `uq_craft_passports_listing` (`listing_id`),
    UNIQUE KEY `uq_craft_passports_slug` (`public_slug`),
    KEY `idx_craft_passports_product` (`product_id`),
    KEY `idx_craft_passports_seller` (`seller_profile_id`),
    KEY `idx_craft_passports_trust` (`overall_trust_level`),
    CONSTRAINT `fk_cp_listing` FOREIGN KEY (`listing_id`) REFERENCES `seller_product_listings` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_cp_product` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_cp_seller` FOREIGN KEY (`seller_profile_id`) REFERENCES `seller_profiles` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 2. Atomic Product Craft Claims (explicit separation of Seller Declared vs Verified)
CREATE TABLE IF NOT EXISTS `craft_product_claims` (
    `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `passport_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `claim_type` ENUM(
        'MATERIAL',
        'ORIGIN',
        'TECHNIQUE',
        'HANDMADE',
        'GI_TAG',
        'CERTIFICATION',
        'OTHER'
    ) NOT NULL,
    `claim_title` VARCHAR(160) NOT NULL,
    `claim_value` VARCHAR(500) NOT NULL,
    `claim_source` ENUM('SELLER_DECLARED', 'THIRD_PARTY_IMPORT') NOT NULL DEFAULT 'SELLER_DECLARED',
    `verification_status` ENUM(
        'SELLER_DECLARED',
        'EVIDENCE_SUBMITTED',
        'UNDER_REVIEW',
        'HUMAN_VERIFIED',
        'THIRD_PARTY_VERIFIED',
        'NOT_ESTABLISHED',
        'REJECTED'
    ) NOT NULL DEFAULT 'SELLER_DECLARED',
    `verified_by_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
    `verified_by_authority` VARCHAR(180) NULL,
    `verified_at` DATETIME(6) NULL,
    `decision_notes` VARCHAR(1000) NULL,
    `ai_advisory_json` JSON NULL,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`id`),
    KEY `idx_cpc_passport_status` (`passport_id`, `verification_status`),
    KEY `idx_cpc_status` (`verification_status`),
    CONSTRAINT `fk_cpc_passport` FOREIGN KEY (`passport_id`) REFERENCES `craft_passports` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_cpc_verified_by` FOREIGN KEY (`verified_by_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 3. Claim Supporting Evidence (reuses private file_security_scans SHA-256 vault)
CREATE TABLE IF NOT EXISTS `craft_claim_evidence` (
    `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `claim_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `passport_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `evidence_type` ENUM(
        'WORKSHOP_PHOTO',
        'LOOM_VIDEO_FRAME',
        'LAB_REPORT',
        'GI_CERTIFICATE',
        'ARTISAN_CARD',
        'INVOICE_RAW_MATERIAL',
        'THIRD_PARTY_REGISTRY',
        'OTHER'
    ) NOT NULL,
    `file_scan_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
    `storage_key` VARCHAR(512) NULL,
    `original_filename` VARCHAR(255) NULL,
    `external_reference_url` VARCHAR(512) NULL,
    `sha256_hash` CHAR(64) NULL,
    `caption` VARCHAR(500) NULL,
    `uploaded_by_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`id`),
    KEY `idx_cce_claim` (`claim_id`),
    KEY `idx_cce_passport` (`passport_id`),
    CONSTRAINT `fk_cce_claim` FOREIGN KEY (`claim_id`) REFERENCES `craft_product_claims` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_cce_passport` FOREIGN KEY (`passport_id`) REFERENCES `craft_passports` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_cce_uploader` FOREIGN KEY (`uploaded_by_user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 4. Immutable Verification Audit Timeline (Hard DB Guard: AI can never mark Verified)
CREATE TABLE IF NOT EXISTS `craft_verification_events` (
    `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `passport_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `claim_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
    `event_type` ENUM(
        'PASSPORT_CREATED',
        'CLAIM_DECLARED',
        'EVIDENCE_ATTACHED',
        'AI_ADVISORY_RUN',
        'STATUS_CHANGED',
        'HUMAN_REVIEW_DECISION',
        'THIRD_PARTY_RECORDED'
    ) NOT NULL,
    `from_status` VARCHAR(32) NULL,
    `to_status` VARCHAR(32) NULL,
    `actor_type` ENUM('SELLER', 'HUMAN_ADMIN', 'THIRD_PARTY', 'AI_ADVISORY', 'SYSTEM') NOT NULL,
    `actor_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
    `summary` VARCHAR(500) NOT NULL,
    `metadata_json` JSON NULL,
    `is_legal_proof` TINYINT(1) NOT NULL DEFAULT 0,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`id`),
    KEY `idx_cve_passport_created` (`passport_id`, `created_at`),
    KEY `idx_cve_claim` (`claim_id`),
    CONSTRAINT `fk_cve_passport` FOREIGN KEY (`passport_id`) REFERENCES `craft_passports` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_cve_claim` FOREIGN KEY (`claim_id`) REFERENCES `craft_product_claims` (`id`) ON DELETE SET NULL,
    CONSTRAINT `fk_cve_actor` FOREIGN KEY (`actor_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL,
    CONSTRAINT `chk_cve_ai_never_verifies` CHECK (
        NOT (
            `actor_type` = 'AI_ADVISORY'
            AND (
                `to_status` IN ('HUMAN_VERIFIED', 'THIRD_PARTY_VERIFIED')
                OR `is_legal_proof` = 1
            )
        )
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 5. Artisan Production Capabilities (feeds Deterministic Demand Bridge & Cluster Pooling)
CREATE TABLE IF NOT EXISTS `artisan_capabilities` (
    `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `seller_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `category_slug` VARCHAR(140) NOT NULL,
    `craft_techniques_json` JSON NOT NULL,
    `monthly_capacity_units` INT UNSIGNED NOT NULL DEFAULT 25,
    `min_order_qty` INT UNSIGNED NOT NULL DEFAULT 5,
    `standard_lead_time_days` SMALLINT UNSIGNED NOT NULL DEFAULT 18,
    `unit_price_min_inr` DECIMAL(14, 2) NOT NULL DEFAULT 1500.00,
    `unit_price_max_inr` DECIMAL(14, 2) NOT NULL DEFAULT 12000.00,
    `supports_custom_design` TINYINT(1) NOT NULL DEFAULT 1,
    `accepts_wholesale` TINYINT(1) NOT NULL DEFAULT 1,
    `availability_status` ENUM('AVAILABLE', 'LIMITED', 'BOOKED') NOT NULL DEFAULT 'AVAILABLE',
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_artisan_cap_seller_cat` (`seller_profile_id`, `category_slug`),
    KEY `idx_artisan_cap_cat_avail` (`category_slug`, `availability_status`),
    CONSTRAINT `fk_ac_seller` FOREIGN KEY (`seller_profile_id`) REFERENCES `seller_profiles` (`id`) ON DELETE CASCADE,
    CONSTRAINT `chk_ac_price_band` CHECK (`unit_price_max_inr` >= `unit_price_min_inr`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 6. Demand Bridge Buyer Requirements (direct natural-language → structured brief)
CREATE TABLE IF NOT EXISTS `buyer_demand_requests` (
    `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `request_code` VARCHAR(40) NOT NULL,
    `buyer_user_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
    `buyer_name` VARCHAR(160) NULL,
    `buyer_email` VARCHAR(255) NULL,
    `raw_request_text` TEXT NOT NULL,
    `structured_requirements_json` JSON NOT NULL,
    `category_slug` VARCHAR(140) NULL,
    `requested_quantity` INT UNSIGNED NOT NULL DEFAULT 10,
    `budget_min_inr` DECIMAL(14, 2) NULL,
    `budget_max_inr` DECIMAL(14, 2) NULL,
    `target_delivery_days` SMALLINT UNSIGNED NULL,
    `requires_verified_claims` TINYINT(1) NOT NULL DEFAULT 0,
    `allow_cluster_pooling` TINYINT(1) NOT NULL DEFAULT 1,
    `fulfillment_mode` ENUM('SINGLE_ARTISAN', 'MULTI_ARTISAN_CLUSTER', 'UNMATCHED') NOT NULL DEFAULT 'SINGLE_ARTISAN',
    `request_status` ENUM('DRAFT', 'MATCHED', 'INQUIRY_SENT', 'CLOSED') NOT NULL DEFAULT 'MATCHED',
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_bdr_code` (`request_code`),
    KEY `idx_bdr_buyer` (`buyer_user_id`),
    KEY `idx_bdr_category` (`category_slug`),
    CONSTRAINT `fk_bdr_buyer` FOREIGN KEY (`buyer_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 7. Deterministic Artisan & Cluster Match Records
CREATE TABLE IF NOT EXISTS `demand_artisan_matches` (
    `id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `demand_request_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `seller_profile_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `match_rank` SMALLINT UNSIGNED NOT NULL DEFAULT 1,
    `is_cluster_member` TINYINT(1) NOT NULL DEFAULT 0,
    `allocated_quantity` INT UNSIGNED NOT NULL DEFAULT 0,
    `match_score` DECIMAL(5, 2) NOT NULL,
    `score_breakdown_json` JSON NOT NULL,
    `match_reasons_json` JSON NOT NULL,
    `estimated_unit_price_inr` DECIMAL(14, 2) NULL,
    `estimated_lead_days` SMALLINT UNSIGNED NULL,
    `match_status` ENUM('SUGGESTED', 'SHORTLISTED', 'CONTACTED', 'ACCEPTED', 'DECLINED') NOT NULL DEFAULT 'SUGGESTED',
    `artisan_response_note` VARCHAR(500) NULL,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`id`),
    KEY `idx_dam_request` (`demand_request_id`),
    KEY `idx_dam_seller_status` (`seller_profile_id`, `match_status`),
    CONSTRAINT `fk_dam_request` FOREIGN KEY (`demand_request_id`) REFERENCES `buyer_demand_requests` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_dam_seller` FOREIGN KEY (`seller_profile_id`) REFERENCES `seller_profiles` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
