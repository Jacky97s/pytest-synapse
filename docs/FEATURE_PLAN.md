# pytest-synapse Feature Plan v2

**Focused on real Developer, SDET, and QA workflows**

---

## Part 1: Must-Have Features for CI/CD (Ship First)

### 1.1 Fail Build on Low Coverage (`--synapse-fail-under`)

**The Pain**: Developers merge PRs without knowing API coverage dropped.

```bash
# Fail if operation coverage drops below 80%
pytest --openapi-spec=api.yaml --synapse-fail-under=80

# Fail with different thresholds per metric
pytest --synapse-fail-under-operations=90 \
       --synapse-fail-under-paths=80 \
       --synapse-fail-under-schemas=70
```

**Exit Codes**:
- `0`: All tests pass, coverage meets threshold
- `1`: Tests failed
- `2`: Tests passed but coverage below threshold

**Why It Matters**: This is THE feature SDETs need for CI gates.

---

### 1.2 GitHub PR Integration (`--synapse-github-comment`)

**The Pain**: Coverage changes are invisible in PRs.

```bash
pytest --synapse-github-comment --synapse-baseline=main-coverage.json
```

**Automatically posts PR comment**:
```markdown
## 📊 API Coverage Report

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Operations | 85% | 82% | ⬇️ -3% |
| Paths | 90% | 90% | ➡️ 0% |
| Schemas | 78% | 80% | ⬆️ +2% |

### ❌ Newly Uncovered
- `DELETE /users/{id}` - Was covered, now missing
- `POST /orders` 400 response - No longer tested

### ✅ Newly Covered
- `PATCH /users/{id}` - Now tested
```

**Also supports**: GitLab MR comments, Bitbucket PR comments

---

### 1.3 Coverage Baseline & Diff (`--synapse-baseline`)

**The Pain**: No way to detect coverage regression between runs.

```bash
# Save baseline (run on main branch)
pytest --synapse-save-baseline=.synapse-baseline.json

# Compare in PR (fail on regression)
pytest --synapse-baseline=.synapse-baseline.json --synapse-fail-on-regression
```

**Output**:
```
Coverage Diff (vs baseline):
  Operations: 85% → 82% (⬇️ -3%)

REGRESSION DETECTED:
  - DELETE /users/{id}: Was COVERED, now UNCOVERED
  - POST /orders: 400 response no longer tested

NEW COVERAGE:
  + PATCH /users/{id}: Now COVERED
```

---

### 1.4 JUnit XML Output (`--synapse-junit`)

**The Pain**: CI systems (Jenkins, GitHub Actions, GitLab) expect JUnit format.

```bash
pytest --synapse-junit=api-coverage.xml
```

**Output**: Each uncovered operation as a "failed test":
```xml
<testsuite name="API Coverage" tests="15" failures="3">
  <testcase name="DELETE /users/{id}" classname="coverage">
    <failure message="Operation not covered">
      No test exercised DELETE /users/{id}
    </failure>
  </testcase>
</testsuite>
```

**Integrates with**: GitHub Actions test reporter, Jenkins, Azure DevOps

---

## Part 2: Developer Experience Features

### 2.1 Watch Mode (`--synapse-watch`)

**The Pain**: Run full test suite just to check one endpoint's coverage.

```bash
pytest --synapse-watch
```

**Behavior**:
- Shows live coverage as tests run
- Reruns on file changes
- Highlights newly covered/uncovered operations
- Perfect for TDD workflow

**Output (live updating)**:
```
Watching for changes... (Ctrl+C to stop)

[12:34:56] Running tests...
  ✅ GET /users       COVERED
  ✅ POST /users      COVERED
  ⏳ DELETE /users/{id}  UNCOVERED (try adding a test!)

Coverage: 66% operations (2/3)
```

---

### 2.2 Single-Endpoint Focus (`--synapse-focus`)

**The Pain**: "I just want to see coverage for the endpoint I'm working on"

