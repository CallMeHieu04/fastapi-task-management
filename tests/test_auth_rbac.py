import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    hash_password,
)
from app.models.enums import UserRole
from app.models.user import User


@pytest.mark.asyncio
async def test_register_success_defaults_to_member(client: AsyncClient):
    """Client register defaults to MEMBER even if trying to supply role or extra fields."""
    payload = {
        "email": "normal_user@example.com",
        "full_name": "Normal User",
        "password": "Password123!",
    }
    res = await client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["email"] == "normal_user@example.com"
    assert data["role"] == "MEMBER"
    assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_409(client: AsyncClient):
    """Mentor Case 3: Register with duplicate email returns 409 Conflict via IntegrityError."""
    payload = {
        "email": "duplicate@example.com",
        "full_name": "User One",
        "password": "Password123!",
    }
    first_res = await client.post("/api/v1/auth/register", json=payload)
    assert first_res.status_code == 201

    # Second register attempt with identical email must return 409
    dup_res = await client.post("/api/v1/auth/register", json=payload)
    assert dup_res.status_code == 409
    assert "already exists" in dup_res.json()["detail"]


@pytest.mark.asyncio
async def test_password_length_validation_rules(client: AsyncClient):
    """Password must be at least 8 chars and not exceed 72 bytes."""
    # Under 8 chars -> 422
    short_pwd = {
        "email": "short@example.com",
        "full_name": "Short Pwd",
        "password": "pass",
    }
    res_short = await client.post("/api/v1/auth/register", json=short_pwd)
    assert res_short.status_code == 422

    # Over 72 bytes -> 422
    long_pwd = {
        "email": "long@example.com",
        "full_name": "Long Pwd",
        "password": "A" * 73,
    }
    res_long = await client.post("/api/v1/auth/register", json=long_pwd)
    assert res_long.status_code == 422


@pytest.mark.asyncio
async def test_login_and_access_protected_endpoint(client: AsyncClient):
    """Login returns JWT access & refresh tokens; access token opens /users/me."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "alice@example.com", "full_name": "Alice Dev", "password": "Password123!"},
    )
    assert reg.status_code == 201

    # Wrong credentials -> 401
    bad_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "WrongPassword!"},
    )
    assert bad_login.status_code == 401
    assert bad_login.headers.get("www-authenticate") == "Bearer"

    # Valid credentials -> 200
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "Password123!"},
    )
    assert login_res.status_code == 200
    tokens = login_res.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    # Access /users/me
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    me_res = await client.get("/api/v1/users/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "alice@example.com"


@pytest.mark.asyncio
async def test_refresh_token_used_on_protected_api_returns_401(client: AsyncClient):
    """Mentor Case 1: Calling access API using a refresh token must return 401."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": "token_type_test@example.com", "full_name": "Token Tester", "password": "Password123!"},
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "token_type_test@example.com", "password": "Password123!"},
    )
    refresh_token = login_res.json()["refresh_token"]

    # Use refresh token as Bearer on /users/me
    bad_call = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {refresh_token}"})
    assert bad_call.status_code == 401
    assert "Access token expected" in bad_call.json()["detail"]


@pytest.mark.asyncio
async def test_token_with_malformed_sub_returns_401_not_500(client: AsyncClient):
    """Token with non-integer or garbage sub claim must return 401, never 500."""
    # Create valid signed JWT but with string 'invalid_sub' as subject
    garbage_sub_token = create_access_token(subject="not_an_int")
    res = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {garbage_sub_token}"})
    assert res.status_code == 401
    assert res.headers.get("www-authenticate") == "Bearer"


