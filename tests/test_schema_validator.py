"""Tests for the schema validator module."""

import pytest

from pytest_synapse.schema_validator import (
    OpenAPISchemaValidator,
    SchemaValidationStatus,
    SchemaValidationResult,
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
                        },
                        "400": {
                            "description": "Bad request",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/Error"
                                    }
                                }
                            }
                        }
                    }
                },
                "get": {
                    "responses": {
                        "200": {
                            "description": "List of users",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {
                                            "$ref": "#/components/schemas/User"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "/users/{userId}": {
                "get": {
                    "parameters": [
                        {
                            "name": "userId",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"}
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "User details",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/User"
                                    }
                                }
                            }
                        },
                        "404": {
                            "description": "User not found"
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
                        "name": {"type": "string"},
                        "email": {"type": "string", "format": "email"}
                    }
                },
                "CreateUserRequest": {
                    "type": "object",
                    "required": ["name", "email"],
                    "properties": {
                        "name": {"type": "string", "minLength": 1},
                        "email": {"type": "string", "format": "email"}
                    }
                },
                "Error": {
                    "type": "object",
                    "required": ["message"],
                    "properties": {
                        "message": {"type": "string"},
                        "code": {"type": "string"}
                    }
                }
            }
        }
    }


@pytest.fixture
def validator(sample_spec):
    """Create a validator instance."""
    return OpenAPISchemaValidator(sample_spec)


class TestSchemaValidationResult:
    """Tests for SchemaValidationResult."""

    def test_to_dict_valid(self):
        """Test to_dict for valid result."""
        result = SchemaValidationResult(
            status=SchemaValidationStatus.VALID,
            schema_path="/users.POST.requestBody"
        )
        d = result.to_dict()
        assert d["status"] == "VALID"
        assert d["schema_path"] == "/users.POST.requestBody"
        assert "errors" not in d

    def test_to_dict_invalid_with_errors(self):
        """Test to_dict for invalid result with errors."""
        result = SchemaValidationResult(
            status=SchemaValidationStatus.INVALID,
            errors=["name: required property missing"],
            schema_path="/users.POST.requestBody"
        )
        d = result.to_dict()
        assert d["status"] == "INVALID"
        assert d["errors"] == ["name: required property missing"]
        assert d["schema_path"] == "/users.POST.requestBody"


