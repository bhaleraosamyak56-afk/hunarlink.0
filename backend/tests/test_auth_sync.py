"""Tests for Clerk JWT -> HunarLink DB user sync, /auth/me, and Artisan verification."""
from __future__ import annotations

from sqlalchemy import func, select

from app.core.auth import get_current_principal, get_verified_clerk_claims
from app.models.core_models import (
    PlatformRole,
    SellerProfile,
    SellerVerificationApplication,
    User,
    UserRoleAssignment,
)
from tests.conftest import set_authenticated_principal


def _set_clerk_claims(app, claims: dict | None) -> None:
    if claims is None:
        app.dependency_overrides.pop(get_verified_clerk_claims, None)
    else:
        app.dependency_overrides[get_verified_clerk_claims] = lambda: claims


def test_01_auth_sync_requires_verified_bearer_token(app_and_client):
    app, client = app_and_client
    _set_clerk_claims(app, None)

    resp = client.post(
        "/api/v1/auth/sync",
        json={
            "email": "new.buyer@example.com",
            "first_name": "Riya",
            "requested_role": "buyer",
        },
    )
    assert resp.status_code == 401


def test_02_new_buyer_login_creates_user_and_customer_role_in_db(app_and_client, db_session):
    app, client = app_and_client
    _set_clerk_claims(app, {"sub": "user_2newBuyer001", "iss": "https://test.clerk.accounts.dev"})

    resp = client.post(
        "/api/v1/auth/sync",
        json={
            "email": "Riya.Verma@Example.com",
            "email_verified": True,
            "first_name": "Riya",
            "last_name": "Verma",
            "display_name": "Riya Verma",
            "phone": "+91 9811011223",
            "requested_role": "buyer",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["synced"] is True
    assert body["is_new_user"] is True
    assert body["clerk_user_id"] == "user_2newBuyer001"
    assert body["email"] == "riya.verma@example.com"
    assert body["roles"] == ["CUSTOMER"]
    assert body["account_status"] == "ACTIVE"

    # Confirm persisted in DB
    db_user = db_session.scalar(select(User).where(User.clerk_user_id == "user_2newBuyer001"))
    assert db_user is not None
    assert db_user.email == "riya.verma@example.com"
    assert db_user.first_name == "Riya"

    # Re-sync updates cleanly without duplicating user rows
    resp2 = client.post(
        "/api/v1/auth/sync",
        json={
            "email": "riya.verma@example.com",
            "email_verified": True,
            "first_name": "Riya",
            "last_name": "Verma-Kapoor",
            "requested_role": "buyer",
        },
    )
    assert resp2.status_code == 200
    assert resp2.json()["is_new_user"] is False
    assert resp2.json()["last_name"] == "Verma-Kapoor"
    user_count = db_session.scalar(
        select(func.count(User.id)).where(User.clerk_user_id == "user_2newBuyer001")
    )
    assert user_count == 1
    _set_clerk_claims(app, None)


def test_03_auth_sync_blocks_admin_role_and_extra_fields(app_and_client):
    app, client = app_and_client
    _set_clerk_claims(app, {"sub": "user_2attacker01"})

    resp_admin = client.post(
        "/api/v1/auth/sync",
        json={
            "email": "attacker@example.com",
            "first_name": "Bad",
            "requested_role": "admin",
        },
    )
    assert resp_admin.status_code == 422

    resp_extra = client.post(
        "/api/v1/auth/sync",
        json={
            "email": "attacker@example.com",
            "first_name": "Bad",
            "requested_role": "buyer",
            "clerk_user_id": "user_spoofed",
        },
    )
    assert resp_extra.status_code == 422
    _set_clerk_claims(app, None)


def test_04_artisan_sync_and_verification_persists_seller_profile_without_self_approval(
    app_and_client, db_session
):
    app, client = app_and_client
    _set_clerk_claims(app, {"sub": "user_2newArtisan01"})

    sync_resp = client.post(
        "/api/v1/auth/sync",
        json={
            "email": "bilal.loom@example.com",
            "email_verified": True,
            "first_name": "Bilal",
            "last_name": "Dar",
            "display_name": "Bilal Dar",
            "requested_role": "artisan",
        },
    )
    assert sync_resp.status_code == 200
    synced = sync_resp.json()
    assert synced["is_new_user"] is True
    assert set(synced["roles"]) == {"DIRECT_SELLER"}

    # Now load principal cleanly via DB lookup and submit Artisan GI verification
    from app.core.auth import load_principal_by_clerk_id

    principal = load_principal_by_clerk_id(db_session, "user_2newArtisan01")
    set_authenticated_principal(app, principal)

    me_resp = client.get("/api/v1/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["user_id"] == synced["user_id"]

    ver_resp = client.post(
        "/api/v1/auth/artisan-verification",
        json={
            "store_name": "Dar Heritage Pashmina Atelier",
            "craft_specialty": "Pashmina Handloom",
            "workshop_district": "Srinagar",
            "verification_path": "GI",
            "claimed_gi_code": "GI-JK-PASH-9911",
            "skill_description": "Third-generation hand-spun Changthangi pashmina weavers.",
            "phone": "+91 9906123456",
        },
    )
    assert ver_resp.status_code == 201
    ver = ver_resp.json()
    assert ver["application_status"] == "SUBMITTED"
    # ASIGS guardrail: sellers can NEVER self-approve GI verification
    assert ver["seller_profile"]["verification_status"] == "SUBMITTED"
    assert ver["seller_profile"]["store_name"] == "Dar Heritage Pashmina Atelier"

    db_seller = db_session.scalar(
        select(SellerProfile).where(SellerProfile.user_id == synced["user_id"])
    )
    assert db_seller is not None
    assert db_seller.verification_status == "SUBMITTED"
    db_app = db_session.scalar(
        select(SellerVerificationApplication).where(
            SellerVerificationApplication.seller_profile_id == db_seller.id
        )
    )
    assert db_app is not None
    assert db_app.claimed_gi_code == "GI-JK-PASH-9911"

    _set_clerk_claims(app, None)
    app.dependency_overrides.pop(get_current_principal, None)


def test_05_user_addresses_crud_requires_auth_and_persists_in_db(app_and_client, db_session):
    app, client = app_and_client
    _set_clerk_claims(app, {"sub": "user_2addrTest01"})
    sync = client.post(
        "/api/v1/auth/sync",
        json={
            "email": "addr.user@example.com",
            "first_name": "Aarav",
            "requested_role": "buyer",
        },
    )
    assert sync.status_code == 200

    from app.core.auth import load_principal_by_clerk_id

    set_authenticated_principal(app, None)
    assert client.get("/api/v1/auth/addresses").status_code == 401

    principal = load_principal_by_clerk_id(db_session, "user_2addrTest01")
    set_authenticated_principal(app, principal)
    assert client.get("/api/v1/auth/addresses").json() == []

    created = client.post(
        "/api/v1/auth/addresses",
        json={
            "address_label": "HOME",
            "recipient_name": "Aarav Sharma",
            "recipient_phone": "+91 9811044210",
            "line1": "Residency Road, Near Lal Chowk",
            "city": "Srinagar",
            "state_province": "Jammu and Kashmir",
            "postal_code": "190001",
            "is_default": True,
        },
    )
    assert created.status_code == 201
    addr_id = created.json()["id"]
    assert created.json()["is_default"] is True

    listed = client.get("/api/v1/auth/addresses").json()
    assert len(listed) == 1
    assert listed[0]["id"] == addr_id

    del_resp = client.delete(f"/api/v1/auth/addresses/{addr_id}")
    assert del_resp.status_code == 204
    assert client.get("/api/v1/auth/addresses").json() == []

    _set_clerk_claims(app, None)
    app.dependency_overrides.pop(get_current_principal, None)


def test_06_admin_overview_blocks_guests_and_normal_users_but_allows_db_admin(app_and_client, db_session):
    from app.core.auth import load_principal_by_clerk_id
    from app.models.base import new_uuid
    from app.models.core_models import (
        AdminPermission,
        AdminProfile,
        AdminRole,
        AdminRolePermission,
        AdminUserRole,
    )

    app, client = app_and_client

    # 1. Guest -> 401
    set_authenticated_principal(app, None)
    assert client.get("/api/v1/admin/overview").status_code == 401

    # 2. Normal signed-in buyer -> is_admin=False & 403 on /admin/overview
    _set_clerk_claims(app, {"sub": "user_2normalBuyer99"})
    sync = client.post(
        "/api/v1/auth/sync",
        json={"email": "normal.buyer@example.com", "first_name": "Riya", "requested_role": "buyer"},
    )
    assert sync.status_code == 200
    assert sync.json()["is_admin"] is False

    buyer_principal = load_principal_by_clerk_id(db_session, "user_2normalBuyer99")
    set_authenticated_principal(app, buyer_principal)
    assert client.get("/api/v1/auth/me").json()["is_admin"] is False
    assert client.get("/api/v1/admin/overview").status_code == 403

    # 3. Promote to active DB Admin (ADMIN platform role + AdminProfile + permissions)
    from sqlalchemy import select
    from app.models.core_models import PlatformRole, UserRoleAssignment

    adm_plat = db_session.scalar(select(PlatformRole).where(PlatformRole.code == "ADMIN"))
    if adm_plat is None:
        adm_plat = PlatformRole(id=new_uuid(), code="ADMIN", name="Admin", is_active=True)
        db_session.add(adm_plat)
    ap = AdminProfile(id=new_uuid(), user_id=buyer_principal.user_id, admin_status="ACTIVE")
    ar = AdminRole(id=new_uuid(), code="SUPER_ADMIN_TEST", name="Super Admin", is_active=True)
    perm = db_session.scalar(select(AdminPermission).where(AdminPermission.code == "payments.read"))
    if perm is None:
        perm = AdminPermission(id=new_uuid(), code="payments.read", module_name="payments", is_high_risk=False)
        db_session.add(perm)
    db_session.add_all([ap, ar])
    db_session.flush()
    db_session.add_all([
        UserRoleAssignment(
            id=new_uuid(),
            user_id=buyer_principal.user_id,
            platform_role_id=adm_plat.id,
            assignment_status="ACTIVE",
        ),
        AdminRolePermission(id=new_uuid(), admin_role_id=ar.id, admin_permission_id=perm.id),
        AdminUserRole(id=new_uuid(), admin_profile_id=ap.id, admin_role_id=ar.id, is_active=True),
    ])
    db_session.commit()

    admin_principal = load_principal_by_clerk_id(db_session, "user_2normalBuyer99")
    set_authenticated_principal(app, admin_principal)
    me = client.get("/api/v1/auth/me").json()
    assert me["is_admin"] is True
    assert "payments.read" in me["admin_permissions"]

    overview = client.get("/api/v1/admin/overview")
    assert overview.status_code == 200
    assert overview.json()["counts"]["users"] >= 1

    _set_clerk_claims(app, None)
    app.dependency_overrides.pop(get_current_principal, None)


def test_07_admin_password_login_allows_only_db_provisioned_admins_and_revocation_works(app_and_client, db_session):
    from sqlalchemy import select
    from app.core.admin_security import hash_admin_password
    from app.models.base import new_uuid
    from app.models.core_models import (
        AdminCredential,
        AdminPermission,
        AdminProfile,
        AdminRole,
        AdminRolePermission,
        AdminUserRole,
        PlatformRole,
        User,
        UserRoleAssignment,
    )

    app, client = app_and_client
    # Remove any dependency override so the REAL HS256 JWT + DB check runs end-to-end
    app.dependency_overrides.pop(get_current_principal, None)

    # 1. Unknown / non-admin email is rejected (401)
    r_unknown = client.post(
        "/api/v1/auth/admin-login",
        json={"email": "outsider@example.com", "password": "SomePassword123!"},
    )
    assert r_unknown.status_code == 401

    # 2. Provision one dedicated Admin directly in DB
    admin_user = User(
        id=new_uuid(),
        clerk_user_id="hl_admin_test_001",
        email="chief.admin@hunarlink.test",
        email_verified=True,
        first_name="Chief",
        last_name="Admin",
        display_name="Chief Admin",
        account_status="ACTIVE",
    )
    db_session.add(admin_user)
    db_session.flush()

    plat_role = db_session.scalar(select(PlatformRole).where(PlatformRole.code == "ADMIN"))
    if plat_role is None:
        plat_role = PlatformRole(id=new_uuid(), code="ADMIN", name="Admin", is_active=True)
        db_session.add(plat_role)
    ap = AdminProfile(id=new_uuid(), user_id=admin_user.id, admin_status="ACTIVE")
    ar = AdminRole(id=new_uuid(), code="SUPER_ADMIN_PW_TEST", name="Super Admin", is_active=True)
    perm = db_session.scalar(select(AdminPermission).where(AdminPermission.code == "payments.read"))
    if perm is None:
        perm = AdminPermission(id=new_uuid(), code="payments.read", module_name="payments", is_high_risk=False)
        db_session.add(perm)
    db_session.add_all([ap, ar])
    db_session.flush()

    secret_pw = "ValleyAdmin#2026!"
    cred = AdminCredential(
        id=new_uuid(),
        user_id=admin_user.id,
        email=admin_user.email,
        password_hash=hash_admin_password(secret_pw),
        is_active=True,
    )
    db_session.add_all([
        UserRoleAssignment(
            id=new_uuid(),
            user_id=admin_user.id,
            platform_role_id=plat_role.id,
            assignment_status="ACTIVE",
        ),
        AdminRolePermission(id=new_uuid(), admin_role_id=ar.id, admin_permission_id=perm.id),
        AdminUserRole(id=new_uuid(), admin_profile_id=ap.id, admin_role_id=ar.id, is_active=True),
        cred,
    ])
    db_session.commit()

    # 3. Wrong password -> 401
    r_bad = client.post(
        "/api/v1/auth/admin-login",
        json={"email": admin_user.email, "password": "WrongPassword!"},
    )
    assert r_bad.status_code == 401

    # 4. Correct email + password -> 200 + working HS256 Admin JWT
    r_ok = client.post(
        "/api/v1/auth/admin-login",
        json={"email": admin_user.email, "password": secret_pw},
    )
    assert r_ok.status_code == 200
    body = r_ok.json()
    token = body["access_token"]
    assert body["email"] == admin_user.email
    assert "payments.read" in body["admin_permissions"]

    # 5. Live DB Admin Overview works with real Bearer token & returns hashed credential row
    ov = client.get(
        "/api/v1/admin/overview",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ov.status_code == 200
    creds_list = ov.json()["admin_credentials"]
    assert len(creds_list) == 1
    assert creds_list[0]["email"] == admin_user.email
    assert creds_list[0]["password_hash"].startswith("pbkdf2_sha256$")
    assert secret_pw not in creds_list[0]["password_hash"]
    admin_row = next(u for u in ov.json()["users"] if u["email"] == admin_user.email)
    assert admin_row["onboarding_state"] == "ADMIN"

    # 6. Revoking admin credential immediately invalidates existing token (403)
    cred.is_active = False
    db_session.commit()
    ov_revoked = client.get(
        "/api/v1/admin/overview",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ov_revoked.status_code == 403


def test_08_standard_artisan_requires_card_image_stays_staged_until_admin_verifies(
    app_and_client, db_session
):
    """End-to-end verification of the Standard Artisan Card staging -> Admin approval flow."""
    from app.core.auth import load_principal_by_clerk_id
    from tests.conftest import seed_marketplace_entities

    app, client = app_and_client
    entities = seed_marketplace_entities(db_session)

    # 1. New Clerk artisan signs in -> synced directly into `users`
    _set_clerk_claims(app, {"sub": "user_2stdArtisanCard01"})
    sync = client.post(
        "/api/v1/auth/sync",
        json={
            "email": "velly.loom@example.com",
            "email_verified": True,
            "first_name": "Samyak",
            "last_name": "Bhalerao",
            "display_name": "Samyak Bhalerao",
            "requested_role": "artisan",
        },
    )
    assert sync.status_code == 200
    _set_clerk_claims(app, None)

    artisan_principal = load_principal_by_clerk_id(db_session, "user_2stdArtisanCard01")
    set_authenticated_principal(app, artisan_principal)

    # 2. Submitting `STANDARD` without an uploaded Artisan Card image returns clear 422
    missing_card = client.post(
        "/api/v1/auth/artisan-verification",
        json={
            "store_name": "Velly Loom",
            "craft_specialty": "pashmina",
            "workshop_district": "Srinagar",
            "verification_path": "STANDARD",
            "phone": "9419012345",
        },
    )
    assert missing_card.status_code == 422
    assert "Artisan Card" in missing_card.json()["detail"]

    # 3. Artisan uploads valid PNG Artisan Card image -> stored in `file_security_scans`
    valid_png = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\x18\xdd\x8d\xb0"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    up_resp = client.post(
        "/api/v1/guardrails/documents/upload",
        data={"owner_scope": "artisan_card"},
        files={"file": ("artisan_pehchan_card.png", valid_png, "image/png")},
    )
    assert up_resp.status_code == 201
    scan_id = up_resp.json()["scan_id"]

    # 4. Artisan submits Standard verification with `artisan_card_scan_id`
    sub_resp = client.post(
        "/api/v1/auth/artisan-verification",
        json={
            "store_name": "Velly Loom",
            "craft_specialty": "pashmina",
            "workshop_district": "Srinagar",
            "verification_path": "STANDARD",
            "artisan_card_scan_id": scan_id,
            "skill_description": "Handloom Pashmina weaving studio in Srinagar.",
            "phone": "9419012345",
        },
    )
    assert sub_resp.status_code == 201
    sub_body = sub_resp.json()
    app_id = sub_body["application_id"]
    seller_uuid = sub_body["seller_profile"]["seller_profile_id"]
    assert sub_body["application_status"] == "SUBMITTED"
    assert sub_body["seller_profile"]["verification_status"] == "SUBMITTED"
    assert sub_body["seller_profile"]["profile_status"] == "DRAFT"
    assert sub_body["seller_profile"]["verification_path"] == "NON_GI"

    # 5. Staged artisan is NOT yet in public `/api/v1/artisans` or `/api/v1/artisans/detail?id=`
    pub_list = client.get("/api/v1/artisans").json()
    assert all(a["seller_profile_id"] != seller_uuid for a in pub_list)
    assert client.get(f"/api/v1/artisans/detail?id={seller_uuid}").status_code == 404

    # 6. Admin opens `/api/v1/admin/overview`, sees the pending application + card scan_id,
    #    fetches the Artisan Card image bytes, and clicks Verify & Push Live (`APPROVE`)
    set_authenticated_principal(app, entities["admin_principal"])
    ov = client.get("/api/v1/admin/overview")
    assert ov.status_code == 200
    ov_data = ov.json()
    assert ov_data["counts"]["pending_applications"] >= 1
    staged_entry = next(a for a in ov_data["artisan_applications"] if a["id"] == app_id)
    assert staged_entry["store_name"] == "Velly Loom"
    assert staged_entry["artisan_card_scan_id"] == scan_id

    card_dl = client.get(f"/api/v1/guardrails/documents/{scan_id}")
    assert card_dl.status_code == 200
    assert card_dl.headers["content-type"] == "image/png"

    approve = client.post(
        f"/api/v1/admin/artisan-applications/{app_id}/decision",
        json={"decision": "APPROVE", "notes": "Pehchan Artisan Card verified."},
    )
    assert approve.status_code == 200
    assert approve.json()["verification_status"] == "APPROVED"
    assert approve.json()["profile_status"] == "ACTIVE"

    # 7. Artisan is NOW immediately live in `/api/v1/artisans` & `/artisan?id=<seller_uuid>`!
    pub_after = client.get("/api/v1/artisans").json()
    assert any(a["seller_profile_id"] == seller_uuid and a["store_name"] == "Velly Loom" for a in pub_after)
    detail_after = client.get(f"/api/v1/artisans/detail?id={seller_uuid}")
    assert detail_after.status_code == 200
    assert detail_after.json()["store_name"] == "Velly Loom"

    app.dependency_overrides.pop(get_current_principal, None)


def test_09_existing_user_cannot_reregister_and_unverified_artisan_flagged_until_admin_approves(app_and_client, db_session):
    from sqlalchemy import select
    from app.models.core_models import SellerProfile
    from tests.conftest import seed_marketplace_entities, set_authenticated_principal

    app, client = app_and_client
    app.dependency_overrides.pop(get_current_principal, None)

    # 1. Brand-new email does not exist yet
    chk0 = client.post("/api/v1/auth/check-account", json={"email": "new.artisan@kashmir.example"})
    assert chk0.status_code == 200
    assert chk0.json()["exists"] is False

    # 2. First-time signup succeeds and marks artisan as NOT YET VERIFIED
    _set_clerk_claims(app, {"sub": "user_artisan_new_001", "email": "new.artisan@kashmir.example"})
    reg = client.post(
        "/api/v1/auth/sync",
        json={
            "email": "new.artisan@kashmir.example",
            "email_verified": True,
            "first_name": "Bilal",
            "last_name": "Dar",
            "requested_role": "artisan",
            "auth_mode": "signup",
        },
    )
    assert reg.status_code == 200
    rbody = reg.json()
    assert rbody["is_new_user"] is True
    assert rbody["is_artisan"] is True
    assert rbody["artisan_verified"] is False
    assert rbody["seller_profile"] is None

    # 3. Account check now reports exists=True & artisan_verified=False
    chk1 = client.post("/api/v1/auth/check-account", json={"email": "new.artisan@kashmir.example"})
    assert chk1.status_code == 200
    assert chk1.json()["exists"] is True
    assert chk1.json()["is_artisan"] is True
    assert chk1.json()["artisan_verified"] is False

    # 4. Trying to REGISTER AGAIN (auth_mode="signup") is BLOCKED with 409 Conflict!
    rereg = client.post(
        "/api/v1/auth/sync",
        json={
            "email": "new.artisan@kashmir.example",
            "email_verified": True,
            "first_name": "Bilal",
            "requested_role": "artisan",
            "auth_mode": "signup",
        },
    )
    assert rereg.status_code == 409
    assert "already exists" in rereg.json()["detail"].lower()

    # 5. Logging in (auth_mode="signin") succeeds, still artisan_verified=False -> must land on Verify page first!
    login = client.post(
        "/api/v1/auth/sync",
        json={
            "email": "new.artisan@kashmir.example",
            "email_verified": True,
            "first_name": "Bilal",
            "requested_role": "artisan",
            "auth_mode": "signin",
        },
    )
    assert login.status_code == 200
    assert login.json()["artisan_verified"] is False

    # 6. Artisan submits verification -> status=SUBMITTED (still not APPROVED until Admin verifies)
    from app.core.auth import AuthenticatedPrincipal

    artisan_user_id = rbody["user_id"]
    set_authenticated_principal(
        app,
        AuthenticatedPrincipal(
            user_id=artisan_user_id,
            clerk_user_id="user_artisan_new_001",
            email="new.artisan@kashmir.example",
            account_status="ACTIVE",
            roles=frozenset({"DIRECT_SELLER", "CUSTOMER"}),
        ),
    )
    sub = client.post(
        "/api/v1/auth/artisan-verification",
        json={
            "store_name": "Dar Heritage Looms",
            "craft_specialty": "Pashmina Textiles",
            "workshop_district": "Srinagar",
            "verification_path": "GI",
            "claimed_gi_code": "GI-JK-PASH-9910",
        },
    )
    assert sub.status_code == 201
    seller_id = sub.json()["seller_profile"]["seller_profile_id"]
    assert sub.json()["seller_profile"]["verification_status"] == "SUBMITTED"

    chk2 = client.post("/api/v1/auth/check-account", json={"email": "new.artisan@kashmir.example"})
    assert chk2.json()["artisan_verified"] is False
    assert chk2.json()["artisan_verification_status"] == "SUBMITTED"

    # 7. Admin approves the artisan -> DB sets APPROVED + ACTIVE -> artisan_verified becomes True!
    entities = seed_marketplace_entities(db_session)
    set_authenticated_principal(app, entities["admin_principal"])
    approve = client.post(
        f"/api/v1/admin/sellers/{seller_id}/verify",
        json={"decision": "APPROVED"},
    )
    assert approve.status_code == 200
    assert approve.json()["verification_status"] == "APPROVED"
    assert approve.json()["profile_status"] == "ACTIVE"

    chk3 = client.post("/api/v1/auth/check-account", json={"email": "new.artisan@kashmir.example"})
    assert chk3.json()["artisan_verified"] is True
    assert chk3.json()["artisan_verification_status"] == "APPROVED"

    _set_clerk_claims(app, None)
    app.dependency_overrides.pop(get_current_principal, None)


def test_09_unregistered_oauth_user_or_artisan_blocked_on_signin_with_404(app_and_client, db_session):
    from sqlalchemy import select
    from app.models.core_models import User

    app, client = app_and_client
    app.dependency_overrides.pop(get_current_principal, None)

    # 1. Brand-new Google buyer clicks "Sign in with Google" (never registered in DB) -> 404!
    _set_clerk_claims(app, {"sub": "user_unreg_google_buyer", "email": "ghost.buyer@gmail.com"})
    r_buyer = client.post(
        "/api/v1/auth/sync",
        json={
            "email": "ghost.buyer@gmail.com",
            "email_verified": True,
            "first_name": "Ghost",
            "requested_role": "buyer",
            "auth_mode": "signin",
        },
    )
    assert r_buyer.status_code == 404
    assert "register first" in r_buyer.json()["detail"].lower()
    assert db_session.scalar(select(User).where(User.email == "ghost.buyer@gmail.com")) is None

    # 2. Brand-new Google artisan clicks "Sign in with Google" (never registered in DB) -> 404!
    _set_clerk_claims(app, {"sub": "user_unreg_google_artisan", "email": "ghost.artisan@gmail.com"})
    r_artisan = client.post(
        "/api/v1/auth/sync",
        json={
            "email": "ghost.artisan@gmail.com",
            "email_verified": True,
            "first_name": "Ghost",
            "requested_role": "artisan",
            "auth_mode": "signin",
        },
    )
    assert r_artisan.status_code == 404
    assert db_session.scalar(select(User).where(User.email == "ghost.artisan@gmail.com")) is None

    # 3. After registering (auth_mode="signup"), subsequent Sign In (auth_mode="signin") succeeds!
    r_reg = client.post(
        "/api/v1/auth/sync",
        json={
            "email": "ghost.artisan@gmail.com",
            "email_verified": True,
            "first_name": "Ghost",
            "requested_role": "artisan",
            "auth_mode": "signup",
        },
    )
    assert r_reg.status_code == 200
    assert r_reg.json()["is_new_user"] is True
    assert r_reg.json()["artisan_verified"] is False

    r_login = client.post(
        "/api/v1/auth/sync",
        json={
            "email": "ghost.artisan@gmail.com",
            "email_verified": True,
            "first_name": "Ghost",
            "requested_role": "artisan",
            "auth_mode": "signin",
        },
    )
    assert r_login.status_code == 200
    assert r_login.json()["is_new_user"] is False
    assert r_login.json()["is_artisan"] is True
    assert r_login.json()["artisan_verified"] is False

    _set_clerk_claims(app, None)


def test_10_strict_role_isolation_blocks_cross_role_login_and_tracks_logs(
    app_and_client, db_session
):
    from app.core.auth import load_principal_by_clerk_id
    from app.models.core_models import UserLoginLog

    app, client = app_and_client
    app.dependency_overrides.pop(get_current_principal, None)

    # 1. Register a pure Buyer (CUSTOMER) — granted ONLY CUSTOMER, event=REGISTER, last_login_at=None
    _set_clerk_claims(app, {"sub": "user_iso_buyer_01", "email": "iso.buyer@example.com"})
    reg_b = client.post(
        "/api/v1/auth/sync",
        json={
            "email": "iso.buyer@example.com",
            "email_verified": True,
            "first_name": "Meera",
            "requested_role": "buyer",
            "auth_mode": "signup",
        },
    )
    assert reg_b.status_code == 200
    assert reg_b.json()["roles"] == ["CUSTOMER"]
    assert reg_b.json()["last_login_at"] is None

    # 2. Register a pure Artisan (DIRECT_SELLER) — granted ONLY DIRECT_SELLER (not CUSTOMER)
    _set_clerk_claims(app, {"sub": "user_iso_artisan_01", "email": "iso.artisan@example.com"})
    reg_a = client.post(
        "/api/v1/auth/sync",
        json={
            "email": "iso.artisan@example.com",
            "email_verified": True,
            "first_name": "Tariq",
            "requested_role": "artisan",
            "auth_mode": "signup",
        },
    )
    assert reg_a.status_code == 200
    assert reg_a.json()["roles"] == ["DIRECT_SELLER"]
    assert reg_a.json()["last_login_at"] is None

    # 3. check-account reports role_conflict=True on mismatched roles
    chk_b_as_art = client.post(
        "/api/v1/auth/check-account",
        json={"email": "iso.buyer@example.com", "requested_role": "artisan"},
    )
    assert chk_b_as_art.status_code == 200
    assert chk_b_as_art.json()["role_conflict"] is True
    assert chk_b_as_art.json()["has_requested_role"] is False
    assert "buyer" in chk_b_as_art.json()["conflict_message"].lower()

    chk_a_as_buy = client.post(
        "/api/v1/auth/check-account",
        json={"email": "iso.artisan@example.com", "requested_role": "buyer"},
    )
    assert chk_a_as_buy.status_code == 200
    assert chk_a_as_buy.json()["role_conflict"] is True
    assert "artisan" in chk_a_as_buy.json()["conflict_message"].lower()

    # 4. Cross-role /auth/sync sign-in is blocked with 403 Forbidden
    _set_clerk_claims(app, {"sub": "user_iso_buyer_01", "email": "iso.buyer@example.com"})
    cross_1 = client.post(
        "/api/v1/auth/sync",
        json={
            "email": "iso.buyer@example.com",
            "email_verified": True,
            "first_name": "Meera",
            "requested_role": "artisan",
            "auth_mode": "signin",
        },
    )
    assert cross_1.status_code == 403

    # Buyer cannot submit /auth/artisan-verification
    buyer_principal = load_principal_by_clerk_id(db_session, "user_iso_buyer_01")
    set_authenticated_principal(app, buyer_principal)
    forbid_ver = client.post(
        "/api/v1/auth/artisan-verification",
        json={
            "store_name": "Fake Studio",
            "craft_specialty": "Pashmina",
            "workshop_district": "Srinagar",
            "verification_path": "GI",
            "claimed_gi_code": "GI-JK-PASH-1111",
        },
    )
    assert forbid_ver.status_code == 403
    app.dependency_overrides.pop(get_current_principal, None)

    _set_clerk_claims(app, {"sub": "user_iso_artisan_01", "email": "iso.artisan@example.com"})
    cross_2 = client.post(
        "/api/v1/auth/sync",
        json={
            "email": "iso.artisan@example.com",
            "email_verified": True,
            "first_name": "Tariq",
            "requested_role": "buyer",
            "auth_mode": "signin",
        },
    )
    assert cross_2.status_code == 403

    # 5. Same-role sign-in succeeds, updates last_login_at, and logs LOGIN event
    _set_clerk_claims(app, {"sub": "user_iso_buyer_01", "email": "iso.buyer@example.com"})
    login_b = client.post(
        "/api/v1/auth/sync",
        json={
            "email": "iso.buyer@example.com",
            "email_verified": True,
            "first_name": "Meera",
            "requested_role": "buyer",
            "auth_mode": "signin",
        },
    )
    assert login_b.status_code == 200
    assert login_b.json()["last_login_at"] is not None

    logs = list(
        db_session.scalars(
            select(UserLoginLog).order_by(UserLoginLog.created_at.asc())
        ).all()
    )
    buyer_events = [l.auth_event_type for l in logs if l.email == "iso.buyer@example.com"]
    artisan_events = [l.auth_event_type for l in logs if l.email == "iso.artisan@example.com"]
    assert buyer_events == ["REGISTER", "LOGIN"]
    assert artisan_events == ["REGISTER"]
    _set_clerk_claims(app, None)


def test_11_admin_overview_and_users_by_role_separate_registered_vs_logged_in(
    app_and_client, db_session
):
    from tests.conftest import seed_marketplace_entities

    app, client = app_and_client
    entities = seed_marketplace_entities(db_session)

    # Register Buyer A (logs in) and Buyer B (registers only, never logs in)
    _set_clerk_claims(app, {"sub": "user_sep_b1", "email": "buyer.active@example.com"})
    assert (
        client.post(
            "/api/v1/auth/sync",
            json={
                "email": "buyer.active@example.com",
                "first_name": "ActiveBuyer",
                "requested_role": "buyer",
                "auth_mode": "signup",
            },
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/auth/sync",
            json={
                "email": "buyer.active@example.com",
                "first_name": "ActiveBuyer",
                "requested_role": "buyer",
                "auth_mode": "signin",
            },
        ).status_code
        == 200
    )

    _set_clerk_claims(app, {"sub": "user_sep_b2", "email": "buyer.regonly@example.com"})
    assert (
        client.post(
            "/api/v1/auth/sync",
            json={
                "email": "buyer.regonly@example.com",
                "first_name": "RegOnlyBuyer",
                "requested_role": "buyer",
                "auth_mode": "signup",
            },
        ).status_code
        == 200
    )

    # Register Artisan A (registers only, never logs in)
    _set_clerk_claims(app, {"sub": "user_sep_a1", "email": "artisan.regonly@example.com"})
    assert (
        client.post(
            "/api/v1/auth/sync",
            json={
                "email": "artisan.regonly@example.com",
                "first_name": "RegOnlyArtisan",
                "requested_role": "artisan",
                "auth_mode": "signup",
            },
        ).status_code
        == 200
    )
    _set_clerk_claims(app, None)

    set_authenticated_principal(app, entities["admin_principal"])
    ov = client.get("/api/v1/admin/overview")
    assert ov.status_code == 200
    data = ov.json()
    rd = data["role_directory"]

    buyer_logged_emails = {u["email"] for u in rd["buyers"]["logged_in"]}
    buyer_never_emails = {u["email"] for u in rd["buyers"]["never_logged_in"]}
    assert "buyer.active@example.com" in buyer_logged_emails
    assert "buyer.regonly@example.com" in buyer_never_emails
    assert "artisan.regonly@example.com" not in {
        u["email"] for u in rd["buyers"]["registered"]
    }

    artisan_never_emails = {u["email"] for u in rd["artisans"]["never_logged_in"]}
    assert "artisan.regonly@example.com" in artisan_never_emails

    # Dedicated endpoint filter test
    res_logged_buyers = client.get(
        "/api/v1/admin/users-by-role?role_code=CUSTOMER&activity=logged_in"
    )
    assert res_logged_buyers.status_code == 200
    logged_emails = {u["email"] for u in res_logged_buyers.json()["groups"]["buyers"]["users"]}
    assert "buyer.active@example.com" in logged_emails
    assert "buyer.regonly@example.com" not in logged_emails

    res_regonly_buyers = client.get(
        "/api/v1/admin/users-by-role?role_code=CUSTOMER&activity=never_logged_in"
    )
    assert res_regonly_buyers.status_code == 200
    regonly_emails = {u["email"] for u in res_regonly_buyers.json()["groups"]["buyers"]["users"]}
    assert "buyer.regonly@example.com" in regonly_emails
    assert "buyer.active@example.com" not in regonly_emails

    res_search = client.get("/api/v1/admin/users-by-role?q=buyer.active")
    assert res_search.status_code == 200
    assert res_search.json()["q"] == "buyer.active"
    searched_emails = {u["email"] for u in res_search.json()["groups"]["buyers"]["users"]}
    assert searched_emails == {"buyer.active@example.com"}

    app.dependency_overrides.pop(get_current_principal, None)


def test_12_self_delete_account_anonymizes_wipes_pii_and_allows_fresh_reregistration(
    app_and_client, db_session
):
    from decimal import Decimal
    from fastapi import HTTPException
    import pytest
    from app.core.auth import load_principal_by_clerk_id
    from app.models.core_models import (
        RetailOrder,
        UserAddress,
        UserLoginLog,
        UserRoleAssignment,
    )
    from tests.conftest import seed_marketplace_entities

    app, client = app_and_client
    entities = seed_marketplace_entities(db_session)

    # 1. Register & sign in as a buyer, create address, and attach a completed DELIVERED order
    _set_clerk_claims(app, {"sub": "user_self_del_01", "email": "self.del@example.com"})
    reg = client.post(
        "/api/v1/auth/sync",
        json={
            "email": "self.del@example.com",
            "email_verified": True,
            "first_name": "Aarav",
            "last_name": "Kapoor",
            "phone": "+91 9811100001",
            "requested_role": "buyer",
            "auth_mode": "signup",
        },
    )
    assert reg.status_code == 200
    old_user_id = reg.json()["user_id"]

    principal = load_principal_by_clerk_id(db_session, "user_self_del_01")
    set_authenticated_principal(app, principal)

    addr = client.post(
        "/api/v1/auth/addresses",
        json={
            "recipient_name": "Aarav Kapoor",
            "recipient_phone": "+91 9811100001",
            "line1": "12 Dal Lake Road",
            "city": "Srinagar",
            "state_province": "Jammu and Kashmir",
            "postal_code": "190001",
        },
    )
    assert addr.status_code == 201

    completed_order = RetailOrder(
        order_number="HL-TEST-DELIVERED-01",
        customer_user_id=old_user_id,
        shipping_address_snapshot_json={"city": "Srinagar"},
        currency_code="INR",
        subtotal_amount=Decimal("2500.00"),
        total_amount=Decimal("2500.00"),
        payment_status="PAID",
        fulfilment_status="DELIVERED",
    )
    db_session.add(completed_order)
    db_session.commit()

    # 2. Delete own account -> 200 OK
    del_resp = client.post(
        "/api/v1/auth/me/delete",
        json={"reason": "No longer needed"},
    )
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] is True
    assert del_resp.json()["anonymized"] is True

    app.dependency_overrides.pop(get_current_principal, None)
    db_session.expire_all()

    # 3. Verify PII wiped, roles revoked, addresses & login logs deleted, historical order intact
    old_user = db_session.scalar(select(User).where(User.id == old_user_id))
    assert old_user is not None
    assert old_user.account_status == "DEACTIVATED"
    assert old_user.email == f"deleted+{old_user_id}@deleted.hunarlink.local"
    assert old_user.clerk_user_id == f"deleted_{old_user_id}"
    assert old_user.phone is None
    assert old_user.first_name == "Deleted"

    assert db_session.scalars(select(UserAddress).where(UserAddress.user_id == old_user_id)).all() == []
    assert db_session.scalars(select(UserLoginLog).where(UserLoginLog.user_id == old_user_id)).all() == []
    uras = db_session.scalars(
        select(UserRoleAssignment).where(UserRoleAssignment.user_id == old_user_id)
    ).all()
    assert all(u.assignment_status == "REVOKED" for u in uras)
    assert db_session.scalar(select(RetailOrder).where(RetailOrder.order_number == "HL-TEST-DELIVERED-01")) is not None

    # 4. Old identity cannot authenticate or sign in
    with pytest.raises(HTTPException) as exc_info:
        load_principal_by_clerk_id(db_session, "user_self_del_01")
    assert exc_info.value.status_code == 401

    chk = client.post(
        "/api/v1/auth/check-account",
        json={"email": "self.del@example.com", "requested_role": "buyer"},
    )
    assert chk.status_code == 200
    assert chk.json()["exists"] is False

    _set_clerk_claims(app, {"sub": "user_self_del_02", "email": "self.del@example.com"})
    old_signin = client.post(
        "/api/v1/auth/sync",
        json={
            "email": "self.del@example.com",
            "first_name": "Aarav",
            "requested_role": "buyer",
            "auth_mode": "signin",
        },
    )
    assert old_signin.status_code == 404

    # 5. Fresh re-registration with the same email succeeds cleanly as a brand-new user
    new_reg = client.post(
        "/api/v1/auth/sync",
        json={
            "email": "self.del@example.com",
            "email_verified": True,
            "first_name": "Aarav",
            "requested_role": "buyer",
            "auth_mode": "signup",
        },
    )
    assert new_reg.status_code == 200
    assert new_reg.json()["is_new_user"] is True
    assert new_reg.json()["user_id"] != old_user_id

    # Admin overview excludes anonymized account and reflects only active accounts
    _set_clerk_claims(app, None)
    set_authenticated_principal(app, entities["admin_principal"])
    ov = client.get("/api/v1/admin/overview").json()
    assert ov["counts"]["deactivated_users"] >= 1
    buyer_emails = {u["email"] for u in ov["role_directory"]["buyers"]["registered"]}
    assert f"deleted+{old_user_id}@deleted.hunarlink.local" not in buyer_emails
    assert "self.del@example.com" in buyer_emails

    app.dependency_overrides.pop(get_current_principal, None)


def test_13_self_delete_blocked_for_active_orders_and_admins(app_and_client, db_session):
    from decimal import Decimal
    from app.core.auth import load_principal_by_clerk_id
    from app.models.core_models import RetailOrder
    from tests.conftest import seed_marketplace_entities

    app, client = app_and_client
    entities = seed_marketplace_entities(db_session)

    # 1. Admin self-delete is strictly forbidden (403)
    set_authenticated_principal(app, entities["admin_principal"])
    admin_del = client.post("/api/v1/auth/me/delete", json={})
    assert admin_del.status_code == 403
    app.dependency_overrides.pop(get_current_principal, None)

    # 2. Buyer with an active CONFIRMED order cannot delete account (409)
    _set_clerk_claims(app, {"sub": "user_active_order_01", "email": "active.order@example.com"})
    reg = client.post(
        "/api/v1/auth/sync",
        json={
            "email": "active.order@example.com",
            "first_name": "Zoya",
            "requested_role": "buyer",
            "auth_mode": "signup",
        },
    )
    assert reg.status_code == 200
    uid = reg.json()["user_id"]
    _set_clerk_claims(app, None)

    db_session.add(
        RetailOrder(
            order_number="HL-TEST-ACTIVE-99",
            customer_user_id=uid,
            shipping_address_snapshot_json={"city": "Delhi"},
            currency_code="INR",
            subtotal_amount=Decimal("4200.00"),
            total_amount=Decimal("4200.00"),
            payment_status="PAID",
            fulfilment_status="CONFIRMED",
        )
    )
    db_session.commit()

    principal = load_principal_by_clerk_id(db_session, "user_active_order_01")
    set_authenticated_principal(app, principal)
    blocked = client.post("/api/v1/auth/me/delete", json={})
    assert blocked.status_code == 409
    assert "HL-TEST-ACTIVE-99" in blocked.json()["detail"]

    still_active = db_session.scalar(select(User).where(User.id == uid))
    assert still_active.account_status == "ACTIVE"
    app.dependency_overrides.pop(get_current_principal, None)


def test_14_self_delete_server_side_clerk_password_verification(
    app_and_client, db_session, monkeypatch
):
    from pydantic import SecretStr
    from app.core.auth import load_principal_by_clerk_id
    from app.core.config import get_settings

    app, client = app_and_client

    _set_clerk_claims(app, {"sub": "user_pwd_del_01", "email": "pwd.del@example.com"})
    reg = client.post(
        "/api/v1/auth/sync",
        json={
            "email": "pwd.del@example.com",
            "first_name": "Rohan",
            "requested_role": "buyer",
            "auth_mode": "signup",
        },
    )
    assert reg.status_code == 200
    uid = reg.json()["user_id"]
    _set_clerk_claims(app, None)

    settings = get_settings()
    monkeypatch.setattr(settings, "clerk_secret_key", SecretStr("sk_test_mock_secret"))
    app.dependency_overrides[get_settings] = lambda: settings

    class _MockResp:
        def __init__(self, status_code, data=None):
            self.status_code = status_code
            self._data = data or {}

        def json(self):
            return self._data

    def _fake_post(url, headers=None, json=None, timeout=None):
        if json and json.get("password") == "RightCurrentPassword#2026":
            return _MockResp(200, {"verified": True})
        return _MockResp(422, {"errors": [{"code": "form_password_incorrect"}]})

    deleted_calls = []

    def _fake_delete(url, headers=None, timeout=None):
        deleted_calls.append(url)
        return _MockResp(200, {"deleted": True})

    monkeypatch.setattr("app.modules.auth.router.httpx.post", _fake_post)
    monkeypatch.setattr("app.modules.auth.router.httpx.delete", _fake_delete)

    principal = load_principal_by_clerk_id(db_session, "user_pwd_del_01")
    set_authenticated_principal(app, principal)

    # Wrong current password -> 401 and account remains ACTIVE
    bad = client.post(
        "/api/v1/auth/me/delete",
        json={"current_password": "WrongPassword!"},
    )
    assert bad.status_code == 401
    assert db_session.scalar(select(User).where(User.id == uid)).account_status == "ACTIVE"
    assert deleted_calls == []

    # Correct current password -> 200 and Clerk delete called
    good = client.post(
        "/api/v1/auth/me/delete",
        json={"current_password": "RightCurrentPassword#2026"},
    )
    assert good.status_code == 200
    assert good.json()["clerk_deleted"] is True
    assert deleted_calls == ["https://api.clerk.com/v1/users/user_pwd_del_01"]

    app.dependency_overrides.pop(get_current_principal, None)
    app.dependency_overrides.pop(get_settings, None)


def test_15_admin_delete_user_cleans_db_and_deletes_clerk_automatically(
    app_and_client, db_session, monkeypatch
):
    from pydantic import SecretStr
    from app.core.auth import AuthenticatedPrincipal, load_principal_by_clerk_id
    from app.core.config import get_settings
    from app.models.core_models import SellerProfile, UserAddress, UserLoginLog

    app, client = app_and_client

    # 1. Register a Buyer + add an address & a LOGIN event
    _set_clerk_claims(app, {"sub": "user_admin_del_b01", "email": "admin.del.buyer@example.com"})
    reg_b = client.post(
        "/api/v1/auth/sync",
        json={
            "email": "admin.del.buyer@example.com",
            "first_name": "Karan",
            "requested_role": "buyer",
            "auth_mode": "signup",
        },
    )
    assert reg_b.status_code == 200
    buyer_uid = reg_b.json()["user_id"]

    # Login event
    assert (
        client.post(
            "/api/v1/auth/sync",
            json={
                "email": "admin.del.buyer@example.com",
                "first_name": "Karan",
                "requested_role": "buyer",
                "auth_mode": "signin",
            },
        ).status_code
        == 200
    )
    _set_clerk_claims(app, None)

    buyer_principal = load_principal_by_clerk_id(db_session, "user_admin_del_b01")
    set_authenticated_principal(app, buyer_principal)
    assert (
        client.post(
            "/api/v1/auth/addresses",
            json={
                "address_label": "HOME",
                "recipient_name": "Karan",
                "recipient_phone": "9999999999",
                "line1": "10 Boulevard Rd",
                "city": "Srinagar",
                "state_province": "Jammu and Kashmir",
                "postal_code": "190001",
            },
        ).status_code
        == 201
    )

    # Non-admin cannot delete via admin endpoint
    forbid = client.delete(f"/api/v1/admin/users/{buyer_uid}")
    assert forbid.status_code == 403
    app.dependency_overrides.pop(get_current_principal, None)

    # 2. Register an Artisan with a SellerProfile
    _set_clerk_claims(app, {"sub": "user_admin_del_a01", "email": "admin.del.artisan@example.com"})
    reg_a = client.post(
        "/api/v1/auth/sync",
        json={
            "email": "admin.del.artisan@example.com",
            "first_name": "Farooq",
            "requested_role": "artisan",
            "auth_mode": "signup",
        },
    )
    assert reg_a.status_code == 200
    artisan_uid = reg_a.json()["user_id"]
    _set_clerk_claims(app, None)
    db_session.add(
        SellerProfile(
            user_id=artisan_uid,
            store_name="Farooq Test Studio",
            store_slug="farooq-test-studio",
            craft_specialty="Papier-Mache",
            workshop_district="Srinagar",
            verification_path="GI",
            verification_status="APPROVED",
            profile_status="ACTIVE",
        )
    )
    db_session.commit()

    # 3. Mock Clerk secret & HTTP calls for automatic Clerk deletion
    settings = get_settings()
    monkeypatch.setattr(settings, "clerk_secret_key", SecretStr("sk_test_admin_del"))
    app.dependency_overrides[get_settings] = lambda: settings

    class _MockResp:
        def __init__(self, status_code, data=None):
            self.status_code = status_code
            self._data = data or []

        def json(self):
            return self._data

    deleted_urls = []

    def _fake_get(url, headers=None, params=None, timeout=None):
        return _MockResp(200, [])

    def _fake_delete(url, headers=None, timeout=None):
        deleted_urls.append(url)
        return _MockResp(200, {"deleted": True})

    monkeypatch.setattr("app.modules.auth.deletion.httpx.get", _fake_get)
    monkeypatch.setattr("app.modules.auth.deletion.httpx.delete", _fake_delete)

    admin_principal = AuthenticatedPrincipal(
        user_id="00000000-0000-0000-0000-000000000099",
        clerk_user_id="hl_admin_test_99",
        email="ops.admin@hunarlink.in",
        account_status="ACTIVE",
        roles=frozenset({"ADMIN"}),
        admin_permissions=frozenset({"payments.read", "guardrails.decide"}),
        is_active_admin=True,
    )
    set_authenticated_principal(app, admin_principal)

    # Delete Buyer via POST alias
    del_b = client.post(
        f"/api/v1/admin/users/{buyer_uid}/delete",
        json={"reason": "Cleanup test buyer"},
    )
    assert del_b.status_code == 200
    assert del_b.json()["deleted"] is True
    assert del_b.json()["clerk_deleted"] is True
    assert "https://api.clerk.com/v1/users/user_admin_del_b01" in deleted_urls

    # Delete Artisan via REST DELETE
    del_a = client.delete(f"/api/v1/admin/users/{artisan_uid}")
    assert del_a.status_code == 200
    assert del_a.json()["deleted"] is True
    assert del_a.json()["clerk_deleted"] is True
    assert "https://api.clerk.com/v1/users/user_admin_del_a01" in deleted_urls

    # Verify DB cleanup + Admin overview hides both users and seller profile
    assert list(db_session.scalars(select(UserAddress).where(UserAddress.user_id == buyer_uid)).all()) == []
    assert list(db_session.scalars(select(UserLoginLog).where(UserLoginLog.user_id == buyer_uid)).all()) == []
    sp = db_session.scalar(select(SellerProfile).where(SellerProfile.user_id == artisan_uid))
    assert sp.profile_status == "TERMINATED"

    ov = client.get("/api/v1/admin/overview")
    assert ov.status_code == 200
    ov_data = ov.json()
    active_ids = {u["id"] for u in ov_data["users"]}
    assert buyer_uid not in active_ids
    assert artisan_uid not in active_ids
    assert all(s["id"] != sp.id for s in ov_data["sellers"])

    # Original emails are completely free for fresh registration
    chk = client.post("/api/v1/auth/check-account", json={"email": "admin.del.buyer@example.com"})
    assert chk.status_code == 200
    assert chk.json()["exists"] is False

    app.dependency_overrides.pop(get_current_principal, None)
    app.dependency_overrides.pop(get_settings, None)


def test_16_cli_purge_clean_user_and_orphaned_clerk_cleanup(
    db_session, monkeypatch
):
    from app.models.core_models import PlatformRole, UserRoleAssignment
    from app.modules.auth.deletion import delete_clerk_account, execute_user_deletion

    # 1. User with NO audit_logs or order history -> cleanly purged from `users`
    role = db_session.scalar(select(PlatformRole).where(PlatformRole.code == "CUSTOMER"))
    if role is None:
        role = PlatformRole(code="CUSTOMER", name="Retail Customer", is_active=True)
        db_session.add(role)
        db_session.flush()

    clean_user = User(
        clerk_user_id="user_clean_purge_01",
        email="clean.purge@example.com",
        first_name="Amaan",
        display_name="Amaan",
        account_status="ACTIVE",
    )
    db_session.add(clean_user)
    db_session.flush()
    db_session.add(
        UserRoleAssignment(
            user_id=clean_user.id,
            platform_role_id=role.id,
            assignment_status="ACTIVE",
        )
    )
    db_session.commit()
    clean_uid = clean_user.id

    class _MockResp:
        def __init__(self, status_code, data=None):
            self.status_code = status_code
            self._data = data or []

        def json(self):
            return self._data

    deleted_urls = []

    def _fake_get(url, headers=None, params=None, timeout=None):
        if params and params.get("email_address") == "orphan@example.com":
            return _MockResp(200, [{"id": "user_orphan_clerk_99"}])
        return _MockResp(200, [])

    def _fake_delete(url, headers=None, timeout=None):
        deleted_urls.append(url)
        return _MockResp(200, {"deleted": True})

    monkeypatch.setattr("app.modules.auth.deletion.httpx.get", _fake_get)
    monkeypatch.setattr("app.modules.auth.deletion.httpx.delete", _fake_delete)

    res = execute_user_deletion(
        db_session,
        user=clean_user,
        actor_user_id=None,
        actor_role="ADMIN",
        reason="CLI purge",
        clerk_secret="sk_test_cli",
        allow_purge_if_clean=True,
        audit_action="CLI_USER_DELETED",
        self_delete_mode=False,
    )
    assert res.purged is True
    assert res.clerk_deleted is True
    assert db_session.scalar(select(User).where(User.id == clean_uid)) is None
    assert "https://api.clerk.com/v1/users/user_clean_purge_01" in deleted_urls

    # 2. Orphaned Clerk user (row already deleted from DB) -> found by email and deleted automatically
    ok, cnt = delete_clerk_account(
        None,
        "orphan@example.com",
        "sk_test_cli",
        also_search_email=True,
    )
    assert ok is True
    assert cnt == 1
    assert "https://api.clerk.com/v1/users/user_orphan_clerk_99" in deleted_urls

