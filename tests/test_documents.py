
def register_and_login(client, username="testuser"):
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


def test_document_upload_success(client):
    token = register_and_login(client)

    response = client.post(
        "/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={
            "file": ("test.txt", b"Hello Mapla", "text/plain")
        },
    )

    assert response.status_code == 201
    assert response.json()["filename"] == "test.txt"
    assert response.json()["file_size"] == 11


def test_document_upload_invalid_extension(client):
    token = register_and_login(client)

    response = client.post(
        "/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={
            "file": ("malware.exe", b"test", "application/octet-stream")
        },
    )

    assert response.status_code == 400


def test_document_upload_unauthorized(client):
    response = client.post(
        "/documents/upload",
        files={
            "file": ("test.txt", b"Hello", "text/plain")
        },
    )

    assert response.status_code == 403


def test_document_upload_empty_file(client):
    token = register_and_login(client)

    response = client.post(
        "/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={
            "file": ("empty.txt", b"", "text/plain")
        },
    )

    assert response.status_code == 400

def test_document_upload_invalid_mime_type(client):
    token = register_and_login(client)

    response = client.post(
        "/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={
            "file": ("test.txt", b"fake image", "image/png")
        },
    )

    assert response.status_code == 400


def test_document_upload_file_exceeds_size_limit(client):
    token = register_and_login(client)

    large_content = b"x" * (5 * 1024 * 1024 + 1)

    response = client.post(
        "/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={
            "file": ("large.txt", large_content, "text/plain")
        },
    )

    assert response.status_code == 413

def test_invalid_pagination(client):
    token = register_and_login(client)

    response = client.get(
        "/documents?page=0",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


def test_invalid_sort_field(client):
    token = register_and_login(client)

    response = client.get(
        "/documents?sort_by=invalid",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