```bash
# Focus on specific path
pytest --synapse-focus="/users/{id}"

# Focus on specific operation
pytest --synapse-focus="POST /orders"

# Focus with pattern
pytest --synapse-focus="/admin/*"
```

**Output**: Only shows coverage for focused endpoints, ignores rest.

---

### 2.3 Debug Mode (`--synapse-debug`)

**The Pain**: "Why isn't my endpoint being detected as covered?"

```bash
pytest --synapse-debug
```

**Output**:
```
[SYNAPSE DEBUG] Intercepted: GET http://localhost:8000/users/123
  → Matched to: GET /users/{id}
  → Request body: None (N/A for GET)
  → Response: 200 (MATCHED spec)
  → Schema validation: VALID

[SYNAPSE DEBUG] Intercepted: POST http://localhost:8000/items
  → NO MATCH FOUND
  → Closest paths in spec: POST /products, POST /inventory
  → Reason: /items not defined in OpenAPI spec
```

---

### 2.4 Contract Violation Detection (`--synapse-strict`)

**The Pain**: Tests pass but API responses don't match the spec.

```bash
pytest --synapse-strict  # Fail tests on contract violations
```

**Detects**:
- Response missing required fields
- Wrong data types (string where number expected)
- Extra fields not in spec (optional strict mode)
- Enum values not in allowed list
- String patterns not matching

**Output**:
```
CONTRACT VIOLATIONS DETECTED:

❌ GET /users/123 → 200 response
   - Missing required field: 'email'
   - Field 'age' is string, expected integer
   - Field 'status' value 'PENDING' not in enum ['ACTIVE', 'INACTIVE']

❌ POST /orders → 201 response
   - Extra field 'internal_id' not defined in schema
```

---

### 2.5 Auto-Generate Test Stubs (`--synapse-generate-tests`)

**The Pain**: "What tests should I write for uncovered endpoints?"

```bash
pytest --synapse-generate-tests=generated_tests.py
```

**Generates actual runnable test stubs**:
```python
# Auto-generated by pytest-synapse
# Endpoint: DELETE /users/{id} - Currently UNCOVERED

import pytest
import requests

BASE_URL = "http://localhost:8000"  # Update this

class TestDeleteUsersId:
    """Tests for DELETE /users/{id}"""

    def test_delete_user_204_success(self):
        """Test successful user deletion (204 No Content)"""
        # TODO: Create a user first or use existing user_id
        user_id = 1
        response = requests.delete(f"{BASE_URL}/users/{user_id}")
        assert response.status_code == 204

    def test_delete_user_404_not_found(self):
        """Test deleting non-existent user (404 Not Found)"""
        response = requests.delete(f"{BASE_URL}/users/999999")
        assert response.status_code == 404
        # Expected response schema: {"error": "string", "message": "string"}
        data = response.json()
        assert "error" in data
```

---

## Part 3: SDET Power Features

### 3.1 Test-to-Endpoint Mapping (`--synapse-test-map`)

**The Pain**: "Which tests cover which endpoints? Which endpoints have only one test?"

```bash
pytest --synapse-test-map=test-map.json
```

**Output**:
```json
{
  "endpoint_to_tests": {
    "GET /users": ["test_api.py::test_list_users", "test_api.py::test_list_users_paginated"],
    "DELETE /users/{id}": ["test_api.py::test_delete_user"]
  },
  "test_to_endpoints": {
    "test_api.py::test_list_users": ["GET /users"],
    "test_api.py::test_crud_user": ["POST /users", "GET /users/{id}", "DELETE /users/{id}"]
  },
  "single_test_coverage": ["DELETE /users/{id}"],  // Risk: only 1 test!
  "redundant_coverage": {
    "GET /users": 5  // 5 tests hit same endpoint - maybe consolidate?
  }
}
```

**Use Cases**:
- Find endpoints with single point of failure (1 test)
- Find redundant tests hitting same endpoint
- Impact analysis: "If I delete this test, what loses coverage?"

---

### 3.2 Mock Validation (`--synapse-validate-mocks`)

