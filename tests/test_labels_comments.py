import pytest
from httpx import AsyncClient

from tests.conftest import create_user_and_token


@pytest.mark.asyncio
async def test_label_crud_and_rbac(client: AsyncClient):
    """Test Label CRUD operations, hex color validation, uniqueness constraint, and workspace RBAC."""
    token_owner, _ = await create_user_and_token(client, "lbl_owner@example.com", "Label Owner")
    token_editor, _ = await create_user_and_token(client, "lbl_editor@example.com", "Label Editor")
    token_viewer, _ = await create_user_and_token(client, "lbl_viewer@example.com", "Label Viewer")
    token_outsider, _ = await create_user_and_token(client, "lbl_outsider@example.com", "Label Outsider")

    headers_owner = {"Authorization": f"Bearer {token_owner}"}
    headers_editor = {"Authorization": f"Bearer {token_editor}"}
    headers_viewer = {"Authorization": f"Bearer {token_viewer}"}
    headers_outsider = {"Authorization": f"Bearer {token_outsider}"}

    # Setup Workspace & Project
    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "Labels Test Workspace"},
        headers=headers_owner,
    )
    assert ws_res.status_code == 201
    ws_id = ws_res.json()["id"]

    add_ed_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": "lbl_editor@example.com", "role": "EDITOR"},
        headers=headers_owner,
    )
    assert add_ed_res.status_code == 201

    add_vi_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": "lbl_viewer@example.com", "role": "VIEWER"},
        headers=headers_owner,
    )
    assert add_vi_res.status_code == 201

    proj_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/projects",
        json={"name": "Labels Project"},
        headers=headers_owner,
    )
    assert proj_res.status_code == 201
    proj_id = proj_res.json()["id"]

    # 1. Viewer attempts to create label -> 403 Forbidden
    viewer_lbl_fail = await client.post(
        f"/api/v1/projects/{proj_id}/labels",
        json={"name": "Bug", "color": "#EF4444"},
        headers=headers_viewer,
    )
    assert viewer_lbl_fail.status_code == 403

    # 2. Outsider attempts to create label -> 404 Not Found (hide project existence)
    outsider_lbl_fail = await client.post(
        f"/api/v1/projects/{proj_id}/labels",
        json={"name": "Feature", "color": "#10B981"},
        headers=headers_outsider,
    )
    assert outsider_lbl_fail.status_code == 404

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

    # 5. Duplicate label creation in same project -> 409 Conflict
    dup_lbl = await client.post(
        f"/api/v1/projects/{proj_id}/labels",
        json={"name": "Frontend Bug", "color": "#3B82F6"},
        headers=headers_editor,
    )
    assert dup_lbl.status_code == 409

    # 6. Viewer lists labels -> 200 OK
    viewer_list = await client.get(f"/api/v1/projects/{proj_id}/labels", headers=headers_viewer)
    assert viewer_list.status_code == 200
    assert len(viewer_list.json()) == 1

    # 7. Outsider lists labels -> 404 Not Found
    outsider_list = await client.get(f"/api/v1/projects/{proj_id}/labels", headers=headers_outsider)
    assert outsider_list.status_code == 404

    # 8. Viewer attempts to update label -> 403 Forbidden
    viewer_patch = await client.patch(
        f"/api/v1/labels/{label_id}",
        json={"name": "Hacked Label"},
        headers=headers_viewer,
    )
    assert viewer_patch.status_code == 403

    # 9. Validation: null or blank name -> 422
    null_name = await client.patch(f"/api/v1/labels/{label_id}", json={"name": None}, headers=headers_editor)
    assert null_name.status_code == 422

    blank_name = await client.patch(f"/api/v1/labels/{label_id}", json={"name": "   "}, headers=headers_editor)
    assert blank_name.status_code == 422

    # 10. Create second label and try renaming to first label name -> 409 Conflict
    lbl2_res = await client.post(
        f"/api/v1/projects/{proj_id}/labels",
        json={"name": "Backend Task", "color": "#10B981"},
        headers=headers_editor,
    )
    assert lbl2_res.status_code == 201
    lbl2_id = lbl2_res.json()["id"]

    rename_conflict = await client.patch(
        f"/api/v1/labels/{lbl2_id}",
        json={"name": "Frontend Bug"},
        headers=headers_editor,
    )
    assert rename_conflict.status_code == 409

    # 11. Editor updates label -> 200 OK
    editor_patch = await client.patch(
        f"/api/v1/labels/{label_id}",
        json={"name": "UI Bug", "color": "#DC2626"},
        headers=headers_editor,
    )
    assert editor_patch.status_code == 200
    assert editor_patch.json()["name"] == "UI Bug"
    assert editor_patch.json()["color"] == "#DC2626"

    # 12. Viewer attempts to delete label -> 403 Forbidden
    viewer_del = await client.delete(f"/api/v1/labels/{label_id}", headers=headers_viewer)
    assert viewer_del.status_code == 403

    # 13. Editor deletes label -> 204 No Content
    editor_del = await client.delete(f"/api/v1/labels/{label_id}", headers=headers_editor)
    assert editor_del.status_code == 204

    # 14. Fetching deleted label returns 404
    fetch_del = await client.patch(f"/api/v1/labels/{label_id}", json={"name": "New"}, headers=headers_editor)
    assert fetch_del.status_code == 404


