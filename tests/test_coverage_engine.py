"""Tests for the coverage engine module."""

import pytest
from pathlib import Path

from pytest_synapse.coverage_engine import SynapseCoverageEngine
from pytest_synapse.spec_parser import OpenAPISpecParser
from pytest_synapse.types import (
    CapturedTrafficEvent,
    CoverageStatus,
    HttpRequest,
    HttpResponse,
)


@pytest.fixture
def spec_path():
    """Path to the test OpenAPI spec."""
    return str(Path(__file__).parent / "fixtures" / "openapi.yaml")


@pytest.fixture
def parser(spec_path):
    """Create a parser for the test spec."""
    return OpenAPISpecParser(spec_path)


@pytest.fixture
def engine(parser):
    """Create a coverage engine."""
    return SynapseCoverageEngine(parser)


class TestSynapseCoverageEngine:
    def test_initialize_coverage_map(self, engine):
        coverage_map = engine.get_coverage_map()
        assert "/users" in coverage_map
        assert "/users/{userId}" in coverage_map
        assert "GET" in coverage_map["/users"].operations
        assert "POST" in coverage_map["/users"].operations

    def test_match_request_exact_path(self, engine):
        request = HttpRequest(method="GET", path="/users")
        match = engine.match_request(request)
        assert match == ("/users", "GET")

    def test_match_request_templated_path(self, engine):
        request = HttpRequest(method="GET", path="/users/123")
        match = engine.match_request(request)
        assert match == ("/users/{userId}", "GET")

    def test_match_request_no_match(self, engine):
        request = HttpRequest(method="GET", path="/nonexistent")
        match = engine.match_request(request)
        assert match is None

    def test_process_event_marks_covered(self, engine):
        event = CapturedTrafficEvent(
            test_id="test::example",
            request=HttpRequest(method="GET", path="/users"),
            response=HttpResponse(status_code=200, body=[{"id": 1, "name": "Alice"}]),
        )
        engine.process_events([event])

        coverage_map = engine.get_coverage_map()
        op_coverage = coverage_map["/users"].operations["GET"]
        assert op_coverage.status == CoverageStatus.COVERED
        assert op_coverage.responses["200"].status == CoverageStatus.COVERED

    def test_process_event_with_request_body(self, engine):
        event = CapturedTrafficEvent(
            test_id="test::example",
            request=HttpRequest(
                method="POST",
                path="/users",
                body={"name": "Alice", "email": "alice@example.com"},
            ),
            response=HttpResponse(
                status_code=201,
                body={"id": 1, "name": "Alice", "email": "alice@example.com"},
            ),
        )
        engine.process_events([event])

        coverage_map = engine.get_coverage_map()
        op_coverage = coverage_map["/users"].operations["POST"]
        assert op_coverage.status == CoverageStatus.COVERED
        assert op_coverage.request_body == CoverageStatus.COVERED
        assert op_coverage.responses["201"].status == CoverageStatus.COVERED

    def test_calculate_summary(self, engine):
        # Process some events
        events = [
            CapturedTrafficEvent(
                test_id="test::1",
                request=HttpRequest(method="GET", path="/users"),
                response=HttpResponse(status_code=200, body=[]),
            ),
            CapturedTrafficEvent(
                test_id="test::2",
                request=HttpRequest(method="GET", path="/users/1"),
                response=HttpResponse(
                    status_code=200,
                    body={"id": 1, "name": "Alice", "email": "a@b.com"},
                ),
            ),
        ]
        engine.process_events(events)

        summary = engine.calculate_summary()
        assert summary.total_paths == 3
        assert summary.covered_paths == 2  # /users and /users/{userId}
        assert summary.total_operations == 6  # 6 total operations in spec
        assert summary.covered_operations == 2  # GET /users and GET /users/{userId}

    def test_get_uncovered_items(self, engine):
        # No events processed, all should be uncovered
        uncovered = engine.get_uncovered_items()
        assert len(uncovered) > 0

        # All operations should be in the uncovered list
        uncovered_ops = [
            item for item in uncovered if item.item_type == "path_method"
        ]
        assert len(uncovered_ops) == 6  # All 6 operations

    def test_get_details_dict(self, engine):
        event = CapturedTrafficEvent(
            test_id="test::example",
            request=HttpRequest(method="GET", path="/health"),
            response=HttpResponse(status_code=200, body={"status": "ok"}),
        )
        engine.process_events([event])

        details = engine.get_details_dict()
        assert "/health" in details
        assert details["/health"]["GET"]["status"] == "COVERED"
