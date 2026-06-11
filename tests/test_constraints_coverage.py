"""Tests for comprehensive constraint coverage tracking."""

import pytest
from pathlib import Path

from pytest_synapse.schema_validator import (
    OpenAPISchemaValidator,
    ConstraintType,
    FieldCoverageInfo,
    SchemaCoverageInfo,
    SchemaValidationStatus,
)


@pytest.fixture
def constraints_spec():
    """Load the constraints spec."""
    import json
    spec_path = Path(__file__).parent / "fixtures" / "openapi_constraints.json"
    with open(spec_path) as f:
        return json.load(f)


@pytest.fixture
def validator(constraints_spec):
    """Create a validator with the constraints spec."""
    return OpenAPISchemaValidator(constraints_spec)


class TestStringConstraints:
    """Tests for string constraint extraction and coverage."""

    def test_minLength_constraint(self, validator, constraints_spec):
        """Test minLength constraint extraction."""
        schema = constraints_spec["components"]["schemas"]["Product"]
        coverage = validator.extract_schema_fields(schema, "/products.POST.201")

        assert "name" in coverage.fields
        field = coverage.fields["name"]

        min_length = [c for c in field.constraints if c.constraint_type == ConstraintType.MIN_LENGTH]
        assert len(min_length) == 1
        assert min_length[0].value == 1

    def test_maxLength_constraint(self, validator, constraints_spec):
        """Test maxLength constraint extraction."""
        schema = constraints_spec["components"]["schemas"]["Product"]
        coverage = validator.extract_schema_fields(schema, "/products.POST.201")

        assert "name" in coverage.fields
        field = coverage.fields["name"]

        max_length = [c for c in field.constraints if c.constraint_type == ConstraintType.MAX_LENGTH]
        assert len(max_length) == 1
        assert max_length[0].value == 200

    def test_pattern_constraint(self, validator, constraints_spec):
        """Test pattern constraint extraction."""
        schema = constraints_spec["components"]["schemas"]["Product"]
        coverage = validator.extract_schema_fields(schema, "/products.POST.201")

        assert "sku" in coverage.fields
        field = coverage.fields["sku"]

        pattern = [c for c in field.constraints if c.constraint_type == ConstraintType.PATTERN]
        assert len(pattern) == 1
        assert pattern[0].value == "^[A-Z]{2,4}-[0-9]{4,8}$"

    def test_format_email_constraint(self, validator, constraints_spec):
        """Test email format constraint extraction."""
        schema = constraints_spec["components"]["schemas"]["UserProfile"]
        coverage = validator.extract_schema_fields(schema, "/users/{userId}/profile.GET.200")

        assert "email" in coverage.fields
        field = coverage.fields["email"]

        format_c = [c for c in field.constraints if c.constraint_type == ConstraintType.FORMAT]
        assert len(format_c) == 1
        assert format_c[0].value == "email"

    def test_format_uri_constraint(self, validator, constraints_spec):
        """Test URI format constraint extraction."""
        schema = constraints_spec["components"]["schemas"]["UserProfile"]
        coverage = validator.extract_schema_fields(schema, "/users/{userId}/profile.GET.200")

        assert "avatarUrl" in coverage.fields
        field = coverage.fields["avatarUrl"]

        format_c = [c for c in field.constraints if c.constraint_type == ConstraintType.FORMAT]
        assert len(format_c) == 1
        assert format_c[0].value == "uri"

    def test_format_datetime_constraint(self, validator, constraints_spec):
        """Test date-time format constraint extraction."""
        schema = constraints_spec["components"]["schemas"]["Product"]
        coverage = validator.extract_schema_fields(schema, "/products.POST.201")

        assert "createdAt" in coverage.fields
        field = coverage.fields["createdAt"]

        format_c = [c for c in field.constraints if c.constraint_type == ConstraintType.FORMAT]
        assert len(format_c) == 1
        assert format_c[0].value == "date-time"

    def test_format_uuid_constraint(self, validator, constraints_spec):
        """Test UUID format constraint extraction."""
        schema = constraints_spec["components"]["schemas"]["Product"]
        coverage = validator.extract_schema_fields(schema, "/products.POST.201")

        assert "id" in coverage.fields
        field = coverage.fields["id"]

        format_c = [c for c in field.constraints if c.constraint_type == ConstraintType.FORMAT]
        assert len(format_c) == 1
        assert format_c[0].value == "uuid"


