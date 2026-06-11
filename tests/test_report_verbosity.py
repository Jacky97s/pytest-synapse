"""Tests for report verbosity levels and coverage suggestions."""

import pytest
from pathlib import Path

from pytest_synapse.coverage_engine import SynapseCoverageEngine
from pytest_synapse.flow_logger import SynapseFlowLogger
from pytest_synapse.report import ReportRenderer, CoverageSuggestion
from pytest_synapse.spec_parser import OpenAPISpecParser


@pytest.fixture(autouse=True)
def reset_logger():
    """Reset the singleton logger before and after each test."""
    SynapseFlowLogger.destroy()
    yield
    SynapseFlowLogger.destroy()


@pytest.fixture
def spec_path():
    return str(Path(__file__).parent / "fixtures" / "openapi.yaml")


@pytest.fixture
def engine_no_coverage(spec_path):
    """Create an engine with no coverage."""
    spec = OpenAPISpecParser(spec_path)
    engine = SynapseCoverageEngine(spec)
    return engine


@pytest.fixture
def engine_partial_coverage(spec_path):
    """Create an engine with partial coverage."""
    import requests
    import responses
    from pytest_synapse.interceptor import SynapseInterceptor

    spec = OpenAPISpecParser(spec_path)
    logger = SynapseFlowLogger()
    interceptor = SynapseInterceptor()
    interceptor.activate(logger)

    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.GET,
            "http://localhost:8000/users",
            json=[{"id": 1, "name": "Alice", "email": "alice@example.com"}],
            status=200,
        )
        rsps.add(
            responses.GET,
            "http://localhost:8000/health",
            json={"status": "ok"},
            status=200,
        )

        logger.set_current_test("test::list_users")
        requests.get("http://localhost:8000/users")
        logger.set_current_test("test::health")
        requests.get("http://localhost:8000/health")

    interceptor.deactivate()
    events = logger.get_events()

    engine = SynapseCoverageEngine(spec)
    engine.process_events(events)
    return engine


class TestReportVerbosityLevels:
    """Tests for different verbosity levels in report output."""

    def test_summary_output_default(self, engine_no_coverage):
        """Test default summary output (verbosity=0)."""
        renderer = ReportRenderer(engine_no_coverage, verbosity=0)
        output = renderer.render_cli_summary()

        assert "OpenAPI Coverage Report" in output
        assert "Paths:" in output
        assert "Operations:" in output
        assert "Coverage Suggestions" not in output  # No suggestions at v=0

    def test_summary_with_suggestions(self, engine_no_coverage):
        """Test summary with suggestions enabled."""
        renderer = ReportRenderer(engine_no_coverage, verbosity=0, show_suggestions=True)
        output = renderer.render_cli_summary()

        assert "Coverage Suggestions:" in output
        assert "[!]" in output or "[*]" in output  # Priority icons

    def test_verbose_output_shows_api_status(self, engine_partial_coverage):
        """Test verbose output (verbosity=1) shows covered/uncovered APIs."""
        renderer = ReportRenderer(engine_partial_coverage, verbosity=1)
        output = renderer.render_cli_verbose()

        assert "API Coverage Status:" in output
        assert "Covered APIs:" in output
        assert "Uncovered APIs:" in output
        assert "[+]" in output  # Covered indicator
        assert "[-]" in output  # Uncovered indicator

    def test_detailed_output_shows_operations(self, engine_partial_coverage):
        """Test detailed output (verbosity=2) shows operation details."""
        renderer = ReportRenderer(engine_partial_coverage, verbosity=2)
        output = renderer.render_cli_detailed()

        assert "Detailed Coverage:" in output
        assert "Request Body" in output
        assert "Responses:" in output

    def test_verbosity_3_shows_suggestions(self, engine_no_coverage):
        """Test that verbosity >= 3 shows suggestions automatically."""
        renderer = ReportRenderer(engine_no_coverage, verbosity=3)
        output = renderer.render_cli_summary()

        assert "Coverage Suggestions:" in output


