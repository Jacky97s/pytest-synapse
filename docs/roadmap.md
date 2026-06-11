# Roadmap

> For detailed feature specifications, see [FEATURE_PLAN.md](./FEATURE_PLAN.md)

## Current Status: v0.7.0 (Beta)

Core functionality working:
- Transparent HTTP interception for `requests` and `httpx` (sync + async)
- OpenAPI 3.x coverage calculation (paths, operations, schemas)
- Multiple report formats (CLI, JSON, CSV, HTML)
- Field-level and constraint coverage tracking
- CI/CD integration (thresholds, JUnit, GitHub PR comments)
- Developer tools (debug mode, focus filtering, strict validation)
- SDET power tools (test mapping, test generation)
- Risk assessment reporting

---

## v0.4.0 - CI/CD Ready (COMPLETED)

**Goal**: Make pytest-synapse production-ready for CI pipelines.

| Feature | Status | Priority |
|---------|--------|----------|
| `--synapse-fail-under` threshold | ✅ DONE | P0 |
| `--synapse-baseline` coverage diff | ✅ DONE | P0 |
| `--synapse-junit` XML output | ✅ DONE | P0 |
| `.synapse.yaml` config file | ✅ DONE | P1 |

**Exit Criteria**: Can gate PRs on API coverage thresholds. ✅

---

## v0.5.0 - Developer Experience (COMPLETED)

**Goal**: Make debugging and development faster.

| Feature | Status | Priority |
|---------|--------|----------|
| `--synapse-strict` contract violations | ✅ DONE | P0 |
| `--synapse-debug` mode | ✅ DONE | P0 |
| `--synapse-focus` single endpoint | ✅ DONE | P1 |
| Async httpx support | ✅ DONE | P1 |
| aiohttp support | ✅ DONE | P2 |

**Exit Criteria**: Developers can quickly debug why coverage isn't working. ✅

---

## v0.6.0 - SDET Power Tools (COMPLETED)

**Goal**: Advanced features for test engineers.

| Feature | Status | Priority |
|---------|--------|----------|
| `--synapse-test-map` endpoint mapping | ✅ DONE | P0 |
| `--synapse-generate-tests` stub generation | ✅ DONE | P1 |
| `--synapse-validate-mocks` | 🔲 TODO | P1 |
| Parallel test coverage merge | 🔲 TODO | P2 |
| `--synapse-optimize` minimum test set | 🔲 TODO | P2 |

**Exit Criteria**: SDETs can analyze test-to-endpoint coverage. ✅

---

## v0.7.0 - QA & Reporting (COMPLETED)

**Goal**: Beautiful reports for stakeholders.

| Feature | Status | Priority |
|---------|--------|----------|
| `--synapse-github-comment` PR integration | ✅ DONE | P0 |
| Interactive HTML dashboard | 🔲 TODO | P1 |
| `--synapse-risk-report` | ✅ DONE | P1 |
| Historical coverage tracking | 🔲 TODO | P2 |

**Exit Criteria**: QA can share coverage reports with stakeholders. ✅

---

## v1.0.0 - Production Ready (Next)

**Goal**: Stable, polished, enterprise-ready.

| Feature | Status | Priority |
|---------|--------|----------|
| VS Code extension | 🔲 TODO | P1 |
| Slack/Teams notifications | 🔲 TODO | P2 |
| `--synapse-watch` mode | 🔲 TODO | P2 |
| pytest markers integration | 🔲 TODO | P2 |
| `--synapse-validate-mocks` | 🔲 TODO | P1 |
| Parallel test coverage merge | 🔲 TODO | P2 |
| Interactive HTML dashboard | 🔲 TODO | P1 |
| Historical coverage tracking | 🔲 TODO | P2 |

---

## Completed Features Summary

### v0.4 - CI/CD Ready
- **`--synapse-fail-under`**: Exit code 2 when coverage below threshold
- **`--synapse-fail-under-operations/paths/schemas`**: Per-metric thresholds
- **`--synapse-baseline`**: Compare against baseline coverage
- **`--synapse-save-baseline`**: Save current coverage as baseline
- **`--synapse-fail-on-regression`**: Fail on coverage regression
- **`--synapse-junit`**: JUnit XML output for CI systems
- **`--synapse-config`**: Load settings from .synapse.yaml

### v0.5 - Developer Experience
- **`--synapse-strict`**: Fail tests on contract violations
- **`--synapse-debug`**: Log intercepted requests with matching details
- **`--synapse-focus`**: Filter coverage to specific endpoints
- **Async httpx support**: Full async httpx.AsyncClient interception
- **aiohttp support**: aiohttp.ClientSession interception

### v0.6 - SDET Power Tools
- **`--synapse-test-map`**: JSON mapping of tests to endpoints
- **`--synapse-generate-tests`**: Generate test stubs for uncovered endpoints

### v0.7 - QA & Reporting
- **`--synapse-github-comment`**: Post coverage to GitHub PRs
- **`--synapse-risk-report`**: Risk assessment categorizing endpoints

---

## Contributing

We prioritize features based on user impact. See [FEATURE_PLAN.md](./FEATURE_PLAN.md) for:
- Detailed specifications
- Implementation guidance
- User pain points each feature solves

**Most Wanted**: VS Code extension, Interactive HTML dashboard
