# Usage Guide

This guide covers how to install, configure, and integrate pytest-synapse into your API test suite.

## Installation

### Prerequisites

- Python 3.9 or higher
- pytest 7.0 or higher
- An OpenAPI 3.x specification for your API

### Install from PyPI

```bash
pip install pytest-synapse
```

### Install from Source

```bash
git clone https://github.com/your-org/pytest-synapse.git
cd pytest-synapse
pip install -e .
```

### Install with Development Dependencies

```bash
pip install -e ".[dev]"
```

This includes `requests`, `httpx`, `responses`, and `respx` for testing.

## Basic Usage

### Step 1: Prepare Your OpenAPI Specification

You need an OpenAPI 3.x specification that describes your API. This can be:
- A local YAML file (`openapi.yaml`)
- A local JSON file (`openapi.json`)
- A URL pointing to a remote spec

Example minimal spec:

```yaml
# openapi.yaml
openapi: "3.0.3"
info:
  title: User API
  version: "1.0.0"

paths:
  /users:
    get:
      summary: List all users
      responses:
        "200":
          description: Success
          content:
            application/json:
              schema:
                type: array
                items:
                  type: object
                  properties:
                    id:
                      type: integer
                    name:
                      type: string

    post:
      summary: Create a user
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                name:
                  type: string
                email:
                  type: string
      responses:
        "201":
          description: Created
        "400":
          description: Bad request

  /users/{userId}:
    get:
      summary: Get user by ID
      parameters:
        - name: userId
          in: path
          required: true
          schema:
            type: integer
      responses:
        "200":
          description: Success
        "404":
          description: Not found
```

### Step 2: Write Your API Tests

Write tests using `requests` or `httpx` as you normally would. **No modifications needed!**

```python
# tests/test_users_api.py
import requests
import pytest

BASE_URL = "http://localhost:8000"


class TestUserAPI:
    """Test suite for the User API."""

    def test_list_users_returns_200(self):
        """Test that listing users returns 200 OK."""
        response = requests.get(f"{BASE_URL}/users")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_create_user_returns_201(self):
        """Test that creating a user returns 201 Created."""
        user_data = {"name": "Alice", "email": "alice@example.com"}
        response = requests.post(f"{BASE_URL}/users", json=user_data)
        assert response.status_code == 201

    def test_create_user_invalid_data_returns_400(self):
        """Test that invalid data returns 400 Bad Request."""
        response = requests.post(f"{BASE_URL}/users", json={})
        assert response.status_code == 400

    def test_get_user_returns_200(self):
        """Test that getting a user returns 200 OK."""
        response = requests.get(f"{BASE_URL}/users/1")
        assert response.status_code == 200

    def test_get_user_not_found_returns_404(self):
        """Test that missing user returns 404 Not Found."""
        response = requests.get(f"{BASE_URL}/users/99999")
        assert response.status_code == 404
```

### Step 3: Run Tests with Coverage

```bash
pytest tests/ --openapi-spec=./openapi.yaml
```

### Step 4: Review Coverage Report

The coverage report is printed after test execution:

```
pytest-synapse: Intercepting HTTP traffic from: Requests, Httpx
============================= test session starts ==============================
...
tests/test_users_api.py .....                                            [100%]
pytest-synapse: Captured 5 HTTP requests/responses

==================================================
OpenAPI Coverage Report
==================================================

Paths:            2/2 (100.0%)
Operations:       3/3 (100.0%)
Request Bodies:   1/1 (100.0%)
Response Schemas: 5/5 (100.0%)

============================== 5 passed in 0.25s ===============================
```

## Configuration Options

### Command Line

```bash
# Basic usage
pytest --openapi-spec=./openapi.yaml

# With JSON report output
pytest --openapi-spec=./openapi.yaml \
       --synapse-report=coverage.json \
       --synapse-report-format=json

# With detailed CLI output
pytest --openapi-spec=./openapi.yaml \
       --synapse-report-format=cli_detailed

# Load spec from URL
pytest --openapi-spec=https://api.example.com/openapi.json
```

### pytest.ini

```ini
[pytest]
addopts =
    --openapi-spec=./openapi.yaml
    --synapse-report=coverage.json
    --synapse-report-format=json
```

### pyproject.toml

```toml
[tool.pytest.ini_options]
addopts = """
    --openapi-spec=./openapi.yaml
    --synapse-report=coverage.json
    --synapse-report-format=json
"""
```

## Using with Different HTTP Clients

### requests Library

```python
import requests

def test_with_requests():
    # All these calls are automatically intercepted
    response = requests.get("http://api.example.com/users")
    response = requests.post("http://api.example.com/users", json={"name": "Bob"})
    response = requests.put("http://api.example.com/users/1", json={"name": "Bob"})
    response = requests.delete("http://api.example.com/users/1")
```

### httpx Library (Sync)

```python
import httpx

def test_with_httpx():
    # Sync httpx calls are automatically intercepted
    response = httpx.get("http://api.example.com/users")
    response = httpx.post("http://api.example.com/users", json={"name": "Bob"})

    # Using a client
    with httpx.Client() as client:
        response = client.get("http://api.example.com/users")
```