class TestNumericConstraints:
    """Tests for numeric constraint extraction and coverage."""

    def test_minimum_constraint(self, validator, constraints_spec):
        """Test minimum constraint extraction."""
        schema = constraints_spec["components"]["schemas"]["Product"]
        coverage = validator.extract_schema_fields(schema, "/products.POST.201")

        assert "price" in coverage.fields
        field = coverage.fields["price"]

        minimum = [c for c in field.constraints if c.constraint_type == ConstraintType.MINIMUM]
        assert len(minimum) == 1
        assert minimum[0].value == 0.01

    def test_maximum_constraint(self, validator, constraints_spec):
        """Test maximum constraint extraction."""
        schema = constraints_spec["components"]["schemas"]["Product"]
        coverage = validator.extract_schema_fields(schema, "/products.POST.201")

        assert "price" in coverage.fields
        field = coverage.fields["price"]

        maximum = [c for c in field.constraints if c.constraint_type == ConstraintType.MAXIMUM]
        assert len(maximum) == 1
        assert maximum[0].value == 999999.99

    def test_integer_type_constraint(self, validator, constraints_spec):
        """Test integer type constraint extraction."""
        schema = constraints_spec["components"]["schemas"]["Product"]
        coverage = validator.extract_schema_fields(schema, "/products.POST.201")

        assert "inventory" in coverage.fields
        field = coverage.fields["inventory"]

        type_c = [c for c in field.constraints if c.constraint_type == ConstraintType.TYPE]
        assert len(type_c) == 1
        assert type_c[0].value == "integer"

    def test_number_type_constraint(self, validator, constraints_spec):
        """Test number type constraint extraction."""
        schema = constraints_spec["components"]["schemas"]["Product"]
        coverage = validator.extract_schema_fields(schema, "/products.POST.201")

        assert "price" in coverage.fields
        field = coverage.fields["price"]

        type_c = [c for c in field.constraints if c.constraint_type == ConstraintType.TYPE]
        assert len(type_c) == 1
        assert type_c[0].value == "number"


class TestEnumConstraints:
    """Tests for enum constraint extraction and coverage."""

    def test_enum_constraint_extraction(self, validator, constraints_spec):
        """Test enum constraint extraction."""
        schema = constraints_spec["components"]["schemas"]["Product"]
        coverage = validator.extract_schema_fields(schema, "/products.POST.201")

        assert "category" in coverage.fields
        field = coverage.fields["category"]

        enum_c = [c for c in field.constraints if c.constraint_type == ConstraintType.ENUM]
        assert len(enum_c) == 1
        assert set(enum_c[0].value) == {"electronics", "clothing", "food", "books", "other"}

    def test_enum_coverage_tracking(self, validator, constraints_spec):
        """Test enum value coverage tracking."""
        schema = constraints_spec["components"]["schemas"]["Product"]
        data1 = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "name": "Phone",
            "price": 999.99,
            "category": "electronics",
            "status": "active"
        }
        data2 = {
            "id": "550e8400-e29b-41d4-a716-446655440001",
            "name": "Shirt",
            "price": 29.99,
            "category": "clothing",
            "status": "active"
        }

        coverage = validator.track_field_coverage(data1, schema, "/products")
        validator._track_data_coverage(data2, "", coverage)

        enum_constraint = [
            c for c in coverage.fields["category"].constraints
            if c.constraint_type == ConstraintType.ENUM
        ][0]

        assert "electronics" in enum_constraint.covered_values
        assert "clothing" in enum_constraint.covered_values
        assert "food" not in enum_constraint.covered_values

    def test_status_enum_values(self, validator, constraints_spec):
        """Test status enum has expected values."""
        schema = constraints_spec["components"]["schemas"]["Product"]
        coverage = validator.extract_schema_fields(schema, "/products.POST.201")

        assert "status" in coverage.fields
        field = coverage.fields["status"]

        enum_c = [c for c in field.constraints if c.constraint_type == ConstraintType.ENUM]
        assert len(enum_c) == 1
        assert set(enum_c[0].value) == {"draft", "active", "discontinued", "out_of_stock"}


