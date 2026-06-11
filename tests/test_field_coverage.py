"""Tests for field-level coverage and constraint tracking."""

import pytest

from pytest_synapse.schema_validator import (
    OpenAPISchemaValidator,
    ConstraintType,
    FieldCoverageInfo,
    SchemaCoverageInfo,
    SchemaValidationStatus,
)


@pytest.fixture
def sample_spec():
    """Create a sample OpenAPI spec for testing."""
    return {
        "openapi": "3.0.3",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {
            "/users": {
                "post": {
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/CreateUserRequest"
                                }
                            }
                        }
                    },
                    "responses": {
                        "201": {
                            "description": "User created",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/User"
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "components": {
            "schemas": {
                "User": {
                    "type": "object",
                    "required": ["id", "name", "email"],
                    "properties": {
                        "id": {"type": "integer"},
                        "name": {"type": "string", "minLength": 1, "maxLength": 100},
                        "email": {"type": "string", "format": "email"},
                        "role": {
                            "type": "string",
                            "enum": ["admin", "user", "guest"]
                        }
                    }
                },
                "CreateUserRequest": {
                    "type": "object",
                    "required": ["name", "email"],
                    "properties": {
                        "name": {"type": "string", "minLength": 1},
                        "email": {"type": "string", "format": "email"},
                        "role": {
                            "type": "string",
                            "enum": ["admin", "user", "guest"]
                        }
                    }
                }
            }
        }
    }


@pytest.fixture
def validator(sample_spec):
    """Create a validator instance."""
    return OpenAPISchemaValidator(sample_spec)


class TestConstraintExtraction:
    """Tests for extracting constraints from schemas."""

    def test_extract_type_constraint(self, validator, sample_spec):
        """Test extraction of type constraints."""
        schema = sample_spec["components"]["schemas"]["User"]
        coverage = validator.extract_schema_fields(schema, "/users.POST.201")

        assert "id" in coverage.fields
        field = coverage.fields["id"]
        assert field.field_type == "integer"

        type_constraints = [
            c for c in field.constraints if c.constraint_type == ConstraintType.TYPE
        ]
        assert len(type_constraints) == 1
        assert type_constraints[0].value == "integer"

    def test_extract_enum_constraint(self, validator, sample_spec):
        """Test extraction of enum constraints."""
        schema = sample_spec["components"]["schemas"]["User"]
        coverage = validator.extract_schema_fields(schema, "/users.POST.201")

        assert "role" in coverage.fields
        field = coverage.fields["role"]

        enum_constraints = [
            c for c in field.constraints if c.constraint_type == ConstraintType.ENUM
        ]
        assert len(enum_constraints) == 1
        assert set(enum_constraints[0].value) == {"admin", "user", "guest"}

    def test_extract_format_constraint(self, validator, sample_spec):
        """Test extraction of format constraints."""
        schema = sample_spec["components"]["schemas"]["User"]
        coverage = validator.extract_schema_fields(schema, "/users.POST.201")

        assert "email" in coverage.fields
        field = coverage.fields["email"]

        format_constraints = [
            c for c in field.constraints if c.constraint_type == ConstraintType.FORMAT
        ]
        assert len(format_constraints) == 1
        assert format_constraints[0].value == "email"

    def test_extract_string_length_constraints(self, validator, sample_spec):
        """Test extraction of minLength/maxLength constraints."""
        schema = sample_spec["components"]["schemas"]["User"]
        coverage = validator.extract_schema_fields(schema, "/users.POST.201")

        assert "name" in coverage.fields
        field = coverage.fields["name"]

        min_constraints = [
            c for c in field.constraints if c.constraint_type == ConstraintType.MIN_LENGTH
        ]
        max_constraints = [
            c for c in field.constraints if c.constraint_type == ConstraintType.MAX_LENGTH
        ]
        assert len(min_constraints) == 1
        assert min_constraints[0].value == 1
        assert len(max_constraints) == 1
        assert max_constraints[0].value == 100

    def test_required_fields_tracked(self, validator, sample_spec):
        """Test that required fields are properly tracked."""
        schema = sample_spec["components"]["schemas"]["User"]
        coverage = validator.extract_schema_fields(schema, "/users.POST.201")

        # id, name, email are required
        assert coverage.fields["id"].is_required is True
        assert coverage.fields["name"].is_required is True
        assert coverage.fields["email"].is_required is True
        # role is optional
        assert coverage.fields["role"].is_required is False

        assert coverage.total_required == 3


class TestFieldCoverageTracking:
    """Tests for tracking field coverage."""

    def test_track_covered_fields(self, validator, sample_spec):
        """Test tracking of covered fields from data."""
        schema = sample_spec["components"]["schemas"]["User"]
        data = {
            "id": 1,
            "name": "John Doe",
            "email": "john@example.com"
        }
        coverage = validator.track_field_coverage(data, schema, "/test")

        assert coverage.fields["id"].is_covered is True
        assert coverage.fields["name"].is_covered is True
        assert coverage.fields["email"].is_covered is True
        assert coverage.fields["role"].is_covered is False

        assert coverage.covered_fields == 3
        assert coverage.total_fields == 4

    def test_track_enum_coverage(self, validator, sample_spec):
        """Test tracking of enum value coverage."""
        schema = sample_spec["components"]["schemas"]["User"]
        data1 = {"id": 1, "name": "John", "email": "john@example.com", "role": "admin"}
        data2 = {"id": 2, "name": "Jane", "email": "jane@example.com", "role": "user"}

        coverage = validator.track_field_coverage(data1, schema, "/test")
        assert "admin" in coverage.fields["role"].constraints[1].covered_values  # enum constraint

        # Track second data
        validator._track_data_coverage(data2, "", coverage)
        enum_constraint = [
            c for c in coverage.fields["role"].constraints
            if c.constraint_type == ConstraintType.ENUM
        ][0]
        assert "admin" in enum_constraint.covered_values
        assert "user" in enum_constraint.covered_values

    def test_coverage_percentages(self, validator, sample_spec):
        """Test coverage percentage calculations."""
        schema = sample_spec["components"]["schemas"]["User"]
        data = {"id": 1, "name": "John", "email": "john@example.com"}

        coverage = validator.track_field_coverage(data, schema, "/test")

        assert coverage.field_coverage_pct == 75.0  # 3 of 4 fields covered
        assert coverage.required_coverage_pct == 100.0  # All 3 required covered


class TestValidateWithCoverage:
    """Tests for combined validation and coverage tracking."""

    def test_validate_with_coverage_valid(self, validator):
        """Test validation with coverage for valid data."""
        schema = {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"}
            }
        }
        data = {"name": "John", "age": 30}

        result = validator.validate_with_coverage(data, schema, "/test")

        assert result.status == SchemaValidationStatus.VALID
        assert result.field_coverage is not None
        assert result.field_coverage.covered_fields == 2

    def test_validate_with_coverage_invalid(self, validator):
        """Test validation with coverage for invalid data."""
        schema = {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"}
            }
        }
        data = {"age": "not-an-integer"}  # Missing name, wrong type for age

        result = validator.validate_with_coverage(data, schema, "/test")

        assert result.status == SchemaValidationStatus.INVALID
        assert result.field_coverage is not None
        # age is covered even though it's invalid
        assert result.field_coverage.fields["age"].is_covered is True