class TestOpenAPISchemaValidator:
    """Tests for OpenAPISchemaValidator."""

    def test_validate_valid_request_body(self, validator):
        """Test validation of a valid request body."""
        data = {"name": "John Doe", "email": "john@example.com"}
        result = validator.validate_request_body("/users", "POST", data)

        assert result.status == SchemaValidationStatus.VALID
        assert result.errors == []
        assert result.schema_path == "/users.POST.requestBody"

    def test_validate_invalid_request_body_missing_required(self, validator):
        """Test validation of request body with missing required field."""
        data = {"name": "John Doe"}  # Missing email
        result = validator.validate_request_body("/users", "POST", data)

        assert result.status == SchemaValidationStatus.INVALID
        assert len(result.errors) > 0
        assert any("email" in err for err in result.errors)

    def test_validate_invalid_request_body_wrong_type(self, validator):
        """Test validation of request body with wrong type."""
        data = {"name": 123, "email": "john@example.com"}  # name should be string
        result = validator.validate_request_body("/users", "POST", data)

        assert result.status == SchemaValidationStatus.INVALID
        assert len(result.errors) > 0

    def test_validate_valid_response_body(self, validator):
        """Test validation of a valid response body."""
        data = {"id": 1, "name": "John Doe", "email": "john@example.com"}
        result = validator.validate_response_body("/users", "POST", 201, data)

        assert result.status == SchemaValidationStatus.VALID
        assert result.errors == []
        assert "201" in result.schema_path

    def test_validate_invalid_response_body_missing_required(self, validator):
        """Test validation of response body with missing required field."""
        data = {"id": 1, "name": "John Doe"}  # Missing email
        result = validator.validate_response_body("/users", "POST", 201, data)

        assert result.status == SchemaValidationStatus.INVALID
        assert len(result.errors) > 0
        assert any("email" in err for err in result.errors)

    def test_validate_response_body_array(self, validator):
        """Test validation of response body that is an array."""
        data = [
            {"id": 1, "name": "John", "email": "john@example.com"},
            {"id": 2, "name": "Jane", "email": "jane@example.com"},
        ]
        result = validator.validate_response_body("/users", "GET", 200, data)

        assert result.status == SchemaValidationStatus.VALID

    def test_validate_response_body_array_invalid_item(self, validator):
        """Test validation of response body array with invalid item."""
        data = [
            {"id": 1, "name": "John", "email": "john@example.com"},
            {"id": "not-an-int", "name": "Jane", "email": "jane@example.com"},  # id should be int
        ]
        result = validator.validate_response_body("/users", "GET", 200, data)

        assert result.status == SchemaValidationStatus.INVALID
        assert len(result.errors) > 0

    def test_validate_no_schema(self, validator):
        """Test validation when no schema exists for the response."""
        data = {"error": "Not found"}
        result = validator.validate_response_body("/users/{userId}", "GET", 404, data)

        assert result.status == SchemaValidationStatus.NO_SCHEMA

    def test_validate_no_body(self, validator):
        """Test validation when body is None."""
        result = validator.validate_request_body("/users", "POST", None)

        assert result.status == SchemaValidationStatus.NO_BODY

    def test_validate_error_response(self, validator):
        """Test validation of an error response."""
        data = {"message": "Invalid input"}
        result = validator.validate_response_body("/users", "POST", 400, data)

        assert result.status == SchemaValidationStatus.VALID

    def test_validate_error_response_invalid(self, validator):
        """Test validation of an invalid error response."""
        data = {"error": "Invalid input"}  # Should have "message" not "error"
        result = validator.validate_response_body("/users", "POST", 400, data)

        assert result.status == SchemaValidationStatus.INVALID
        assert any("message" in err for err in result.errors)

    def test_has_request_body_schema(self, validator):
        """Test checking if request body schema exists."""
        assert validator.has_request_body_schema("/users", "post") is True
        assert validator.has_request_body_schema("/users", "get") is False

    def test_has_response_schema(self, validator):
        """Test checking if response schema exists."""
        assert validator.has_response_schema("/users", "post", "201") is True
        assert validator.has_response_schema("/users/{userId}", "get", "404") is False

    def test_content_type_matching(self, validator):
        """Test schema extraction with specific content type."""
        data = {"name": "John", "email": "john@example.com"}
        result = validator.validate_request_body(
            "/users", "POST", data, "application/json; charset=utf-8"
        )

        assert result.status == SchemaValidationStatus.VALID


class TestValidationWithNestedSchemas:
    """Tests for validation with nested and referenced schemas."""

    @pytest.fixture
    def nested_spec(self):
        """Create a spec with nested schemas."""
        return {
            "openapi": "3.0.3",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {
                "/orders": {
                    "post": {
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/Order"
                                    }
                                }
                            }
                        },
                        "responses": {
                            "201": {
                                "description": "Created",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": "#/components/schemas/Order"
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
                    "Order": {
                        "type": "object",
                        "required": ["id", "items"],
                        "properties": {
                            "id": {"type": "string"},
                            "items": {
                                "type": "array",
                                "items": {
                                    "$ref": "#/components/schemas/OrderItem"
                                }
                            }
                        }
                    },
                    "OrderItem": {
                        "type": "object",
                        "required": ["productId", "quantity"],
                        "properties": {
                            "productId": {"type": "string"},
                            "quantity": {"type": "integer", "minimum": 1}
                        }
                    }
                }
            }
        }

    def test_validate_nested_schema_valid(self, nested_spec):
        """Test validation of nested schema."""
        validator = OpenAPISchemaValidator(nested_spec)
        data = {
            "id": "order-123",
            "items": [
                {"productId": "prod-1", "quantity": 2},
                {"productId": "prod-2", "quantity": 1}
            ]
        }
        result = validator.validate_request_body("/orders", "POST", data)

        assert result.status == SchemaValidationStatus.VALID

    def test_validate_nested_schema_invalid_child(self, nested_spec):
        """Test validation of nested schema with invalid child."""
        validator = OpenAPISchemaValidator(nested_spec)
        data = {
            "id": "order-123",
            "items": [
                {"productId": "prod-1", "quantity": 0}  # quantity must be >= 1
            ]
        }
        result = validator.validate_request_body("/orders", "POST", data)

        assert result.status == SchemaValidationStatus.INVALID
        assert len(result.errors) > 0
