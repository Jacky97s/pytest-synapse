# pytest-synapse

A pytest plugin for measuring OpenAPI contract test coverage by transparently intercepting HTTP traffic during test execution.

## Key Features

- **Transparent Interception**: Automatically captures HTTP requests/responses from `requests`, `httpx`, and `aiohttp` without modifying test code
- **OpenAPI Coverage**: Maps captured traffic to your OpenAPI 3.x specification
- **Granular Metrics**: Coverage for paths, HTTP methods, request bodies, response status codes, response schemas, and field-level constraints
- **Risk Assessment**: Identifies high-risk untested endpoints with detailed risk scoring
- **Multiple Output Formats**: CLI, JSON, CSV, and HTML reports with interactive dashboards
- **CI/CD Integration**: Fail thresholds, baseline comparison, JUnit XML output, GitHub PR comments
- **Field & Constraint Coverage**: Track coverage of required fields, enums, string patterns, numeric ranges, and more

## Installation

```bash
pip install pytest-synapse
```

## Quick Start

```bash
# Basic usage
pytest --openapi-spec=./openapi.yaml

# With HTML report including risk assessment
pytest --openapi-spec=./openapi.yaml --synapse-report=report.html --synapse-report-format=html

# With coverage threshold
pytest --openapi-spec=./openapi.yaml --synapse-fail-under=80
```

## Coverage Output

```
==================================================
OpenAPI Coverage Report
==================================================

Paths:            3/5 (60.0%)
Operations:       5/8 (62.5%)
Request Bodies:   2/3 (66.7%)
Response Schemas: 7/12 (58.3%)

==================================================
API RISK ASSESSMENT
==================================================

RISK SUMMARY
------------------------------------------------------------
  Total Endpoints:     8
  High Risk:           2
  Medium Risk:         3
  Low Risk:            3
  Risk Score:          45.0/100

CRITICAL GAPS (High-risk + Uncovered):
  [!] DELETE /users/{id}
  [!] POST /payments
```

## CLI Options

| Option | Description |
|--------|-------------|
| `--openapi-spec` | Path to OpenAPI spec file or URL |
| `--synapse-report` | Output path for coverage report |
| `--synapse-report-format` | Format: `json`, `csv`, `html`, `cli_summary`, `cli_detailed` |
| `--synapse-fail-under` | Fail if coverage below threshold |
| `--synapse-risk-report` | Include risk assessment in CLI output |
| `--synapse-risk-report-output` | Export risk report to JSON file |
| `--synapse-strict` | Fail on contract violations |
| `--synapse-debug` | Enable debug logging |

## Configuration File

Create `.synapse.yaml` in your project root:

```yaml
spec: ./openapi.yaml

thresholds:
  operations: 80
  paths: 90

ignore:
  paths:
    - /health
    - /metrics
  methods:
    - OPTIONS

risk:
  high_risk_paths:
    - /api/v1/admin/*
    - /api/v1/payments/*
  high_risk_methods:
    - DELETE
    - POST
```

## Supported HTTP Clients

| Client | Sync | Async |
|--------|------|-------|
| requests | Yes | N/A |
| httpx | Yes | Yes |
| aiohttp | N/A | Yes |

## Documentation

- [Usage Guide](https://github.com/Jacky97s/pytest-synapse#usage)
- [Configuration](https://github.com/Jacky97s/pytest-synapse#configuration)
- [Roadmap](https://github.com/Jacky97s/pytest-synapse#roadmap)

## License

MIT License
