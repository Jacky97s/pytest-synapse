"""pytest plugin for OpenAPI coverage measurement."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

import pytest

from pytest_synapse.coverage_engine import SynapseCoverageEngine
from pytest_synapse.flow_logger import SynapseFlowLogger
from pytest_synapse.interceptor import SynapseInterceptor
from pytest_synapse.report import ReportRenderer
from pytest_synapse.spec_parser import OpenAPISpecParser

# Custom exit code for coverage threshold failure
COVERAGE_THRESHOLD_EXIT_CODE = 2


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add command line options for pytest-synapse."""
    group = parser.getgroup("synapse", "OpenAPI coverage options")

    # Basic options
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
        choices=["json", "csv", "html", "cli_summary", "cli_detailed", "junit"],
        default="cli_summary",
        help="Format for the coverage report: json, csv, html, cli_summary, cli_detailed, junit (default: cli_summary)",
    )

    group.addoption(
        "--synapse-ignore-paths",
        dest="synapse_ignore_paths",
        metavar="PATHS",
        help="Comma-separated list of paths to ignore",
    )

    group.addoption(
        "--sv",
        "--synapse-verbose",
        dest="synapse_verbosity",
        action="count",
        default=0,
        help=(
            "Increase synapse report verbosity (use multiple times for more detail). "
            "Level 1: Show covered/uncovered APIs. "
            "Level 2: Show field-level coverage. "
            "Level 3: Show constraints and suggestions."
        ),
    )

    group.addoption(
        "--synapse-show-suggestions",
        dest="synapse_show_suggestions",
        action="store_true",
        default=False,
        help="Show coverage improvement suggestions",
    )

    # v0.4: CI/CD Features
    group.addoption(
        "--synapse-fail-under",
        dest="synapse_fail_under",
        metavar="PERCENT",
        type=float,
        help="Fail if overall operation coverage is below this percentage (0-100)",
    )

    group.addoption(
        "--synapse-fail-under-operations",
        dest="synapse_fail_under_operations",
        metavar="PERCENT",
        type=float,
        help="Fail if operation coverage is below this percentage",
    )

    group.addoption(
        "--synapse-fail-under-paths",
        dest="synapse_fail_under_paths",
        metavar="PERCENT",
        type=float,
        help="Fail if path coverage is below this percentage",
    )

    group.addoption(
        "--synapse-fail-under-schemas",
        dest="synapse_fail_under_schemas",
        metavar="PERCENT",
        type=float,
        help="Fail if schema coverage is below this percentage",
    )

    group.addoption(
        "--synapse-baseline",
        dest="synapse_baseline",
        metavar="PATH",
        help="Path to baseline coverage JSON for comparison",
    )

    group.addoption(
        "--synapse-save-baseline",
        dest="synapse_save_baseline",
        metavar="PATH",
        help="Save current coverage as baseline to this path",
    )

    group.addoption(
        "--synapse-fail-on-regression",
        dest="synapse_fail_on_regression",
        action="store_true",
        default=False,
        help="Fail if coverage regresses from baseline",
    )

    group.addoption(
        "--synapse-junit",
        dest="synapse_junit",
        metavar="PATH",
        help="Write JUnit XML report to this path",
    )

    group.addoption(
        "--synapse-config",
        dest="synapse_config",
        metavar="PATH",
        help="Path to .synapse.yaml configuration file",
    )

    # v0.5: Developer Experience
    group.addoption(
        "--synapse-strict",
        dest="synapse_strict",
        action="store_true",
        default=False,
        help="Fail on any contract violations (schema mismatches)",
    )

    group.addoption(
        "--synapse-debug",
        dest="synapse_debug",
        action="store_true",
        default=False,
        help="Enable debug mode - log all intercepted requests and matching",
    )

    group.addoption(
        "--synapse-focus",
        dest="synapse_focus",
        metavar="PATTERN",
        help="Focus on specific endpoints (e.g., '/users/*' or 'POST /orders')",
    )

    # v0.6: SDET Power Tools
    group.addoption(
        "--synapse-test-map",
        dest="synapse_test_map",
        metavar="PATH",
        help="Write test-to-endpoint mapping JSON to this path",
    )

    group.addoption(
        "--synapse-generate-tests",
        dest="synapse_generate_tests",
        metavar="PATH",
        help="Generate test stubs for uncovered endpoints to this path",
    )

    # v0.7: QA & Reporting
    group.addoption(
        "--synapse-github-comment",
        dest="synapse_github_comment",
        action="store_true",
        default=False,
        help="Post coverage report as GitHub PR comment",
    )

    group.addoption(
        "--synapse-risk-report",
        dest="synapse_risk_report",
        action="store_true",
        default=False,
        help="Include risk assessment in the CLI report",
    )

    group.addoption(
        "--synapse-risk-report-output",
        dest="synapse_risk_report_output",
        metavar="PATH",
        default=None,
        help="Output path for JSON risk report file",
    )