@pytest.mark.asyncio
async def test_task_label_attachment_and_cross_project_rejection(client: AsyncClient):
    """Test attaching/detaching labels to tasks, duplicate attach rejection, and cross-project rejection."""
    token_owner, _ = await create_user_and_token(client, "attach_owner@example.com", "Attach Owner")
    token_editor, _ = await create_user_and_token(client, "attach_editor@example.com", "Attach Editor")
    token_viewer, _ = await create_user_and_token(client, "attach_viewer@example.com", "Attach Viewer")

    headers_owner = {"Authorization": f"Bearer {token_owner}"}
    headers_editor = {"Authorization": f"Bearer {token_editor}"}
    headers_viewer = {"Authorization": f"Bearer {token_viewer}"}

    # Workspace setup
    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "Task Labels WS"},
        headers=headers_owner,
    )
    assert ws_res.status_code == 201
    ws_id = ws_res.json()["id"]

    add_ed = await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": "attach_editor@example.com", "role": "EDITOR"},
        headers=headers_owner,
    )
    assert add_ed.status_code == 201

    add_vi = await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": "attach_viewer@example.com", "role": "VIEWER"},
        headers=headers_owner,
    )
    assert add_vi.status_code == 201

    # Create 2 projects
    proj_a_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/projects",
        json={"name": "Project Alpha"},
        headers=headers_owner,
    )
    assert proj_a_res.status_code == 201
    proj_a = proj_a_res.json()

    proj_b_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/projects",
        json={"name": "Project Beta"},
        headers=headers_owner,
    )
    assert proj_b_res.status_code == 201
    proj_b = proj_b_res.json()

    # Create task in Project Alpha
    task_a_res = await client.post(
        f"/api/v1/projects/{proj_a['id']}/tasks",
        json={"title": "Task in Alpha"},
        headers=headers_editor,
    )
    assert task_a_res.status_code == 201
    task_a = task_a_res.json()

    # Create Label A in Project Alpha, Label B in Project Beta
    lbl_a_res = await client.post(
        f"/api/v1/projects/{proj_a['id']}/labels",
        json={"name": "Alpha Label", "color": "#3B82F6"},
        headers=headers_editor,
    )
    assert lbl_a_res.status_code == 201
    lbl_a = lbl_a_res.json()

    lbl_b_res = await client.post(
        f"/api/v1/projects/{proj_b['id']}/labels",
        json={"name": "Beta Label", "color": "#10B981"},
        headers=headers_editor,
    )
    assert lbl_b_res.status_code == 201
    lbl_b = lbl_b_res.json()

    # 1. Viewer attempts to attach label -> 403 Forbidden
    viewer_attach = await client.post(
        f"/api/v1/tasks/{task_a['id']}/labels/{lbl_a['id']}",
        headers=headers_viewer,
    )
    assert viewer_attach.status_code == 403

    # 2. Editor attempts cross-project label attachment (Label B to Task A) -> 404 (hide other project label)
    cross_attach = await client.post(
        f"/api/v1/tasks/{task_a['id']}/labels/{lbl_b['id']}",
        headers=headers_editor,
    )
    assert cross_attach.status_code == 404

    # 3. Editor successfully attaches Label A to Task A -> 200 OK
    attach_res = await client.post(
        f"/api/v1/tasks/{task_a['id']}/labels/{lbl_a['id']}",
        headers=headers_editor,
    )
    assert attach_res.status_code == 200
    task_data = attach_res.json()
    assert len(task_data["labels"]) == 1
    assert task_data["labels"][0]["id"] == lbl_a["id"]

    # 4. Duplicate attachment attempt -> 409 Conflict
    dup_attach = await client.post(
        f"/api/v1/tasks/{task_a['id']}/labels/{lbl_a['id']}",
        headers=headers_editor,
    )
    assert dup_attach.status_code == 409

    # 5. Detach label not attached to task (e.g. Label B) -> 404 Not Found
    detach_unattached = await client.delete(
        f"/api/v1/tasks/{task_a['id']}/labels/{lbl_b['id']}",
        headers=headers_editor,
    )
    assert detach_unattached.status_code == 404

    # 6. Editor detaches Label A from Task A -> 200 OK
    detach_res = await client.delete(
        f"/api/v1/tasks/{task_a['id']}/labels/{lbl_a['id']}",
        headers=headers_editor,
    )
    assert detach_res.status_code == 200
    assert len(detach_res.json()["labels"]) == 0

    # 7. Detaching again when already detached -> 404 Not Found
    detach_again = await client.delete(
        f"/api/v1/tasks/{task_a['id']}/labels/{lbl_a['id']}",
        headers=headers_editor,
    )
    assert detach_again.status_code == 404