class TestNestedSchemaExtraction:
    """Tests for nested schema field extraction."""

    def test_nested_object_fields(self, validator):
        """Test extraction of nested object fields."""
        spec = {
            "openapi": "3.0.3",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {},
            "components": {
                "schemas": {
                    "Order": {
                        "type": "object",
                        "required": ["id", "customer"],
                        "properties": {
                            "id": {"type": "string"},
                            "customer": {
                                "type": "object",
                                "required": ["name"],
                                "properties": {
                                    "name": {"type": "string"},
                                    "email": {"type": "string"}
                                }
                            }
                        }
                    }
                }
            }
        }
        validator = OpenAPISchemaValidator(spec)
        schema = spec["components"]["schemas"]["Order"]
        coverage = validator.extract_schema_fields(schema, "/orders")

        assert "id" in coverage.fields
        assert "customer" in coverage.fields
        assert "customer.name" in coverage.fields
        assert "customer.email" in coverage.fields

    def test_array_item_fields(self, validator):
        """Test extraction of array item fields."""
        spec = {
            "openapi": "3.0.3",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {},
            "components": {
                "schemas": {
                    "Order": {
                        "type": "object",
                        "properties": {
                            "items": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["productId"],
                                    "properties": {
                                        "productId": {"type": "string"},
                                        "quantity": {"type": "integer", "minimum": 1}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        validator = OpenAPISchemaValidator(spec)
        schema = spec["components"]["schemas"]["Order"]
        coverage = validator.extract_schema_fields(schema, "/orders")

        assert "items" in coverage.fields
        assert "items[].productId" in coverage.fields
        assert "items[].quantity" in coverage.fields


class TestNumericConstraints:
    """Tests for numeric constraint extraction."""

    def test_minimum_maximum_constraints(self, validator):
        """Test extraction of minimum/maximum constraints."""
        schema = {
            "type": "object",
            "properties": {
                "age": {"type": "integer", "minimum": 0, "maximum": 150},
                "price": {"type": "number", "minimum": 0.01}
            }
        }
        coverage = validator.extract_schema_fields(schema, "/test")

        age_constraints = coverage.fields["age"].constraints
        min_c = [c for c in age_constraints if c.constraint_type == ConstraintType.MINIMUM]
        max_c = [c for c in age_constraints if c.constraint_type == ConstraintType.MAXIMUM]

        assert len(min_c) == 1
        assert min_c[0].value == 0
        assert len(max_c) == 1
        assert max_c[0].value == 150


class TestArrayConstraints:
    """Tests for array constraint extraction."""

    def test_array_item_constraints(self, validator):
        """Test extraction of minItems/maxItems constraints."""
        schema = {
            "type": "object",
            "properties": {
                "tags": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 10,
                    "uniqueItems": True,
                    "items": {"type": "string"}
                }
            }
        }
        coverage = validator.extract_schema_fields(schema, "/test")

        tags_constraints = coverage.fields["tags"].constraints
        min_items = [c for c in tags_constraints if c.constraint_type == ConstraintType.MIN_ITEMS]
        max_items = [c for c in tags_constraints if c.constraint_type == ConstraintType.MAX_ITEMS]
        unique = [c for c in tags_constraints if c.constraint_type == ConstraintType.UNIQUE_ITEMS]

        assert len(min_items) == 1
        assert min_items[0].value == 1
        assert len(max_items) == 1
        assert max_items[0].value == 10
        assert len(unique) == 1
        assert unique[0].value is True
