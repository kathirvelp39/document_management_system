
from app.models import User


def test_viewer_cannot_upload_document(client, db_session):
    client.post(
        "/auth/register",
        json={
            "username": "vieweruser",
            "email": "viewer@example.com",
            "password": "TestPass@123",
        },
    )

    viewer = db_session.query(User).filter_by(
        username="vieweruser"
    ).first()

    viewer.role = "viewer"
    db_session.commit()

    login_response = client.post(
        "/auth/login",
        json={
            "username": "vieweruser",
            "password": "TestPass@123",
        },
    )

    token = login_response.json()["access_token"]

    response = client.post(
        "/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={
            "file": ("test.txt", b"Viewer test", "text/plain")
        },
    )

    assert response.status_code == 403


def test_user_can_upload_document(client):
    client.post(
        "/auth/register",
        json={
            "username": "normaluser",
            "email": "normal@example.com",
            "password": "TestPass@123",
        },
    )

    login_response = client.post(
        "/auth/login",
        json={
            "username": "normaluser",
            "password": "TestPass@123",
        },
    )

    token = login_response.json()["access_token"]

    response = client.post(
        "/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={
            "file": ("userfile.txt", b"User test", "text/plain")
        },
    )

    assert response.status_code == 201