def _load_config_file(config_path: Optional[str]) -> Dict[str, Any]:
    """Load configuration from .synapse.yaml file."""
    if config_path:
        path = Path(config_path)
    else:
        # Look for .synapse.yaml in current directory
        path = Path(".synapse.yaml")
        if not path.exists():
            path = Path("synapse.yaml")
        if not path.exists():
            return {}

    if not path.exists():
        return {}

    try:
        import yaml
        with open(path, "r") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def pytest_configure(config: pytest.Config) -> None:
    """Configure the pytest-synapse plugin."""
    # Load config file first
    config_file = getattr(config.option, "synapse_config", None)
    file_config = _load_config_file(config_file)

    # Determine spec path (CLI takes precedence over config file)
    spec_path = config.option.openapi_spec or file_config.get("spec")

    if not spec_path:
        return

    # Store all configuration
    config._synapse_spec_path = spec_path
    config._synapse_report_path = config.option.synapse_report or file_config.get("reporting", {}).get("output")
    config._synapse_report_format = config.option.synapse_report_format or file_config.get("reporting", {}).get("format", "cli_summary")
    config._synapse_verbosity = config.option.synapse_verbosity
    config._synapse_show_suggestions = config.option.synapse_show_suggestions or file_config.get("reporting", {}).get("include_suggestions", False)

    # CI/CD options
    thresholds = file_config.get("thresholds", {})
    config._synapse_fail_under = config.option.synapse_fail_under or thresholds.get("operations")
    config._synapse_fail_under_operations = config.option.synapse_fail_under_operations or thresholds.get("operations")
    config._synapse_fail_under_paths = config.option.synapse_fail_under_paths or thresholds.get("paths")
    config._synapse_fail_under_schemas = config.option.synapse_fail_under_schemas or thresholds.get("schemas")

    ci_config = file_config.get("ci", {})
    config._synapse_baseline = config.option.synapse_baseline or ci_config.get("baseline")
    config._synapse_save_baseline = config.option.synapse_save_baseline
    config._synapse_fail_on_regression = config.option.synapse_fail_on_regression or ci_config.get("fail_on_regression", False)
    config._synapse_junit = config.option.synapse_junit

    # Developer options
    config._synapse_strict = config.option.synapse_strict
    config._synapse_debug = config.option.synapse_debug
    config._synapse_focus = config.option.synapse_focus

    # SDET options
    config._synapse_test_map = config.option.synapse_test_map
    config._synapse_generate_tests = config.option.synapse_generate_tests

    # QA options
    config._synapse_github_comment = config.option.synapse_github_comment or ci_config.get("github_comment", False)
    config._synapse_risk_report = config.option.synapse_risk_report
    config._synapse_risk_report_output = config.option.synapse_risk_report_output

    # Risk assessment custom patterns from config
    risk_config = file_config.get("risk", {})
    config._synapse_custom_risk_paths = risk_config.get("high_risk_paths", [])
    config._synapse_custom_risk_methods = risk_config.get("high_risk_methods", [])

    # Ignore patterns
    ignore_config = file_config.get("ignore", {})
    ignore_paths = config.option.synapse_ignore_paths
    if ignore_paths:
        config._synapse_ignore_paths = [p.strip() for p in ignore_paths.split(",")]
    else:
        config._synapse_ignore_paths = ignore_config.get("paths", [])


