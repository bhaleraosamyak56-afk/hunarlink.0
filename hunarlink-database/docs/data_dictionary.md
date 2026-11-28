# HunarLink MySQL 8.4 LTS — Complete Data Dictionary

Auto-reconciled directly from `sql/01`–`sql/08` (**96 base tables**, **256 foreign keys**, **135 CHECK constraints**, **9 MySQL generated partial-uniqueness columns**).

All tables use `ENGINE=InnoDB`, `DEFAULT CHARSET=utf8mb4`, `COLLATE=utf8mb4_0900_ai_ci`, UTC `DATETIME(6)` timestamps, `DECIMAL` monetary/quantity types, and `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin` UUID identifiers.

## 1. `users`
*Defined in:* `sql/01_identity_and_admin_access.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `clerk_user_id` | `VARCHAR(128) NOT NULL` |
| `email` | `VARCHAR(255) NOT NULL` |
| `email_verified` | `TINYINT(1) NOT NULL DEFAULT 0` |
| `phone` | `VARCHAR(32) NULL` |
| `phone_verified` | `TINYINT(1) NOT NULL DEFAULT 0` |
| `first_name` | `VARCHAR(100) NOT NULL` |
| `last_name` | `VARCHAR(100) NULL` |
| `display_name` | `VARCHAR(160) NULL` |
| `avatar_storage_key` | `VARCHAR(512) NULL` |
| `preferred_locale` | `VARCHAR(16) NOT NULL DEFAULT 'en-IN'` |
| `preferred_currency` | `CHAR(3) NOT NULL DEFAULT 'INR'` |
| `account_role` | `ENUM('BUYER', 'ARTISAN', 'ADMIN', 'WHOLESALE_BUYER', 'DEALER', 'SUPPLIER', 'DEACTIVATED') NOT NULL DEFAULT 'BUYER'` |
| `account_status` | `ENUM('PENDING_VERIFICATION', 'ACTIVE', 'SUSPENDED', 'DEACTIVATED') NOT NULL DEFAULT 'ACTIVE'` |
| `suspended_reason` | `VARCHAR(500) NULL` |
| `last_login_at` | `DATETIME(6) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

## 2. `platform_roles`
*Defined in:* `sql/01_identity_and_admin_access.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `code` | `VARCHAR(50) NOT NULL` |
| `name` | `VARCHAR(100) NOT NULL` |
| `description` | `VARCHAR(500) NULL` |
| `is_active` | `TINYINT(1) NOT NULL DEFAULT 1` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

## 3. `user_role_assignments`
*Defined in:* `sql/01_identity_and_admin_access.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `platform_role_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `assignment_status` | `ENUM('PENDING', 'ACTIVE', 'SUSPENDED', 'REVOKED') NOT NULL DEFAULT 'PENDING'` |
| `active_role_guard` | `TINYINT(1) GENERATED ALWAYS AS (IF(`assignment_status` = 'ACTIVE', 1, NULL)) STORED` |
| `granted_by_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `granted_at` | `DATETIME(6) NULL` |
| `revoked_by_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `revoked_at` | `DATETIME(6) NULL` |
| `status_reason` | `VARCHAR(500) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `user_id` → `users`.`id` (`fk_ura_user`), `platform_role_id` → `platform_roles`.`id` (`fk_ura_role`), `granted_by_user_id` → `users`.`id` (`fk_ura_granted_by`), `revoked_by_user_id` → `users`.`id` (`fk_ura_revoked_by`)

## 4. `user_addresses`
*Defined in:* `sql/01_identity_and_admin_access.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `address_label` | `VARCHAR(50) NOT NULL DEFAULT 'HOME'` |
| `recipient_name` | `VARCHAR(160) NOT NULL` |
| `recipient_phone` | `VARCHAR(32) NOT NULL` |
| `line1` | `VARCHAR(255) NOT NULL` |
| `line2` | `VARCHAR(255) NULL` |
| `landmark` | `VARCHAR(160) NULL` |
| `city` | `VARCHAR(100) NOT NULL` |
| `district` | `VARCHAR(100) NULL` |
| `state_province` | `VARCHAR(100) NOT NULL` |
| `postal_code` | `VARCHAR(20) NOT NULL` |
| `country_code` | `CHAR(2) NOT NULL DEFAULT 'IN'` |
| `is_default` | `TINYINT(1) NOT NULL DEFAULT 0` |
| `is_active` | `TINYINT(1) NOT NULL DEFAULT 1` |
| `default_address_guard` | `TINYINT(1) GENERATED ALWAYS AS (IF(`is_default` = 1 AND `is_active` = 1, 1, NULL)) STORED` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `user_id` → `users`.`id` (`fk_user_addresses_user`)

## 5. `admin_profiles`
*Defined in:* `sql/01_identity_and_admin_access.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `employee_code` | `VARCHAR(64) NULL` |
| `department` | `VARCHAR(100) NULL` |
| `job_title` | `VARCHAR(120) NULL` |
| `admin_status` | `ENUM('ACTIVE', 'SUSPENDED', 'REVOKED') NOT NULL DEFAULT 'ACTIVE'` |
| `mfa_required` | `TINYINT(1) NOT NULL DEFAULT 1` |
| `provisioned_by_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `user_id` → `users`.`id` (`fk_admin_profiles_user`), `provisioned_by_user_id` → `users`.`id` (`fk_admin_profiles_provisioned_by`)

## 6. `admin_roles`
*Defined in:* `sql/01_identity_and_admin_access.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `code` | `VARCHAR(64) NOT NULL` |
| `name` | `VARCHAR(120) NOT NULL` |
| `description` | `VARCHAR(500) NULL` |
| `is_system_role` | `TINYINT(1) NOT NULL DEFAULT 1` |
| `is_active` | `TINYINT(1) NOT NULL DEFAULT 1` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

## 7. `admin_permissions`
*Defined in:* `sql/01_identity_and_admin_access.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `code` | `VARCHAR(100) NOT NULL` |
| `module_name` | `VARCHAR(64) NOT NULL` |
| `description` | `VARCHAR(500) NULL` |
| `is_high_risk` | `TINYINT(1) NOT NULL DEFAULT 0` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

## 8. `admin_user_roles`
*Defined in:* `sql/01_identity_and_admin_access.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `admin_profile_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `admin_role_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `assigned_by_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `is_active` | `TINYINT(1) NOT NULL DEFAULT 1` |
| `active_assignment_guard` | `TINYINT(1) GENERATED ALWAYS AS (IF(`is_active` = 1, 1, NULL)) STORED` |
| `assigned_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `revoked_at` | `DATETIME(6) NULL` |

**Foreign Keys:** `admin_profile_id` → `admin_profiles`.`id` (`fk_aur_admin_profile`), `admin_role_id` → `admin_roles`.`id` (`fk_aur_admin_role`), `assigned_by_user_id` → `users`.`id` (`fk_aur_assigned_by`)

## 9. `admin_role_permissions`
*Defined in:* `sql/01_identity_and_admin_access.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `admin_role_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `admin_permission_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `admin_role_id` → `admin_roles`.`id` (`fk_arp_role`), `admin_permission_id` → `admin_permissions`.`id` (`fk_arp_permission`)

## 10. `admin_credentials`
*Defined in:* `sql/01_identity_and_admin_access.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `email` | `VARCHAR(255) NOT NULL` |
| `password_hash` | `VARCHAR(255) NOT NULL` |
| `is_active` | `TINYINT(1) NOT NULL DEFAULT 1` |
| `last_login_at` | `DATETIME(6) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `user_id` → `users`.`id` (`fk_admin_credentials_user`)

## 11. `seller_profiles`
*Defined in:* `sql/02_sellers_and_verification.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `store_name` | `VARCHAR(160) NOT NULL` |
| `store_slug` | `VARCHAR(180) NOT NULL` |
| `legal_business_name` | `VARCHAR(200) NULL` |
| `business_type` | `ENUM('INDIVIDUAL_ARTISAN', 'PROPRIETORSHIP', 'PARTNERSHIP', 'COOPERATIVE', 'PRIVATE_LIMITED', 'LLP') NOT NULL DEFAULT 'INDIVIDUAL_ARTISAN'` |
| `craft_specialty` | `VARCHAR(160) NULL` |
| `workshop_district` | `VARCHAR(100) NULL` |
| `workshop_state` | `VARCHAR(100) NOT NULL DEFAULT 'Jammu & Kashmir'` |
| `tax_id_masked` | `VARCHAR(64) NULL` |
| `gstin` | `VARCHAR(20) NULL` |
| `verification_path` | `ENUM('GI', 'NON_GI') NOT NULL DEFAULT 'NON_GI'` |
| `profile_status` | `ENUM('DRAFT', 'ACTIVE', 'SUSPENDED', 'TERMINATED') NOT NULL DEFAULT 'DRAFT'` |
| `verification_status` | `ENUM('UNVERIFIED', 'SUBMITTED', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'REVOKED') NOT NULL DEFAULT 'UNVERIFIED'` |
| `claimed_gi_authorized_user_no` | `VARCHAR(120) NULL` |
| `bio` | `TEXT NULL` |
| `average_rating` | `DECIMAL(3,2) NOT NULL DEFAULT 0.00` |
| `total_reviews` | `INT UNSIGNED NOT NULL DEFAULT 0` |
| `approved_at` | `DATETIME(6) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `user_id` → `users`.`id` (`fk_seller_profiles_user`)

## 12. `seller_verification_applications`
*Defined in:* `sql/02_sellers_and_verification.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `seller_profile_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `application_number` | `VARCHAR(64) NOT NULL` |
| `verification_path` | `ENUM('GI', 'NON_GI') NOT NULL` |
| `application_status` | `ENUM('DRAFT', 'SUBMITTED', 'UNDER_REVIEW', 'NEEDS_MORE_INFO', 'APPROVED', 'REJECTED', 'WITHDRAWN') NOT NULL DEFAULT 'DRAFT'` |
| `claimed_gi_code` | `VARCHAR(120) NULL` |
| `claimed_craft_cluster` | `VARCHAR(160) NULL` |
| `submitted_metadata` | `JSON NULL` |
| `submitted_at` | `DATETIME(6) NULL` |
| `assigned_reviewer_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `reviewed_by_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `reviewed_at` | `DATETIME(6) NULL` |
| `review_decision_notes` | `TEXT NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `seller_profile_id` → `seller_profiles`.`id` (`fk_sva_seller`), `assigned_reviewer_user_id` → `users`.`id` (`fk_sva_assigned_reviewer`), `reviewed_by_user_id` → `users`.`id` (`fk_sva_reviewed_by`)

## 13. `seller_documents`
*Defined in:* `sql/02_sellers_and_verification.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `seller_profile_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `application_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `document_type` | `ENUM('IDENTITY_PROOF', 'BUSINESS_REGISTRATION', 'TAX_CERTIFICATE', 'GI_AUTHORIZED_USER_CERT', 'WORKSHOP_PROOF', 'ARTISAN_PORTRAIT', 'BANK_PROOF', 'OTHER') NOT NULL` |
| `storage_key` | `VARCHAR(512) NOT NULL` |
| `original_filename` | `VARCHAR(255) NOT NULL` |
| `detected_mime_type` | `VARCHAR(120) NOT NULL` |
| `file_size_bytes` | `BIGINT UNSIGNED NOT NULL` |
| `sha256_hash` | `CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `scan_status` | `ENUM('PENDING_SCAN', 'CLEAN', 'INFECTED', 'SCAN_ERROR') NOT NULL DEFAULT 'PENDING_SCAN'` |
| `verification_status` | `ENUM('PENDING', 'ACCEPTED', 'REJECTED') NOT NULL DEFAULT 'PENDING'` |
| `uploaded_by_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `reviewed_by_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `review_notes` | `VARCHAR(500) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `seller_profile_id` → `seller_profiles`.`id` (`fk_seller_docs_seller`), `application_id` → `seller_verification_applications`.`id` (`fk_seller_docs_app`), `uploaded_by_user_id` → `users`.`id` (`fk_seller_docs_uploaded_by`), `reviewed_by_user_id` → `users`.`id` (`fk_seller_docs_reviewed_by`)

## 14. `seller_verification_history`
*Defined in:* `sql/02_sellers_and_verification.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `application_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `seller_profile_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `from_status` | `VARCHAR(40) NULL` |
| `to_status` | `VARCHAR(40) NOT NULL` |
| `actor_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `reason` | `VARCHAR(1000) NULL` |
| `correlation_id` | `VARCHAR(100) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `application_id` → `seller_verification_applications`.`id` (`fk_svh_app`), `seller_profile_id` → `seller_profiles`.`id` (`fk_svh_seller`), `actor_user_id` → `users`.`id` (`fk_svh_actor`)

