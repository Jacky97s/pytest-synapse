"""Example API tests demonstrating pytest-synapse usage.

This file demonstrates how tests written using the requests library
are automatically intercepted by pytest-synapse to generate OpenAPI
coverage reports.

Run with:
    pytest examples/test_api_example.py --openapi-spec=tests/fixtures/openapi.yaml

"""

import responses


@responses.activate
def test_list_users():
    """Test listing all users."""
    import requests

    responses.add(
        responses.GET,
        "http://localhost:8000/users",
        json=[
            {"id": 1, "name": "Alice", "email": "alice@example.com"},
            {"id": 2, "name": "Bob", "email": "bob@example.com"},
        ],
        status=200,
    )

    response = requests.get("http://localhost:8000/users")
    assert response.status_code == 200
    users = response.json()
    assert len(users) == 2


@responses.activate
def test_create_user():
    """Test creating a new user."""
    import requests

    responses.add(
        responses.POST,
        "http://localhost:8000/users",
        json={"id": 3, "name": "Charlie", "email": "charlie@example.com"},
        status=201,
    )

    response = requests.post(
        "http://localhost:8000/users",
        json={"name": "Charlie", "email": "charlie@example.com"},
    )
    assert response.status_code == 201
    user = response.json()
    assert user["id"] == 3


@responses.activate
def test_get_user():
    """Test getting a specific user."""
    import requests

    responses.add(
        responses.GET,
        "http://localhost:8000/users/1",
        json={"id": 1, "name": "Alice", "email": "alice@example.com"},
        status=200,
    )

    response = requests.get("http://localhost:8000/users/1")
    assert response.status_code == 200
    user = response.json()
    assert user["name"] == "Alice"


@responses.activate
def test_get_user_not_found():
    """Test getting a user that doesn't exist."""
    import requests

    responses.add(
        responses.GET,
        "http://localhost:8000/users/999",
        json={"message": "User not found"},
        status=404,
    )

    response = requests.get("http://localhost:8000/users/999")
    assert response.status_code == 404


@responses.activate
def test_health_check():
    """Test the health endpoint."""
    import requests

    responses.add(
        responses.GET,
        "http://localhost:8000/health",
        json={"status": "ok"},
        status=200,
    )

    response = requests.get("http://localhost:8000/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