def pytest_sessionstart(session: pytest.Session) -> None:
    """Start the synapse session - activate interception."""
    config = session.config

    if not hasattr(config, "_synapse_spec_path"):
        return

    # Initialize the flow logger
    logger = SynapseFlowLogger()
    logger.reset()

    # Initialize and activate the interceptor
    debug_mode = getattr(config, "_synapse_debug", False)
    interceptor = SynapseInterceptor(debug=debug_mode)
    activated = interceptor.activate(logger)

    # Store references in session for later use
    session._synapse_logger = logger
    session._synapse_interceptor = interceptor
    session._synapse_engine = None  # Will be set after processing

    if activated:
        print(f"\npytest-synapse: Intercepting HTTP traffic from: {', '.join(activated)}")
        if debug_mode:
            print("pytest-synapse: Debug mode enabled - logging all requests")


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

    # Apply focus filter if specified
    focus_pattern = getattr(config, "_synapse_focus", None)

    # Create coverage engine and process events
    engine = SynapseCoverageEngine(spec)
    engine.process_events(events)

    # Store engine for access by other hooks
    session._synapse_engine = engine

    # Generate and output the report
    verbosity = getattr(config, "_synapse_verbosity", 0)
    show_suggestions = getattr(config, "_synapse_show_suggestions", False)
    show_risk = getattr(config, "_synapse_risk_report", False)
    risk_report_output = getattr(config, "_synapse_risk_report_output", None)
    custom_risk_paths = getattr(config, "_synapse_custom_risk_paths", [])
    custom_risk_methods = getattr(config, "_synapse_custom_risk_methods", [])

    # Enable risk report if output path is specified
    if risk_report_output:
        show_risk = True

    renderer = ReportRenderer(
        engine,
        verbosity=verbosity,
        show_suggestions=show_suggestions,
        show_risk=show_risk,
        focus_pattern=focus_pattern,
        custom_risk_paths=custom_risk_paths,
        custom_risk_methods=custom_risk_methods,
    )

    # Print CLI output based on verbosity level
    if verbosity >= 2:
        print(renderer.render_cli_detailed())
    elif verbosity >= 1:
        print(renderer.render_cli_verbose())
    else:
        print(renderer.render_cli_summary())

    # Write report file if specified
    report_path = getattr(config, "_synapse_report_path", None)
    report_format = getattr(config, "_synapse_report_format", "cli_summary")

    if report_path:
        renderer.write_report(report_path, report_format)
        print(f"pytest-synapse: Report written to {report_path}")

    # Write risk report JSON if specified
    if risk_report_output:
        risk_json = renderer.render_risk_report_json()
        Path(risk_report_output).write_text(risk_json)
        print(f"pytest-synapse: Risk report written to {risk_report_output}")

    # Write JUnit XML if specified
    junit_path = getattr(config, "_synapse_junit", None)
    if junit_path:
        _write_junit_report(engine, junit_path)
        print(f"pytest-synapse: JUnit report written to {junit_path}")

    # Save baseline if specified
    save_baseline_path = getattr(config, "_synapse_save_baseline", None)
    if save_baseline_path:
        _save_baseline(engine, save_baseline_path)
        print(f"pytest-synapse: Baseline saved to {save_baseline_path}")

    # Compare with baseline if specified
    baseline_path = getattr(config, "_synapse_baseline", None)
    if baseline_path:
        _compare_baseline(engine, baseline_path, config, session)

    # Write test map if specified
    test_map_path = getattr(config, "_synapse_test_map", None)
    if test_map_path:
        _write_test_map(engine, events, test_map_path)
        print(f"pytest-synapse: Test map written to {test_map_path}")

    # Generate test stubs if specified
    generate_tests_path = getattr(config, "_synapse_generate_tests", None)
    if generate_tests_path:
        _generate_test_stubs(engine, spec, generate_tests_path)
        print(f"pytest-synapse: Test stubs written to {generate_tests_path}")

    # Post GitHub comment if specified
    github_comment = getattr(config, "_synapse_github_comment", False)
    if github_comment:
        _post_github_comment(engine, baseline_path)

    # Check strict mode (contract violations)
    strict_mode = getattr(config, "_synapse_strict", False)
    if strict_mode:
        violations = engine.get_validation_errors()
        if violations:
            print("\npytest-synapse: CONTRACT VIOLATIONS DETECTED!")
            _print_contract_violations(violations)
            session.exitstatus = 1

    # Check coverage thresholds
    _check_coverage_thresholds(engine, config, session)


