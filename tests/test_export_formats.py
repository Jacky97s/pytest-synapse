"""Tests for report export formats (JSON, CSV, HTML)."""

import csv
import io
import json
import pytest
from pathlib import Path

from pytest_synapse.coverage_engine import SynapseCoverageEngine
from pytest_synapse.flow_logger import SynapseFlowLogger
from pytest_synapse.report import ReportRenderer
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
def constraints_spec_path():
    return str(Path(__file__).parent / "fixtures" / "openapi_constraints.json")


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
            responses.POST,
            "http://localhost:8000/users",
            json={"id": 2, "name": "Bob", "email": "bob@example.com"},
            status=201,
        )
        rsps.add(
            responses.GET,
            "http://localhost:8000/health",
            json={"status": "ok"},
            status=200,
        )

        logger.set_current_test("test::list_users")
        requests.get("http://localhost:8000/users")
        logger.set_current_test("test::create_user")
        requests.post(
            "http://localhost:8000/users",
            json={"name": "Bob", "email": "bob@example.com"},
        )
        logger.set_current_test("test::health")
        requests.get("http://localhost:8000/health")

    interceptor.deactivate()
    events = logger.get_events()

    engine = SynapseCoverageEngine(spec)
    engine.process_events(events)
    return engine


class TestJSONExport:
    """Tests for JSON export format."""

    def test_json_export_structure(self, engine_no_coverage):
        """Test JSON export has correct structure."""
        renderer = ReportRenderer(engine_no_coverage)
        json_output = renderer.render_json()
        data = json.loads(json_output)

        assert "summary" in data
        assert "details" in data
        assert "uncovered_items_list" in data
        assert "validation_errors" in data
        assert "suggestions" in data

    def test_json_export_summary_fields(self, engine_partial_coverage):
        """Test JSON export summary contains all fields."""
        renderer = ReportRenderer(engine_partial_coverage)
        json_output = renderer.render_json()
        data = json.loads(json_output)

        summary = data["summary"]
        assert "total_paths" in summary
        assert "covered_paths" in summary
        assert "total_operations" in summary
        assert "covered_operations" in summary
        assert "path_coverage_percentage" in summary
        assert "operation_coverage_percentage" in summary

    def test_json_export_pretty(self, engine_no_coverage):
        """Test pretty-printed JSON output."""
        renderer = ReportRenderer(engine_no_coverage)
        json_pretty = renderer.render_json(pretty=True)
        json_compact = renderer.render_json(pretty=False)

        # Pretty should have more characters due to indentation
        assert len(json_pretty) > len(json_compact)
        assert "\n" in json_pretty
        assert "  " in json_pretty  # Indentation

    def test_json_export_with_suggestions(self, engine_no_coverage):
        """Test JSON export includes suggestions when enabled."""
        renderer = ReportRenderer(engine_no_coverage, show_suggestions=True)
        json_output = renderer.render_json()
        data = json.loads(json_output)

        assert len(data["suggestions"]) > 0
        suggestion = data["suggestions"][0]
        assert "priority" in suggestion
        assert "category" in suggestion
        assert "path" in suggestion
        assert "message" in suggestion
        assert "action" in suggestion

    def test_write_json_report(self, engine_partial_coverage, tmp_path):
        """Test writing JSON report to file."""
        renderer = ReportRenderer(engine_partial_coverage)
        report_path = tmp_path / "report.json"
        renderer.write_json_report(str(report_path))

        assert report_path.exists()
        data = json.loads(report_path.read_text())
        assert "summary" in data


