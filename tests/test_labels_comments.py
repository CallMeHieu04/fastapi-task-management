import pytest
from httpx import AsyncClient


async def create_user_and_token(
    client: AsyncClient,
    email: str,
    name: str,
    password: str = "Password123!",
) -> tuple[str, int]:
    """Helper to register and login a test user, returning access token and user ID."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": name, "password": password},
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    token = login_res.json()["access_token"]
    me_res = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    user_id = me_res.json()["id"]
    return token, user_id


@pytest.mark.asyncio
async def test_label_crud_and_rbac(client: AsyncClient):
    """Test Label CRUD operations, hex color validation, and workspace RBAC."""
    token_owner, _ = await create_user_and_token(client, "lbl_owner@example.com", "Label Owner")
    token_editor, _ = await create_user_and_token(client, "lbl_editor@example.com", "Label Editor")
    token_viewer, _ = await create_user_and_token(client, "lbl_viewer@example.com", "Label Viewer")
    token_outsider, _ = await create_user_and_token(client, "lbl_outsider@example.com", "Label Outsider")

    headers_owner = {"Authorization": f"Bearer {token_owner}"}
    headers_editor = {"Authorization": f"Bearer {token_editor}"}
    headers_viewer = {"Authorization": f"Bearer {token_viewer}"}
    headers_outsider = {"Authorization": f"Bearer {token_outsider}"}

    # Setup Workspace & Project
    ws = (
        await client.post(
            "/api/v1/workspaces",
            json={"name": "Labels Test Workspace"},
            headers=headers_owner,
        )
    ).json()
    ws_id = ws["id"]

    await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": "lbl_editor@example.com", "role": "EDITOR"},
        headers=headers_owner,
    )
    await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": "lbl_viewer@example.com", "role": "VIEWER"},
        headers=headers_owner,
    )

    proj = (
        await client.post(
            f"/api/v1/workspaces/{ws_id}/projects",
            json={"name": "Labels Project"},
            headers=headers_owner,
        )
    ).json()
    proj_id = proj["id"]

    # 1. Viewer attempts to create label -> 403 Forbidden
    viewer_lbl_fail = await client.post(
        f"/api/v1/projects/{proj_id}/labels",
        json={"name": "Bug", "color": "#EF4444"},
        headers=headers_viewer,
    )
    assert viewer_lbl_fail.status_code == 403

    # 2. Outsider attempts to create label -> 403 Forbidden
    outsider_lbl_fail = await client.post(
        f"/api/v1/projects/{proj_id}/labels",
        json={"name": "Feature", "color": "#10B981"},
        headers=headers_outsider,
    )
    assert outsider_lbl_fail.status_code == 403

    # 3. Invalid color validation -> 422
    invalid_color = await client.post(
        f"/api/v1/projects/{proj_id}/labels",
        json={"name": "Invalid Color", "color": "not-a-hex"},
        headers=headers_editor,
    )
    assert invalid_color.status_code == 422

    # 4. Editor creates label -> 201 Created
    editor_lbl = await client.post(
        f"/api/v1/projects/{proj_id}/labels",
        json={"name": "Frontend Bug", "color": "#EF4444"},
        headers=headers_editor,
    )
    assert editor_lbl.status_code == 201
    label_data = editor_lbl.json()
    label_id = label_data["id"]
    assert label_data["name"] == "Frontend Bug"
    assert label_data["color"] == "#EF4444"

    # 5. Viewer lists labels -> 200 OK
    viewer_list = await client.get(f"/api/v1/projects/{proj_id}/labels", headers=headers_viewer)
    assert viewer_list.status_code == 200
    assert len(viewer_list.json()) == 1

    # 6. Outsider lists labels -> 403 Forbidden
    outsider_list = await client.get(f"/api/v1/projects/{proj_id}/labels", headers=headers_outsider)
    assert outsider_list.status_code == 403

    # 7. Viewer attempts to update label -> 403 Forbidden
    viewer_patch = await client.patch(
        f"/api/v1/labels/{label_id}",
        json={"name": "Hacked Label"},
        headers=headers_viewer,
    )
    assert viewer_patch.status_code == 403

    # 8. Validation: null or blank name -> 422
    null_name = await client.patch(f"/api/v1/labels/{label_id}", json={"name": None}, headers=headers_editor)
    assert null_name.status_code == 422

    blank_name = await client.patch(f"/api/v1/labels/{label_id}", json={"name": "   "}, headers=headers_editor)
    assert blank_name.status_code == 422

    # 9. Editor updates label -> 200 OK
    editor_patch = await client.patch(
        f"/api/v1/labels/{label_id}",
        json={"name": "UI Bug", "color": "#DC2626"},
        headers=headers_editor,
    )
    assert editor_patch.status_code == 200
    assert editor_patch.json()["name"] == "UI Bug"
    assert editor_patch.json()["color"] == "#DC2626"

    # 10. Viewer attempts to delete label -> 403 Forbidden
    viewer_del = await client.delete(f"/api/v1/labels/{label_id}", headers=headers_viewer)
    assert viewer_del.status_code == 403

    # 11. Editor deletes label -> 204 No Content
    editor_del = await client.delete(f"/api/v1/labels/{label_id}", headers=headers_editor)
    assert editor_del.status_code == 204

    # Fetching deleted label returns 404
    fetch_del = await client.patch(f"/api/v1/labels/{label_id}", json={"name": "New"}, headers=headers_editor)
    assert fetch_del.status_code == 404


@pytest.mark.asyncio
async def test_task_label_attachment_and_cross_project_rejection(client: AsyncClient):
    """Test attaching/detaching labels to tasks and rejecting cross-project label attachment."""
    token_owner, _ = await create_user_and_token(client, "attach_owner@example.com", "Attach Owner")
    token_editor, _ = await create_user_and_token(client, "attach_editor@example.com", "Attach Editor")
    token_viewer, _ = await create_user_and_token(client, "attach_viewer@example.com", "Attach Viewer")

    headers_owner = {"Authorization": f"Bearer {token_owner}"}
    headers_editor = {"Authorization": f"Bearer {token_editor}"}
    headers_viewer = {"Authorization": f"Bearer {token_viewer}"}

    # Workspace setup
    ws = (
        await client.post(
            "/api/v1/workspaces",
            json={"name": "Task Labels WS"},
            headers=headers_owner,
        )
    ).json()
    ws_id = ws["id"]

    await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": "attach_editor@example.com", "role": "EDITOR"},
        headers=headers_owner,
    )
    await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": "attach_viewer@example.com", "role": "VIEWER"},
        headers=headers_owner,
    )

    # Create 2 projects
    proj_a = (
        await client.post(
            f"/api/v1/workspaces/{ws_id}/projects",
            json={"name": "Project Alpha"},
            headers=headers_owner,
        )
    ).json()
    proj_b = (
        await client.post(
            f"/api/v1/workspaces/{ws_id}/projects",
            json={"name": "Project Beta"},
            headers=headers_owner,
        )
    ).json()

    # Create task in Project Alpha
    task_a = (
        await client.post(
            f"/api/v1/projects/{proj_a['id']}/tasks",
            json={"title": "Task in Alpha"},
            headers=headers_editor,
        )
    ).json()

    # Create Label A in Project Alpha, Label B in Project Beta
    lbl_a = (
        await client.post(
            f"/api/v1/projects/{proj_a['id']}/labels",
            json={"name": "Alpha Label", "color": "#3B82F6"},
            headers=headers_editor,
        )
    ).json()
    lbl_b = (
        await client.post(
            f"/api/v1/projects/{proj_b['id']}/labels",
            json={"name": "Beta Label", "color": "#10B981"},
            headers=headers_editor,
        )
    ).json()

    # 1. Viewer attempts to attach label -> 403 Forbidden
    viewer_attach = await client.post(
        f"/api/v1/tasks/{task_a['id']}/labels/{lbl_a['id']}",
        headers=headers_viewer,
    )
    assert viewer_attach.status_code == 403

    # 2. Editor attempts cross-project label attachment (Label B to Task A) -> 400 Bad Request
    cross_attach = await client.post(
        f"/api/v1/tasks/{task_a['id']}/labels/{lbl_b['id']}",
        headers=headers_editor,
    )
    assert cross_attach.status_code == 400

    # 3. Editor successfully attaches Label A to Task A -> 200 OK
    attach_res = await client.post(
        f"/api/v1/tasks/{task_a['id']}/labels/{lbl_a['id']}",
        headers=headers_editor,
    )
    assert attach_res.status_code == 200
    task_data = attach_res.json()
    assert len(task_data["labels"]) == 1
    assert task_data["labels"][0]["id"] == lbl_a["id"]

    # 4. Editor detaches Label A from Task A -> 200 OK
    detach_res = await client.delete(
        f"/api/v1/tasks/{task_a['id']}/labels/{lbl_a['id']}",
        headers=headers_editor,
    )
    assert detach_res.status_code == 200
    assert len(detach_res.json()["labels"]) == 0


@pytest.mark.asyncio
async def test_comments_management_and_resource_ownership(client: AsyncClient):
    """Test Comments creation, listing, updating, deleting, and resource ownership enforcement."""
    token_owner, _ = await create_user_and_token(client, "cmt_owner@example.com", "Cmt Owner")
    token_member1, _ = await create_user_and_token(client, "cmt_member1@example.com", "Cmt Member 1")
    token_member2, _ = await create_user_and_token(client, "cmt_member2@example.com", "Cmt Member 2")
    token_outsider, _ = await create_user_and_token(client, "cmt_outsider@example.com", "Cmt Outsider")

    headers_owner = {"Authorization": f"Bearer {token_owner}"}
    headers_m1 = {"Authorization": f"Bearer {token_member1}"}
    headers_m2 = {"Authorization": f"Bearer {token_member2}"}
    headers_outsider = {"Authorization": f"Bearer {token_outsider}"}

    # Workspace & Project & Task Setup
    ws = (
        await client.post(
            "/api/v1/workspaces",
            json={"name": "Comments WS"},
            headers=headers_owner,
        )
    ).json()
    ws_id = ws["id"]

    await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": "cmt_member1@example.com", "role": "VIEWER"},
        headers=headers_owner,
    )
    await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": "cmt_member2@example.com", "role": "EDITOR"},
        headers=headers_owner,
    )

    proj = (
        await client.post(
            f"/api/v1/workspaces/{ws_id}/projects",
            json={"name": "Comments Project"},
            headers=headers_owner,
        )
    ).json()

    task = (
        await client.post(
            f"/api/v1/projects/{proj['id']}/tasks",
            json={"title": "Task for Comments"},
            headers=headers_owner,
        )
    ).json()
    task_id = task["id"]

    # 1. Outsider attempts to add comment -> 403 Forbidden
    outsider_cmt = await client.post(
        f"/api/v1/tasks/{task_id}/comments",
        json={"content": "Spam from outsider"},
        headers=headers_outsider,
    )
    assert outsider_cmt.status_code == 403

    # 2. Validation: blank or empty comment -> 422
    blank_cmt = await client.post(
        f"/api/v1/tasks/{task_id}/comments",
        json={"content": "   "},
        headers=headers_m1,
    )
    assert blank_cmt.status_code == 422

    # 3. Member 1 (Viewer) posts comment -> 201 Created
    create_cmt = await client.post(
        f"/api/v1/tasks/{task_id}/comments",
        json={"content": "Looks good to me, reviewed code."},
        headers=headers_m1,
    )
    assert create_cmt.status_code == 201
    comment_data = create_cmt.json()
    comment_id = comment_data["id"]
    assert comment_data["content"] == "Looks good to me, reviewed code."
    assert comment_data["author"]["email"] == "cmt_member1@example.com"

    # 4. Member 2 lists comments -> 200 OK
    list_cmt = await client.get(f"/api/v1/tasks/{task_id}/comments", headers=headers_m2)
    assert list_cmt.status_code == 200
    assert len(list_cmt.json()) == 1

    # 5. Outsider lists comments -> 403 Forbidden
    outsider_list = await client.get(f"/api/v1/tasks/{task_id}/comments", headers=headers_outsider)
    assert outsider_list.status_code == 403

    # 6. Resource Ownership: Member 2 attempts to edit Member 1's comment -> 403 Forbidden
    m2_edit_fail = await client.patch(
        f"/api/v1/comments/{comment_id}",
        json={"content": "Malicious edit by Member 2"},
        headers=headers_m2,
    )
    assert m2_edit_fail.status_code == 403

    # 7. Author (Member 1) updates own comment -> 200 OK
    m1_edit = await client.patch(
        f"/api/v1/comments/{comment_id}",
        json={"content": "Updated review notes."},
        headers=headers_m1,
    )
    assert m1_edit.status_code == 200
    assert m1_edit.json()["content"] == "Updated review notes."

    # 8. Resource Ownership on Delete: Member 2 attempts to delete Member 1's comment -> 403 Forbidden
    m2_del_fail = await client.delete(f"/api/v1/comments/{comment_id}", headers=headers_m2)
    assert m2_del_fail.status_code == 403

    # 9. Workspace Owner deletes Member 1's comment (Owner moderation privilege) -> 204 No Content
    owner_del = await client.delete(f"/api/v1/comments/{comment_id}", headers=headers_owner)
    assert owner_del.status_code == 204

    # 10. Fetching deleted comment -> 404 Not Found
    fetch_del = await client.patch(f"/api/v1/comments/{comment_id}", json={"content": "New"}, headers=headers_m1)
    assert fetch_del.status_code == 404