def _write_junit_report(engine: SynapseCoverageEngine, output_path: str) -> None:
    """Write JUnit XML report for CI integration."""
    summary = engine.calculate_summary()
    uncovered = engine.get_uncovered_items()
    coverage_map = engine.get_coverage_map()

    # Count total operations
    total_ops = sum(
        len(path_cov.operations)
        for path_cov in coverage_map.values()
    )
    uncovered_ops = len([u for u in uncovered if u.item_type == "path_method"])

    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<testsuite name="API Coverage" tests="{total_ops}" failures="{uncovered_ops}" errors="0">',
    ]

    # Add test cases for each operation
    for path, path_coverage in sorted(coverage_map.items()):
        for method, op_coverage in sorted(path_coverage.operations.items()):
            test_name = f"{method.upper()} {path}"
            class_name = "api.coverage"

            if op_coverage.status.value == "COVERED":
                xml_lines.append(f'  <testcase name="{test_name}" classname="{class_name}" />')
            else:
                xml_lines.append(f'  <testcase name="{test_name}" classname="{class_name}">')
                xml_lines.append(f'    <failure message="Operation not covered">')
                xml_lines.append(f'      No test exercised {method.upper()} {path}')
                xml_lines.append(f'    </failure>')
                xml_lines.append(f'  </testcase>')

    xml_lines.append('</testsuite>')

    Path(output_path).write_text("\n".join(xml_lines), encoding="utf-8")


def _save_baseline(engine: SynapseCoverageEngine, output_path: str) -> None:
    """Save current coverage as baseline."""
    summary = engine.calculate_summary()
    coverage_map = engine.get_coverage_map()

    baseline = {
        "summary": summary.to_dict(),
        "covered_operations": [],
        "uncovered_operations": [],
    }

    for path, path_coverage in coverage_map.items():
        for method, op_coverage in path_coverage.operations.items():
            op_key = f"{method.upper()} {path}"
            if op_coverage.status.value == "COVERED":
                baseline["covered_operations"].append(op_key)
            else:
                baseline["uncovered_operations"].append(op_key)

    Path(output_path).write_text(json.dumps(baseline, indent=2), encoding="utf-8")


