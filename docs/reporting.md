# Coverage report format

The JSON report is designed for CI and automation. It contains a summary and detailed coverage per path and operation.

## Example structure
```json
{
  "summary": {
    "total_paths": 5,
    "covered_paths": 3,
    "path_coverage_percentage": 60.0,
    "total_operations": 8,
    "covered_operations": 5,
    "operation_coverage_percentage": 62.5,
    "total_request_bodies": 3,
    "covered_request_bodies": 2,
    "request_body_coverage_percentage": 66.7,
    "total_response_schemas": 12,
    "covered_response_schemas": 7,
    "response_schema_coverage_percentage": 58.3,
    "uncovered_items_count": 5
  },
  "details": {
    "/users/{id}": {
      "GET": {
        "status": "COVERED",
        "request_body": {"status": "NOT_APPLICABLE"},
        "responses": {
          "200": {"status": "COVERED", "schema": {"status": "COVERED"}},
          "404": {"status": "UNCOVERED", "schema": {"status": "UNCOVERED"}}
        }
      }
    }
  },
  "uncovered_items_list": [
    {
      "type": "path_method",
      "path": "/products",
      "method": "GET",
      "reason": "No traffic intercepted"
    }
  ]
}
```

## Status values
- COVERED: observed and validated against the spec.
- UNCOVERED: defined in the spec but not observed.
- PARTIALLY_COVERED: some child elements covered, others not.
- NOT_APPLICABLE: not relevant for the operation (for example request body on GET).
