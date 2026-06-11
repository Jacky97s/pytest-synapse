"""Tests for multi-version OpenAPI support (Swagger 2.0, 3.0.x, 3.1.x)."""

from pathlib import Path

import pytest

from pytest_synapse.coverage_engine import SynapseCoverageEngine
from pytest_synapse.schema_validator import (
    OpenAPISchemaValidator,
    SchemaValidationStatus,
)
from pytest_synapse.spec_parser import OpenAPISpecParser
from pytest_synapse.types import (
    CapturedTrafficEvent,
    CoverageStatus,
    HttpRequest,
    HttpResponse,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def swagger2_parser():
    return OpenAPISpecParser(str(FIXTURES / "swagger2.json"))


@pytest.fixture
def openapi31_parser():
    return OpenAPISpecParser(str(FIXTURES / "openapi31.json"))


@pytest.fixture
def openapi30_nullable_parser():
    return OpenAPISpecParser(str(FIXTURES / "openapi30_nullable.json"))


class TestVersionMajor:
    def test_swagger2_major(self, swagger2_parser):
        assert swagger2_parser.version_major == 2

    def test_openapi30_major(self, openapi30_nullable_parser):
        assert openapi30_nullable_parser.version_major == 3

    def test_openapi31_major(self, openapi31_parser):
        assert openapi31_parser.version_major == 3


class TestSwagger2RequestBody:
    def test_has_request_body_for_body_param(self, swagger2_parser):
        assert swagger2_parser.has_request_body("/users", "post") is True

    def test_get_request_body_schema_from_body_param(self, swagger2_parser):
        schema = swagger2_parser.get_request_body_schema("/users", "post")
        # The body parameter's schema is a $ref to CreateUserRequest
        assert schema == {"$ref": "#/definitions/CreateUserRequest"}

    def test_get_without_body_param_is_none(self, swagger2_parser):
        assert swagger2_parser.has_request_body("/users", "get") is False

    def test_has_request_body_for_formdata(self, swagger2_parser):
        assert swagger2_parser.has_request_body("/uploads", "post") is True

    def test_formdata_synthesized_into_object_schema(self, swagger2_parser):
        schema = swagger2_parser.get_request_body_schema("/uploads", "post")
        assert schema["type"] == "object"
        assert set(schema["properties"]) == {"title", "size"}
        assert schema["properties"]["title"]["type"] == "string"
        assert schema["properties"]["size"]["type"] == "integer"
        assert schema["required"] == ["title"]


class TestSwagger2BasePath:
    def test_base_path_from_basepath_field(self, swagger2_parser):
        assert swagger2_parser.get_base_paths() == ["/v1"]


class TestSwagger2Coverage:
    @pytest.fixture
    def engine(self, swagger2_parser):
        return SynapseCoverageEngine(swagger2_parser)

    def test_operation_covered_behind_base_path(self, engine):
        event = CapturedTrafficEvent(
            test_id="t",
            request=HttpRequest(method="GET", path="/v1/users/123"),
            response=HttpResponse(status_code=200, body={"id": 123, "name": "A"}),
        )
        engine.process_events([event])
        op = engine.get_coverage_map()["/users/{userId}"].operations["GET"]
        assert op.status == CoverageStatus.COVERED
        assert op.responses["200"].status == CoverageStatus.COVERED

    def test_body_param_request_body_covered(self, engine):
        event = CapturedTrafficEvent(
            test_id="t",
            request=HttpRequest(
                method="POST", path="/v1/users", body={"name": "Alice"}
            ),
            response=HttpResponse(status_code=201, body={"id": 1, "name": "Alice"}),
        )
        engine.process_events([event])
        op = engine.get_coverage_map()["/users"].operations["POST"]
        assert op.status == CoverageStatus.COVERED
        assert op.request_body == CoverageStatus.COVERED

    def test_formdata_request_body_covered(self, engine):
        event = CapturedTrafficEvent(
            test_id="t",
            request=HttpRequest(
                method="POST", path="/v1/uploads", body={"title": "x", "size": 10}
            ),
            response=HttpResponse(status_code=201, body=None),
        )
        engine.process_events([event])
        op = engine.get_coverage_map()["/uploads"].operations["POST"]
        assert op.status == CoverageStatus.COVERED
        assert op.request_body == CoverageStatus.COVERED

    def test_body_param_is_schema_validated(self, engine):
        # A valid 2.0 body must be schema-validated, not just marked covered.
        event = CapturedTrafficEvent(
            test_id="t",
            request=HttpRequest(
                method="POST", path="/v1/users", body={"name": "Alice"}
            ),
            response=HttpResponse(status_code=201, body={"id": 1, "name": "Alice"}),
        )
        engine.process_events([event])
        op = engine.get_coverage_map()["/users"].operations["POST"]
        assert op.request_body_coverage.valid_count == 1

    def test_response_schema_on_response_is_validated(self, engine):
        event = CapturedTrafficEvent(
            test_id="t",
            request=HttpRequest(method="GET", path="/v1/users/1"),
            response=HttpResponse(status_code=200, body={"id": 1, "name": "Alice"}),
        )
        engine.process_events([event])
        resp = engine.get_coverage_map()["/users/{userId}"].operations["GET"].responses["200"]
        assert resp.schema_coverage.valid_count == 1


class TestSwagger2Validation:
    @pytest.fixture
    def validator(self, swagger2_parser):
        return OpenAPISchemaValidator(swagger2_parser.spec)

    def test_validate_body_param_against_definitions_ref(self, validator):
        result = validator.validate(
            {"name": "Alice"},
            {"$ref": "#/definitions/CreateUserRequest"},
            "/users.POST.requestBody",
        )
        assert result.status == SchemaValidationStatus.VALID

    def test_response_schema_on_response_validates(self, validator):
        result = validator.validate_response_body(
            "/users", "GET", 200, [{"id": 1, "name": "A"}]
        )
        assert result.status == SchemaValidationStatus.VALID


class TestOpenAPI30Nullable:
    @pytest.fixture
    def validator(self, openapi30_nullable_parser):
        return OpenAPISchemaValidator(openapi30_nullable_parser.spec)

    def test_nullable_field_accepts_null(self, validator):
        result = validator.validate_request_body(
            "/users", "POST", {"name": "Alice", "nickname": None}
        )
        assert result.status == SchemaValidationStatus.VALID

    def test_nullable_field_still_accepts_string(self, validator):
        result = validator.validate_request_body(
            "/users", "POST", {"name": "Alice", "nickname": "Al"}
        )
        assert result.status == SchemaValidationStatus.VALID

    def test_non_nullable_field_rejects_null(self, validator):
        result = validator.validate_request_body(
            "/users", "POST", {"name": None}
        )
        assert result.status == SchemaValidationStatus.INVALID


class TestOpenAPI31:
    @pytest.fixture
    def validator(self, openapi31_parser):
        return OpenAPISchemaValidator(openapi31_parser.spec)

    def test_type_array_accepts_null(self, validator):
        result = validator.validate_request_body(
            "/users", "POST", {"name": "Alice", "nickname": None, "kind": "user"}
        )
        assert result.status == SchemaValidationStatus.VALID

    def test_field_type_normalized_for_type_array(self, validator, openapi31_parser):
        schema = openapi31_parser.spec["components"]["schemas"]["CreateUserRequest"]
        coverage = validator.extract_schema_fields(schema, "/users.POST.requestBody")
        assert coverage.fields["nickname"].field_type == "string"

    def test_uses_2020_12_dialect_for_prefix_items(self, validator):
        # prefixItems + "items": false is 2020-12 tuple validation. Under
        # Draft 7 "items": false rejects every element, so a valid 2-tuple
        # would wrongly fail; only a 2020-12 validator accepts it.
        valid = validator.validate_request_body(
            "/coordinates", "POST", {"point": [1.0, 2.0]}
        )
        assert valid.status == SchemaValidationStatus.VALID

        bad = validator.validate_request_body(
            "/coordinates", "POST", {"point": [1.0, "not-a-number"]}
        )
        assert bad.status == SchemaValidationStatus.INVALID