def _compare_baseline(
    engine: SynapseCoverageEngine,
    baseline_path: str,
    config: pytest.Config,
    session: pytest.Session
) -> None:
    """Compare current coverage against baseline."""
    try:
        with open(baseline_path, "r") as f:
            baseline = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"\npytest-synapse: Could not load baseline: {e}")
        return

    summary = engine.calculate_summary()
    coverage_map = engine.get_coverage_map()

    # Get current covered/uncovered operations
    current_covered = set()
    current_uncovered = set()
    for path, path_coverage in coverage_map.items():
        for method, op_coverage in path_coverage.operations.items():
            op_key = f"{method.upper()} {path}"
            if op_coverage.status.value == "COVERED":
                current_covered.add(op_key)
            else:
                current_uncovered.add(op_key)

    baseline_covered = set(baseline.get("covered_operations", []))
    baseline_uncovered = set(baseline.get("uncovered_operations", []))

    # Calculate regressions and improvements
    newly_uncovered = baseline_covered - current_covered
    newly_covered = current_uncovered & baseline_covered  # Was uncovered, now covered
    newly_covered = baseline_uncovered & current_covered  # Correct: was uncovered, now covered

    # Print comparison
    baseline_summary = baseline.get("summary", {})
    print("\n" + "=" * 60)
    print("Coverage Diff (vs baseline)")
    print("=" * 60)

    old_op_pct = baseline_summary.get("operation_coverage_percentage", 0)
    new_op_pct = summary.operation_coverage_percentage
    diff = new_op_pct - old_op_pct
    diff_str = f"+{diff:.1f}%" if diff >= 0 else f"{diff:.1f}%"
    arrow = "⬆️" if diff > 0 else ("⬇️" if diff < 0 else "➡️")
    print(f"Operations: {old_op_pct:.1f}% → {new_op_pct:.1f}% ({arrow} {diff_str})")

    if newly_uncovered:
        print("\n❌ REGRESSION - Newly Uncovered:")
        for op in sorted(newly_uncovered):
            print(f"   - {op}")

    if newly_covered:
        print("\n✅ Newly Covered:")
        for op in sorted(newly_covered):
            print(f"   + {op}")

    # Fail on regression if configured
    fail_on_regression = getattr(config, "_synapse_fail_on_regression", False)
    if fail_on_regression and newly_uncovered:
        print("\npytest-synapse: Failing due to coverage regression!")
        session.exitstatus = COVERAGE_THRESHOLD_EXIT_CODE


def _write_test_map(
    engine: SynapseCoverageEngine,
    events: list,
    output_path: str
) -> None:
    """Write test-to-endpoint mapping."""
    from collections import defaultdict

    endpoint_to_tests: Dict[str, List[str]] = defaultdict(list)
    test_to_endpoints: Dict[str, List[str]] = defaultdict(list)

    for event in events:
        match = engine.match_request(event.request)
        if match:
            path, method = match
            endpoint = f"{method.upper()} {path}"
            test_id = event.test_id

            if test_id not in endpoint_to_tests[endpoint]:
                endpoint_to_tests[endpoint].append(test_id)
            if endpoint not in test_to_endpoints[test_id]:
                test_to_endpoints[test_id].append(endpoint)

    # Find single-test coverage (risk)
    single_test_coverage = [
        endpoint for endpoint, tests in endpoint_to_tests.items()
        if len(tests) == 1
    ]

    # Find redundant coverage
    redundant_coverage = {
        endpoint: len(tests)
        for endpoint, tests in endpoint_to_tests.items()
        if len(tests) > 3
    }

    test_map = {
        "endpoint_to_tests": dict(endpoint_to_tests),
        "test_to_endpoints": dict(test_to_endpoints),
        "single_test_coverage": single_test_coverage,
        "redundant_coverage": redundant_coverage,
    }

    Path(output_path).write_text(json.dumps(test_map, indent=2), encoding="utf-8")


