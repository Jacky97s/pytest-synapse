# Configuration

pytest-synapse is configured through pytest options. The MVP focuses on a minimal, predictable set of flags.

## pytest.ini example
```ini
[pytest]
addopts = \
  --openapi-spec=./openapi.yaml \
  --synapse-report=coverage.json \
  --synapse-report-format=json
```

## CLI options
- --openapi-spec: Path to the OpenAPI YAML or JSON file, or a URL (http:// or https://) pointing to an OpenAPI spec.
- --synapse-report: Output path for the report file.
- --synapse-report-format: Output format. Planned values: cli_summary, cli_detailed, json.
- --synapse-ignore-paths: Optional comma separated list of paths to exclude.

## Loading OpenAPI specs from URLs

pytest-synapse supports loading OpenAPI specifications directly from URLs:

```bash
# From a remote JSON file
pytest --openapi-spec=https://api.example.com/openapi.json

# From a remote YAML file
pytest --openapi-spec=https://petstore.swagger.io/v2/swagger.yaml
```

The parser automatically detects the format based on:
1. Content-Type header (application/json, application/yaml)
2. URL file extension (.json, .yaml, .yml)
3. Content parsing (tries JSON first, then YAML)

## Environment constraints
- The interceptor must run inside the pytest process to observe client calls.
- If tests spawn subprocesses for HTTP calls, those requests may not be captured in the MVP.