**The Pain**: Mocks drift from actual API spec.

```bash
pytest --synapse-validate-mocks
```

**Works with**: responses, respx, httpretty, pytest-httpserver

**Detects**:
```
MOCK VALIDATION WARNINGS:

⚠️ tests/test_users.py::test_get_user
   Mock for GET /users/{id} returns:
     {"id": 1, "name": "Test"}

   But spec requires:
     {"id": integer, "name": string, "email": string (REQUIRED)}

   Missing required field: 'email'
```

---

### 3.3 Minimum Test Set (`--synapse-optimize`)

**The Pain**: "Which tests can I skip while maintaining coverage?"

```bash
pytest --synapse-optimize
```

**Output**:
```
TEST OPTIMIZATION ANALYSIS:

Minimum test set for current coverage (8 tests instead of 45):
  ✓ test_api.py::test_crud_user_lifecycle
  ✓ test_api.py::test_orders_flow
  ✓ test_api.py::test_error_responses
  ...

Tests that can be skipped (covered by others):
  - test_api.py::test_get_user (covered by test_crud_user_lifecycle)
  - test_api.py::test_get_user_not_found (covered by test_error_responses)

Potential savings: Run 8 tests instead of 45 (82% faster)
```

---

### 3.4 Async Support (httpx, aiohttp)

**The Pain**: Async codebases can't use pytest-synapse.

```python
# Just works with async
import httpx
import pytest

@pytest.mark.asyncio
async def test_async_api():
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8000/users")
        assert response.status_code == 200
```

**Supports**:
- `httpx.AsyncClient`
- `aiohttp.ClientSession`
- Works with `pytest-asyncio` and `pytest-aiohttp`

---

### 3.5 Parallel Test Coverage Merge

**The Pain**: Parallel test runs have incomplete coverage each.

```bash
# Run tests in parallel (pytest-xdist)
pytest -n 4 --synapse-report=coverage-{worker}.json

# Merge coverage from all workers
synapse merge coverage-*.json -o combined-coverage.json
```

**Also supports**: Merging coverage from different CI jobs

---

## Part 4: QA & Reporting Features

### 4.1 Historical Coverage Tracking

**The Pain**: "Is coverage improving or declining over time?"

```bash
# Store coverage in history
pytest --synapse-history

# View trend
synapse history --last 30
```

**Output**:
```
Coverage Trend (Last 30 days):

Operations:  ████████████████░░░░ 82% (+5% from 30d ago)
Paths:       ██████████████████░░ 90% (+2%)
Schemas:     ████████████████░░░░ 78% (+8%)

        Dec 1   Dec 8   Dec 15   Dec 22   Dec 29
Ops:      77%     79%     80%      81%     82%
Paths:    88%     89%     89%      90%     90%
```

**Storage**: SQLite file, PostgreSQL, or cloud service

---

### 4.2 Risk Assessment Report

**The Pain**: "Which untested endpoints are highest risk?"

```bash
pytest --synapse-risk-report
```

**Output**:
```
API RISK ASSESSMENT:

🔴 HIGH RISK (Untested + Critical):
   DELETE /users/{id} - Data destruction, no coverage
   POST /payments - Financial operation, no coverage
   PUT /admin/settings - Admin operation, no coverage

🟡 MEDIUM RISK (Partial coverage):
   POST /orders - 201 covered, but 400/500 not tested
   PATCH /users/{id} - Success tested, validation errors not

🟢 LOW RISK (Well covered):
   GET /users - All scenarios tested
   GET /products - All scenarios tested
```