@pytest.mark.asyncio
async def test_comments_management_and_resource_ownership(client: AsyncClient):
    """Test Comments creation, pagination, updating, deleting, and resource ownership enforcement."""
    token_owner, _ = await create_user_and_token(client, "cmt_owner@example.com", "Cmt Owner")
    token_member1, _ = await create_user_and_token(client, "cmt_member1@example.com", "Cmt Member 1")
    token_member2, _ = await create_user_and_token(client, "cmt_member2@example.com", "Cmt Member 2")
    token_outsider, _ = await create_user_and_token(client, "cmt_outsider@example.com", "Cmt Outsider")

    headers_owner = {"Authorization": f"Bearer {token_owner}"}
    headers_m1 = {"Authorization": f"Bearer {token_member1}"}
    headers_m2 = {"Authorization": f"Bearer {token_member2}"}
    headers_outsider = {"Authorization": f"Bearer {token_outsider}"}

    # Workspace & Project & Task Setup
    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "Comments WS"},
        headers=headers_owner,
    )
    assert ws_res.status_code == 201
    ws_id = ws_res.json()["id"]

    add_m1 = await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": "cmt_member1@example.com", "role": "VIEWER"},
        headers=headers_owner,
    )
    assert add_m1.status_code == 201

    add_m2 = await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": "cmt_member2@example.com", "role": "EDITOR"},
        headers=headers_owner,
    )
    assert add_m2.status_code == 201

    proj_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/projects",
        json={"name": "Comments Project"},
        headers=headers_owner,
    )
    assert proj_res.status_code == 201
    proj_id = proj_res.json()["id"]

    task_res = await client.post(
        f"/api/v1/projects/{proj_id}/tasks",
        json={"title": "Task for Comments"},
        headers=headers_owner,
    )
    assert task_res.status_code == 201
    task = task_res.json()
    task_id = task["id"]

    # 1. Outsider attempts to add comment -> 404 Not Found (hide project existence)
    outsider_cmt = await client.post(
        f"/api/v1/tasks/{task_id}/comments",
        json={"content": "Spam from outsider"},
        headers=headers_outsider,
    )
    assert outsider_cmt.status_code == 404

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

    # 4. Member 2 lists comments (paginated) -> 200 OK
    list_cmt = await client.get(f"/api/v1/tasks/{task_id}/comments", headers=headers_m2)
    assert list_cmt.status_code == 200
    res_data = list_cmt.json()
    assert "items" in res_data
    assert "meta" in res_data
    assert len(res_data["items"]) == 1
    assert res_data["meta"]["total"] == 1

    # 5. Outsider lists comments -> 404 Not Found
    outsider_list = await client.get(f"/api/v1/tasks/{task_id}/comments", headers=headers_outsider)
    assert outsider_list.status_code == 404

    # 6. Resource Ownership: Member 2 attempts to edit Member 1's comment -> 403 Forbidden
    m2_edit_fail = await client.patch(
        f"/api/v1/comments/{comment_id}",
        json={"content": "Malicious edit by Member 2"},
        headers=headers_m2,
    )
    assert m2_edit_fail.status_code == 403

    # 7. Workspace OWNER attempts to edit Member 1's comment -> 403 Forbidden (Author ONLY!)
    owner_edit_fail = await client.patch(
        f"/api/v1/comments/{comment_id}",
        json={"content": "Owner trying to edit author's words"},
        headers=headers_owner,
    )
    assert owner_edit_fail.status_code == 403

    # 8. Author (Member 1) updates own comment -> 200 OK
    m1_edit = await client.patch(
        f"/api/v1/comments/{comment_id}",
        json={"content": "Updated review notes."},
        headers=headers_m1,
    )
    assert m1_edit.status_code == 200
    assert m1_edit.json()["content"] == "Updated review notes."

    # 9. Resource Ownership on Delete: Member 2 attempts to delete Member 1's comment -> 403 Forbidden
    m2_del_fail = await client.delete(f"/api/v1/comments/{comment_id}", headers=headers_m2)
    assert m2_del_fail.status_code == 403

    # 10. Workspace Owner deletes Member 1's comment (Owner moderation privilege) -> 204 No Content
    owner_del = await client.delete(f"/api/v1/comments/{comment_id}", headers=headers_owner)
    assert owner_del.status_code == 204

    # 11. Fetching deleted comment -> 404 Not Found
    fetch_del = await client.patch(f"/api/v1/comments/{comment_id}", json={"content": "New"}, headers=headers_m1)
    assert fetch_del.status_code == 404