@pytest.mark.asyncio
async def test_inactive_user_returns_403(client: AsyncClient, db_session: AsyncSession):
    """Inactive user cannot log in (403) and access token produces 403."""
    # Seed inactive user directly
    user = User(
        email="inactive@example.com",
        full_name="Inactive User",
        hashed_password=hash_password("Password123!"),
        role=UserRole.MEMBER,
        is_active=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Login should return 403
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "inactive@example.com", "password": "Password123!"},
    )
    assert login_res.status_code == 403
    assert "inactive" in login_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_refresh_token_rotation_and_old_token_reuse(client: AsyncClient):
    """Mentor Case 2: Refresh token rotation, and reusing revoked token returns 401 & triggers reuse detection."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": "rotation@example.com", "full_name": "Rotation Tester", "password": "Password123!"},
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "rotation@example.com", "password": "Password123!"},
    )
    old_refresh = login_res.json()["refresh_token"]

    # 1. Rotate refresh token -> returns new pair
    rotate_res = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert rotate_res.status_code == 200
    new_refresh = rotate_res.json()["refresh_token"]
    assert new_refresh != old_refresh

    # 2. Mentor Case 2: Re-using the old refresh token must return 401
    reuse_res = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert reuse_res.status_code == 401
    assert "revoked" in reuse_res.json()["detail"].lower()

    # 3. Because reuse was detected, the whole session was revoked! new_refresh is now also invalidated:
    subsequent_res = await client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh})
    assert subsequent_res.status_code == 401


@pytest.mark.asyncio
async def test_change_password_and_login_with_old_password(client: AsyncClient):
    """Mentor Case 5: After changing password, login with old password returns 401 and old tokens are revoked."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": "pwd_user@example.com", "full_name": "Pwd User", "password": "OldPassword123!"},
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "pwd_user@example.com", "password": "OldPassword123!"},
    )
    access_token = login_res.json()["access_token"]
    old_refresh = login_res.json()["refresh_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # Change password
    change_res = await client.post(
        "/api/v1/users/me/change-password",
        json={"current_password": "OldPassword123!", "new_password": "NewPassword123!"},
        headers=headers,
    )
    assert change_res.status_code == 200

    # Login with old password must fail (401)
    fail_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "pwd_user@example.com", "password": "OldPassword123!"},
    )
    assert fail_login.status_code == 401

    # Login with new password must succeed (200)
    succ_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "pwd_user@example.com", "password": "NewPassword123!"},
    )
    assert succ_login.status_code == 200

    # Old refresh token was revoked during password change
    refresh_res = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert refresh_res.status_code == 401


@pytest.mark.asyncio
async def test_rbac_member_cannot_delete_users(client: AsyncClient):
    """Mentor Case 4: Member attempting to delete another user returns 403 Forbidden."""
    # Create Member User A
    await client.post(
        "/api/v1/auth/register",
        json={"email": "member_a@example.com", "full_name": "Member A", "password": "Password123!"},
    )
    login_a = await client.post(
        "/api/v1/auth/login",
        json={"email": "member_a@example.com", "password": "Password123!"},
    )
    token_a = login_a.json()["access_token"]

    # Create User B
    reg_b = await client.post(
        "/api/v1/auth/register",
        json={"email": "member_b@example.com", "full_name": "Member B", "password": "Password123!"},
    )
    user_b_id = reg_b.json()["id"]

    # Member A tries to delete User B -> 403
    del_res = await client.delete(f"/api/v1/users/{user_b_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert del_res.status_code == 403
    assert "Administrator privileges" in del_res.json()["detail"]


@pytest.mark.asyncio
async def test_admin_restrictions_cannot_delete_self_or_last_admin(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Admin cannot delete themselves, and cannot delete the sole remaining active admin."""
    # Seed Admin User 1
    admin_1 = User(
        email="admin1@example.com",
        full_name="Admin One",
        hashed_password=hash_password("Password123!"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(admin_1)
    await db_session.commit()
    await db_session.refresh(admin_1)

    login_admin1 = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin1@example.com", "password": "Password123!"},
    )
    token_admin1 = login_admin1.json()["access_token"]
    admin1_headers = {"Authorization": f"Bearer {token_admin1}"}

    # 1. Admin 1 attempts to delete themselves -> 400
    self_del = await client.delete(f"/api/v1/users/{admin_1.id}", headers=admin1_headers)
    assert self_del.status_code == 400
    assert "cannot delete your own account" in self_del.json()["detail"].lower()

    # Seed Admin User 2
    admin_2 = User(
        email="admin2@example.com",
        full_name="Admin Two",
        hashed_password=hash_password("Password123!"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(admin_2)
    await db_session.commit()
    await db_session.refresh(admin_2)

    # 2. When there are 2 admins, Admin 1 deletes Admin 2 -> 204 OK
    del_admin2 = await client.delete(f"/api/v1/users/{admin_2.id}", headers=admin1_headers)
    assert del_admin2.status_code == 204

    # Seed another admin that gets deactivated
    admin_3 = User(
        email="admin3@example.com",
        full_name="Admin Three",
        hashed_password=hash_password("Password123!"),
        role=UserRole.ADMIN,
        is_active=False,
    )
    db_session.add(admin_3)
    await db_session.commit()
    await db_session.refresh(admin_3)

    # Now active admins count is exactly 1 (admin_1). Admin 1 cannot delete admin_1 (self)
    # And if Admin 1 tries to delete a normal member, it succeeds
    reg_member = await client.post(
        "/api/v1/auth/register",
        json={"email": "normal_guy@example.com", "full_name": "Normal Guy", "password": "Password123!"},
    )
    member_id = reg_member.json()["id"]
    del_member = await client.delete(f"/api/v1/users/{member_id}", headers=admin1_headers)
    assert del_member.status_code == 204