def _generate_test_stubs(
    engine: SynapseCoverageEngine,
    spec: OpenAPISpecParser,
    output_path: str
) -> None:
    """Generate test stubs for uncovered endpoints."""
    uncovered = engine.get_uncovered_items()
    uncovered_ops = [u for u in uncovered if u.item_type == "path_method"]

    if not uncovered_ops:
        Path(output_path).write_text("# All endpoints are covered!\n", encoding="utf-8")
        return

    lines = [
        '"""Auto-generated test stubs by pytest-synapse."""',
        "",
        "import pytest",
        "import requests",
        "",
        "# TODO: Update this to your API base URL",
        'BASE_URL = "http://localhost:8000"',
        "",
        "",
    ]

    for item in uncovered_ops:
        method = item.method.upper()
        path = item.path

        # Convert path params to Python format
        test_path = path.replace("{", "{").replace("}", "}")
        class_name = f"Test{method.title()}{''.join(p.title() for p in path.split('/') if p and not p.startswith('{'))}"

        lines.extend([
            f'class {class_name}:',
            f'    """Tests for {method} {path}"""',
            "",
        ])

        # Get response codes from spec
        try:
            responses = spec.get_response_status_codes(path, method.lower())
        except Exception:
            responses = ["200"]

        for status_code in responses:
            test_name = f"test_{method.lower()}_{status_code}"
            lines.extend([
                f"    def {test_name}(self):",
                f'        """Test {method} {path} returns {status_code}."""',
            ])

            # Add path parameter handling
            import re
            params = re.findall(r"\{(\w+)\}", path)
            if params:
                for param in params:
                    lines.append(f'        {param} = 1  # TODO: Set appropriate value')

            # Generate request
            url_path = path
            for param in params:
                url_path = url_path.replace(f"{{{param}}}", f"{{{param}}}")

            lines.append(f'        response = requests.{method.lower()}(f"{{BASE_URL}}{url_path}")')
            lines.append(f"        assert response.status_code == {status_code}")
            lines.append("")

        lines.append("")

    Path(output_path).write_text("\n".join(lines), encoding="utf-8")


def _post_github_comment(
    engine: SynapseCoverageEngine,
    baseline_path: Optional[str]
) -> None:
    """Post coverage report as GitHub PR comment."""
    # Check for GitHub environment
    github_token = os.environ.get("GITHUB_TOKEN")
    github_event_path = os.environ.get("GITHUB_EVENT_PATH")

    if not github_token or not github_event_path:
        print("pytest-synapse: GitHub environment not detected, skipping PR comment")
        return

    try:
        import requests as http_requests

        # Load GitHub event
        with open(github_event_path, "r") as f:
            event = json.load(f)

        pr_number = event.get("pull_request", {}).get("number")
        repo = os.environ.get("GITHUB_REPOSITORY")

        if not pr_number or not repo:
            print("pytest-synapse: Not a PR context, skipping comment")
            return

        # Generate comment body
        summary = engine.calculate_summary()

        comment_lines = [
            "## 📊 API Coverage Report",
            "",
            "| Metric | Coverage |",
            "|--------|----------|",
            f"| Operations | {summary.covered_operations}/{summary.total_operations} ({summary.operation_coverage_percentage}%) |",
            f"| Paths | {summary.covered_paths}/{summary.total_paths} ({summary.path_coverage_percentage}%) |",
            f"| Schemas | {summary.covered_response_schemas}/{summary.total_response_schemas} ({summary.response_schema_coverage_percentage}%) |",
            "",
        ]

        # Add uncovered items
        uncovered = engine.get_uncovered_items()
        uncovered_ops = [u for u in uncovered if u.item_type == "path_method"]
        if uncovered_ops:
            comment_lines.append("### ❌ Uncovered Operations")
            for item in uncovered_ops[:10]:
                comment_lines.append(f"- `{item.method.upper()} {item.path}`")
            if len(uncovered_ops) > 10:
                comment_lines.append(f"- ... and {len(uncovered_ops) - 10} more")
            comment_lines.append("")

        comment_lines.append("---")
        comment_lines.append("*Generated by pytest-synapse*")

        comment_body = "\n".join(comment_lines)

        # Post comment
        api_url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        response = http_requests.post(
            api_url,
            headers=headers,
            json={"body": comment_body},
        )

        if response.status_code == 201:
            print("pytest-synapse: Posted coverage comment to PR")
        else:
            print(f"pytest-synapse: Failed to post PR comment: {response.status_code}")

    except Exception as e:
        print(f"pytest-synapse: Error posting GitHub comment: {e}")