### Using with Mock Libraries

pytest-synapse works seamlessly with mock libraries like `responses` and `respx`:

```python
import requests
import responses

@responses.activate
def test_with_mocked_api():
    # Set up mock
    responses.add(
        responses.GET,
        "http://api.example.com/users",
        json=[{"id": 1, "name": "Alice"}],
        status=200,
    )

    # Make request - intercepted by pytest-synapse
    response = requests.get("http://api.example.com/users")
    assert response.status_code == 200

    # Coverage is calculated even with mocked responses!
```

## Understanding the Coverage Report

### JSON Report Structure

```json
{
  "summary": {
    "total_paths": 2,
    "covered_paths": 2,
    "path_coverage_percentage": 100.0,
    "total_operations": 3,
    "covered_operations": 3,
    "operation_coverage_percentage": 100.0,
    "total_request_bodies": 1,
    "covered_request_bodies": 1,
    "request_body_coverage_percentage": 100.0,
    "total_response_schemas": 5,
    "covered_response_schemas": 4,
    "response_schema_coverage_percentage": 80.0,
    "uncovered_items_count": 1
  },
  "details": {
    "/users": {
      "GET": {
        "status": "COVERED",
        "request_body": {"status": "NOT_APPLICABLE"},
        "responses": {
          "200": {"status": "COVERED", "schema": {"status": "COVERED"}}
        }
      },
      "POST": {
        "status": "COVERED",
        "request_body": {"status": "COVERED"},
        "responses": {
          "201": {"status": "COVERED", "schema": {"status": "COVERED"}},
          "400": {"status": "UNCOVERED", "schema": {"status": "UNCOVERED"}}
        }
      }
    },
    "/users/{userId}": {
      "GET": {
        "status": "COVERED",
        "request_body": {"status": "NOT_APPLICABLE"},
        "responses": {
          "200": {"status": "COVERED", "schema": {"status": "COVERED"}},
          "404": {"status": "COVERED", "schema": {"status": "COVERED"}}
        }
      }
    }
  },
  "uncovered_items_list": [
    {
      "type": "response_status_code",
      "path": "/users",
      "method": "POST",
      "status_code": "400",
      "reason": "No 400 response observed"
    }
  ]
}
```

### Coverage Metrics Explained

| Metric | Description |
|--------|-------------|
| **Paths** | Unique API paths that received at least one request |
| **Operations** | Path + Method combinations (e.g., GET /users, POST /users) |
| **Request Bodies** | Operations with request bodies that received valid payloads |
| **Response Schemas** | Response status codes that were observed |

### Coverage Status Values

| Status | Meaning |
|--------|---------|
| `COVERED` | Observed during test execution |
| `UNCOVERED` | Defined in spec but not observed |
| `PARTIALLY_COVERED` | Some elements covered, others not |
| `NOT_APPLICABLE` | Not relevant (e.g., request body for GET) |

## CI/CD Integration

### GitHub Actions

```yaml
name: API Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"

      - name: Run API tests with coverage
        run: |
          pytest tests/ \
            --openapi-spec=./openapi.yaml \
            --synapse-report=coverage.json \
            --synapse-report-format=json

      - name: Upload coverage report
        uses: actions/upload-artifact@v3
        with:
          name: api-coverage-report
          path: coverage.json

      - name: Check coverage threshold
        run: |
          python -c "
          import json
          with open('coverage.json') as f:
              data = json.load(f)
          coverage = data['summary']['operation_coverage_percentage']
          print(f'API Coverage: {coverage}%')
          if coverage < 80:
              raise SystemExit(f'Coverage {coverage}% below 80% threshold')
          "
```

### GitLab CI

```yaml
api-tests:
  stage: test
  script:
    - pip install -e ".[dev]"
    - pytest tests/ --openapi-spec=./openapi.yaml --synapse-report=coverage.json --synapse-report-format=json
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage.json
```

## Troubleshooting

### No Traffic Captured

If you see "No HTTP traffic was captured":

1. Ensure your tests actually make HTTP requests
2. Check that you're using `requests` or `httpx` (sync mode)
3. Verify the interception message appears: "Intercepting HTTP traffic from: Requests, Httpx"

### Requests Not Matching Spec

If coverage is lower than expected:

1. Check that request paths match your OpenAPI path templates
2. Verify the base URL matches what's in your spec's `servers` section
3. Use `--synapse-report-format=cli_detailed` to see which paths are uncovered

### URL Loading Errors

If loading from URL fails:

1. Check the URL is accessible
2. Verify the Content-Type header or file extension is correct
3. Ensure the content is valid OpenAPI 3.x format

## Best Practices

1. **Keep your OpenAPI spec up to date** - Coverage is only meaningful if your spec reflects the actual API

2. **Test all response codes** - Don't just test happy paths; test error responses too

3. **Use meaningful test names** - Each captured request is associated with its test ID for debugging

4. **Set coverage thresholds in CI** - Prevent coverage regression by failing builds below a threshold

5. **Review uncovered items regularly** - The `uncovered_items_list` shows exactly what needs more testing
