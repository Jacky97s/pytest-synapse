# pytest-synapse Documentation

Welcome to the pytest-synapse documentation. This folder contains comprehensive guides for installing, configuring, and using pytest-synapse to measure OpenAPI contract test coverage.

## What is pytest-synapse?

pytest-synapse is a pytest plugin that measures OpenAPI contract test coverage by transparently intercepting HTTP traffic during test execution. It bridges dynamic test execution with a static OpenAPI definition, computing coverage for paths, methods, request bodies, response status codes, and response schemas.

## Key Features

- **Transparent Interception**: Automatically captures HTTP requests/responses from `requests` and `httpx` libraries without modifying test code
- **OpenAPI Coverage**: Maps captured traffic to your OpenAPI 3.x specification
- **Granular Metrics**: Coverage for paths, HTTP methods, request bodies, response status codes, and response schemas
- **Multiple Output Formats**: CLI summary, detailed CLI output, and JSON reports
- **URL Support**: Load OpenAPI specs from local files or remote URLs
- **HTTPS Friendly**: Captures decrypted payloads above TLS layer

## Quick Links

| Document | Description |
|----------|-------------|
| [Usage Guide](usage.md) | Complete installation and implementation guide |
| [Configuration](configuration.md) | CLI options and pytest.ini settings |
| [Architecture](architecture.md) | System design and component overview |
| [Reporting](reporting.md) | Coverage report formats and metrics |
| [Roadmap](roadmap.md) | Future features and enhancements |

## Getting Started

### 1. Install

```bash
pip install pytest-synapse
```

### 2. Run with OpenAPI Spec

```bash
pytest --openapi-spec=./openapi.yaml
```

### 3. View Coverage

```
==================================================
OpenAPI Coverage Report
==================================================

Paths:            2/2 (100.0%)
Operations:       3/3 (100.0%)
Request Bodies:   1/1 (100.0%)
Response Schemas: 5/5 (100.0%)
```

## Documentation Index

### Core Documentation

- **[Usage Guide](usage.md)** - Step-by-step instructions for installation, basic usage, and integration with your test suite. Includes examples for `requests` and `httpx` libraries, mock library integration, and CI/CD setup.

- **[Configuration](configuration.md)** - All configuration options including CLI flags, pytest.ini settings, and URL loading for remote OpenAPI specs.

### Technical Documentation

- **[Architecture](architecture.md)** - Technical overview of the system architecture, including the interceptor layer, flow logger, coverage engine, and report renderer.

- **[Reporting](reporting.md)** - Detailed explanation of coverage report formats, metrics definitions, and how to interpret results.

### Planning

- **[Roadmap](roadmap.md)** - Planned features and future enhancements including async httpx support, deep schema validation, and more.

## Guiding Principles

1. **Transparent Interception**: No changes to test code or HTTP clients required
2. **HTTPS Friendly**: Capture decrypted payloads above the TLS layer
3. **Adaptive Support**: Automatically detect and patch popular clients
4. **Normalized Data Model**: Unified traffic representation across clients
5. **Actionable Coverage**: Clear reporting of what is covered and what is not

## Supported HTTP Clients

| Client | Sync | Async |
|--------|------|-------|
| requests | Yes | N/A |
| httpx | Yes | Planned |

## Need Help?

- Check the [Usage Guide](usage.md) for detailed examples
- Review [Configuration](configuration.md) for all available options
- See the main [README](../README.md) for quick start instructions