## 15. `gi_reference_records`
*Defined in:* `sql/02_sellers_and_verification.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `gi_registration_number` | `VARCHAR(100) NOT NULL` |
| `gi_name` | `VARCHAR(255) NOT NULL` |
| `craft_class` | `VARCHAR(120) NULL` |
| `authorized_geographic_area` | `VARCHAR(255) NOT NULL` |
| `state_region` | `VARCHAR(120) NOT NULL` |
| `source_authority` | `VARCHAR(255) NOT NULL` |
| `source_url` | `VARCHAR(512) NULL` |
| `dataset_version` | `VARCHAR(64) NOT NULL` |
| `reference_payload` | `JSON NULL` |
| `valid_from` | `DATE NULL` |
| `valid_until` | `DATE NULL` |
| `is_active` | `TINYINT(1) NOT NULL DEFAULT 1` |
| `imported_by_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `imported_by_user_id` → `users`.`id` (`fk_gi_ref_imported_by`)

## 16. `categories`
*Defined in:* `sql/03_catalog_and_gi_products.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `parent_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `code` | `VARCHAR(64) NOT NULL` |
| `name` | `VARCHAR(120) NOT NULL` |
| `slug` | `VARCHAR(140) NOT NULL` |
| `description` | `TEXT NULL` |
| `is_gi_eligible_category` | `TINYINT(1) NOT NULL DEFAULT 0` |
| `display_order` | `INT NOT NULL DEFAULT 0` |
| `is_active` | `TINYINT(1) NOT NULL DEFAULT 1` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `parent_id` → `categories`.`id` (`fk_categories_parent`)