def _generate_coverage_comment_body(
    engine: SynapseCoverageEngine,
    baseline_path: Optional[str] = None
) -> str:
    """Generate a markdown comment body for coverage report."""
    summary = engine.calculate_summary()

    lines = [
        "## 📊 API Coverage Report",
        "",
        "| Metric | Coverage |",
        "|--------|----------|",
        f"| Operations | {summary.covered_operations}/{summary.total_operations} ({summary.operation_coverage_percentage}%) |",
        f"| Paths | {summary.covered_paths}/{summary.total_paths} ({summary.path_coverage_percentage}%) |",
        f"| Schemas | {summary.covered_response_schemas}/{summary.total_response_schemas} ({summary.response_schema_coverage_percentage}%) |",
        "",
    ]

    # Add baseline comparison if available
    if baseline_path:
        try:
            with open(baseline_path, "r") as f:
                baseline = json.load(f)
            baseline_summary = baseline.get("summary", {})
            old_pct = baseline_summary.get("operation_coverage_percentage", 0)
            new_pct = summary.operation_coverage_percentage
            diff = new_pct - old_pct
            if diff > 0:
                lines.append(f"📈 **Coverage improved**: +{diff:.1f}% from baseline")
            elif diff < 0:
                lines.append(f"📉 **Coverage decreased**: {diff:.1f}% from baseline")
            else:
                lines.append("➡️ **Coverage unchanged** from baseline")
            lines.append("")
        except Exception:
            pass

    # Add uncovered items
    uncovered = engine.get_uncovered_items()
    uncovered_ops = [u for u in uncovered if u.item_type == "path_method"]
    if uncovered_ops:
        lines.append("### ❌ Uncovered Operations")
        for item in uncovered_ops[:10]:
            lines.append(f"- `{item.method.upper()} {item.path}`")
        if len(uncovered_ops) > 10:
            lines.append(f"- ... and {len(uncovered_ops) - 10} more")
        lines.append("")

    lines.append("---")
    lines.append("*Generated by pytest-synapse*")

    return "\n".join(lines)


def _print_contract_violations(violations: Dict[str, Any]) -> None:
    """Print contract violations in a readable format."""
    for operation, errors in violations.items():
        print(f"\n❌ {operation}")
        for error_type, error_list in errors.items():
            print(f"   {error_type}:")
            for error in error_list:
                for err_msg in error.get("errors", []):
                    print(f"     - {err_msg}")


def _check_coverage_thresholds(
    engine: SynapseCoverageEngine,
    config: pytest.Config,
    session: pytest.Session
) -> None:
    """Check if coverage meets configured thresholds."""
    summary = engine.calculate_summary()
    failed_thresholds = []

    # Check overall threshold (alias for operations)
    fail_under = getattr(config, "_synapse_fail_under", None)
    if fail_under is not None:
        if summary.operation_coverage_percentage < fail_under:
            failed_thresholds.append(
                f"Operations: {summary.operation_coverage_percentage:.1f}% < {fail_under}%"
            )

    # Check operations threshold
    fail_under_ops = getattr(config, "_synapse_fail_under_operations", None)
    if fail_under_ops is not None:
        if summary.operation_coverage_percentage < fail_under_ops:
            failed_thresholds.append(
                f"Operations: {summary.operation_coverage_percentage:.1f}% < {fail_under_ops}%"
            )

    # Check paths threshold
    fail_under_paths = getattr(config, "_synapse_fail_under_paths", None)
    if fail_under_paths is not None:
        if summary.path_coverage_percentage < fail_under_paths:
            failed_thresholds.append(
                f"Paths: {summary.path_coverage_percentage:.1f}% < {fail_under_paths}%"
            )

    # Check schemas threshold
    fail_under_schemas = getattr(config, "_synapse_fail_under_schemas", None)
    if fail_under_schemas is not None:
        if summary.response_schema_coverage_percentage < fail_under_schemas:
            failed_thresholds.append(
                f"Schemas: {summary.response_schema_coverage_percentage:.1f}% < {fail_under_schemas}%"
            )

    if failed_thresholds:
        print("\n" + "=" * 60)
        print("COVERAGE THRESHOLD FAILED")
        print("=" * 60)
        for failure in failed_thresholds:
            print(f"  ❌ {failure}")
        session.exitstatus = COVERAGE_THRESHOLD_EXIT_CODE


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