class TestCoverageSuggestions:
    """Tests for coverage suggestion generation."""

    def test_suggestions_for_uncovered_operations(self, engine_no_coverage):
        """Test suggestions are generated for uncovered operations."""
        renderer = ReportRenderer(engine_no_coverage)
        suggestions = renderer.generate_suggestions()

        # Should have HIGH priority suggestions for uncovered operations
        high_priority = [s for s in suggestions if s.priority == "HIGH"]
        assert len(high_priority) > 0

        # Check suggestion content
        op_suggestions = [s for s in suggestions if s.category == "operation"]
        assert len(op_suggestions) > 0
        assert any("is not covered" in s.message for s in op_suggestions)
        assert any("Write a test" in s.action for s in op_suggestions)

    def test_suggestions_for_uncovered_status_codes(self, engine_partial_coverage):
        """Test suggestions for uncovered response status codes."""
        renderer = ReportRenderer(engine_partial_coverage)
        suggestions = renderer.generate_suggestions()

        # Should have some suggestions (operations, status codes, or request bodies)
        # When partial coverage exists, we expect at least some uncovered items
        assert len(suggestions) > 0

        # Check that suggestions have valid structure
        for s in suggestions:
            assert s.priority in ["HIGH", "MEDIUM", "LOW"]
            assert s.category in ["operation", "status_code", "request_body", "response_schema"]
            assert len(s.message) > 0
            assert len(s.action) > 0

    def test_suggestions_sorted_by_priority(self, engine_no_coverage):
        """Test that suggestions are sorted by priority."""
        renderer = ReportRenderer(engine_no_coverage)
        suggestions = renderer.generate_suggestions()

        if len(suggestions) > 1:
            priorities = [s.priority for s in suggestions]
            priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
            priority_values = [priority_order.get(p, 3) for p in priorities]
            assert priority_values == sorted(priority_values)

    def test_suggestion_to_dict(self):
        """Test CoverageSuggestion.to_dict()."""
        suggestion = CoverageSuggestion(
            priority="HIGH",
            category="operation",
            path="/users",
            method="POST",
            message="POST /users is not covered",
            action="Write a test that makes a POST request to /users"
        )
        d = suggestion.to_dict()

        assert d["priority"] == "HIGH"
        assert d["category"] == "operation"
        assert d["path"] == "/users"
        assert d["method"] == "POST"
        assert d["message"] == "POST /users is not covered"


class TestReportWithValidation:
    """Tests for report generation with validation enabled."""

    def test_report_includes_validation_stats(self, spec_path):
        """Test that report includes validation statistics."""
        import requests
        import responses
        from pytest_synapse.interceptor import SynapseInterceptor

        spec = OpenAPISpecParser(spec_path)
        logger = SynapseFlowLogger()
        interceptor = SynapseInterceptor()
        interceptor.activate(logger)

        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.POST,
                "http://localhost:8000/users",
                json={"id": 1, "name": "Alice", "email": "alice@example.com"},
                status=201,
            )

            logger.set_current_test("test::create_user")
            requests.post(
                "http://localhost:8000/users",
                json={"name": "Alice", "email": "alice@example.com"},
            )

        interceptor.deactivate()
        events = logger.get_events()

        engine = SynapseCoverageEngine(spec, validate_schemas=True)
        engine.process_events(events)

        renderer = ReportRenderer(engine, verbosity=2)
        output = renderer.render_cli_detailed()

        # Should show validation info
        assert "Valid:" in output or "Schema Validation" in output


class TestReportGeneration:
    """Tests for report generation."""

    def test_generate_report_includes_suggestions(self, engine_no_coverage):
        """Test that generate_report includes suggestions when enabled."""
        renderer = ReportRenderer(engine_no_coverage, show_suggestions=True)
        report = renderer.generate_report()

        assert len(report.suggestions) > 0

    def test_report_to_dict_includes_suggestions(self, engine_no_coverage):
        """Test that report.to_dict() includes suggestions."""
        renderer = ReportRenderer(engine_no_coverage, show_suggestions=True)
        report = renderer.generate_report()
        report_dict = report.to_dict()

        assert "suggestions" in report_dict
        assert len(report_dict["suggestions"]) > 0

    def test_json_report_includes_suggestions(self, engine_no_coverage, tmp_path):
        """Test that JSON report includes suggestions."""
        import json

        renderer = ReportRenderer(engine_no_coverage, show_suggestions=True)
        report_path = tmp_path / "report.json"
        renderer.write_json_report(str(report_path))

        report_data = json.loads(report_path.read_text())
        assert "suggestions" in report_data