class TestArrayConstraints:
    """Tests for array constraint extraction and coverage."""

    def test_minItems_constraint(self, validator, constraints_spec):
        """Test minItems constraint extraction."""
        schema = constraints_spec["components"]["schemas"]["Order"]
        coverage = validator.extract_schema_fields(schema, "/orders.POST.201")

        assert "items" in coverage.fields
        field = coverage.fields["items"]

        min_items = [c for c in field.constraints if c.constraint_type == ConstraintType.MIN_ITEMS]
        assert len(min_items) == 1
        assert min_items[0].value == 1

    def test_maxItems_constraint(self, validator, constraints_spec):
        """Test maxItems constraint extraction."""
        schema = constraints_spec["components"]["schemas"]["Order"]
        coverage = validator.extract_schema_fields(schema, "/orders.POST.201")

        assert "items" in coverage.fields
        field = coverage.fields["items"]

        max_items = [c for c in field.constraints if c.constraint_type == ConstraintType.MAX_ITEMS]
        assert len(max_items) == 1
        assert max_items[0].value == 100

    def test_uniqueItems_constraint(self, validator, constraints_spec):
        """Test uniqueItems constraint extraction."""
        schema = constraints_spec["components"]["schemas"]["Product"]
        coverage = validator.extract_schema_fields(schema, "/products.POST.201")

        assert "tags" in coverage.fields
        field = coverage.fields["tags"]

        unique = [c for c in field.constraints if c.constraint_type == ConstraintType.UNIQUE_ITEMS]
        assert len(unique) == 1
        assert unique[0].value is True


class TestRequiredFields:
    """Tests for required field tracking."""

    def test_required_fields_identification(self, validator, constraints_spec):
        """Test required fields are identified."""
        schema = constraints_spec["components"]["schemas"]["Product"]
        coverage = validator.extract_schema_fields(schema, "/products.POST.201")

        # id, name, price, category, status are required
        assert coverage.fields["id"].is_required is True
        assert coverage.fields["name"].is_required is True
        assert coverage.fields["price"].is_required is True
        assert coverage.fields["category"].is_required is True
        assert coverage.fields["status"].is_required is True

        # Optional fields
        assert coverage.fields["description"].is_required is False
        assert coverage.fields["tags"].is_required is False

    def test_required_field_count(self, validator, constraints_spec):
        """Test required field count includes nested required fields."""
        schema = constraints_spec["components"]["schemas"]["Product"]
        coverage = validator.extract_schema_fields(schema, "/products.POST.201")

        # Required fields: id, name, price, category, status + nested dimensions required fields
        # dimensions.length, dimensions.width, dimensions.height are required in Dimensions schema
        assert coverage.total_required == 8  # 5 top-level + 3 nested in dimensions

    def test_required_coverage_percentage(self, validator, constraints_spec):
        """Test required field coverage percentage calculation."""
        schema = constraints_spec["components"]["schemas"]["Product"]
        # Include all required fields including nested dimensions
        data = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "name": "Phone",
            "price": 999.99,
            "category": "electronics",
            "status": "active",
            "dimensions": {
                "length": 10,
                "width": 5,
                "height": 2
            }
        }

        coverage = validator.track_field_coverage(data, schema, "/products")
        assert coverage.required_coverage_pct == 100.0


class TestNestedObjectCoverage:
    """Tests for nested object field coverage."""

    def test_nested_object_fields_extracted(self, validator, constraints_spec):
        """Test nested object fields are extracted."""
        schema = constraints_spec["components"]["schemas"]["Order"]
        coverage = validator.extract_schema_fields(schema, "/orders.POST.201")

        # Should have shippingAddress fields
        assert "shippingAddress" in coverage.fields
        assert "shippingAddress.street" in coverage.fields
        assert "shippingAddress.city" in coverage.fields
        assert "shippingAddress.country" in coverage.fields

    def test_nested_object_required_tracking(self, validator, constraints_spec):
        """Test nested required fields are tracked."""
        schema = constraints_spec["components"]["schemas"]["Order"]
        coverage = validator.extract_schema_fields(schema, "/orders.POST.201")

        # shippingAddress.street is required within Address schema
        assert coverage.fields["shippingAddress.street"].is_required is True
        assert coverage.fields["shippingAddress.city"].is_required is True
        # street2 is optional
        assert coverage.fields["shippingAddress.street2"].is_required is False

    def test_nested_object_coverage_tracking(self, validator, constraints_spec):
        """Test coverage tracking for nested objects."""
        schema = constraints_spec["components"]["schemas"]["Order"]
        data = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "customerId": 1,
            "items": [{"productId": "123", "quantity": 1, "unitPrice": 10}],
            "status": "pending",
            "total": 10.00,
            "shippingAddress": {
                "street": "123 Main St",
                "city": "New York",
                "country": "US",
                "postalCode": "10001"
            }
        }

        coverage = validator.track_field_coverage(data, schema, "/orders")

        assert coverage.fields["shippingAddress"].is_covered is True
        assert coverage.fields["shippingAddress.street"].is_covered is True
        assert coverage.fields["shippingAddress.city"].is_covered is True