## 17. `brands`
*Defined in:* `sql/03_catalog_and_gi_products.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `name` | `VARCHAR(140) NOT NULL` |
| `slug` | `VARCHAR(160) NOT NULL` |
| `description` | `TEXT NULL` |
| `origin_region` | `VARCHAR(120) NULL` |
| `logo_storage_key` | `VARCHAR(512) NULL` |
| `is_active` | `TINYINT(1) NOT NULL DEFAULT 1` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

## 18. `products`
*Defined in:* `sql/03_catalog_and_gi_products.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `category_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `brand_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `created_by_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `sku_root` | `VARCHAR(80) NOT NULL` |
| `name` | `VARCHAR(220) NOT NULL` |
| `slug` | `VARCHAR(240) NOT NULL` |
| `short_description` | `VARCHAR(500) NULL` |
| `description` | `MEDIUMTEXT NULL` |
| `craft_technique` | `VARCHAR(120) NULL` |
| `origin_district` | `VARCHAR(100) NULL` |
| `material_composition` | `VARCHAR(255) NULL` |
| `gi_status` | `ENUM('NOT_APPLICABLE', 'UNVERIFIED', 'PENDING_REVIEW', 'GI_VERIFIED', 'GI_REJECTED', 'GI_REVOKED') NOT NULL DEFAULT 'UNVERIFIED'` |
| `approval_status` | `ENUM('DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'REJECTED', 'ARCHIVED') NOT NULL DEFAULT 'DRAFT'` |
| `attributes_json` | `JSON NULL` |
| `is_active` | `TINYINT(1) NOT NULL DEFAULT 1` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `category_id` → `categories`.`id` (`fk_products_category`), `brand_id` → `brands`.`id` (`fk_products_brand`), `created_by_user_id` → `users`.`id` (`fk_products_created_by`)

## 19. `product_variants`
*Defined in:* `sql/03_catalog_and_gi_products.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `product_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `variant_sku` | `VARCHAR(100) NOT NULL` |
| `variant_name` | `VARCHAR(160) NOT NULL` |
| `option_values_json` | `JSON NULL` |
| `unit_of_measure` | `VARCHAR(32) NOT NULL DEFAULT 'PCS'` |
| `weight_grams` | `DECIMAL(10,2) NULL` |
| `dimensions_cm_json` | `JSON NULL` |
| `base_mrp` | `DECIMAL(14,2) NOT NULL` |
| `currency_code` | `CHAR(3) NOT NULL DEFAULT 'INR'` |
| `is_active` | `TINYINT(1) NOT NULL DEFAULT 1` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `product_id` → `products`.`id` (`fk_product_variants_product`)

## 20. `product_images`
*Defined in:* `sql/03_catalog_and_gi_products.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `product_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `product_variant_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `storage_key` | `VARCHAR(512) NOT NULL` |
| `alt_text` | `VARCHAR(255) NULL` |
| `sort_order` | `INT NOT NULL DEFAULT 0` |
| `is_primary` | `TINYINT(1) NOT NULL DEFAULT 0` |
| `primary_image_guard` | `TINYINT(1) GENERATED ALWAYS AS (IF(`is_primary` = 1, 1, NULL)) STORED` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `product_id` → `products`.`id` (`fk_product_images_product`), `product_variant_id` → `product_variants`.`id` (`fk_product_images_variant`)

## 21. `product_gi_claims`
*Defined in:* `sql/03_catalog_and_gi_products.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `product_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `seller_profile_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `gi_reference_record_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `claimed_gi_code` | `VARCHAR(120) NOT NULL` |
| `claimed_origin_location` | `VARCHAR(200) NOT NULL` |
| `claim_statement` | `TEXT NULL` |
| `claim_status` | `ENUM('DRAFT', 'SUBMITTED', 'ASSESSED_NEEDS_REVIEW', 'APPROVED', 'REJECTED', 'REVOKED') NOT NULL DEFAULT 'DRAFT'` |
| `reviewed_by_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `reviewed_at` | `DATETIME(6) NULL` |
| `review_notes` | `TEXT NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `product_id` → `products`.`id` (`fk_pgc_product`), `seller_profile_id` → `seller_profiles`.`id` (`fk_pgc_seller`), `gi_reference_record_id` → `gi_reference_records`.`id` (`fk_pgc_reference`), `reviewed_by_user_id` → `users`.`id` (`fk_pgc_reviewed_by`)

## 22. `gi_claim_documents`
*Defined in:* `sql/03_catalog_and_gi_products.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `product_gi_claim_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `document_type` | `ENUM('GI_TAG_PHOTO', 'LAB_PURITY_REPORT', 'ORIGIN_CERTIFICATE', 'WORKSHOP_LOOM_PROOF', 'OTHER') NOT NULL` |
| `storage_key` | `VARCHAR(512) NOT NULL` |
| `original_filename` | `VARCHAR(255) NOT NULL` |
| `detected_mime_type` | `VARCHAR(120) NOT NULL` |
| `file_size_bytes` | `BIGINT UNSIGNED NOT NULL` |
| `sha256_hash` | `CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `scan_status` | `ENUM('PENDING_SCAN', 'CLEAN', 'INFECTED', 'SCAN_ERROR') NOT NULL DEFAULT 'PENDING_SCAN'` |
| `uploaded_by_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `product_gi_claim_id` → `product_gi_claims`.`id` (`fk_gcd_claim`), `uploaded_by_user_id` → `users`.`id` (`fk_gcd_uploaded_by`)

## 23. `gi_verification_runs`
*Defined in:* `sql/03_catalog_and_gi_products.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `target_type` | `ENUM('SELLER_APPLICATION', 'PRODUCT_GI_CLAIM') NOT NULL` |
| `seller_application_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `product_gi_claim_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `gi_reference_record_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `provider_name` | `VARCHAR(80) NOT NULL` |
| `model_version` | `VARCHAR(120) NOT NULL` |
| `prompt_version` | `VARCHAR(64) NOT NULL` |
| `dataset_version` | `VARCHAR(64) NOT NULL` |
| `input_sha256` | `CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `evidence_reference_ids` | `JSON NOT NULL` |
| `assessment_outcome` | `ENUM('LIKELY_MATCH', 'NEEDS_HUMAN_REVIEW', 'CONFLICT_DETECTED', 'INSUFFICIENT_EVIDENCE', 'ERROR') NOT NULL` |
| `confidence_score` | `DECIMAL(5,2) NULL` |
| `structured_findings_json` | `JSON NOT NULL` |
| `is_legal_proof` | `TINYINT(1) NOT NULL DEFAULT 0` |
| `is_mock_provider` | `TINYINT(1) NOT NULL DEFAULT 0` |
| `human_review_decision` | `ENUM('PENDING', 'APPROVED', 'REJECTED', 'ESCALATED') NOT NULL DEFAULT 'PENDING'` |
| `human_reviewed_by_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `human_reviewed_at` | `DATETIME(6) NULL` |
| `human_review_notes` | `TEXT NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `seller_application_id` → `seller_verification_applications`.`id` (`fk_gvr_seller_app`), `product_gi_claim_id` → `product_gi_claims`.`id` (`fk_gvr_product_claim`), `gi_reference_record_id` → `gi_reference_records`.`id` (`fk_gvr_reference`), `human_reviewed_by_user_id` → `users`.`id` (`fk_gvr_reviewer`)

## 24. `seller_product_listings`
*Defined in:* `sql/03_catalog_and_gi_products.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `seller_profile_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `product_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `product_variant_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `seller_sku` | `VARCHAR(100) NOT NULL` |
| `listing_title` | `VARCHAR(220) NOT NULL` |
| `selling_price` | `DECIMAL(14,2) NOT NULL` |
| `compare_at_mrp` | `DECIMAL(14,2) NULL` |
| `currency_code` | `CHAR(3) NOT NULL DEFAULT 'INR'` |
| `min_order_qty` | `INT UNSIGNED NOT NULL DEFAULT 1` |
| `max_order_qty` | `INT UNSIGNED NULL` |
| `dispatch_lead_days` | `SMALLINT UNSIGNED NOT NULL DEFAULT 3` |
| `listing_status` | `ENUM('DRAFT', 'PENDING_APPROVAL', 'ACTIVE', 'PAUSED', 'REJECTED', 'ARCHIVED') NOT NULL DEFAULT 'DRAFT'` |
| `published_at` | `DATETIME(6) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `seller_profile_id` → `seller_profiles`.`id` (`fk_spl_seller`), `product_id` → `products`.`id` (`fk_spl_product`), `product_variant_id` → `product_variants`.`id` (`fk_spl_variant`)

## 25. `supplier_profiles`
*Defined in:* `sql/04_suppliers_dealers_and_procurement.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `supplier_name` | `VARCHAR(180) NOT NULL` |
| `legal_entity_name` | `VARCHAR(200) NULL` |
| `supplier_type` | `ENUM('PRODUCER', 'ARTISAN_COOPERATIVE', 'WEAVER_CLUSTER', 'MANUFACTURER', 'AGGREGATOR') NOT NULL DEFAULT 'PRODUCER'` |
| `craft_cluster` | `VARCHAR(140) NULL` |
| `district` | `VARCHAR(100) NULL` |
| `state_province` | `VARCHAR(100) NOT NULL DEFAULT 'Jammu & Kashmir'` |
| `gstin` | `VARCHAR(20) NULL` |
| `profile_status` | `ENUM('DRAFT', 'ACTIVE', 'SUSPENDED', 'TERMINATED') NOT NULL DEFAULT 'DRAFT'` |
| `verification_status` | `ENUM('UNVERIFIED', 'SUBMITTED', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'REVOKED') NOT NULL DEFAULT 'UNVERIFIED'` |
| `monthly_capacity_units` | `INT UNSIGNED NULL` |
| `approved_at` | `DATETIME(6) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `user_id` → `users`.`id` (`fk_supplier_profiles_user`)

## 26. `supplier_verification_applications`
*Defined in:* `sql/04_suppliers_dealers_and_procurement.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `supplier_profile_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `application_number` | `VARCHAR(64) NOT NULL` |
| `application_status` | `ENUM('DRAFT', 'SUBMITTED', 'UNDER_REVIEW', 'NEEDS_MORE_INFO', 'APPROVED', 'REJECTED', 'WITHDRAWN') NOT NULL DEFAULT 'DRAFT'` |
| `submitted_metadata` | `JSON NULL` |
| `submitted_at` | `DATETIME(6) NULL` |
| `reviewed_by_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `reviewed_at` | `DATETIME(6) NULL` |
| `review_notes` | `TEXT NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `supplier_profile_id` → `supplier_profiles`.`id` (`fk_sup_va_supplier`), `reviewed_by_user_id` → `users`.`id` (`fk_sup_va_reviewed_by`)

## 27. `supplier_documents`
*Defined in:* `sql/04_suppliers_dealers_and_procurement.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `supplier_profile_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `application_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `document_type` | `ENUM('IDENTITY_PROOF', 'BUSINESS_REGISTRATION', 'TAX_CERTIFICATE', 'WORKSHOP_PROOF', 'BANK_PROOF', 'QUALITY_CERT', 'OTHER') NOT NULL` |
| `storage_key` | `VARCHAR(512) NOT NULL` |
| `original_filename` | `VARCHAR(255) NOT NULL` |
| `detected_mime_type` | `VARCHAR(120) NOT NULL` |
| `file_size_bytes` | `BIGINT UNSIGNED NOT NULL` |
| `sha256_hash` | `CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `scan_status` | `ENUM('PENDING_SCAN', 'CLEAN', 'INFECTED', 'SCAN_ERROR') NOT NULL DEFAULT 'PENDING_SCAN'` |
| `verification_status` | `ENUM('PENDING', 'ACCEPTED', 'REJECTED') NOT NULL DEFAULT 'PENDING'` |
| `uploaded_by_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `supplier_profile_id` → `supplier_profiles`.`id` (`fk_sup_docs_supplier`), `application_id` → `supplier_verification_applications`.`id` (`fk_sup_docs_app`), `uploaded_by_user_id` → `users`.`id` (`fk_sup_docs_uploaded_by`)

## 28. `supplier_verification_history`
*Defined in:* `sql/04_suppliers_dealers_and_procurement.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `application_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `supplier_profile_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `from_status` | `VARCHAR(40) NULL` |
| `to_status` | `VARCHAR(40) NOT NULL` |
| `actor_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `reason` | `VARCHAR(1000) NULL` |
| `correlation_id` | `VARCHAR(100) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `application_id` → `supplier_verification_applications`.`id` (`fk_sup_vh_app`), `supplier_profile_id` → `supplier_profiles`.`id` (`fk_sup_vh_supplier`), `actor_user_id` → `users`.`id` (`fk_sup_vh_actor`)

## 29. `supplier_lots`
*Defined in:* `sql/04_suppliers_dealers_and_procurement.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `lot_number` | `VARCHAR(64) NOT NULL` |
| `supplier_profile_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `category_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `product_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `product_variant_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `lot_title` | `VARCHAR(220) NOT NULL` |
| `lot_description` | `TEXT NULL` |
| `offered_quantity` | `DECIMAL(14,3) NOT NULL` |
| `remaining_quantity` | `DECIMAL(14,3) NOT NULL` |
| `unit_of_measure` | `VARCHAR(32) NOT NULL DEFAULT 'PCS'` |
| `expected_unit_price` | `DECIMAL(14,2) NOT NULL` |
| `currency_code` | `CHAR(3) NOT NULL DEFAULT 'INR'` |
| `is_gi_claimed` | `TINYINT(1) NOT NULL DEFAULT 0` |
| `available_from_date` | `DATE NOT NULL` |
| `available_until_date` | `DATE NULL` |
| `origin_location` | `VARCHAR(160) NULL` |
| `lot_status` | `ENUM('DRAFT', 'SUBMITTED', 'UNDER_REVIEW', 'APPROVED_FOR_MATCHING', 'ASSIGNED', 'PARTIALLY_PROCURED', 'PROCURED', 'REJECTED', 'EXPIRED', 'CANCELLED') NOT NULL DEFAULT 'DRAFT'` |
| `reviewed_by_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `reviewed_at` | `DATETIME(6) NULL` |
| `review_notes` | `TEXT NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `supplier_profile_id` → `supplier_profiles`.`id` (`fk_sl_supplier`), `category_id` → `categories`.`id` (`fk_sl_category`), `product_id` → `products`.`id` (`fk_sl_product`), `product_variant_id` → `product_variants`.`id` (`fk_sl_variant`), `reviewed_by_user_id` → `users`.`id` (`fk_sl_reviewed_by`)

## 30. `supplier_lot_documents`
*Defined in:* `sql/04_suppliers_dealers_and_procurement.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `supplier_lot_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `document_type` | `ENUM('LOT_PHOTO', 'QUALITY_REPORT', 'GI_CERTIFICATE', 'PACKING_LIST', 'OTHER') NOT NULL` |
| `storage_key` | `VARCHAR(512) NOT NULL` |
| `original_filename` | `VARCHAR(255) NOT NULL` |
| `detected_mime_type` | `VARCHAR(120) NOT NULL` |
| `file_size_bytes` | `BIGINT UNSIGNED NOT NULL` |
| `sha256_hash` | `CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `scan_status` | `ENUM('PENDING_SCAN', 'CLEAN', 'INFECTED', 'SCAN_ERROR') NOT NULL DEFAULT 'PENDING_SCAN'` |
| `uploaded_by_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `supplier_lot_id` → `supplier_lots`.`id` (`fk_sld_lot`), `uploaded_by_user_id` → `users`.`id` (`fk_sld_uploaded_by`)

## 31. `supplier_lot_status_history`
*Defined in:* `sql/04_suppliers_dealers_and_procurement.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `supplier_lot_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `from_status` | `VARCHAR(40) NULL` |
| `to_status` | `VARCHAR(40) NOT NULL` |
| `actor_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `reason` | `VARCHAR(1000) NULL` |
| `correlation_id` | `VARCHAR(100) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `supplier_lot_id` → `supplier_lots`.`id` (`fk_slsh_lot`), `actor_user_id` → `users`.`id` (`fk_slsh_actor`)

## 32. `dealer_profiles`
*Defined in:* `sql/04_suppliers_dealers_and_procurement.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `dealership_name` | `VARCHAR(180) NOT NULL` |
| `dealership_slug` | `VARCHAR(200) NOT NULL` |
| `legal_entity_name` | `VARCHAR(200) NULL` |
| `gstin` | `VARCHAR(20) NULL` |
| `city` | `VARCHAR(100) NOT NULL` |
| `state_province` | `VARCHAR(100) NOT NULL` |
| `country_code` | `CHAR(2) NOT NULL DEFAULT 'IN'` |
| `monthly_procurement_capacity` | `DECIMAL(14,2) NULL` |
| `currency_code` | `CHAR(3) NOT NULL DEFAULT 'INR'` |
| `reliability_rating` | `DECIMAL(3,2) NOT NULL DEFAULT 0.00` |
| `profile_status` | `ENUM('DRAFT', 'ACTIVE', 'SUSPENDED', 'TERMINATED') NOT NULL DEFAULT 'DRAFT'` |
| `verification_status` | `ENUM('UNVERIFIED', 'SUBMITTED', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'REVOKED') NOT NULL DEFAULT 'UNVERIFIED'` |
| `approved_at` | `DATETIME(6) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `user_id` → `users`.`id` (`fk_dealer_profiles_user`)

## 33. `dealer_documents`
*Defined in:* `sql/04_suppliers_dealers_and_procurement.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `dealer_profile_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `document_type` | `ENUM('BUSINESS_REGISTRATION', 'GST_CERTIFICATE', 'WAREHOUSE_LEASE', 'BANK_PROOF', 'IDENTITY_PROOF', 'OTHER') NOT NULL` |
| `storage_key` | `VARCHAR(512) NOT NULL` |
| `original_filename` | `VARCHAR(255) NOT NULL` |
| `detected_mime_type` | `VARCHAR(120) NOT NULL` |
| `file_size_bytes` | `BIGINT UNSIGNED NOT NULL` |
| `sha256_hash` | `CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `scan_status` | `ENUM('PENDING_SCAN', 'CLEAN', 'INFECTED', 'SCAN_ERROR') NOT NULL DEFAULT 'PENDING_SCAN'` |
| `verification_status` | `ENUM('PENDING', 'ACCEPTED', 'REJECTED') NOT NULL DEFAULT 'PENDING'` |
| `uploaded_by_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `dealer_profile_id` → `dealer_profiles`.`id` (`fk_dealer_docs_dealer`), `uploaded_by_user_id` → `users`.`id` (`fk_dealer_docs_uploaded_by`)

## 34. `dealer_categories`
*Defined in:* `sql/04_suppliers_dealers_and_procurement.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `dealer_profile_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `category_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `is_approved` | `TINYINT(1) NOT NULL DEFAULT 1` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `dealer_profile_id` → `dealer_profiles`.`id` (`fk_dc_dealer`), `category_id` → `categories`.`id` (`fk_dc_category`)

## 35. `warehouses`
*Defined in:* `sql/04_suppliers_dealers_and_procurement.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `warehouse_code` | `VARCHAR(64) NOT NULL` |
| `name` | `VARCHAR(160) NOT NULL` |
| `owner_type` | `ENUM('SELLER', 'DEALER', 'PLATFORM') NOT NULL` |
| `seller_profile_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `dealer_profile_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `address_line1` | `VARCHAR(255) NOT NULL` |
| `address_line2` | `VARCHAR(255) NULL` |
| `city` | `VARCHAR(100) NOT NULL` |
| `state_province` | `VARCHAR(100) NOT NULL` |
| `postal_code` | `VARCHAR(20) NOT NULL` |
| `country_code` | `CHAR(2) NOT NULL DEFAULT 'IN'` |
| `is_active` | `TINYINT(1) NOT NULL DEFAULT 1` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `seller_profile_id` → `seller_profiles`.`id` (`fk_wh_seller`), `dealer_profile_id` → `dealer_profiles`.`id` (`fk_wh_dealer`)

## 36. `dealer_assignment_recommendations`
*Defined in:* `sql/04_suppliers_dealers_and_procurement.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `supplier_lot_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `dealer_profile_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `rank_position` | `SMALLINT UNSIGNED NOT NULL` |
| `match_score` | `DECIMAL(5,2) NOT NULL` |
| `scoring_factors_json` | `JSON NULL` |
| `generated_by_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `supplier_lot_id` → `supplier_lots`.`id` (`fk_dar_lot`), `dealer_profile_id` → `dealer_profiles`.`id` (`fk_dar_dealer`), `generated_by_user_id` → `users`.`id` (`fk_dar_generated_by`)

## 37. `dealer_assignments`
*Defined in:* `sql/04_suppliers_dealers_and_procurement.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `supplier_lot_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `dealer_profile_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `recommendation_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `attempt_number` | `INT UNSIGNED NOT NULL DEFAULT 1` |
| `assigned_quantity` | `DECIMAL(14,3) NOT NULL` |
| `proposed_unit_price` | `DECIMAL(14,2) NULL` |
| `currency_code` | `CHAR(3) NOT NULL DEFAULT 'INR'` |
| `assignment_status` | `ENUM('INVITED', 'ACCEPTED', 'DECLINED', 'TERMS_AGREED', 'EXPIRED', 'CANCELLED', 'PO_CREATED') NOT NULL DEFAULT 'INVITED'` |
| `active_invitation_guard` | `TINYINT(1) GENERATED ALWAYS AS (IF(`assignment_status` IN ('INVITED', 'ACCEPTED', 'TERMS_AGREED'), 1, NULL)) STORED` |
| `assigned_by_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `expires_at` | `DATETIME(6) NULL` |
| `responded_at` | `DATETIME(6) NULL` |
| `response_notes` | `TEXT NULL` |
| `agreed_terms_json` | `JSON NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `supplier_lot_id` → `supplier_lots`.`id` (`fk_da_lot`), `dealer_profile_id` → `dealer_profiles`.`id` (`fk_da_dealer`), `recommendation_id` → `dealer_assignment_recommendations`.`id` (`fk_da_recommendation`), `assigned_by_user_id` → `users`.`id` (`fk_da_assigned_by`)

## 38. `dealer_assignment_history`
*Defined in:* `sql/04_suppliers_dealers_and_procurement.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `dealer_assignment_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `from_status` | `VARCHAR(40) NULL` |
| `to_status` | `VARCHAR(40) NOT NULL` |
| `actor_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `notes` | `VARCHAR(1000) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `dealer_assignment_id` → `dealer_assignments`.`id` (`fk_dah_assignment`), `actor_user_id` → `users`.`id` (`fk_dah_actor`)

## 39. `supplier_purchase_orders`
*Defined in:* `sql/04_suppliers_dealers_and_procurement.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `po_number` | `VARCHAR(64) NOT NULL` |
| `supplier_lot_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `dealer_assignment_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `supplier_profile_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `dealer_profile_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `destination_warehouse_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `currency_code` | `CHAR(3) NOT NULL DEFAULT 'INR'` |
| `subtotal_amount` | `DECIMAL(14,2) NOT NULL` |
| `tax_amount` | `DECIMAL(14,2) NOT NULL DEFAULT 0.00` |
| `freight_amount` | `DECIMAL(14,2) NOT NULL DEFAULT 0.00` |
| `total_amount` | `DECIMAL(14,2) NOT NULL` |
| `payment_terms` | `VARCHAR(160) NULL` |
| `payment_due_date` | `DATE NULL` |
| `settlement_status` | `ENUM('UNPAID', 'PARTIALLY_SETTLED', 'SETTLED', 'DISPUTED') NOT NULL DEFAULT 'UNPAID'` |
| `po_status` | `ENUM('DRAFT', 'ISSUED', 'CONFIRMED_BY_SUPPLIER', 'IN_TRANSIT', 'PARTIALLY_RECEIVED', 'RECEIVED', 'INSPECTED', 'CLOSED', 'CANCELLED') NOT NULL DEFAULT 'DRAFT'` |
| `expected_delivery_date` | `DATE NULL` |
| `created_by_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `supplier_lot_id` → `supplier_lots`.`id` (`fk_spo_lot`), `dealer_assignment_id` → `dealer_assignments`.`id` (`fk_spo_assignment`), `supplier_profile_id` → `supplier_profiles`.`id` (`fk_spo_supplier`), `dealer_profile_id` → `dealer_profiles`.`id` (`fk_spo_dealer`), `destination_warehouse_id` → `warehouses`.`id` (`fk_spo_warehouse`), `created_by_user_id` → `users`.`id` (`fk_spo_created_by`)

## 40. `supplier_purchase_order_status_history`
*Defined in:* `sql/04_suppliers_dealers_and_procurement.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `supplier_purchase_order_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `from_status` | `VARCHAR(40) NULL` |
| `to_status` | `VARCHAR(40) NOT NULL` |
| `actor_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `reason` | `VARCHAR(1000) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `supplier_purchase_order_id` → `supplier_purchase_orders`.`id` (`fk_sposh_po`), `actor_user_id` → `users`.`id` (`fk_sposh_actor`)

## 41. `supplier_purchase_order_items`
*Defined in:* `sql/04_suppliers_dealers_and_procurement.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `supplier_purchase_order_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `product_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `product_variant_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `item_title_snapshot` | `VARCHAR(220) NOT NULL` |
| `sku_snapshot` | `VARCHAR(100) NOT NULL` |
| `ordered_quantity` | `DECIMAL(14,3) NOT NULL` |
| `unit_of_measure` | `VARCHAR(32) NOT NULL DEFAULT 'PCS'` |
| `unit_cost` | `DECIMAL(14,2) NOT NULL` |
| `tax_amount` | `DECIMAL(14,2) NOT NULL DEFAULT 0.00` |
| `line_total` | `DECIMAL(14,2) NOT NULL` |
| `currency_code` | `CHAR(3) NOT NULL DEFAULT 'INR'` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `supplier_purchase_order_id` → `supplier_purchase_orders`.`id` (`fk_spoi_po`), `product_id` → `products`.`id` (`fk_spoi_product`), `product_variant_id` → `product_variants`.`id` (`fk_spoi_variant`)

## 42. `goods_receipts`
*Defined in:* `sql/04_suppliers_dealers_and_procurement.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `receipt_number` | `VARCHAR(64) NOT NULL` |
| `supplier_purchase_order_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `warehouse_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `dealer_profile_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `received_by_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `received_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `receipt_status` | `ENUM('RECEIVED_PENDING_INSPECTION', 'INSPECTED', 'POSTED_TO_INVENTORY', 'REJECTED') NOT NULL DEFAULT 'RECEIVED_PENDING_INSPECTION'` |
| `carrier_reference` | `VARCHAR(120) NULL` |
| `notes` | `TEXT NULL` |
| `posted_to_inventory_at` | `DATETIME(6) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `supplier_purchase_order_id` → `supplier_purchase_orders`.`id` (`fk_gr_po`), `warehouse_id` → `warehouses`.`id` (`fk_gr_warehouse`), `dealer_profile_id` → `dealer_profiles`.`id` (`fk_gr_dealer`), `received_by_user_id` → `users`.`id` (`fk_gr_received_by`)

## 43. `goods_receipt_items`
*Defined in:* `sql/04_suppliers_dealers_and_procurement.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `goods_receipt_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `supplier_po_item_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `product_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `product_variant_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `received_quantity` | `DECIMAL(14,3) NOT NULL` |
| `accepted_quantity` | `DECIMAL(14,3) NOT NULL DEFAULT 0.000` |
| `rejected_quantity` | `DECIMAL(14,3) NOT NULL DEFAULT 0.000` |
| `damaged_quantity` | `DECIMAL(14,3) NOT NULL DEFAULT 0.000` |
| `inventory_posted` | `TINYINT(1) NOT NULL DEFAULT 0` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |
| `received_quantity` | `>= 0.000` |

**Foreign Keys:** `goods_receipt_id` → `goods_receipts`.`id` (`fk_gri_receipt`), `supplier_po_item_id` → `supplier_purchase_order_items`.`id` (`fk_gri_po_item`), `product_id` → `products`.`id` (`fk_gri_product`), `product_variant_id` → `product_variants`.`id` (`fk_gri_variant`)

## 44. `quality_inspections`
*Defined in:* `sql/04_suppliers_dealers_and_procurement.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `goods_receipt_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `goods_receipt_item_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `inspector_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `inspection_outcome` | `ENUM('PASSED', 'PARTIALLY_PASSED', 'FAILED') NOT NULL` |
| `checklist_results_json` | `JSON NULL` |
| `notes` | `TEXT NULL` |
| `inspected_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `goods_receipt_id` → `goods_receipts`.`id` (`fk_qi_receipt`), `goods_receipt_item_id` → `goods_receipt_items`.`id` (`fk_qi_receipt_item`), `inspector_user_id` → `users`.`id` (`fk_qi_inspector`)

## 45. `warehouse_stock`
*Defined in:* `sql/05_inventory_and_retail.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `warehouse_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `product_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `product_variant_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `owner_type` | `ENUM('SELLER', 'DEALER', 'PLATFORM') NOT NULL` |
| `seller_profile_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `dealer_profile_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `seller_listing_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `available_quantity` | `DECIMAL(14,3) NOT NULL DEFAULT 0.000` |
| `reserved_quantity` | `DECIMAL(14,3) NOT NULL DEFAULT 0.000` |
| `damaged_quantity` | `DECIMAL(14,3) NOT NULL DEFAULT 0.000` |
| `reorder_threshold` | `DECIMAL(14,3) NOT NULL DEFAULT 0.000` |
| `version` | `BIGINT UNSIGNED NOT NULL DEFAULT 1` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `warehouse_id` → `warehouses`.`id` (`fk_ws_warehouse`), `product_id` → `products`.`id` (`fk_ws_product`), `product_variant_id` → `product_variants`.`id` (`fk_ws_variant`), `seller_profile_id` → `seller_profiles`.`id` (`fk_ws_seller`), `dealer_profile_id` → `dealer_profiles`.`id` (`fk_ws_dealer`), `seller_listing_id` → `seller_product_listings`.`id` (`fk_ws_seller_listing`)

## 46. `inventory_transactions`
*Defined in:* `sql/05_inventory_and_retail.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `warehouse_stock_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `warehouse_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `product_variant_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `goods_receipt_item_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `movement_type` | `ENUM('OPENING_BALANCE', 'GOODS_RECEIPT_ACCEPT', 'GOODS_RECEIPT_DAMAGED', 'RESERVE', 'RELEASE_RESERVATION', 'CONSUME_RESERVATION', 'RETURN_RESTOCK', 'DAMAGE_WRITE_OFF', 'MANUAL_ADJUSTMENT') NOT NULL` |
| `quantity_delta` | `DECIMAL(14,3) NOT NULL` |
| `available_after` | `DECIMAL(14,3) NOT NULL` |
| `reserved_after` | `DECIMAL(14,3) NOT NULL` |
| `damaged_after` | `DECIMAL(14,3) NOT NULL` |
| `reference_type` | `VARCHAR(64) NULL` |
| `reference_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `goods_receipt_post_guard` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin GENERATED ALWAYS AS (` |
| `actor_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `reason` | `VARCHAR(500) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `warehouse_stock_id` → `warehouse_stock`.`id` (`fk_inv_tx_stock`), `warehouse_id` → `warehouses`.`id` (`fk_inv_tx_warehouse`), `product_variant_id` → `product_variants`.`id` (`fk_inv_tx_variant`), `goods_receipt_item_id` → `goods_receipt_items`.`id` (`fk_inv_tx_gr_item`), `actor_user_id` → `users`.`id` (`fk_inv_tx_actor`)

## 47. `carts`
*Defined in:* `sql/05_inventory_and_retail.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `cart_status` | `ENUM('ACTIVE', 'CONVERTED', 'ABANDONED') NOT NULL DEFAULT 'ACTIVE'` |
| `active_cart_guard` | `TINYINT(1) GENERATED ALWAYS AS (IF(`cart_status` = 'ACTIVE', 1, NULL)) STORED` |
| `currency_code` | `CHAR(3) NOT NULL DEFAULT 'INR'` |
| `applied_coupon_code` | `VARCHAR(64) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `user_id` → `users`.`id` (`fk_carts_user`)

## 48. `cart_items`
*Defined in:* `sql/05_inventory_and_retail.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `cart_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `seller_listing_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `product_variant_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `quantity` | `INT UNSIGNED NOT NULL DEFAULT 1` |
| `unit_price_snapshot` | `DECIMAL(14,2) NOT NULL` |
| `currency_code` | `CHAR(3) NOT NULL DEFAULT 'INR'` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `cart_id` → `carts`.`id` (`fk_ci_cart`), `seller_listing_id` → `seller_product_listings`.`id` (`fk_ci_listing`), `product_variant_id` → `product_variants`.`id` (`fk_ci_variant`)

## 49. `wishlists`
*Defined in:* `sql/05_inventory_and_retail.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `name` | `VARCHAR(100) NOT NULL DEFAULT 'Saved Crafts'` |
| `is_default` | `TINYINT(1) NOT NULL DEFAULT 1` |
| `default_wishlist_guard` | `TINYINT(1) GENERATED ALWAYS AS (IF(`is_default` = 1, 1, NULL)) STORED` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `user_id` → `users`.`id` (`fk_wishlists_user`)

## 50. `wishlist_items`
*Defined in:* `sql/05_inventory_and_retail.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `wishlist_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `product_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `product_variant_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `seller_listing_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `wishlist_id` → `wishlists`.`id` (`fk_wi_wishlist`), `product_id` → `products`.`id` (`fk_wi_product`), `product_variant_id` → `product_variants`.`id` (`fk_wi_variant`), `seller_listing_id` → `seller_product_listings`.`id` (`fk_wi_listing`)

## 51. `retail_orders`
*Defined in:* `sql/05_inventory_and_retail.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `order_number` | `VARCHAR(64) NOT NULL` |
| `customer_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `shipping_address_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `shipping_address_snapshot_json` | `JSON NOT NULL` |
| `currency_code` | `CHAR(3) NOT NULL DEFAULT 'INR'` |
| `subtotal_amount` | `DECIMAL(14,2) NOT NULL` |
| `discount_amount` | `DECIMAL(14,2) NOT NULL DEFAULT 0.00` |
| `tax_amount` | `DECIMAL(14,2) NOT NULL DEFAULT 0.00` |
| `shipping_fee` | `DECIMAL(14,2) NOT NULL DEFAULT 0.00` |
| `total_amount` | `DECIMAL(14,2) NOT NULL` |
| `coupon_code_snapshot` | `VARCHAR(64) NULL` |
| `payment_method` | `ENUM('RAZORPAY_STANDARD', 'COD') NOT NULL DEFAULT 'RAZORPAY_STANDARD'` |
| `payment_status` | `ENUM('PENDING', 'AUTHORIZED', 'PAID', 'FAILED', 'PARTIALLY_REFUNDED', 'REFUNDED', 'COD_PENDING', 'COD_COLLECTED') NOT NULL DEFAULT 'PENDING'` |
| `fulfilment_status` | `ENUM('PENDING_PAYMENT', 'CONFIRMED', 'PROCESSING', 'PARTIALLY_SHIPPED', 'SHIPPED', 'DELIVERED', 'CANCELLED', 'RETURNED') NOT NULL DEFAULT 'PENDING_PAYMENT'` |
| `placed_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `confirmed_at` | `DATETIME(6) NULL` |
| `cancelled_at` | `DATETIME(6) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `customer_user_id` → `users`.`id` (`fk_ro_customer`), `shipping_address_id` → `user_addresses`.`id` (`fk_ro_shipping_addr`)

## 52. `seller_fulfilment_groups`
*Defined in:* `sql/05_inventory_and_retail.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `fulfilment_number` | `VARCHAR(64) NOT NULL` |
| `retail_order_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `seller_profile_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `warehouse_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `currency_code` | `CHAR(3) NOT NULL DEFAULT 'INR'` |
| `subtotal_amount` | `DECIMAL(14,2) NOT NULL` |
| `discount_amount` | `DECIMAL(14,2) NOT NULL DEFAULT 0.00` |
| `tax_amount` | `DECIMAL(14,2) NOT NULL DEFAULT 0.00` |
| `shipping_fee` | `DECIMAL(14,2) NOT NULL DEFAULT 0.00` |
| `group_total_amount` | `DECIMAL(14,2) NOT NULL` |
| `fulfilment_status` | `ENUM('PENDING_PAYMENT', 'CONFIRMED', 'PACKED', 'SHIPPED', 'OUT_FOR_DELIVERY', 'DELIVERED', 'CANCELLED', 'RETURNED') NOT NULL DEFAULT 'PENDING_PAYMENT'` |
| `seller_notes` | `VARCHAR(500) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `retail_order_id` → `retail_orders`.`id` (`fk_sfg_order`), `seller_profile_id` → `seller_profiles`.`id` (`fk_sfg_seller`), `warehouse_id` → `warehouses`.`id` (`fk_sfg_warehouse`)

## 53. `retail_order_items`
*Defined in:* `sql/05_inventory_and_retail.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `retail_order_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `seller_fulfilment_group_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `seller_listing_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `product_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `product_variant_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `product_name_snapshot` | `VARCHAR(220) NOT NULL` |
| `sku_snapshot` | `VARCHAR(100) NOT NULL` |
| `gi_status_snapshot` | `VARCHAR(40) NOT NULL` |
| `quantity` | `INT UNSIGNED NOT NULL` |
| `unit_price_snapshot` | `DECIMAL(14,2) NOT NULL` |
| `discount_amount_snapshot` | `DECIMAL(14,2) NOT NULL DEFAULT 0.00` |
| `tax_amount_snapshot` | `DECIMAL(14,2) NOT NULL DEFAULT 0.00` |
| `line_total_amount` | `DECIMAL(14,2) NOT NULL` |
| `currency_code` | `CHAR(3) NOT NULL DEFAULT 'INR'` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `retail_order_id` → `retail_orders`.`id` (`fk_roi_order`), `seller_fulfilment_group_id` → `seller_fulfilment_groups`.`id` (`fk_roi_group`), `seller_listing_id` → `seller_product_listings`.`id` (`fk_roi_listing`), `product_id` → `products`.`id` (`fk_roi_product`), `product_variant_id` → `product_variants`.`id` (`fk_roi_variant`)

## 54. `retail_order_status_history`
*Defined in:* `sql/05_inventory_and_retail.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `retail_order_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `seller_fulfilment_group_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `status_scope` | `ENUM('ORDER_FULFILMENT', 'SELLER_FULFILMENT', 'PAYMENT_SYNC') NOT NULL DEFAULT 'ORDER_FULFILMENT'` |
| `from_status` | `VARCHAR(40) NULL` |
| `to_status` | `VARCHAR(40) NOT NULL` |
| `actor_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `reason` | `VARCHAR(1000) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `retail_order_id` → `retail_orders`.`id` (`fk_rosh_order`), `seller_fulfilment_group_id` → `seller_fulfilment_groups`.`id` (`fk_rosh_group`), `actor_user_id` → `users`.`id` (`fk_rosh_actor`)

## 55. `dealer_wholesale_listings`
*Defined in:* `sql/06_wholesale_marketplace.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `dealer_profile_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `product_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `product_variant_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `warehouse_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `warehouse_stock_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `dealer_sku` | `VARCHAR(100) NOT NULL` |
| `listing_title` | `VARCHAR(220) NOT NULL` |
| `base_unit_price` | `DECIMAL(14,2) NOT NULL` |
| `currency_code` | `CHAR(3) NOT NULL DEFAULT 'INR'` |
| `minimum_order_quantity` | `DECIMAL(14,3) NOT NULL` |
| `order_quantity_increment` | `DECIMAL(14,3) NOT NULL DEFAULT 1.000` |
| `lead_time_days` | `SMALLINT UNSIGNED NOT NULL DEFAULT 14` |
| `listing_status` | `ENUM('DRAFT', 'PENDING_APPROVAL', 'ACTIVE', 'PAUSED', 'REJECTED', 'ARCHIVED') NOT NULL DEFAULT 'DRAFT'` |
| `published_at` | `DATETIME(6) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `dealer_profile_id` → `dealer_profiles`.`id` (`fk_dwl_dealer`), `product_id` → `products`.`id` (`fk_dwl_product`), `product_variant_id` → `product_variants`.`id` (`fk_dwl_variant`), `warehouse_id` → `warehouses`.`id` (`fk_dwl_warehouse`), `warehouse_stock_id` → `warehouse_stock`.`id` (`fk_dwl_stock`)

## 56. `wholesale_buyer_profiles`
*Defined in:* `sql/06_wholesale_marketplace.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `company_name` | `VARCHAR(200) NOT NULL` |
| `buyer_segment` | `ENUM('RETAIL_BOUTIQUE', 'HOSPITALITY', 'INTERIOR_STUDIO', 'EXPORTER', 'CORPORATE_GIFTING', 'OTHER') NOT NULL DEFAULT 'RETAIL_BOUTIQUE'` |
| `gstin` | `VARCHAR(20) NULL` |
| `business_city` | `VARCHAR(100) NOT NULL` |
| `business_state` | `VARCHAR(100) NOT NULL` |
| `country_code` | `CHAR(2) NOT NULL DEFAULT 'IN'` |
| `profile_status` | `ENUM('DRAFT', 'ACTIVE', 'SUSPENDED', 'TERMINATED') NOT NULL DEFAULT 'DRAFT'` |
| `verification_status` | `ENUM('UNVERIFIED', 'SUBMITTED', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'REVOKED') NOT NULL DEFAULT 'UNVERIFIED'` |
| `approved_at` | `DATETIME(6) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `user_id` → `users`.`id` (`fk_wbp_user`)

## 57. `wholesale_price_tiers`
*Defined in:* `sql/06_wholesale_marketplace.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `dealer_wholesale_listing_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `min_quantity` | `DECIMAL(14,3) NOT NULL` |
| `max_quantity` | `DECIMAL(14,3) NULL` |
| `unit_price` | `DECIMAL(14,2) NOT NULL` |
| `currency_code` | `CHAR(3) NOT NULL DEFAULT 'INR'` |
| `is_active` | `TINYINT(1) NOT NULL DEFAULT 1` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `dealer_wholesale_listing_id` → `dealer_wholesale_listings`.`id` (`fk_wpt_listing`)

## 58. `wholesale_carts`
*Defined in:* `sql/06_wholesale_marketplace.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `wholesale_buyer_profile_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `cart_status` | `ENUM('ACTIVE', 'CONVERTED', 'ABANDONED') NOT NULL DEFAULT 'ACTIVE'` |
| `active_cart_guard` | `TINYINT(1) GENERATED ALWAYS AS (IF(`cart_status` = 'ACTIVE', 1, NULL)) STORED` |
| `currency_code` | `CHAR(3) NOT NULL DEFAULT 'INR'` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `wholesale_buyer_profile_id` → `wholesale_buyer_profiles`.`id` (`fk_wc_buyer`), `user_id` → `users`.`id` (`fk_wc_user`)

## 59. `wholesale_cart_items`
*Defined in:* `sql/06_wholesale_marketplace.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `wholesale_cart_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `dealer_wholesale_listing_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `product_variant_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `quantity` | `DECIMAL(14,3) NOT NULL` |
| `tier_unit_price_snapshot` | `DECIMAL(14,2) NOT NULL` |
| `currency_code` | `CHAR(3) NOT NULL DEFAULT 'INR'` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `wholesale_cart_id` → `wholesale_carts`.`id` (`fk_wci_cart`), `dealer_wholesale_listing_id` → `dealer_wholesale_listings`.`id` (`fk_wci_listing`), `product_variant_id` → `product_variants`.`id` (`fk_wci_variant`)

## 60. `wholesale_rfqs`
*Defined in:* `sql/06_wholesale_marketplace.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `rfq_number` | `VARCHAR(64) NOT NULL` |
| `wholesale_buyer_profile_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `buyer_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `delivery_address_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `title` | `VARCHAR(220) NOT NULL` |
| `requirements_notes` | `TEXT NULL` |
| `target_delivery_date` | `DATE NULL` |
| `currency_code` | `CHAR(3) NOT NULL DEFAULT 'INR'` |
| `rfq_status` | `ENUM('DRAFT', 'OPEN', 'QUOTES_RECEIVED', 'QUOTE_ACCEPTED', 'EXPIRED', 'CANCELLED', 'CLOSED') NOT NULL DEFAULT 'DRAFT'` |
| `expires_at` | `DATETIME(6) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `wholesale_buyer_profile_id` → `wholesale_buyer_profiles`.`id` (`fk_wrfq_buyer`), `buyer_user_id` → `users`.`id` (`fk_wrfq_user`), `delivery_address_id` → `user_addresses`.`id` (`fk_wrfq_delivery_addr`)

## 61. `wholesale_rfq_items`
*Defined in:* `sql/06_wholesale_marketplace.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `wholesale_rfq_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `category_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `product_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `product_variant_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `item_description` | `VARCHAR(300) NOT NULL` |
| `requested_quantity` | `DECIMAL(14,3) NOT NULL` |
| `unit_of_measure` | `VARCHAR(32) NOT NULL DEFAULT 'PCS'` |
| `target_unit_price` | `DECIMAL(14,2) NULL` |
| `requires_gi_verified` | `TINYINT(1) NOT NULL DEFAULT 0` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `wholesale_rfq_id` → `wholesale_rfqs`.`id` (`fk_wrfqi_rfq`), `category_id` → `categories`.`id` (`fk_wrfqi_category`), `product_id` → `products`.`id` (`fk_wrfqi_product`), `product_variant_id` → `product_variants`.`id` (`fk_wrfqi_variant`)

## 62. `rfq_dealer_invitations`
*Defined in:* `sql/06_wholesale_marketplace.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `wholesale_rfq_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `dealer_profile_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `invited_by_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `invitation_status` | `ENUM('INVITED', 'VIEWED', 'QUOTED', 'DECLINED', 'EXPIRED') NOT NULL DEFAULT 'INVITED'` |
| `invited_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `responded_at` | `DATETIME(6) NULL` |

**Foreign Keys:** `wholesale_rfq_id` → `wholesale_rfqs`.`id` (`fk_rdi_rfq`), `dealer_profile_id` → `dealer_profiles`.`id` (`fk_rdi_dealer`), `invited_by_user_id` → `users`.`id` (`fk_rdi_invited_by`)

## 63. `dealer_quotes`
*Defined in:* `sql/06_wholesale_marketplace.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `quote_number` | `VARCHAR(64) NOT NULL` |
| `wholesale_rfq_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `rfq_invitation_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `dealer_profile_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `submitted_by_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `currency_code` | `CHAR(3) NOT NULL DEFAULT 'INR'` |
| `subtotal_amount` | `DECIMAL(14,2) NOT NULL` |
| `discount_amount` | `DECIMAL(14,2) NOT NULL DEFAULT 0.00` |
| `tax_amount` | `DECIMAL(14,2) NOT NULL DEFAULT 0.00` |
| `shipping_fee` | `DECIMAL(14,2) NOT NULL DEFAULT 0.00` |
| `total_amount` | `DECIMAL(14,2) NOT NULL` |
| `lead_time_days` | `SMALLINT UNSIGNED NOT NULL DEFAULT 14` |
| `valid_until` | `DATETIME(6) NOT NULL` |
| `quote_status` | `ENUM('DRAFT', 'SUBMITTED', 'ACCEPTED', 'REJECTED', 'WITHDRAWN', 'EXPIRED', 'CONVERTED_TO_ORDER') NOT NULL DEFAULT 'DRAFT'` |
| `terms_notes` | `TEXT NULL` |
| `accepted_at` | `DATETIME(6) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `wholesale_rfq_id` → `wholesale_rfqs`.`id` (`fk_dq_rfq`), `rfq_invitation_id` → `rfq_dealer_invitations`.`id` (`fk_dq_invitation`), `dealer_profile_id` → `dealer_profiles`.`id` (`fk_dq_dealer`), `submitted_by_user_id` → `users`.`id` (`fk_dq_submitted_by`)

## 64. `dealer_quote_items`
*Defined in:* `sql/06_wholesale_marketplace.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `dealer_quote_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `wholesale_rfq_item_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `dealer_wholesale_listing_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `product_variant_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `item_title_snapshot` | `VARCHAR(220) NOT NULL` |
| `quoted_quantity` | `DECIMAL(14,3) NOT NULL` |
| `unit_price` | `DECIMAL(14,2) NOT NULL` |
| `tax_amount` | `DECIMAL(14,2) NOT NULL DEFAULT 0.00` |
| `line_total` | `DECIMAL(14,2) NOT NULL` |
| `currency_code` | `CHAR(3) NOT NULL DEFAULT 'INR'` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `dealer_quote_id` → `dealer_quotes`.`id` (`fk_dqi_quote`), `wholesale_rfq_item_id` → `wholesale_rfq_items`.`id` (`fk_dqi_rfq_item`), `dealer_wholesale_listing_id` → `dealer_wholesale_listings`.`id` (`fk_dqi_listing`), `product_variant_id` → `product_variants`.`id` (`fk_dqi_variant`)

## 65. `wholesale_orders`
*Defined in:* `sql/06_wholesale_marketplace.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `order_number` | `VARCHAR(64) NOT NULL` |
| `wholesale_buyer_profile_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `buyer_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `dealer_profile_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `order_source` | `ENUM('DIRECT_BULK', 'ACCEPTED_RFQ_QUOTE') NOT NULL` |
| `wholesale_rfq_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `dealer_quote_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `shipping_address_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `shipping_address_snapshot_json` | `JSON NOT NULL` |
| `currency_code` | `CHAR(3) NOT NULL DEFAULT 'INR'` |
| `subtotal_amount` | `DECIMAL(14,2) NOT NULL` |
| `discount_amount` | `DECIMAL(14,2) NOT NULL DEFAULT 0.00` |
| `tax_amount` | `DECIMAL(14,2) NOT NULL DEFAULT 0.00` |
| `shipping_fee` | `DECIMAL(14,2) NOT NULL DEFAULT 0.00` |
| `total_amount` | `DECIMAL(14,2) NOT NULL` |
| `payment_method` | `ENUM('RAZORPAY_STANDARD', 'COD', 'BANK_TRANSFER_VERIFIED') NOT NULL DEFAULT 'RAZORPAY_STANDARD'` |
| `payment_status` | `ENUM('PENDING', 'AUTHORIZED', 'PAID', 'FAILED', 'PARTIALLY_REFUNDED', 'REFUNDED', 'COD_PENDING', 'COD_COLLECTED') NOT NULL DEFAULT 'PENDING'` |
| `fulfilment_status` | `ENUM('PENDING_PAYMENT', 'CONFIRMED', 'PROCESSING', 'SHIPPED', 'DELIVERED', 'CANCELLED', 'RETURNED') NOT NULL DEFAULT 'PENDING_PAYMENT'` |
| `confirmed_at` | `DATETIME(6) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `wholesale_buyer_profile_id` → `wholesale_buyer_profiles`.`id` (`fk_wo_buyer_profile`), `buyer_user_id` → `users`.`id` (`fk_wo_buyer_user`), `dealer_profile_id` → `dealer_profiles`.`id` (`fk_wo_dealer`), `wholesale_rfq_id` → `wholesale_rfqs`.`id` (`fk_wo_rfq`), `dealer_quote_id` → `dealer_quotes`.`id` (`fk_wo_quote`), `shipping_address_id` → `user_addresses`.`id` (`fk_wo_shipping_addr`)

## 66. `wholesale_order_items`
*Defined in:* `sql/06_wholesale_marketplace.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `wholesale_order_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `dealer_wholesale_listing_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `dealer_quote_item_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `product_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `product_variant_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `product_name_snapshot` | `VARCHAR(220) NOT NULL` |
| `sku_snapshot` | `VARCHAR(100) NOT NULL` |
| `quantity` | `DECIMAL(14,3) NOT NULL` |
| `unit_price_snapshot` | `DECIMAL(14,2) NOT NULL` |
| `discount_amount_snapshot` | `DECIMAL(14,2) NOT NULL DEFAULT 0.00` |
| `tax_amount_snapshot` | `DECIMAL(14,2) NOT NULL DEFAULT 0.00` |
| `line_total_amount` | `DECIMAL(14,2) NOT NULL` |
| `currency_code` | `CHAR(3) NOT NULL DEFAULT 'INR'` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `wholesale_order_id` → `wholesale_orders`.`id` (`fk_woi_order`), `dealer_wholesale_listing_id` → `dealer_wholesale_listings`.`id` (`fk_woi_listing`), `dealer_quote_item_id` → `dealer_quote_items`.`id` (`fk_woi_quote_item`), `product_id` → `products`.`id` (`fk_woi_product`), `product_variant_id` → `product_variants`.`id` (`fk_woi_variant`)

## 67. `wholesale_order_status_history`
*Defined in:* `sql/06_wholesale_marketplace.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `wholesale_order_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `status_scope` | `ENUM('ORDER_FULFILMENT', 'PAYMENT_SYNC') NOT NULL DEFAULT 'ORDER_FULFILMENT'` |
| `from_status` | `VARCHAR(40) NULL` |
| `to_status` | `VARCHAR(40) NOT NULL` |
| `actor_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `reason` | `VARCHAR(1000) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `wholesale_order_id` → `wholesale_orders`.`id` (`fk_wosh_order`), `actor_user_id` → `users`.`id` (`fk_wosh_actor`)

## 68. `stock_reservations`
*Defined in:* `sql/06_wholesale_marketplace.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `warehouse_stock_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `reservation_scope` | `ENUM('RETAIL_ORDER', 'WHOLESALE_ORDER') NOT NULL` |
| `retail_order_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `wholesale_order_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `reserved_by_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `reserved_quantity` | `DECIMAL(14,3) NOT NULL` |
| `reservation_status` | `ENUM('ACTIVE', 'RELEASED', 'CONSUMED', 'EXPIRED') NOT NULL DEFAULT 'ACTIVE'` |
| `expires_at` | `DATETIME(6) NOT NULL` |
| `resolved_at` | `DATETIME(6) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `warehouse_stock_id` → `warehouse_stock`.`id` (`fk_sr_stock`), `retail_order_id` → `retail_orders`.`id` (`fk_sr_retail_order`), `wholesale_order_id` → `wholesale_orders`.`id` (`fk_sr_wholesale_order`), `reserved_by_user_id` → `users`.`id` (`fk_sr_user`)

## 69. `payments`
*Defined in:* `sql/07_payments_shipping_returns_reviews.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `payment_reference` | `VARCHAR(64) NOT NULL` |
| `payment_purpose` | `ENUM('RETAIL_ORDER', 'WHOLESALE_ORDER', 'SUPPLIER_PROCUREMENT') NOT NULL` |
| `retail_order_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `wholesale_order_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `supplier_purchase_order_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `payer_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `payment_method` | `ENUM('RAZORPAY_STANDARD', 'COD', 'BANK_TRANSFER_OFFLINE') NOT NULL DEFAULT 'RAZORPAY_STANDARD'` |
| `provider_name` | `VARCHAR(40) NOT NULL DEFAULT 'RAZORPAY'` |
| `amount` | `DECIMAL(14,2) NOT NULL` |
| `captured_amount` | `DECIMAL(14,2) NOT NULL DEFAULT 0.00` |
| `currency_code` | `CHAR(3) NOT NULL DEFAULT 'INR'` |
| `payment_status` | `ENUM('CREATED', 'ORDER_CREATED', 'CHECKOUT_OPENED', 'AUTHORIZED', 'CAPTURED', 'FAILED', 'CANCELLED', 'REFUND_PENDING', 'PARTIALLY_REFUNDED', 'REFUNDED', 'RECONCILIATION_REQUIRED', 'COD_PENDING', 'COD_COLLECTED') NOT NULL DEFAULT 'CREATED'` |
| `idempotency_key` | `VARCHAR(128) NOT NULL` |
| `provider_order_id` | `VARCHAR(128) NULL` |
| `provider_payment_id` | `VARCHAR(128) NULL` |
| `provider_receipt` | `VARCHAR(80) NULL` |
| `authorized_at` | `DATETIME(6) NULL` |
| `captured_at` | `DATETIME(6) NULL` |
| `failed_at` | `DATETIME(6) NULL` |
| `failure_code` | `VARCHAR(100) NULL` |
| `failure_reason` | `VARCHAR(500) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `payer_user_id` → `users`.`id` (`fk_payments_payer`), `retail_order_id` → `retail_orders`.`id` (`fk_payments_retail_order`), `wholesale_order_id` → `wholesale_orders`.`id` (`fk_payments_wholesale_order`), `supplier_purchase_order_id` → `supplier_purchase_orders`.`id` (`fk_payments_supplier_po`)

## 70. `payment_attempts`
*Defined in:* `sql/07_payments_shipping_returns_reviews.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `payment_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `payer_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `attempt_number` | `INT UNSIGNED NOT NULL DEFAULT 1` |
| `idempotency_key` | `VARCHAR(128) NOT NULL` |
| `provider_order_id` | `VARCHAR(128) NULL` |
| `provider_payment_id` | `VARCHAR(128) NULL` |
| `amount` | `DECIMAL(14,2) NOT NULL` |
| `currency_code` | `CHAR(3) NOT NULL DEFAULT 'INR'` |
| `attempt_status` | `ENUM('INITIATED', 'ORDER_CREATED', 'CHECKOUT_OPENED', 'PENDING_VERIFICATION', 'AUTHORIZED', 'CAPTURED', 'FAILED', 'CANCELLED', 'RECONCILIATION_REQUIRED') NOT NULL DEFAULT 'INITIATED'` |
| `failure_code` | `VARCHAR(100) NULL` |
| `failure_description` | `VARCHAR(500) NULL` |
| `safe_metadata_json` | `JSON NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `payment_id` → `payments`.`id` (`fk_pa_payment`), `payer_user_id` → `users`.`id` (`fk_pa_payer`)

## 71. `payment_status_history`
*Defined in:* `sql/07_payments_shipping_returns_reviews.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `payment_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `from_status` | `VARCHAR(40) NULL` |
| `to_status` | `VARCHAR(40) NOT NULL` |
| `event_source` | `ENUM('CREATE_ORDER', 'VERIFY_CALLBACK', 'WEBHOOK', 'RECONCILIATION', 'REFUND', 'COD_COLLECTION', 'ADMIN') NOT NULL` |
| `actor_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `provider_event_ref` | `VARCHAR(128) NULL` |
| `notes` | `VARCHAR(500) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `payment_id` → `payments`.`id` (`fk_psh_payment`), `actor_user_id` → `users`.`id` (`fk_psh_actor`)

## 72. `payment_webhook_events`
*Defined in:* `sql/07_payments_shipping_returns_reviews.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `provider_name` | `VARCHAR(40) NOT NULL DEFAULT 'RAZORPAY'` |
| `provider_event_id` | `VARCHAR(128) NOT NULL` |
| `event_type` | `VARCHAR(100) NOT NULL` |
| `payment_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `provider_order_id` | `VARCHAR(128) NULL` |
| `provider_payment_id` | `VARCHAR(128) NULL` |
| `signature_verified` | `TINYINT(1) NOT NULL DEFAULT 0` |
| `processing_status` | `ENUM('RECEIVED', 'PROCESSED', 'DUPLICATE_IGNORED', 'IGNORED_OUT_OF_ORDER', 'FAILED') NOT NULL DEFAULT 'RECEIVED'` |
| `safe_payload_summary_json` | `JSON NULL` |
| `error_summary` | `VARCHAR(500) NULL` |
| `received_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `processed_at` | `DATETIME(6) NULL` |

**Foreign Keys:** `payment_id` → `payments`.`id` (`fk_pwe_payment`)

## 73. `refunds`
*Defined in:* `sql/07_payments_shipping_returns_reviews.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `refund_reference` | `VARCHAR(64) NOT NULL` |
| `payment_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `provider_refund_id` | `VARCHAR(128) NULL` |
| `idempotency_key` | `VARCHAR(128) NOT NULL` |
| `amount` | `DECIMAL(14,2) NOT NULL` |
| `currency_code` | `CHAR(3) NOT NULL DEFAULT 'INR'` |
| `refund_type` | `ENUM('FULL', 'PARTIAL') NOT NULL` |
| `refund_status` | `ENUM('REQUESTED', 'PENDING_PROVIDER', 'PROCESSED', 'FAILED', 'CANCELLED') NOT NULL DEFAULT 'REQUESTED'` |
| `reason` | `VARCHAR(500) NOT NULL` |
| `initiated_by_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `approved_by_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `processed_at` | `DATETIME(6) NULL` |
| `failure_reason` | `VARCHAR(500) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `payment_id` → `payments`.`id` (`fk_refunds_payment`), `initiated_by_user_id` → `users`.`id` (`fk_refunds_initiated_by`), `approved_by_user_id` → `users`.`id` (`fk_refunds_approved_by`)

## 74. `payouts`
*Defined in:* `sql/07_payments_shipping_returns_reviews.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `payout_reference` | `VARCHAR(64) NOT NULL` |
| `recipient_type` | `ENUM('DIRECT_SELLER', 'DEALER', 'SUPPLIER') NOT NULL` |
| `recipient_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `seller_profile_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `dealer_profile_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `supplier_profile_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `retail_order_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `wholesale_order_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `supplier_purchase_order_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `gross_amount` | `DECIMAL(14,2) NOT NULL` |
| `platform_fee_amount` | `DECIMAL(14,2) NOT NULL DEFAULT 0.00` |
| `tax_withheld_amount` | `DECIMAL(14,2) NOT NULL DEFAULT 0.00` |
| `net_payout_amount` | `DECIMAL(14,2) NOT NULL` |
| `currency_code` | `CHAR(3) NOT NULL DEFAULT 'INR'` |
| `payout_status` | `ENUM('OBLIGATION_RECORDED', 'APPROVED', 'PROCESSING', 'SETTLED', 'ON_HOLD', 'FAILED', 'CANCELLED') NOT NULL DEFAULT 'OBLIGATION_RECORDED'` |
| `settlement_reference` | `VARCHAR(128) NULL` |
| `settled_at` | `DATETIME(6) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `recipient_user_id` → `users`.`id` (`fk_payouts_user`), `seller_profile_id` → `seller_profiles`.`id` (`fk_payouts_seller`), `dealer_profile_id` → `dealer_profiles`.`id` (`fk_payouts_dealer`), `supplier_profile_id` → `supplier_profiles`.`id` (`fk_payouts_supplier`), `retail_order_id` → `retail_orders`.`id` (`fk_payouts_retail_order`), `wholesale_order_id` → `wholesale_orders`.`id` (`fk_payouts_wholesale_order`), `supplier_purchase_order_id` → `supplier_purchase_orders`.`id` (`fk_payouts_supplier_po`)

## 75. `shipments`
*Defined in:* `sql/07_payments_shipping_returns_reviews.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `shipment_number` | `VARCHAR(64) NOT NULL` |
| `shipment_scope` | `ENUM('RETAIL_FULFILMENT', 'WHOLESALE_ORDER', 'SUPPLIER_PROCUREMENT') NOT NULL` |
| `retail_order_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `seller_fulfilment_group_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `wholesale_order_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `supplier_purchase_order_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `origin_warehouse_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `carrier_name` | `VARCHAR(100) NULL` |
| `tracking_number` | `VARCHAR(128) NULL` |
| `shipment_status` | `ENUM('LABEL_CREATED', 'PICKED_UP', 'IN_TRANSIT', 'OUT_FOR_DELIVERY', 'DELIVERED', 'DELIVERY_FAILED', 'RETURNED_TO_ORIGIN', 'CANCELLED') NOT NULL DEFAULT 'LABEL_CREATED'` |
| `dispatched_at` | `DATETIME(6) NULL` |
| `delivered_at` | `DATETIME(6) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `retail_order_id` → `retail_orders`.`id` (`fk_shipments_retail`), `seller_fulfilment_group_id` → `seller_fulfilment_groups`.`id` (`fk_shipments_sfg`), `wholesale_order_id` → `wholesale_orders`.`id` (`fk_shipments_wholesale`), `supplier_purchase_order_id` → `supplier_purchase_orders`.`id` (`fk_shipments_po`), `origin_warehouse_id` → `warehouses`.`id` (`fk_shipments_warehouse`)

## 76. `shipment_items`
*Defined in:* `sql/07_payments_shipping_returns_reviews.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `shipment_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `retail_order_item_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `wholesale_order_item_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `supplier_po_item_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `shipped_quantity` | `DECIMAL(14,3) NOT NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `shipment_id` → `shipments`.`id` (`fk_si_shipment`), `retail_order_item_id` → `retail_order_items`.`id` (`fk_si_retail_item`), `wholesale_order_item_id` → `wholesale_order_items`.`id` (`fk_si_wholesale_item`), `supplier_po_item_id` → `supplier_purchase_order_items`.`id` (`fk_si_po_item`)

## 77. `tracking_events`
*Defined in:* `sql/07_payments_shipping_returns_reviews.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `shipment_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `provider_event_id` | `VARCHAR(128) NULL` |
| `event_status` | `VARCHAR(80) NOT NULL` |
| `location_name` | `VARCHAR(160) NULL` |
| `event_description` | `VARCHAR(500) NULL` |
| `occurred_at` | `DATETIME(6) NOT NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `shipment_id` → `shipments`.`id` (`fk_te_shipment`)

## 78. `return_requests`
*Defined in:* `sql/07_payments_shipping_returns_reviews.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `return_number` | `VARCHAR(64) NOT NULL` |
| `order_scope` | `ENUM('RETAIL_ORDER', 'WHOLESALE_ORDER') NOT NULL` |
| `retail_order_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `seller_fulfilment_group_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `wholesale_order_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `payment_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `requested_by_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `reason_code` | `VARCHAR(64) NOT NULL` |
| `reason_details` | `TEXT NULL` |
| `return_status` | `ENUM('REQUESTED', 'APPROVED', 'REJECTED', 'PICKUP_SCHEDULED', 'RECEIVED', 'INSPECTED', 'REFUND_INITIATED', 'CLOSED', 'CANCELLED') NOT NULL DEFAULT 'REQUESTED'` |
| `requested_refund_amount` | `DECIMAL(14,2) NULL` |
| `currency_code` | `CHAR(3) NOT NULL DEFAULT 'INR'` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `requested_by_user_id` → `users`.`id` (`fk_rr_user`), `retail_order_id` → `retail_orders`.`id` (`fk_rr_retail`), `seller_fulfilment_group_id` → `seller_fulfilment_groups`.`id` (`fk_rr_sfg`), `wholesale_order_id` → `wholesale_orders`.`id` (`fk_rr_wholesale`), `payment_id` → `payments`.`id` (`fk_rr_payment`)

## 79. `return_status_history`
*Defined in:* `sql/07_payments_shipping_returns_reviews.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `return_request_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `from_status` | `VARCHAR(40) NULL` |
| `to_status` | `VARCHAR(40) NOT NULL` |
| `actor_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `notes` | `VARCHAR(1000) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `return_request_id` → `return_requests`.`id` (`fk_rsh_return`), `actor_user_id` → `users`.`id` (`fk_rsh_actor`)

## 80. `return_items`
*Defined in:* `sql/07_payments_shipping_returns_reviews.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `return_request_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `retail_order_item_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `wholesale_order_item_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `return_quantity` | `DECIMAL(14,3) NOT NULL` |
| `item_condition` | `ENUM('UNOPENED', 'OPENED_GOOD', 'DAMAGED', 'DEFECTIVE', 'WRONG_ITEM') NOT NULL DEFAULT 'OPENED_GOOD'` |
| `restock_approved` | `TINYINT(1) NOT NULL DEFAULT 0` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `return_request_id` → `return_requests`.`id` (`fk_ri_return`), `retail_order_item_id` → `retail_order_items`.`id` (`fk_ri_retail_item`), `wholesale_order_item_id` → `wholesale_order_items`.`id` (`fk_ri_wholesale_item`)

## 81. `product_reviews`
*Defined in:* `sql/07_payments_shipping_returns_reviews.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `product_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `product_variant_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `seller_profile_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `reviewer_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `retail_order_item_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `rating` | `TINYINT UNSIGNED NOT NULL` |
| `title` | `VARCHAR(160) NULL` |
| `review_body` | `TEXT NULL` |
| `is_verified_purchase` | `TINYINT(1) NOT NULL DEFAULT 0` |
| `moderation_status` | `ENUM('PENDING', 'PUBLISHED', 'HIDDEN', 'REJECTED') NOT NULL DEFAULT 'PUBLISHED'` |
| `seller_reply` | `TEXT NULL` |
| `seller_replied_at` | `DATETIME(6) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `product_id` → `products`.`id` (`fk_pr_product`), `product_variant_id` → `product_variants`.`id` (`fk_pr_variant`), `seller_profile_id` → `seller_profiles`.`id` (`fk_pr_seller`), `reviewer_user_id` → `users`.`id` (`fk_pr_reviewer`), `retail_order_item_id` → `retail_order_items`.`id` (`fk_pr_order_item`)

## 82. `coupons`
*Defined in:* `sql/08_promotions_notifications_and_admin_operations.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `code` | `VARCHAR(64) NOT NULL` |
| `description` | `VARCHAR(255) NULL` |
| `discount_type` | `ENUM('PERCENTAGE', 'FIXED_AMOUNT') NOT NULL` |
| `discount_value` | `DECIMAL(14,2) NOT NULL` |
| `max_discount_amount` | `DECIMAL(14,2) NULL` |
| `min_order_amount` | `DECIMAL(14,2) NOT NULL DEFAULT 0.00` |
| `currency_code` | `CHAR(3) NOT NULL DEFAULT 'INR'` |
| `applicable_scope` | `ENUM('RETAIL', 'WHOLESALE', 'BOTH') NOT NULL DEFAULT 'RETAIL'` |
| `max_total_redemptions` | `INT UNSIGNED NULL` |
| `max_per_user` | `INT UNSIGNED NOT NULL DEFAULT 1` |
| `starts_at` | `DATETIME(6) NOT NULL` |
| `ends_at` | `DATETIME(6) NULL` |
| `is_active` | `TINYINT(1) NOT NULL DEFAULT 1` |
| `created_by_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `created_by_user_id` → `users`.`id` (`fk_coupons_created_by`)

## 83. `coupon_usage`
*Defined in:* `sql/08_promotions_notifications_and_admin_operations.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `coupon_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `retail_order_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `wholesale_order_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `discount_applied` | `DECIMAL(14,2) NOT NULL` |
| `currency_code` | `CHAR(3) NOT NULL DEFAULT 'INR'` |
| `used_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `coupon_id` → `coupons`.`id` (`fk_cu_coupon`), `user_id` → `users`.`id` (`fk_cu_user`), `retail_order_id` → `retail_orders`.`id` (`fk_cu_retail_order`), `wholesale_order_id` → `wholesale_orders`.`id` (`fk_cu_wholesale_order`)

## 84. `promotions`
*Defined in:* `sql/08_promotions_notifications_and_admin_operations.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `code` | `VARCHAR(64) NOT NULL` |
| `name` | `VARCHAR(160) NOT NULL` |
| `description` | `TEXT NULL` |
| `promotion_type` | `ENUM('PERCENTAGE_OFF', 'FIXED_OFF', 'FREE_SHIPPING', 'BUNDLE') NOT NULL` |
| `discount_value` | `DECIMAL(14,2) NOT NULL DEFAULT 0.00` |
| `currency_code` | `CHAR(3) NOT NULL DEFAULT 'INR'` |
| `starts_at` | `DATETIME(6) NOT NULL` |
| `ends_at` | `DATETIME(6) NULL` |
| `is_active` | `TINYINT(1) NOT NULL DEFAULT 1` |
| `created_by_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `created_by_user_id` → `users`.`id` (`fk_promotions_created_by`)

## 85. `promotion_products`
*Defined in:* `sql/08_promotions_notifications_and_admin_operations.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `promotion_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `product_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `promotion_id` → `promotions`.`id` (`fk_pp_promo`), `product_id` → `products`.`id` (`fk_pp_product`)

## 86. `promotion_categories`
*Defined in:* `sql/08_promotions_notifications_and_admin_operations.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `promotion_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `category_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `promotion_id` → `promotions`.`id` (`fk_pc_promo`), `category_id` → `categories`.`id` (`fk_pc_category`)

## 87. `notifications`
*Defined in:* `sql/08_promotions_notifications_and_admin_operations.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `channel` | `ENUM('IN_APP', 'EMAIL', 'SMS', 'WEBHOOK') NOT NULL DEFAULT 'IN_APP'` |
| `notification_type` | `VARCHAR(80) NOT NULL` |
| `title` | `VARCHAR(200) NOT NULL` |
| `body` | `TEXT NOT NULL` |
| `reference_type` | `VARCHAR(64) NULL` |
| `reference_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `is_read` | `TINYINT(1) NOT NULL DEFAULT 0` |
| `read_at` | `DATETIME(6) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `user_id` → `users`.`id` (`fk_notif_user`)

## 88. `support_tickets`
*Defined in:* `sql/08_promotions_notifications_and_admin_operations.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `ticket_number` | `VARCHAR(64) NOT NULL` |
| `requester_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `assigned_admin_profile_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `category` | `ENUM('ORDER_ISSUE', 'PAYMENT_ISSUE', 'RETURN_DISPUTE', 'GI_VERIFICATION', 'PROCUREMENT', 'ACCOUNT_ACCESS', 'OTHER') NOT NULL DEFAULT 'OTHER'` |
| `priority` | `ENUM('LOW', 'MEDIUM', 'HIGH', 'URGENT') NOT NULL DEFAULT 'MEDIUM'` |
| `ticket_status` | `ENUM('OPEN', 'IN_PROGRESS', 'WAITING_ON_USER', 'RESOLVED', 'CLOSED') NOT NULL DEFAULT 'OPEN'` |
| `subject` | `VARCHAR(220) NOT NULL` |
| `retail_order_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `wholesale_order_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `supplier_purchase_order_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `resolved_at` | `DATETIME(6) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `requester_user_id` → `users`.`id` (`fk_st_requester`), `assigned_admin_profile_id` → `admin_profiles`.`id` (`fk_st_admin`), `retail_order_id` → `retail_orders`.`id` (`fk_st_retail`), `wholesale_order_id` → `wholesale_orders`.`id` (`fk_st_wholesale`), `supplier_purchase_order_id` → `supplier_purchase_orders`.`id` (`fk_st_po`)

## 89. `support_ticket_messages`
*Defined in:* `sql/08_promotions_notifications_and_admin_operations.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `support_ticket_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `sender_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `is_internal_note` | `TINYINT(1) NOT NULL DEFAULT 0` |
| `message_body` | `TEXT NOT NULL` |
| `attachment_storage_key` | `VARCHAR(512) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `support_ticket_id` → `support_tickets`.`id` (`fk_stm_ticket`), `sender_user_id` → `users`.`id` (`fk_stm_sender`)

## 90. `audit_logs`
*Defined in:* `sql/08_promotions_notifications_and_admin_operations.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `actor_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `actor_role` | `VARCHAR(64) NOT NULL` |
| `action` | `VARCHAR(120) NOT NULL` |
| `target_type` | `VARCHAR(80) NOT NULL` |
| `target_id` | `VARCHAR(128) NOT NULL` |
| `reason` | `VARCHAR(1000) NULL` |
| `previous_values_json` | `JSON NULL` |
| `new_values_json` | `JSON NULL` |
| `correlation_id` | `VARCHAR(100) NOT NULL` |
| `ip_address` | `VARCHAR(45) NULL` |
| `user_agent` | `VARCHAR(255) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `actor_user_id` → `users`.`id` (`fk_audit_actor`)

## 91. `admin_action_requests`
*Defined in:* `sql/08_promotions_notifications_and_admin_operations.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `request_type` | `VARCHAR(100) NOT NULL` |
| `target_type` | `VARCHAR(80) NOT NULL` |
| `target_id` | `VARCHAR(128) NOT NULL` |
| `requested_payload_json` | `JSON NOT NULL` |
| `request_reason` | `VARCHAR(1000) NOT NULL` |
| `requested_by_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `approval_status` | `ENUM('PENDING', 'APPROVED', 'REJECTED', 'EXECUTED', 'CANCELLED', 'EXPIRED') NOT NULL DEFAULT 'PENDING'` |
| `reviewed_by_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `review_reason` | `VARCHAR(1000) NULL` |
| `reviewed_at` | `DATETIME(6) NULL` |
| `executed_at` | `DATETIME(6) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `requested_by_user_id` → `users`.`id` (`fk_aar_requested_by`), `reviewed_by_user_id` → `users`.`id` (`fk_aar_reviewed_by`)

## 92. `platform_settings`
*Defined in:* `sql/08_promotions_notifications_and_admin_operations.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `setting_key` | `VARCHAR(100) NOT NULL` |
| `setting_value_json` | `JSON NOT NULL` |
| `description` | `VARCHAR(500) NULL` |
| `is_sensitive` | `TINYINT(1) NOT NULL DEFAULT 0` |
| `is_active` | `TINYINT(1) NOT NULL DEFAULT 1` |
| `updated_by_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `updated_by_user_id` → `users`.`id` (`fk_ps_updated_by`)

## 93. `announcements`
*Defined in:* `sql/08_promotions_notifications_and_admin_operations.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `title` | `VARCHAR(200) NOT NULL` |
| `body` | `TEXT NOT NULL` |
| `audience_role_code` | `VARCHAR(50) NULL` |
| `severity` | `ENUM('INFO', 'NOTICE', 'WARNING', 'MAINTENANCE') NOT NULL DEFAULT 'INFO'` |
| `starts_at` | `DATETIME(6) NOT NULL` |
| `ends_at` | `DATETIME(6) NULL` |
| `is_active` | `TINYINT(1) NOT NULL DEFAULT 1` |
| `created_by_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |
| `updated_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `created_by_user_id` → `users`.`id` (`fk_ann_created_by`)

## 94. `product_approval_history`
*Defined in:* `sql/08_promotions_notifications_and_admin_operations.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `product_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `seller_listing_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `dealer_wholesale_listing_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `from_status` | `VARCHAR(40) NULL` |
| `to_status` | `VARCHAR(40) NOT NULL` |
| `actor_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `reason` | `VARCHAR(1000) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `product_id` → `products`.`id` (`fk_pah_product`), `seller_listing_id` → `seller_product_listings`.`id` (`fk_pah_seller_listing`), `dealer_wholesale_listing_id` → `dealer_wholesale_listings`.`id` (`fk_pah_dealer_listing`), `actor_user_id` → `users`.`id` (`fk_pah_actor`)

## 95. `dealer_status_history`
*Defined in:* `sql/08_promotions_notifications_and_admin_operations.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `dealer_profile_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `status_field` | `ENUM('PROFILE_STATUS', 'VERIFICATION_STATUS') NOT NULL` |
| `from_status` | `VARCHAR(40) NULL` |
| `to_status` | `VARCHAR(40) NOT NULL` |
| `actor_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `reason` | `VARCHAR(1000) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `dealer_profile_id` → `dealer_profiles`.`id` (`fk_dsh_dealer`), `actor_user_id` → `users`.`id` (`fk_dsh_actor`)

## 96. `supplier_status_history`
*Defined in:* `sql/08_promotions_notifications_and_admin_operations.sql`

| Column | MySQL Definition |
|---|---|
| `id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `supplier_profile_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL` |
| `status_field` | `ENUM('PROFILE_STATUS', 'VERIFICATION_STATUS') NOT NULL` |
| `from_status` | `VARCHAR(40) NULL` |
| `to_status` | `VARCHAR(40) NOT NULL` |
| `actor_user_id` | `CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL` |
| `reason` | `VARCHAR(1000) NULL` |
| `created_at` | `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

**Foreign Keys:** `supplier_profile_id` → `supplier_profiles`.`id` (`fk_ssh_supplier`), `actor_user_id` → `users`.`id` (`fk_ssh_actor`)