**Factors considered**:
- HTTP method (DELETE/POST riskier than GET)
- Path patterns (/admin/*, /payments/*)
- Response codes (error paths untested?)
- Schema complexity

---

### 4.3 Interactive HTML Dashboard

**The Pain**: Static reports hard to navigate for large APIs.

```bash
pytest --synapse-dashboard
# Opens browser with interactive report
```

**Features**:
- Collapsible tree view
- Search/filter by path, method, status
- Click to see which tests cover each endpoint
- Diff view comparing to baseline
- Export to PDF for stakeholders
- Share link for team

---

### 4.4 Slack/Teams Notifications

**The Pain**: Coverage drops but nobody notices until too late.

```yaml
# .synapse.yaml
notifications:
  slack:
    webhook: ${SLACK_WEBHOOK_URL}
    on:
      - coverage_dropped
      - new_uncovered_critical  # /admin/*, /payments/*
      - contract_violation
```

**Message**:
```
🚨 API Coverage Alert

Coverage dropped from 85% to 78% in PR #123
Newly uncovered: DELETE /users/{id}, POST /orders

View report: https://...
```

---

### 4.5 Coverage Badge for README

```bash
pytest --synapse-badge=coverage-badge.svg
```

**Generates**:
![API Coverage](https://img.shields.io/badge/API%20Coverage-85%25-green)

**Dynamic badge endpoint**:
```markdown
![API Coverage](https://your-ci.com/synapse/badge/main)
```

---

## Part 5: Configuration & Developer Experience

### 5.1 Configuration File (`.synapse.yaml`)

**The Pain**: Long CLI commands, inconsistent across team.

```yaml
# .synapse.yaml
spec: ./openapi.yaml

thresholds:
  operations: 80
  paths: 90
  schemas: 70

ignore:
  paths:
    - /health
    - /metrics
    - /internal/*
  methods:
    - OPTIONS
  status_codes:
    - 500  # Don't require 500 error coverage

reporting:
  format: html
  output: coverage-report.html
  include_suggestions: true

ci:
  fail_on_regression: true
  baseline: .synapse-baseline.json
  github_comment: true

notifications:
  slack:
    webhook: ${SLACK_WEBHOOK}
    on_failure: true
```

---

### 5.2 VS Code Extension

**The Pain**: Have to run tests to see coverage.

**Features**:
- Inline coverage indicators in test files
- "Jump to uncovered endpoint" command
- Coverage gutter in OpenAPI spec file
- Quick test generation for uncovered endpoints

---

### 5.3 pytest Markers Integration

```python
import pytest

@pytest.mark.synapse_covers("GET /users/{id}")
def test_get_user():
    """Explicitly declare which endpoint this test covers"""
    ...

@pytest.mark.synapse_skip
def test_internal_helper():
    """Don't count HTTP calls from this test"""
    ...

@pytest.mark.synapse_expect_violation
def test_invalid_response():
    """This test intentionally triggers contract violation"""
    ...
```

---

## Implementation Priority

### Phase 1: CI/CD Essentials (v0.4)
1. `--synapse-fail-under` threshold enforcement
2. `--synapse-baseline` and `--synapse-fail-on-regression`
3. `--synapse-junit` JUnit XML output
4. Configuration file support

### Phase 2: Developer Experience (v0.5)
5. `--synapse-strict` contract violations
6. `--synapse-debug` mode
7. `--synapse-focus` single endpoint
8. Async httpx/aiohttp support

### Phase 3: SDET Power Tools (v0.6)
9. `--synapse-test-map` test-to-endpoint mapping
10. `--synapse-generate-tests` stub generation
11. `--synapse-validate-mocks` mock validation
12. Parallel test coverage merge

### Phase 4: QA & Reporting (v0.7)
13. `--synapse-github-comment` PR integration
14. Interactive HTML dashboard
15. Historical tracking
16. Risk assessment report

### Phase 5: Polish (v1.0)
17. VS Code extension
18. Slack/Teams notifications
19. Coverage badge generation
20. `--synapse-watch` mode

---

## Quick Wins (Can Ship This Week)

1. **`--synapse-fail-under`** - 50 lines of code in `plugin.py`
2. **`--synapse-junit`** - 100 lines in `report.py`
3. **`--synapse-debug`** - Add logging to `interceptor.py`
4. **`.synapse.yaml` config** - 150 lines, new module

These 4 features would make pytest-synapse CI/CD ready.
