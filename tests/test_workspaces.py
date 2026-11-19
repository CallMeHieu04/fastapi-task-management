import pytest
from httpx import AsyncClient


async def create_user_and_token(client: AsyncClient, email: str, name: str, password: str = "Password123!") -> str:
    """Helper to register and login a test user, returning their access token."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": name, "password": password},
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    return login_res.json()["access_token"]


@pytest.mark.asyncio
async def test_workspace_creation_and_member_list(client: AsyncClient):
    """Creating a workspace assigns the creator as an OWNER in the membership list."""
    token_a = await create_user_and_token(client, "alice_ws@example.com", "Alice Ws")
    headers_a = {"Authorization": f"Bearer {token_a}"}

    create_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "Engineering Team Workspace"},
        headers=headers_a,
    )
    assert create_res.status_code == 201
    ws = create_res.json()
    assert ws["name"] == "Engineering Team Workspace"
    assert "id" in ws
    assert len(ws["members"]) == 1
    assert ws["members"][0]["role"] == "OWNER"
    assert ws["members"][0]["email"] == "alice_ws@example.com"

    # List workspaces (paginated response)
    list_res = await client.get("/api/v1/workspaces", headers=headers_a)
    assert list_res.status_code == 200
    page_data = list_res.json()
    assert "items" in page_data
    assert "meta" in page_data
    assert page_data["meta"]["total"] >= 1
    workspaces = page_data["items"]
    assert any(w["id"] == ws["id"] for w in workspaces)
    # Listing workspaces does not include full member details
    for w in workspaces:
        assert w["members"] == []


@pytest.mark.asyncio
async def test_workspace_rbac_non_member_access_denied(client: AsyncClient):
    """User B cannot view, modify, or delete a workspace owned by User A."""
    token_a = await create_user_and_token(client, "user_a@example.com", "User A")
    token_b = await create_user_and_token(client, "user_b@example.com", "User B")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User A creates workspace
    ws = (
        await client.post(
            "/api/v1/workspaces",
            json={"name": "Private Alpha"},
            headers=headers_a,
        )
    ).json()
    ws_id = ws["id"]

    # User B tries to view workspace -> 404 (non-member receives 404 to avoid leaking existence)
    get_res = await client.get(f"/api/v1/workspaces/{ws_id}", headers=headers_b)
    assert get_res.status_code == 404

    # User B tries to update workspace -> 404
    patch_res = await client.patch(
        f"/api/v1/workspaces/{ws_id}",
        json={"name": "Hijacked Workspace"},
        headers=headers_b,
    )
    assert patch_res.status_code == 404

    # User B tries to delete workspace -> 404
    del_res = await client.delete(f"/api/v1/workspaces/{ws_id}", headers=headers_b)
    assert del_res.status_code == 404


@pytest.mark.asyncio
async def test_workspace_membership_invitation_and_removal(client: AsyncClient):
    """Owner invites member, member can view, member cannot delete, owner removes member."""
    token_owner = await create_user_and_token(client, "ws_owner@example.com", "Ws Owner")
    token_member = await create_user_and_token(client, "ws_collab@example.com", "Ws Collab")
    owner_headers = {"Authorization": f"Bearer {token_owner}"}
    collab_headers = {"Authorization": f"Bearer {token_member}"}

    # 1. Create workspace
    ws_id = (
        await client.post(
            "/api/v1/workspaces",
            json={"name": "Collaborative HQ"},
            headers=owner_headers,
        )
    ).json()["id"]

    # 2. Owner invites Collab as EDITOR
    invite_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": "ws_collab@example.com", "role": "EDITOR"},
        headers=owner_headers,
    )
    assert invite_res.status_code == 201
    member_data = invite_res.json()
    assert member_data["role"] == "EDITOR"
    collab_user_id = member_data["user_id"]

    # 3. Collab can now view workspace
    collab_view = await client.get(f"/api/v1/workspaces/{ws_id}", headers=collab_headers)
    assert collab_view.status_code == 200
    assert len(collab_view.json()["members"]) == 2

    # 4. Collab (EDITOR) cannot delete workspace (OWNER only) -> 403
    fail_delete = await client.delete(f"/api/v1/workspaces/{ws_id}", headers=collab_headers)
    assert fail_delete.status_code == 403

    # 5. Collab cannot update workspace name -> 403
    fail_patch = await client.patch(
        f"/api/v1/workspaces/{ws_id}",
        json={"name": "Collab Attempted Name"},
        headers=collab_headers,
    )
    assert fail_patch.status_code == 403

    # 6. Owner cannot remove themselves from workspace -> 400
    owner_id = (await client.get("/api/v1/users/me", headers=owner_headers)).json()["id"]
    fail_self_remove = await client.delete(
        f"/api/v1/workspaces/{ws_id}/members/{owner_id}",
        headers=owner_headers,
    )
    assert fail_self_remove.status_code == 400

    # 7. Owner removes Collab
    remove_res = await client.delete(
        f"/api/v1/workspaces/{ws_id}/members/{collab_user_id}",
        headers=owner_headers,
    )
    assert remove_res.status_code == 204

    # 8. Collab can no longer view workspace -> 404
    after_remove_view = await client.get(f"/api/v1/workspaces/{ws_id}", headers=collab_headers)
    assert after_remove_view.status_code == 404


@pytest.mark.asyncio
async def test_workspace_update_validation_and_deletion(client: AsyncClient):
    """Owner can update workspace; null/blank updates are rejected with 422; deletion cleans up."""
    token = await create_user_and_token(client, "updater@example.com", "Updater")
    headers = {"Authorization": f"Bearer {token}"}

    ws_id = (
        await client.post(
            "/api/v1/workspaces",
            json={"name": "Pre-Update WS"},
            headers=headers,
        )
    ).json()["id"]

    # Valid update
    update_res = await client.patch(
        f"/api/v1/workspaces/{ws_id}",
        json={"name": "Post-Update WS"},
        headers=headers,
    )
    assert update_res.status_code == 200
    assert update_res.json()["name"] == "Post-Update WS"

    # Invalid empty name -> 422
    blank_res = await client.patch(
        f"/api/v1/workspaces/{ws_id}",
        json={"name": "   "},
        headers=headers,
    )
    assert blank_res.status_code == 422

    # Invalid null name -> 422
    null_res = await client.patch(
        f"/api/v1/workspaces/{ws_id}",
        json={"name": None},
        headers=headers,
    )
    assert null_res.status_code == 422

    # Delete workspace
    del_res = await client.delete(f"/api/v1/workspaces/{ws_id}", headers=headers)
    assert del_res.status_code == 204

    # Fetching deleted workspace returns 404
    missing_res = await client.get(f"/api/v1/workspaces/{ws_id}", headers=headers)
    assert missing_res.status_code == 404


@pytest.mark.asyncio
async def test_workspace_invitation_restrictions_and_duplicate_conflict(client: AsyncClient):
    """Inviting with role OWNER is rejected (422), duplicate invitation returns 409 Conflict."""
    token_owner = await create_user_and_token(client, "owner_invite_test@example.com", "Owner Invite")
    await create_user_and_token(client, "invitee@example.com", "Invitee")
    owner_headers = {"Authorization": f"Bearer {token_owner}"}

    # 1. Create workspace
    create_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "Invite Rules Workspace"},
        headers=owner_headers,
    )
    assert create_res.status_code == 201
    ws_id = create_res.json()["id"]

    # 2. Case: Invite without user_id or email -> 422 with MSG_MEMBER_IDENTIFIER_REQUIRED
    missing_id_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"role": "VIEWER"},
        headers=owner_headers,
    )
    assert missing_id_res.status_code == 422
    assert "Either user_id or email must be provided" in missing_id_res.text

    # 3. Case: Invite with role OWNER must be rejected -> 422
    owner_role_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": "invitee@example.com", "role": "OWNER"},
        headers=owner_headers,
    )
    assert owner_role_res.status_code == 422

    # 4. Invite with valid role (EDITOR) -> 201
    valid_invite = await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": "invitee@example.com", "role": "EDITOR"},
        headers=owner_headers,
    )
    assert valid_invite.status_code == 201
    assert valid_invite.json()["role"] == "EDITOR"

    # 5. Case: Invite same user again (duplicate) must return 409 Conflict
    dup_invite = await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": "invitee@example.com", "role": "VIEWER"},
        headers=owner_headers,
    )
    assert dup_invite.status_code == 409
    assert "already a member" in dup_invite.json()["detail"].lower()