@pytest.mark.asyncio
async def test_archived_project_and_removed_member_comment_rbac(client: AsyncClient):
    """Test that archived projects block label/comment creation, and removed members cannot edit/delete comments."""
    token_owner, _ = await create_user_and_token(client, "arch_owner@example.com", "Arch Owner")
    token_dev, dev_id = await create_user_and_token(client, "arch_dev@example.com", "Arch Dev")

    headers_owner = {"Authorization": f"Bearer {token_owner}"}
    headers_dev = {"Authorization": f"Bearer {token_dev}"}

    # Setup Workspace & Project
    ws_res = await client.post("/api/v1/workspaces", json={"name": "Archived WS"}, headers=headers_owner)
    assert ws_res.status_code == 201
    ws_id = ws_res.json()["id"]

    add_dev = await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": "arch_dev@example.com", "role": "EDITOR"},
        headers=headers_owner,
    )
    assert add_dev.status_code == 201

    proj_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/projects",
        json={"name": "Archived Project"},
        headers=headers_owner,
    )
    assert proj_res.status_code == 201
    proj_id = proj_res.json()["id"]

    task_res = await client.post(
        f"/api/v1/projects/{proj_id}/tasks",
        json={"title": "Active Task"},
        headers=headers_owner,
    )
    assert task_res.status_code == 201
    task_id = task_res.json()["id"]

    # Dev writes a comment while active
    dev_cmt = await client.post(
        f"/api/v1/tasks/{task_id}/comments",
        json={"content": "Comment written when active"},
        headers=headers_dev,
    )
    assert dev_cmt.status_code == 201
    cmt_id = dev_cmt.json()["id"]

    # Owner removes Dev from workspace
    rem_dev = await client.delete(f"/api/v1/workspaces/{ws_id}/members/{dev_id}", headers=headers_owner)
    assert rem_dev.status_code == 204

    # Removed dev tries to update comment -> 404 Not Found (no longer has access to workspace/task)
    fail_update = await client.patch(
        f"/api/v1/comments/{cmt_id}",
        json={"content": "I was removed but trying to edit"},
        headers=headers_dev,
    )
    assert fail_update.status_code == 404

    # Removed dev tries to delete comment -> 404 Not Found
    fail_del = await client.delete(f"/api/v1/comments/{cmt_id}", headers=headers_dev)
    assert fail_del.status_code == 404

    # Owner archives project
    arch_res = await client.patch(
        f"/api/v1/projects/{proj_id}",
        json={"status": "ARCHIVED"},
        headers=headers_owner,
    )
    assert arch_res.status_code == 200

    # Creating label in archived project -> 400 Bad Request
    arch_lbl = await client.post(
        f"/api/v1/projects/{proj_id}/labels",
        json={"name": "Archived Label", "color": "#EF4444"},
        headers=headers_owner,
    )
    assert arch_lbl.status_code == 400

    # Adding comment in archived project -> 400 Bad Request
    arch_cmt = await client.post(
        f"/api/v1/tasks/{task_id}/comments",
        json={"content": "Comment on archived project"},
        headers=headers_owner,
    )
    assert arch_cmt.status_code == 400