class TestArrayItemCoverage:
    """Tests for array item field coverage."""

    def test_array_item_fields_extracted(self, validator, constraints_spec):
        """Test array item fields are extracted."""
        schema = constraints_spec["components"]["schemas"]["Order"]
        coverage = validator.extract_schema_fields(schema, "/orders.POST.201")

        # Should have items[] fields
        assert "items" in coverage.fields
        assert "items[].productId" in coverage.fields
        assert "items[].quantity" in coverage.fields

    def test_array_item_constraints(self, validator, constraints_spec):
        """Test array item constraints are extracted."""
        schema = constraints_spec["components"]["schemas"]["Order"]
        coverage = validator.extract_schema_fields(schema, "/orders.POST.201")

        # items[].quantity should have min/max constraints
        quantity_field = coverage.fields["items[].quantity"]

        min_c = [c for c in quantity_field.constraints if c.constraint_type == ConstraintType.MINIMUM]
        max_c = [c for c in quantity_field.constraints if c.constraint_type == ConstraintType.MAXIMUM]

        assert len(min_c) == 1
        assert min_c[0].value == 1
        assert len(max_c) == 1
        assert max_c[0].value == 999


class TestValidationWithCoverage:
    """Tests for combined validation and coverage tracking."""

    def test_valid_data_returns_valid_status(self, validator, constraints_spec):
        """Test valid data returns VALID status."""
        schema = constraints_spec["components"]["schemas"]["CreateProductRequest"]
        data = {
            "name": "Test Product",
            "price": 99.99,
            "category": "electronics"
        }

        result = validator.validate_with_coverage(data, schema, "/products")
        assert result.status == SchemaValidationStatus.VALID

    def test_invalid_data_returns_invalid_status(self, validator, constraints_spec):
        """Test invalid data returns INVALID status."""
        schema = constraints_spec["components"]["schemas"]["CreateProductRequest"]
        data = {
            "name": "",  # Empty name, violates minLength
            "price": -10,  # Negative price, violates minimum
            "category": "invalid_category"  # Not in enum
        }

        result = validator.validate_with_coverage(data, schema, "/products")
        assert result.status == SchemaValidationStatus.INVALID

    def test_missing_required_returns_invalid(self, validator, constraints_spec):
        """Test missing required fields return INVALID status."""
        schema = constraints_spec["components"]["schemas"]["CreateProductRequest"]
        data = {
            "name": "Test Product"
            # Missing price and category which are required
        }

        result = validator.validate_with_coverage(data, schema, "/products")
        assert result.status == SchemaValidationStatus.INVALID

    def test_coverage_tracked_even_when_invalid(self, validator, constraints_spec):
        """Test that coverage is tracked even for invalid data."""
        schema = constraints_spec["components"]["schemas"]["CreateProductRequest"]
        data = {
            "name": "Test",
            "price": "not-a-number",  # Invalid type
            "category": "electronics"
        }

        result = validator.validate_with_coverage(data, schema, "/products")

        assert result.field_coverage is not None
        # name and category should be covered even though price is invalid
        assert result.field_coverage.fields["name"].is_covered is True
        assert result.field_coverage.fields["category"].is_covered is True


