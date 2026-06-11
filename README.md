# pytest-synapse

A pytest plugin for measuring OpenAPI contract test coverage by transparently intercepting HTTP traffic during test execution.

## Features

- **Transparent Interception**: Automatically captures HTTP requests/responses from `requests` and `httpx` libraries without modifying test code
- **OpenAPI Coverage**: Maps captured traffic to your OpenAPI 3.x specification to calculate coverage metrics
- **Granular Reporting**: Coverage for paths, HTTP methods, request bodies, response status codes, and response schemas
- **Multiple Output Formats**: CLI summary, detailed CLI output, and JSON reports for CI/CD integration
- **URL Support**: Load OpenAPI specs from local files or remote URLs

## Installation

### From TestPyPI

```bash
pip install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ pytest-synapse
```

### From Source

```bash
git clone https://github.com/pytest-synapse/pytest-synapse.git
cd pytest-synapse
pip install -e ".[dev]"
```

### Dependencies

The plugin automatically installs required dependencies:
- `pytest>=7.0.0`
- `openapi-core>=0.18.0`
- `pyyaml>=6.0`
- `werkzeug>=2.0.0`

## Quick Start

### 1. Create or obtain your OpenAPI specification

You need an OpenAPI 3.x specification file (YAML or JSON) that describes your API:

```yaml
# openapi.yaml
openapi: "3.0.3"
info:
  title: My API
  version: "1.0.0"
paths:
  /users:
    get:
      summary: List users
      responses:
        "200":
          description: A list of users
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: "#/components/schemas/User"
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
          description: A user
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/User"
        "404":
          description: User not found

components:
  schemas:
    User:
      type: object
      properties:
        id:
          type: integer
        name:
          type: string
        email:
          type: string
```

### 2. Write your API tests as usual

No changes to your existing test code are required! Just use `requests` or `httpx` as you normally would:

```python
# tests/test_api.py
import requests

BASE_URL = "http://localhost:8000"

def test_list_users():
    response = requests.get(f"{BASE_URL}/users")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_get_user():
    response = requests.get(f"{BASE_URL}/users/1")
    assert response.status_code == 200
    user = response.json()
    assert "id" in user
    assert "name" in user

def test_get_user_not_found():
    response = requests.get(f"{BASE_URL}/users/99999")
    assert response.status_code == 404
```

### 3. Run pytest with the OpenAPI spec

```bash
pytest --openapi-spec=./openapi.yaml
```

### 4. View coverage results

```
pytest-synapse: Intercepting HTTP traffic from: Requests, Httpx
============================= test session starts ==============================
...
pytest-synapse: Captured 3 HTTP requests/responses

==================================================
OpenAPI Coverage Report
==================================================

Paths:            2/2 (100.0%)
Operations:       2/2 (100.0%)
Request Bodies:   0/0 (100.0%)
Response Schemas: 3/3 (100.0%)

============================== 3 passed in 0.15s ===============================
```

## Configuration

### Command Line Options

| Option | Description |
|--------|-------------|
| `--openapi-spec` | Path to OpenAPI spec file or URL (required for coverage) |
| `--synapse-report` | Output path for the coverage report file |
| `--synapse-report-format` | Report format: `cli_summary`, `cli_detailed`, or `json` |
| `--synapse-ignore-paths` | Comma-separated list of paths to exclude |

### pytest.ini Configuration

```ini
[pytest]
addopts =
    --openapi-spec=./openapi.yaml
    --synapse-report=coverage.json
    --synapse-report-format=json
```

### Loading OpenAPI Specs from URLs

```bash
# From a remote JSON file
pytest --openapi-spec=https://api.example.com/openapi.json

# From a remote YAML file
pytest --openapi-spec=https://petstore.swagger.io/v2/swagger.yaml
```

### Server Base Paths

If the spec's `servers` entries include a path prefix (e.g.
`https://api.example.com/api/v2`), captured requests such as
`GET /api/v2/users/1` are automatically matched to the spec path keys
(`/users/{userId}`) — the base path is stripped during matching.

## Report Formats

### CLI Summary (default)

```
==================================================
OpenAPI Coverage Report
==================================================

Paths:            3/5 (60.0%)
Operations:       5/8 (62.5%)
Request Bodies:   2/3 (66.7%)
Response Schemas: 7/12 (58.3%)

Uncovered items: 5
```

### CLI Detailed

```bash
pytest --openapi-spec=./openapi.yaml --synapse-report-format=cli_detailed
```

Shows a tree view of all paths, operations, and their coverage status.

### JSON Report

```bash
pytest --openapi-spec=./openapi.yaml --synapse-report=coverage.json --synapse-report-format=json
```

Generates a machine-readable JSON report:

```json
{
  "summary": {
    "total_paths": 5,
    "covered_paths": 3,
    "path_coverage_percentage": 60.0,
    "total_operations": 8,
    "covered_operations": 5,
    "operation_coverage_percentage": 62.5
  },
  "details": {
    "/users": {
      "GET": {
        "status": "COVERED",
        "request_body": {"status": "NOT_APPLICABLE"},
        "responses": {
          "200": {"status": "COVERED", "schema": {"status": "COVERED"}}
        }
      }
    }
  },
  "uncovered_items_list": [...]
}
```

## Coverage Status Values

| Status | Description |
|--------|-------------|
| `COVERED` | The element was observed and validated |
| `UNCOVERED` | The element is defined in the spec but was not observed |
| `PARTIALLY_COVERED` | Some child elements are covered, others are not |
| `NOT_APPLICABLE` | Not relevant (e.g., request body for GET requests) |

## Supported HTTP Clients

pytest-synapse transparently intercepts traffic from:

- **requests** - `requests.get()`, `requests.post()`, etc.
- **httpx** (sync & async) - `httpx.get()`, `httpx.AsyncClient()`, etc.
- **aiohttp** - `aiohttp.ClientSession()` for async HTTP

The interception happens at a high level, after TLS decryption, so HTTPS traffic is fully supported without any certificate configuration.

## Integration with CI/CD

### GitHub Actions Example

```yaml
- name: Run API tests with coverage
  run: |
    pytest --openapi-spec=./openapi.yaml \
           --synapse-report=coverage.json \
           --synapse-report-format=json

- name: Upload coverage report
  uses: actions/upload-artifact@v3
  with:
    name: api-coverage
    path: coverage.json
```

### Fail on Low Coverage (Custom Script)

```python
import json
import sys

with open("coverage.json") as f:
    report = json.load(f)

coverage = report["summary"]["operation_coverage_percentage"]
if coverage < 80:
    print(f"API coverage {coverage}% is below threshold of 80%")
    sys.exit(1)
```

## Programmatic Usage

You can also use pytest-synapse components directly in your code:

```python
from pytest_synapse import (
    OpenAPISpecParser,
    SynapseCoverageEngine,
    ReportRenderer,
)

# Parse the OpenAPI spec
spec = OpenAPISpecParser("./openapi.yaml")
# Or from URL:
# spec = OpenAPISpecParser("https://api.example.com/openapi.json")

# Create coverage engine
engine = SynapseCoverageEngine(spec)

# Process captured events (from your own interception logic)
engine.process_events(events)

# Generate report
renderer = ReportRenderer(engine)
print(renderer.render_cli_summary())
```

## Limitations

- Only captures HTTP traffic from the pytest process (not subprocesses)

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run example
pytest examples/test_api_example.py --openapi-spec=tests/fixtures/openapi.yaml
```

## License

MIT License

## Contributing

Contributions are welcome! Please see our contributing guidelines for details.
