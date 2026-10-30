
def create_user_and_login(client, username):
    client.post(
        "/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "TestPass@123",
        },
    )

    response = client.post(
        "/auth/login",
        json={
            "username": username,
            "password": "TestPass@123",
        },
    )

    return response.json()["access_token"]


def upload_test_document(client, token):
    response = client.post(
        "/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={
            "file": ("shared.txt", b"Sharing test content", "text/plain")
        },
    )

    assert response.status_code == 201
    return response.json()["id"]


def test_document_sharing_view_permission(client):
    owner_token = create_user_and_login(client, "owner")
    recipient_token = create_user_and_login(client, "recipient")

    document_id = upload_test_document(client, owner_token)

    share_response = client.post(
        f"/documents/{document_id}/share",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"username": "recipient", "permission": "view"},
    )

    assert share_response.status_code == 201

    view_response = client.get(
        f"/documents/{document_id}",
        headers={"Authorization": f"Bearer {recipient_token}"},
    )

    assert view_response.status_code == 200


def test_view_permission_cannot_download(client):
    owner_token = create_user_and_login(client, "owner")
    recipient_token = create_user_and_login(client, "recipient")

    document_id = upload_test_document(client, owner_token)

    client.post(
        f"/documents/{document_id}/share",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"username": "recipient", "permission": "view"},
    )

    response = client.get(
        f"/documents/{document_id}/download",
        headers={"Authorization": f"Bearer {recipient_token}"},
    )

    assert response.status_code == 403


def test_other_user_cannot_access_private_document(client):
    owner_token = create_user_and_login(client, "owner")
    other_token = create_user_and_login(client, "other")

    document_id = upload_test_document(client, owner_token)

    response = client.get(
        f"/documents/{document_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 404