class TestCoveragePercentages:
    """Tests for coverage percentage calculations."""

    def test_field_coverage_percentage(self, validator, constraints_spec):
        """Test field coverage percentage calculation."""
        schema = constraints_spec["components"]["schemas"]["CreateProductRequest"]
        data = {
            "name": "Test",
            "price": 99.99,
            "category": "electronics"
        }

        coverage = validator.track_field_coverage(data, schema, "/products")

        # 3 required fields covered out of total
        assert coverage.field_coverage_pct > 0

    def test_partial_coverage_percentage(self, validator, constraints_spec):
        """Test partial coverage percentage."""
        schema = constraints_spec["components"]["schemas"]["CreateProductRequest"]
        data = {
            "name": "Test",
            "price": 99.99,
            "category": "electronics",
            "tags": ["tag1", "tag2"]
        }

        coverage = validator.track_field_coverage(data, schema, "/products")

        # More fields covered
        assert coverage.covered_fields >= 4

    def test_enum_coverage_percentage(self, validator, constraints_spec):
        """Test enum value coverage percentage calculation."""
        schema = constraints_spec["components"]["schemas"]["Product"]
        data1 = {"id": "1", "name": "A", "price": 1, "category": "electronics", "status": "active"}
        data2 = {"id": "2", "name": "B", "price": 1, "category": "clothing", "status": "active"}
        data3 = {"id": "3", "name": "C", "price": 1, "category": "food", "status": "draft"}

        coverage = validator.track_field_coverage(data1, schema, "/products")
        validator._track_data_coverage(data2, "", coverage)
        validator._track_data_coverage(data3, "", coverage)

        # Check category enum coverage
        category_enum = [
            c for c in coverage.fields["category"].constraints
            if c.constraint_type == ConstraintType.ENUM
        ][0]

        assert len(category_enum.covered_values) == 3  # electronics, clothing, food
        # 3 out of 5 enum values = 60%


class TestUserProfileConstraints:
    """Tests for UserProfile schema constraints."""

    def test_username_pattern_constraint(self, validator, constraints_spec):
        """Test username pattern constraint."""
        schema = constraints_spec["components"]["schemas"]["UserProfile"]
        coverage = validator.extract_schema_fields(schema, "/users/{userId}/profile.GET.200")

        assert "username" in coverage.fields
        field = coverage.fields["username"]

        pattern = [c for c in field.constraints if c.constraint_type == ConstraintType.PATTERN]
        assert len(pattern) == 1
        assert pattern[0].value == "^[a-z0-9_-]+$"

    def test_age_range_constraints(self, validator, constraints_spec):
        """Test age minimum and maximum constraints."""
        schema = constraints_spec["components"]["schemas"]["UserProfile"]
        coverage = validator.extract_schema_fields(schema, "/users/{userId}/profile.GET.200")

        assert "age" in coverage.fields
        field = coverage.fields["age"]

        min_c = [c for c in field.constraints if c.constraint_type == ConstraintType.MINIMUM]
        max_c = [c for c in field.constraints if c.constraint_type == ConstraintType.MAXIMUM]

        assert len(min_c) == 1
        assert min_c[0].value == 13
        assert len(max_c) == 1
        assert max_c[0].value == 150

    def test_account_type_enum(self, validator, constraints_spec):
        """Test accountType enum values."""
        schema = constraints_spec["components"]["schemas"]["UserProfile"]
        coverage = validator.extract_schema_fields(schema, "/users/{userId}/profile.GET.200")

        assert "accountType" in coverage.fields
        field = coverage.fields["accountType"]

        enum_c = [c for c in field.constraints if c.constraint_type == ConstraintType.ENUM]
        assert len(enum_c) == 1
        assert set(enum_c[0].value) == {"free", "basic", "premium", "enterprise"}

    def test_nested_preferences(self, validator, constraints_spec):
        """Test nested preferences object."""
        schema = constraints_spec["components"]["schemas"]["UserProfile"]
        coverage = validator.extract_schema_fields(schema, "/users/{userId}/profile.GET.200")

        assert "preferences" in coverage.fields
        assert "preferences.theme" in coverage.fields
        assert "preferences.language" in coverage.fields

        # Check theme enum
        theme_field = coverage.fields["preferences.theme"]
        enum_c = [c for c in theme_field.constraints if c.constraint_type == ConstraintType.ENUM]
        assert len(enum_c) == 1
        assert set(enum_c[0].value) == {"light", "dark", "auto"}

    def test_social_links_array(self, validator, constraints_spec):
        """Test socialLinks array constraints."""
        schema = constraints_spec["components"]["schemas"]["UserProfile"]
        coverage = validator.extract_schema_fields(schema, "/users/{userId}/profile.GET.200")

        assert "socialLinks" in coverage.fields
        assert "socialLinks[].platform" in coverage.fields
        assert "socialLinks[].url" in coverage.fields

        # Check platform enum
        platform_field = coverage.fields["socialLinks[].platform"]
        enum_c = [c for c in platform_field.constraints if c.constraint_type == ConstraintType.ENUM]
        assert len(enum_c) == 1
        assert "twitter" in enum_c[0].value
        assert "github" in enum_c[0].value
