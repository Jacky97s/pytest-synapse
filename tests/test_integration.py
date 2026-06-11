"""End-to-end integration tests for pytest-synapse."""

import json
import pytest
from pathlib import Path

from pytest_synapse.coverage_engine import SynapseCoverageEngine
from pytest_synapse.flow_logger import SynapseFlowLogger
from pytest_synapse.interceptor import SynapseInterceptor
from pytest_synapse.report import ReportRenderer
from pytest_synapse.spec_parser import OpenAPISpecParser


@pytest.fixture(autouse=True)
def reset_logger():
    """Reset the singleton logger before and after each test."""
    SynapseFlowLogger.destroy()
    yield
    SynapseFlowLogger.destroy()


class TestEndToEndWorkflow:
    """Test the complete workflow from interception to report generation."""

    @pytest.fixture
    def spec_path(self):
        return str(Path(__file__).parent / "fixtures" / "openapi.yaml")

    def test_complete_workflow(self, spec_path, tmp_path):
        import requests
        import responses

        # 1. Initialize components
        logger = SynapseFlowLogger()
        interceptor = SynapseInterceptor()

        # 2. Activate interception
        activated = interceptor.activate(logger)
        assert len(activated) > 0

        # 3. Simulate test execution with HTTP calls
        with responses.RequestsMock() as rsps:
            # Mock API responses
            rsps.add(
                responses.GET,
                "http://localhost:8000/users",
                json=[
                    {"id": 1, "name": "Alice", "email": "alice@example.com"},
                    {"id": 2, "name": "Bob", "email": "bob@example.com"},
                ],
                status=200,
            )
            rsps.add(
                responses.POST,
                "http://localhost:8000/users",
                json={"id": 3, "name": "Charlie", "email": "charlie@example.com"},
                status=201,
            )
            rsps.add(
                responses.GET,
                "http://localhost:8000/users/1",
                json={"id": 1, "name": "Alice", "email": "alice@example.com"},
                status=200,
            )
            rsps.add(
                responses.GET,
                "http://localhost:8000/users/999",
                json={"message": "User not found"},
                status=404,
            )
            rsps.add(
                responses.GET,
                "http://localhost:8000/health",
                json={"status": "ok"},
                status=200,
            )

            # Simulate tests making HTTP calls
            logger.set_current_test("test::list_users")
            response = requests.get("http://localhost:8000/users")
            assert response.status_code == 200

            logger.set_current_test("test::create_user")
            response = requests.post(
                "http://localhost:8000/users",
                json={"name": "Charlie", "email": "charlie@example.com"},
            )
            assert response.status_code == 201

            logger.set_current_test("test::get_user")
            response = requests.get("http://localhost:8000/users/1")
            assert response.status_code == 200

            logger.set_current_test("test::get_user_not_found")
            response = requests.get("http://localhost:8000/users/999")
            assert response.status_code == 404

            logger.set_current_test("test::health_check")
            response = requests.get("http://localhost:8000/health")
            assert response.status_code == 200

        # 4. Deactivate interception
        interceptor.deactivate()

        # 5. Verify captured events
        events = logger.get_events()
        assert len(events) == 5

        # Verify events are linked to correct tests
        test_events = logger.get_events_for_test("test::list_users")
        assert len(test_events) == 1
        assert test_events[0].request.path == "/users"

        # 6. Parse OpenAPI spec
        spec = OpenAPISpecParser(spec_path)
        assert spec.title == "Sample API"

        # 7. Calculate coverage
        engine = SynapseCoverageEngine(spec)
        engine.process_events(events)

        summary = engine.calculate_summary()
        # Should have covered:
        # - GET /users (200)
        # - POST /users (201)
        # - GET /users/{userId} (200, 404)
        # - GET /health (200)
        assert summary.covered_operations == 4  # 4 unique operations covered
        assert summary.total_operations == 6

        # 8. Generate report
        renderer = ReportRenderer(engine)
        report = renderer.generate_report()

        # Verify report structure
        assert report.summary.covered_paths > 0
        assert len(report.details) > 0

        # 9. Write JSON report
        report_path = tmp_path / "coverage.json"
        renderer.write_json_report(str(report_path))

        # Verify JSON report
        report_data = json.loads(report_path.read_text())
        assert report_data["summary"]["covered_operations"] == 4
        assert "/users" in report_data["details"]
        assert report_data["details"]["/users"]["GET"]["status"] == "COVERED"
        assert report_data["details"]["/users"]["POST"]["status"] == "COVERED"

        # 10. Render CLI output
        cli_output = renderer.render_cli_summary()
        assert "OpenAPI Coverage Report" in cli_output
        assert "Operations:" in cli_output

    def test_no_traffic_scenario(self, spec_path):
        """Test behavior when no HTTP traffic is captured."""
        logger = SynapseFlowLogger()
        interceptor = SynapseInterceptor()

        interceptor.activate(logger)
        # No HTTP calls made
        interceptor.deactivate()

        events = logger.get_events()
        assert len(events) == 0

        spec = OpenAPISpecParser(spec_path)
        engine = SynapseCoverageEngine(spec)
        engine.process_events(events)

        summary = engine.calculate_summary()
        assert summary.covered_operations == 0
        assert summary.total_operations == 6

    def test_unmatched_requests_ignored(self, spec_path):
        """Test that requests not matching the spec are gracefully ignored."""
        import requests
        import responses

        logger = SynapseFlowLogger()
        interceptor = SynapseInterceptor()
        interceptor.activate(logger)

        with responses.RequestsMock() as rsps:
            # Request to path not in spec
            rsps.add(
                responses.GET,
                "http://localhost:8000/unknown",
                json={"error": "Not found"},
                status=404,
            )

            logger.set_current_test("test::unknown")
            requests.get("http://localhost:8000/unknown")

        interceptor.deactivate()

        events = logger.get_events()
        assert len(events) == 1  # Event is still captured

        spec = OpenAPISpecParser(spec_path)
        engine = SynapseCoverageEngine(spec)
        engine.process_events(events)

        # But it doesn't affect coverage since it doesn't match any spec path
        summary = engine.calculate_summary()
        assert summary.covered_operations == 0

    def test_schema_validation_integration(self, spec_path, tmp_path):
        """Test schema validation with valid and invalid request/response bodies."""
        import requests
        import responses

        logger = SynapseFlowLogger()
        interceptor = SynapseInterceptor()
        interceptor.activate(logger)

        with responses.RequestsMock() as rsps:
            # Valid request body, valid response
            rsps.add(
                responses.POST,
                "http://localhost:8000/users",
                json={"id": 1, "name": "Alice", "email": "alice@example.com"},
                status=201,
            )
            # Invalid request body (missing email), returns 400
            rsps.add(
                responses.POST,
                "http://localhost:8000/users",
                json={"message": "Missing required field: email"},
                status=400,
            )
            # Valid GET response
            rsps.add(
                responses.GET,
                "http://localhost:8000/users",
                json=[{"id": 1, "name": "Alice", "email": "alice@example.com"}],
                status=200,
            )
            # Invalid GET response (missing required field)
            rsps.add(
                responses.GET,
                "http://localhost:8000/users",
                json=[{"id": 1, "name": "Alice"}],  # Missing email
                status=200,
            )

            # Test 1: Valid request body
            logger.set_current_test("test::create_user_valid")
            requests.post(
                "http://localhost:8000/users",
                json={"name": "Alice", "email": "alice@example.com"},
            )

            # Test 2: Invalid request body (missing email)
            logger.set_current_test("test::create_user_invalid")
            requests.post(
                "http://localhost:8000/users",
                json={"name": "Bob"},  # Missing email
            )

            # Test 3: Valid response body
            logger.set_current_test("test::list_users_valid")
            requests.get("http://localhost:8000/users")

            # Test 4: Invalid response body
            logger.set_current_test("test::list_users_invalid")
            requests.get("http://localhost:8000/users")

        interceptor.deactivate()

        events = logger.get_events()
        assert len(events) == 4

        spec = OpenAPISpecParser(spec_path)
        engine = SynapseCoverageEngine(spec, validate_schemas=True)
        engine.process_events(events)

        summary = engine.calculate_summary()

        # Verify request body validation stats
        # 2 request bodies sent (one valid, one invalid per schema)
        assert summary.total_request_body_validations == 2
        assert summary.request_body_valid_count == 1  # First POST has valid body
        assert summary.request_body_invalid_count == 1  # Second POST has invalid body

        # Verify response schema validation stats
        # 4 responses with schemas (201, 400, 200, 200)
        assert summary.total_response_schema_validations >= 2  # At least the GET responses
        assert summary.response_schema_valid_count >= 1  # First GET response is valid
        assert summary.response_schema_invalid_count >= 1  # Fourth response is invalid

        # Generate report
        renderer = ReportRenderer(engine)
        report = renderer.generate_report()

        # Verify validation errors are captured
        validation_errors = report.validation_errors
        # Should have errors for request body and/or response schema
        assert len(validation_errors) > 0 or (
            summary.request_body_invalid_count > 0 or
            summary.response_schema_invalid_count > 0
        )

        # Write JSON report and verify schema_validation section
        report_path = tmp_path / "coverage_validation.json"
        renderer.write_json_report(str(report_path))

        import json
        report_data = json.loads(report_path.read_text())
        assert "schema_validation" in report_data["summary"]
        assert "request_body" in report_data["summary"]["schema_validation"]
        assert "response_schema" in report_data["summary"]["schema_validation"]

        # Verify CLI output includes validation info
        cli_output = renderer.render_cli_summary()
        if summary.total_request_body_validations > 0 or summary.total_response_schema_validations > 0:
            assert "Schema Validation" in cli_output

    def test_schema_validation_disabled(self, spec_path):
        """Test that schema validation can be disabled."""
        import requests
        import responses

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
        spec = OpenAPISpecParser(spec_path)

        # Create engine with validation disabled
        engine = SynapseCoverageEngine(spec, validate_schemas=False)
        engine.process_events(events)

        summary = engine.calculate_summary()

        # Coverage should still work
        assert summary.covered_operations >= 1

        # But validation counts should be zero
        assert summary.request_body_valid_count == 0
        assert summary.request_body_invalid_count == 0
        assert summary.response_schema_valid_count == 0
        assert summary.response_schema_invalid_count == 0
