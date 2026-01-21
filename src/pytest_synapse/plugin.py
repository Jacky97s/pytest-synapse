"""pytest plugin for OpenAPI coverage measurement."""

from typing import Generator, Optional

import pytest

from pytest_synapse.coverage_engine import SynapseCoverageEngine
from pytest_synapse.flow_logger import SynapseFlowLogger
from pytest_synapse.interceptor import SynapseInterceptor
from pytest_synapse.report import ReportRenderer
from pytest_synapse.spec_parser import OpenAPISpecParser


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add command line options for pytest-synapse."""
    group = parser.getgroup("synapse", "OpenAPI coverage options")

    group.addoption(
        "--openapi-spec",
        dest="openapi_spec",
        metavar="PATH",
        help="Path to the OpenAPI specification file (YAML or JSON)",
    )

    group.addoption(
        "--synapse-report",
        dest="synapse_report",
        metavar="PATH",
        help="Path to write the coverage report",
    )

    group.addoption(
        "--synapse-report-format",
        dest="synapse_report_format",
        choices=["json", "cli_summary", "cli_detailed"],
        default="cli_summary",
        help="Format for the coverage report (default: cli_summary)",
    )

    group.addoption(
        "--synapse-ignore-paths",
        dest="synapse_ignore_paths",
        metavar="PATHS",
        help="Comma-separated list of paths to ignore",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Configure the pytest-synapse plugin."""
    # Only activate if an OpenAPI spec is provided
    if not config.option.openapi_spec:
        return

    # Store the spec path in config for later use
    config._synapse_spec_path = config.option.openapi_spec
    config._synapse_report_path = config.option.synapse_report
    config._synapse_report_format = config.option.synapse_report_format


def pytest_sessionstart(session: pytest.Session) -> None:
    """Start the synapse session - activate interception."""
    config = session.config

    if not hasattr(config, "_synapse_spec_path"):
        return

    # Initialize the flow logger
    logger = SynapseFlowLogger()
    logger.reset()

    # Initialize and activate the interceptor
    interceptor = SynapseInterceptor()
    activated = interceptor.activate(logger)

    # Store references in session for later use
    session._synapse_logger = logger
    session._synapse_interceptor = interceptor

    if activated:
        print(f"\npytest-synapse: Intercepting HTTP traffic from: {', '.join(activated)}")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(
    item: pytest.Item, nextitem: Optional[pytest.Item]
) -> Generator[None, None, None]:
    """Track the current test being executed."""
    session = item.session

    if hasattr(session, "_synapse_logger"):
        session._synapse_logger.set_current_test(item.nodeid)

    yield


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """End the synapse session - generate coverage report."""
    config = session.config

    if not hasattr(session, "_synapse_interceptor"):
        return

    # Deactivate the interceptor
    session._synapse_interceptor.deactivate()

    # Get all captured events
    logger: SynapseFlowLogger = session._synapse_logger
    events = logger.get_events()

    if not events:
        print("\npytest-synapse: No HTTP traffic was captured")
        return

    print(f"\npytest-synapse: Captured {len(events)} HTTP requests/responses")

    # Parse the OpenAPI spec
    try:
        spec = OpenAPISpecParser(config._synapse_spec_path)
    except (FileNotFoundError, ValueError) as e:
        print(f"\npytest-synapse: Error loading OpenAPI spec: {e}")
        return

    # Create coverage engine and process events
    engine = SynapseCoverageEngine(spec)
    engine.process_events(events)

    # Generate and output the report
    renderer = ReportRenderer(engine)

    # Always print CLI summary to terminal
    print(renderer.render_cli_summary())

    # Write report file if specified
    report_path = getattr(config, "_synapse_report_path", None)
    report_format = getattr(config, "_synapse_report_format", "cli_summary")

    if report_path:
        renderer.write_report(report_path, report_format)
        print(f"pytest-synapse: Report written to {report_path}")


def pytest_unconfigure(config: pytest.Config) -> None:
    """Clean up synapse resources."""
    SynapseFlowLogger.destroy()


# Fixtures for programmatic access


@pytest.fixture
def synapse_flow_logger() -> SynapseFlowLogger:
    """Fixture to access the flow logger directly."""
    return SynapseFlowLogger()


@pytest.fixture
def synapse_events(synapse_flow_logger: SynapseFlowLogger):
    """Fixture to access captured events for the current test."""
    yield
    # After the test, return events for this test
    test_id = synapse_flow_logger.get_current_test()
    if test_id:
        return synapse_flow_logger.get_events_for_test(test_id)
    return []
