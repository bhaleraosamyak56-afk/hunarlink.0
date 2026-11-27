# HunarLink ASIGS — Advanced Seller Input Guardrail System Architecture

## 1. Core Design Principles
1. **Server-Side Authority:** React UI validation is advisory only; FastAPI enforces all 10 guardrail layers before persistence or publication.
2. **Identity vs Authorization Separation:** Clerk RS256 JWTs authenticate *who* the caller is (`sub` -> `users.clerk_user_id`), while HunarLink's MySQL tables (`users`, `user_role_assignments`, `admin_profiles`, `admin_role_permissions`, `seller_profiles`, `supplier_profiles`, `dealer_profiles`) decide *what* the caller is permitted to do.
3. **Outcome vs Business Status Separation:**
   - **Guardrail Outcomes:** `PASS`, `WARNING`, `REVIEW_REQUIRED`, `BLOCK`
   - **Business Statuses:** `PENDING_APPROVAL`, `ACTIVE`, `SUBMITTED`, `APPROVED_FOR_MATCHING`, `INVITED`, `ACCEPTED`, etc.
   Guardrail flags never overwrite business statuses directly, and warnings/duplicate indicators escalate to human review rather than auto-banning genuine artisans.
4. **Honesty Over Mock Theater:**
   - Without a real antivirus daemon (`MALWARE_SCANNER_MODE=pending_only`), uploaded files are recorded as `PENDING_SCAN` — never falsely stamped `CLEAN`.
   - Deterministic GI reference checks always route to mandatory human Admin approval (`REVIEW_REQUIRED`).

## 2. The 10 Guardrail Layers
| Layer | Module | Protections Enforced |
|---|---|---|
| 1. Identity & Access | `rules/identity.py`, `core/auth.py` | Active account, verified/active role profile, rejects spoofed profile IDs |
| 2. Local-Language Safe Validation | `rules/input_validation.py` | Preserves Kashmiri/Urdu/Hindi/English craft text; blocks null/control bytes & `<script>` / event handlers; validates SKUs & Indian GSTIN |
| 3. Document & File Security | `rules/documents.py`, `providers/malware_scanner.py` | Extension allowlist (`.jpg/.jpeg/.png/.webp/.pdf`), real magic-byte sniffing, PDF active-script check, size cap, server UUID storage outside web root, SHA-256 hash, EICAR detection & `PENDING_SCAN` honest status |
| 4. Product & Listing Integrity | `rules/products.py` | Blocks seller self-assignment of `GI_VERIFIED`, blocks skipping `PENDING_APPROVAL` (`LIVE`/`ACTIVE`), validates product/variant linkage & qty bounds |
| 5. GI vs Non-GI Separation | `rules/gi_claims.py` | `NON_GI` uses Admin manual review only; missing GI evidence routes to `REVIEW_REQUIRED`; deterministic GI reference lookups always require human Admin decision |
| 6. Commercial Rules | `rules/commercial.py` | `Decimal` money only, `INR` currency check, MRP >= selling price, wholesale MOQ & non-overlapping monotonically non-increasing price tiers, extreme outlier `WARNING` only |
| 7. Inventory & Procurement Isolation | `rules/inventory.py` | Atomic conditional `UPDATE` prevents negative stock / overselling; supplier lots never inflate dealer stock; goods receipt enforces PO quantity cap, passing quality inspection, and single posting (`inventory_posted` guard) |
| 8. Duplicate & Risk Signals | `rules/duplicates.py` | SHA-256 normalized fingerprints for listings, lots, and files; matches escalate to `REVIEW_REQUIRED` case |
| 9. Ownership & Workflow State Machines | `rules/ownership.py` | Enforces owner-or-admin reads/writes, blocks cross-dealer assignment responses, enforces legal state transitions, forbids Admin self-approval |
| 10. Admin Guardrail Center & Audit | `router.py`, `repository.py`, `core/audit.py` | `guardrail_rules`, `guardrail_checks`, `guardrail_cases`, `guardrail_case_events`, `file_security_scans`, `input_fingerprints`, plus immutable `audit_logs` with mandatory decision reasons and correlation IDs |
