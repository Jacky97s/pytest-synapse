"""Tests for the report module."""

import json
import pytest
from pathlib import Path

from pytest_synapse.coverage_engine import SynapseCoverageEngine
from pytest_synapse.report import CoverageReport, ReportRenderer
from pytest_synapse.spec_parser import OpenAPISpecParser
from pytest_synapse.types import CapturedTrafficEvent, HttpRequest, HttpResponse


@pytest.fixture
def spec_path():
    """Path to the test OpenAPI spec."""
    return str(Path(__file__).parent / "fixtures" / "openapi.yaml")


@pytest.fixture
def engine(spec_path):
    """Create a coverage engine with some events processed."""
    parser = OpenAPISpecParser(spec_path)
    engine = SynapseCoverageEngine(parser)

    events = [
        CapturedTrafficEvent(
            test_id="test::get_users",
            request=HttpRequest(method="GET", path="/users"),
            response=HttpResponse(status_code=200, body=[]),
        ),
        CapturedTrafficEvent(
            test_id="test::get_user",
            request=HttpRequest(method="GET", path="/users/1"),
            response=HttpResponse(
                status_code=200,
                body={"id": 1, "name": "Alice", "email": "alice@example.com"},
            ),
        ),
        CapturedTrafficEvent(
            test_id="test::create_user",
            request=HttpRequest(
                method="POST",
                path="/users",
                body={"name": "Bob", "email": "bob@example.com"},
            ),
            response=HttpResponse(
                status_code=201,
                body={"id": 2, "name": "Bob", "email": "bob@example.com"},
            ),
        ),
    ]
    engine.process_events(events)
    return engine


@pytest.fixture
def renderer(engine):
    """Create a report renderer."""
    return ReportRenderer(engine)


class TestReportRenderer:
    def test_generate_report(self, renderer):
        report = renderer.generate_report()
        assert isinstance(report, CoverageReport)
        assert report.summary.covered_operations == 3
        assert len(report.details) > 0

    def test_render_cli_summary(self, renderer):
        output = renderer.render_cli_summary()
        assert "OpenAPI Coverage Report" in output
        assert "Paths:" in output
        assert "Operations:" in output
        assert "3/6" in output  # 3 covered out of 6 total

    def test_render_cli_detailed(self, renderer):
        output = renderer.render_cli_detailed()
        assert "OpenAPI Coverage Report" in output
        assert "Detailed Coverage:" in output
        assert "/users" in output
        assert "[+]" in output  # Covered indicator
        assert "[-]" in output  # Uncovered indicator

    def test_render_json(self, renderer):
        output = renderer.render_json()
        data = json.loads(output)

        assert "summary" in data
        assert "details" in data
        assert "uncovered_items_list" in data

        summary = data["summary"]
        assert summary["total_operations"] == 6
        assert summary["covered_operations"] == 3

    def test_write_json_report(self, renderer, tmp_path):
        output_path = str(tmp_path / "coverage.json")
        renderer.write_json_report(output_path)

        assert Path(output_path).exists()
        data = json.loads(Path(output_path).read_text())
        assert "summary" in data

    def test_write_report_returns_content_when_no_path(self, renderer):
        content = renderer.write_report(None, "cli_summary")
        assert content is not None
        assert "OpenAPI Coverage Report" in content

    def test_write_report_writes_file_when_path_given(self, renderer, tmp_path):
        output_path = str(tmp_path / "report.txt")
        result = renderer.write_report(output_path, "cli_summary")
        assert result is None
        assert Path(output_path).exists()


class TestCoverageReport:
    def test_to_dict(self, renderer):
        report = renderer.generate_report()
        data = report.to_dict()

        assert "summary" in data
        assert "details" in data
        assert "uncovered_items_list" in data
        assert isinstance(data["summary"], dict)
        assert isinstance(data["details"], dict)
        assert isinstance(data["uncovered_items_list"], list)