class TestCSVExport:
    """Tests for CSV export format."""

    def test_csv_export_header(self, engine_no_coverage):
        """Test CSV export has correct header."""
        renderer = ReportRenderer(engine_no_coverage)
        csv_output = renderer.render_csv()

        reader = csv.reader(io.StringIO(csv_output))
        header = next(reader)

        expected_headers = [
            "Path",
            "Method",
            "Operation Status",
            "Request Body Status",
            "Request Valid",
            "Request Invalid",
            "Status Code",
            "Response Status",
            "Schema Status",
            "Response Valid",
            "Response Invalid",
        ]
        assert header == expected_headers

    def test_csv_export_rows(self, engine_partial_coverage):
        """Test CSV export contains data rows."""
        renderer = ReportRenderer(engine_partial_coverage)
        csv_output = renderer.render_csv()

        reader = csv.reader(io.StringIO(csv_output))
        rows = list(reader)

        # Should have header + data rows
        assert len(rows) > 1

        # Check a data row
        data_row = rows[1]
        assert len(data_row) == 11  # 11 columns
        assert data_row[0].startswith("/")  # Path
        assert data_row[1].isupper()  # Method should be uppercase

    def test_csv_export_all_operations(self, engine_no_coverage):
        """Test CSV includes all operations."""
        renderer = ReportRenderer(engine_no_coverage)
        csv_output = renderer.render_csv()

        reader = csv.reader(io.StringIO(csv_output))
        rows = list(reader)

        # Extract unique path/method combinations
        operations = set()
        for row in rows[1:]:  # Skip header
            path, method = row[0], row[1]
            operations.add((path, method))

        # Should have multiple operations
        assert len(operations) > 0

    def test_csv_export_coverage_status(self, engine_partial_coverage):
        """Test CSV shows correct coverage status."""
        renderer = ReportRenderer(engine_partial_coverage)
        csv_output = renderer.render_csv()

        reader = csv.reader(io.StringIO(csv_output))
        rows = list(reader)

        # Find GET /users row
        users_row = None
        for row in rows[1:]:
            if row[0] == "/users" and row[1] == "GET":
                users_row = row
                break

        assert users_row is not None
        assert users_row[2] == "COVERED"  # Operation status

    def test_write_csv_report(self, engine_partial_coverage, tmp_path):
        """Test writing CSV report to file."""
        renderer = ReportRenderer(engine_partial_coverage)
        report_path = tmp_path / "report.csv"
        renderer.write_report(str(report_path), report_format="csv")

        assert report_path.exists()
        content = report_path.read_text()
        assert "Path,Method" in content


class TestHTMLExport:
    """Tests for HTML export format."""

    def test_html_export_structure(self, engine_no_coverage):
        """Test HTML export has correct structure."""
        renderer = ReportRenderer(engine_no_coverage)
        html_output = renderer.render_html()

        assert "<!DOCTYPE html>" in html_output
        assert "<html" in html_output
        assert "</html>" in html_output
        assert "<head>" in html_output
        assert "<body>" in html_output

    def test_html_export_title(self, engine_no_coverage):
        """Test HTML export has correct title."""
        renderer = ReportRenderer(engine_no_coverage)
        html_output = renderer.render_html()

        assert "<title>OpenAPI Coverage Report</title>" in html_output
        assert "OpenAPI Coverage Report" in html_output

    def test_html_export_summary_cards(self, engine_partial_coverage):
        """Test HTML export includes summary cards."""
        renderer = ReportRenderer(engine_partial_coverage)
        html_output = renderer.render_html()

        assert "summary-card" in html_output
        assert "Paths" in html_output
        assert "Operations" in html_output
        assert "Request Bodies" in html_output
        assert "Response Schemas" in html_output

    def test_html_export_coverage_table(self, engine_partial_coverage):
        """Test HTML export includes coverage table."""
        renderer = ReportRenderer(engine_partial_coverage)
        html_output = renderer.render_html()

        assert "<table>" in html_output
        assert "<thead>" in html_output
        assert "<tbody>" in html_output
        assert "Path" in html_output
        assert "Method" in html_output
        assert "Status" in html_output

    def test_html_export_status_badges(self, engine_partial_coverage):
        """Test HTML export uses status badges."""
        renderer = ReportRenderer(engine_partial_coverage)
        html_output = renderer.render_html()

        assert "status-badge" in html_output
        # Should have some covered and some uncovered
        assert "status-covered" in html_output or "status-uncovered" in html_output

    def test_html_export_with_suggestions(self, engine_no_coverage):
        """Test HTML export includes suggestions when enabled."""
        renderer = ReportRenderer(engine_no_coverage, show_suggestions=True)
        html_output = renderer.render_html()

        assert "Coverage Suggestions" in html_output
        assert "suggestion" in html_output  # CSS class
        assert "suggestion-priority" in html_output
        assert "suggestion-message" in html_output

    def test_html_export_css_styles(self, engine_no_coverage):
        """Test HTML export includes CSS styles."""
        renderer = ReportRenderer(engine_no_coverage)
        html_output = renderer.render_html()

        assert "<style>" in html_output
        assert "</style>" in html_output
        assert "font-family" in html_output
        assert "background" in html_output

    def test_html_export_responsive(self, engine_no_coverage):
        """Test HTML export is responsive."""
        renderer = ReportRenderer(engine_no_coverage)
        html_output = renderer.render_html()

        assert 'viewport' in html_output
        assert 'width=device-width' in html_output

    def test_write_html_report(self, engine_partial_coverage, tmp_path):
        """Test writing HTML report to file."""
        renderer = ReportRenderer(engine_partial_coverage)
        report_path = tmp_path / "report.html"
        renderer.write_report(str(report_path), report_format="html")

        assert report_path.exists()
        content = report_path.read_text()
        assert "<!DOCTYPE html>" in content


