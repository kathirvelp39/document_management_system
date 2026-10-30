
def test_user_registration_success(client):
    response = client.post(
        "/auth/register",
        json={
            "username": "testuser",
            "email": "testuser@example.com",
            "password": "TestPass@123",
        },
    )

    assert response.status_code == 201
    assert response.json()["username"] == "testuser"
    assert response.json()["email"] == "testuser@example.com"


def test_duplicate_user_registration(client):
    user_data = {
        "username": "testuser",
        "email": "testuser@example.com",
        "password": "TestPass@123",
    }

    first_response = client.post("/auth/register", json=user_data)
    second_response = client.post("/auth/register", json=user_data)

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_user_login_success(client):
    client.post(
        "/auth/register",
        json={
            "username": "testuser",
            "email": "testuser@example.com",
            "password": "TestPass@123",
        },
    )

    response = client.post(
        "/auth/login",
        json={
            "username": "testuser",
            "password": "TestPass@123",
        },
    )

    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"


def test_user_login_invalid_password(client):
    client.post(
        "/auth/register",
        json={
            "username": "testuser",
            "email": "testuser@example.com",
            "password": "TestPass@123",
        },
    )

    response = client.post(
        "/auth/login",
        json={
            "username": "testuser",
            "password": "WrongPassword@123",
        },
    )

    assert response.status_code == 401

def test_invalid_jwt_token(client):
    response = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid.token.value"},
    )

    assert response.status_code == 401
