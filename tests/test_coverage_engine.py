"""Tests for the coverage engine module."""

import json

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


class TestServerBasePathMatching:
    """Requests sent to a server with a base path must match spec path keys.

    When the OpenAPI servers[].url contains a path (e.g.
    https://api.example.com/api/v2), intercepted request paths carry that
    prefix while the spec's paths keys do not.
    """

    def _make_engine(self, tmp_path, servers):
        spec = {
            "openapi": "3.0.3",
            "info": {"title": "Base Path API", "version": "1.0.0"},
            "paths": {
                "/users": {
                    "get": {"responses": {"200": {"description": "OK"}}}
                },
                "/users/{userId}": {
                    "get": {
                        "parameters": [
                            {
                                "name": "userId",
                                "in": "path",
                                "required": True,
                                "schema": {"type": "integer"},
                            }
                        ],
                        "responses": {"200": {"description": "OK"}},
                    }
                },
            },
        }
        if servers is not None:
            spec["servers"] = servers

        spec_file = tmp_path / "spec.json"
        spec_file.write_text(json.dumps(spec))
        return SynapseCoverageEngine(OpenAPISpecParser(str(spec_file)))

    def test_match_request_strips_server_base_path(self, tmp_path):
        engine = self._make_engine(
            tmp_path, [{"url": "https://api.example.com/api/v2"}]
        )
        request = HttpRequest(method="GET", path="/api/v2/users/123")
        assert engine.match_request(request) == ("/users/{userId}", "GET")

    def test_match_request_strips_base_path_for_exact_path(self, tmp_path):
        engine = self._make_engine(
            tmp_path, [{"url": "https://api.example.com/api/v2"}]
        )
        request = HttpRequest(method="GET", path="/api/v2/users")
        assert engine.match_request(request) == ("/users", "GET")

    def test_match_request_without_base_path_still_matches(self, tmp_path):
        engine = self._make_engine(
            tmp_path, [{"url": "https://api.example.com/api/v2"}]
        )
        request = HttpRequest(method="GET", path="/users/123")
        assert engine.match_request(request) == ("/users/{userId}", "GET")

    def test_base_path_only_stripped_on_segment_boundary(self, tmp_path):
        engine = self._make_engine(
            tmp_path, [{"url": "https://api.example.com/api/v2"}]
        )
        request = HttpRequest(method="GET", path="/api/v2x/users")
        assert engine.match_request(request) is None

    def test_multiple_servers_with_different_base_paths(self, tmp_path):
        engine = self._make_engine(
            tmp_path,
            [
                {"url": "https://api.example.com/api/v2"},
                {"url": "https://staging.example.com/staging/api"},
            ],
        )
        assert engine.match_request(
            HttpRequest(method="GET", path="/api/v2/users")
        ) == ("/users", "GET")
        assert engine.match_request(
            HttpRequest(method="GET", path="/staging/api/users/7")
        ) == ("/users/{userId}", "GET")

    def test_relative_server_url_base_path(self, tmp_path):
        engine = self._make_engine(tmp_path, [{"url": "/api/v2"}])
        request = HttpRequest(method="GET", path="/api/v2/users/123")
        assert engine.match_request(request) == ("/users/{userId}", "GET")

    def test_templated_server_path_does_not_break_matching(self, tmp_path):
        engine = self._make_engine(
            tmp_path, [{"url": "https://api.example.com/{version}"}]
        )
        request = HttpRequest(method="GET", path="/users/123")
        assert engine.match_request(request) == ("/users/{userId}", "GET")

    def test_process_events_covers_operations_behind_base_path(self, tmp_path):
        engine = self._make_engine(
            tmp_path, [{"url": "https://api.example.com/api/v2"}]
        )
        event = CapturedTrafficEvent(
            test_id="test::example",
            request=HttpRequest(method="GET", path="/api/v2/users/123"),
            response=HttpResponse(status_code=200, body={"id": 123}),
        )
        engine.process_events([event])

        op_coverage = engine.get_coverage_map()["/users/{userId}"].operations["GET"]
        assert op_coverage.status == CoverageStatus.COVERED
        assert op_coverage.responses["200"].status == CoverageStatus.COVERED