class TestWriteReport:
    """Tests for the write_report method with different formats."""

    def test_write_report_json(self, engine_partial_coverage, tmp_path):
        """Test write_report with JSON format."""
        renderer = ReportRenderer(engine_partial_coverage)
        report_path = tmp_path / "report.json"
        renderer.write_report(str(report_path), report_format="json")

        assert report_path.exists()
        data = json.loads(report_path.read_text())
        assert "summary" in data

    def test_write_report_csv(self, engine_partial_coverage, tmp_path):
        """Test write_report with CSV format."""
        renderer = ReportRenderer(engine_partial_coverage)
        report_path = tmp_path / "report.csv"
        renderer.write_report(str(report_path), report_format="csv")

        assert report_path.exists()
        content = report_path.read_text()
        assert "Path" in content

    def test_write_report_html(self, engine_partial_coverage, tmp_path):
        """Test write_report with HTML format."""
        renderer = ReportRenderer(engine_partial_coverage)
        report_path = tmp_path / "report.html"
        renderer.write_report(str(report_path), report_format="html")

        assert report_path.exists()
        content = report_path.read_text()
        assert "<!DOCTYPE html>" in content

    def test_write_report_cli_summary(self, engine_partial_coverage, tmp_path):
        """Test write_report with CLI summary format."""
        renderer = ReportRenderer(engine_partial_coverage)
        report_path = tmp_path / "report.txt"
        renderer.write_report(str(report_path), report_format="cli_summary")

        assert report_path.exists()
        content = report_path.read_text()
        assert "OpenAPI Coverage Report" in content

    def test_write_report_cli_detailed(self, engine_partial_coverage, tmp_path):
        """Test write_report with CLI detailed format."""
        renderer = ReportRenderer(engine_partial_coverage)
        report_path = tmp_path / "report.txt"
        renderer.write_report(str(report_path), report_format="cli_detailed")

        assert report_path.exists()
        content = report_path.read_text()
        assert "Detailed Coverage" in content

    def test_write_report_returns_content(self, engine_partial_coverage):
        """Test write_report returns content when no path specified."""
        renderer = ReportRenderer(engine_partial_coverage)
        content = renderer.write_report(None, report_format="json")

        assert content is not None
        data = json.loads(content)
        assert "summary" in data

    def test_write_report_default_format(self, engine_partial_coverage, tmp_path):
        """Test write_report uses json as default."""
        renderer = ReportRenderer(engine_partial_coverage)
        report_path = tmp_path / "report.json"
        renderer.write_report(str(report_path))

        content = report_path.read_text()
        data = json.loads(content)
        assert "summary" in data


class TestConstraintsSpecExport:
    """Tests for exporting reports from constraint-heavy spec."""

    def test_export_constraints_spec_json(self, constraints_spec_path):
        """Test JSON export with constraints spec."""
        spec = OpenAPISpecParser(constraints_spec_path)
        engine = SynapseCoverageEngine(spec)
        renderer = ReportRenderer(engine)

        json_output = renderer.render_json()
        data = json.loads(json_output)

        # Should have multiple paths
        assert data["summary"]["total_paths"] >= 4
        assert data["summary"]["total_operations"] >= 6

    def test_export_constraints_spec_csv(self, constraints_spec_path):
        """Test CSV export with constraints spec."""
        spec = OpenAPISpecParser(constraints_spec_path)
        engine = SynapseCoverageEngine(spec)
        renderer = ReportRenderer(engine)

        csv_output = renderer.render_csv()
        reader = csv.reader(io.StringIO(csv_output))
        rows = list(reader)

        # Should have header + multiple data rows
        assert len(rows) > 5

    def test_export_constraints_spec_html(self, constraints_spec_path):
        """Test HTML export with constraints spec."""
        spec = OpenAPISpecParser(constraints_spec_path)
        engine = SynapseCoverageEngine(spec)
        renderer = ReportRenderer(engine, show_suggestions=True)

        html_output = renderer.render_html()

        # Should contain paths from constraints spec
        assert "/products" in html_output
        assert "/orders" in html_output
        assert "Coverage Suggestions" in html_output


class TestExportWithValidation:
    """Tests for export formats with validation enabled."""

    def test_json_export_validation_stats(self, spec_path):
        """Test JSON export includes validation statistics."""
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

        renderer = ReportRenderer(engine)
        json_output = renderer.render_json()
        data = json.loads(json_output)

        # Summary should have schema_validation section with validation counts
        summary = data["summary"]
        assert "schema_validation" in summary
        assert "request_body" in summary["schema_validation"]
        assert "valid_count" in summary["schema_validation"]["request_body"]

    def test_html_export_validation_section(self, spec_path):
        """Test HTML export includes validation section when validations exist."""
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

        renderer = ReportRenderer(engine)
        html_output = renderer.render_html()

        # Should mention validation in HTML when validations occurred
        assert "Valid" in html_output or "validation" in html_output.lower()
