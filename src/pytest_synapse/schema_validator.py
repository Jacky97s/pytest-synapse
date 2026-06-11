"""JSON Schema validation for OpenAPI request and response bodies."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from jsonschema import Draft7Validator, ValidationError, RefResolver
from jsonschema.exceptions import SchemaError


class SchemaValidationStatus(str, Enum):
    """Status of schema validation."""

    VALID = "VALID"
    INVALID = "INVALID"
    NO_SCHEMA = "NO_SCHEMA"
    NO_BODY = "NO_BODY"
    VALIDATION_ERROR = "VALIDATION_ERROR"


class ConstraintType(str, Enum):
    """Type of schema constraint."""

    REQUIRED = "required"
    ENUM = "enum"
    TYPE = "type"
    FORMAT = "format"
    MIN_LENGTH = "minLength"
    MAX_LENGTH = "maxLength"
    MINIMUM = "minimum"
    MAXIMUM = "maximum"
    PATTERN = "pattern"
    MIN_ITEMS = "minItems"
    MAX_ITEMS = "maxItems"
    UNIQUE_ITEMS = "uniqueItems"


@dataclass
class FieldConstraint:
    """A constraint on a schema field."""

    constraint_type: ConstraintType
    value: Any  # The constraint value (e.g., enum values, min/max, pattern)
    covered: bool = False
    covered_values: List[Any] = field(default_factory=list)  # For enum: values seen

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "type": self.constraint_type.value,
            "value": self.value,
            "covered": self.covered,
        }
        if self.covered_values:
            result["covered_values"] = self.covered_values
        return result


@dataclass
class FieldCoverageInfo:
    """Coverage information for a single schema field."""

    path: str  # e.g., "user.email" or "items[0].id"
    field_type: str  # string, number, integer, boolean, array, object
    is_required: bool = False
    is_covered: bool = False
    constraints: List[FieldConstraint] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "path": self.path,
            "type": self.field_type,
            "required": self.is_required,
            "covered": self.is_covered,
            "constraints": [c.to_dict() for c in self.constraints],
        }


@dataclass
class SchemaCoverageInfo:
    """Coverage information for an entire schema."""

    schema_path: str
    fields: Dict[str, FieldCoverageInfo] = field(default_factory=dict)
    total_fields: int = 0
    covered_fields: int = 0
    total_required: int = 0
    covered_required: int = 0
    total_enum_values: int = 0
    covered_enum_values: int = 0

    @property
    def field_coverage_pct(self) -> float:
        """Calculate field coverage percentage."""
        if self.total_fields == 0:
            return 100.0
        return round(self.covered_fields / self.total_fields * 100, 1)

    @property
    def required_coverage_pct(self) -> float:
        """Calculate required field coverage percentage."""
        if self.total_required == 0:
            return 100.0
        return round(self.covered_required / self.total_required * 100, 1)

    @property
    def enum_coverage_pct(self) -> float:
        """Calculate enum value coverage percentage."""
        if self.total_enum_values == 0:
            return 100.0
        return round(self.covered_enum_values / self.total_enum_values * 100, 1)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "schema_path": self.schema_path,
            "total_fields": self.total_fields,
            "covered_fields": self.covered_fields,
            "field_coverage_pct": self.field_coverage_pct,
            "total_required": self.total_required,
            "covered_required": self.covered_required,
            "required_coverage_pct": self.required_coverage_pct,
            "total_enum_values": self.total_enum_values,
            "covered_enum_values": self.covered_enum_values,
            "enum_coverage_pct": self.enum_coverage_pct,
            "fields": {k: v.to_dict() for k, v in self.fields.items()},
        }


@dataclass
class SchemaValidationResult:
    """Result of validating data against a JSON schema."""

    status: SchemaValidationStatus
    errors: List[str] = field(default_factory=list)
    schema_path: Optional[str] = None
    field_coverage: Optional[SchemaCoverageInfo] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {"status": self.status.value}
        if self.errors:
            result["errors"] = self.errors
        if self.schema_path:
            result["schema_path"] = self.schema_path
        if self.field_coverage:
            result["field_coverage"] = self.field_coverage.to_dict()
        return result


class OpenAPISchemaValidator:
    """Validator for JSON data against OpenAPI schemas.

    Handles schema resolution and validation using the OpenAPI spec as the
    base for resolving $ref references.
    """

    def __init__(self, spec: Dict[str, Any]) -> None:
        """Initialize the validator with an OpenAPI spec.

        Args:
            spec: The full OpenAPI specification dictionary.
        """
        self._spec = spec
        self._resolver = RefResolver.from_schema(spec)

    def validate(
        self,
        data: Any,
        schema: Optional[Dict[str, Any]],
        schema_path: Optional[str] = None,
    ) -> SchemaValidationResult:
        """Validate data against a JSON schema.

        Args:
            data: The data to validate (usually a parsed JSON body).
            schema: The JSON schema to validate against.
            schema_path: Optional path to the schema for reference.

        Returns:
            A SchemaValidationResult with the validation outcome.
        """
        if schema is None:
            return SchemaValidationResult(
                status=SchemaValidationStatus.NO_SCHEMA,
                schema_path=schema_path,
            )

        if data is None:
            return SchemaValidationResult(
                status=SchemaValidationStatus.NO_BODY,
                schema_path=schema_path,
            )

        try:
            # Resolve $ref if the schema is a reference
            resolved_schema = self._resolve_schema(schema)

            # Create validator with resolver for reference resolution
            validator = Draft7Validator(
                resolved_schema,
                resolver=self._resolver,
            )

            # Collect all validation errors
            errors = list(validator.iter_errors(data))

            if errors:
                error_messages = [
                    self._format_error(error) for error in errors[:10]  # Limit to 10 errors
                ]
                return SchemaValidationResult(
                    status=SchemaValidationStatus.INVALID,
                    errors=error_messages,
                    schema_path=schema_path,
                )

            return SchemaValidationResult(
                status=SchemaValidationStatus.VALID,
                schema_path=schema_path,
            )

        except SchemaError as e:
            return SchemaValidationResult(
                status=SchemaValidationStatus.VALIDATION_ERROR,
                errors=[f"Invalid schema: {e.message}"],
                schema_path=schema_path,
            )
        except Exception as e:
            return SchemaValidationResult(
                status=SchemaValidationStatus.VALIDATION_ERROR,
                errors=[f"Validation error: {str(e)}"],
                schema_path=schema_path,
            )

    def _resolve_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve a schema that may be a $ref.

        Args:
            schema: The schema or reference to resolve.

        Returns:
            The resolved schema dictionary.
        """
        if "$ref" in schema:
            ref = schema["$ref"]
            resolved_url, resolved_schema = self._resolver.resolve(ref)
            return resolved_schema
        return schema

    def _format_error(self, error: ValidationError) -> str:
        """Format a validation error into a readable message.

        Args:
            error: The validation error.

        Returns:
            A formatted error message.
        """
        path = ".".join(str(p) for p in error.absolute_path) if error.absolute_path else "root"
        return f"{path}: {error.message}"

    def validate_request_body(
        self,
        path: str,
        method: str,
        body: Any,
        content_type: Optional[str] = None,
    ) -> SchemaValidationResult:
        """Validate a request body against the OpenAPI spec.

        Args:
            path: The OpenAPI path template (e.g., "/users/{userId}").
            method: The HTTP method (e.g., "POST").
            body: The request body data.
            content_type: The Content-Type of the request.

        Returns:
            A SchemaValidationResult with the validation outcome.
        """
        schema = self._get_request_body_schema(path, method.lower(), content_type)
        schema_path = f"{path}.{method.upper()}.requestBody"
        return self.validate(body, schema, schema_path)

    def validate_response_body(
        self,
        path: str,
        method: str,
        status_code: int,
        body: Any,
        content_type: Optional[str] = None,
    ) -> SchemaValidationResult:
        """Validate a response body against the OpenAPI spec.

        Args:
            path: The OpenAPI path template (e.g., "/users/{userId}").
            method: The HTTP method (e.g., "GET").
            status_code: The HTTP response status code.
            body: The response body data.
            content_type: The Content-Type of the response.

        Returns:
            A SchemaValidationResult with the validation outcome.
        """
        schema = self._get_response_schema(path, method.lower(), str(status_code), content_type)
        schema_path = f"{path}.{method.upper()}.responses.{status_code}"
        return self.validate(body, schema, schema_path)

    def _get_request_body_schema(
        self,
        path: str,
        method: str,
        content_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get the request body schema for an operation.

        Args:
            path: The OpenAPI path template.
            method: The HTTP method.
            content_type: Optional content type to match.

        Returns:
            The schema dictionary or None if not found.
        """
        paths = self._spec.get("paths", {})
        path_item = paths.get(path, {})
        operation = path_item.get(method, {})
        request_body = operation.get("requestBody", {})
        content = request_body.get("content", {})

        # Find schema based on content type or use first available
        return self._extract_schema_from_content(content, content_type)

    def _get_response_schema(
        self,
        path: str,
        method: str,
        status_code: str,
        content_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get the response schema for an operation and status code.

        Args:
            path: The OpenAPI path template.
            method: The HTTP method.
            status_code: The response status code.
            content_type: Optional content type to match.

        Returns:
            The schema dictionary or None if not found.
        """
        paths = self._spec.get("paths", {})
        path_item = paths.get(path, {})
        operation = path_item.get(method, {})
        responses = operation.get("responses", {})

        # Try exact status code first, then default
        response = responses.get(status_code, responses.get("default", {}))
        content = response.get("content", {})

        # Handle OpenAPI 2.x schema directly on response
        if "schema" in response and not content:
            return response["schema"]

        return self._extract_schema_from_content(content, content_type)

    def _extract_schema_from_content(
        self,
        content: Dict[str, Any],
        content_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Extract schema from content object.

        Args:
            content: The content object from OpenAPI spec.
            content_type: Optional content type to match.

        Returns:
            The schema dictionary or None if not found.
        """
        if not content:
            return None

        # Try to match specific content type
        if content_type:
            # Normalize content type (remove charset, etc.)
            base_type = content_type.split(";")[0].strip().lower()

            # Try exact match first
            if base_type in content:
                return content[base_type].get("schema")

            # Try matching with wildcard
            for ct, media in content.items():
                if ct.lower() == base_type or ct == "*/*":
                    return media.get("schema")

        # Default to application/json or first available
        if "application/json" in content:
            return content["application/json"].get("schema")

        # Return first available schema
        for media in content.values():
            if "schema" in media:
                return media["schema"]

        return None

    def has_request_body_schema(self, path: str, method: str) -> bool:
        """Check if an operation has a request body schema defined.

        Args:
            path: The OpenAPI path template.
            method: The HTTP method.

        Returns:
            True if a request body schema is defined.
        """
        return self._get_request_body_schema(path, method.lower()) is not None

    def has_response_schema(self, path: str, method: str, status_code: str) -> bool:
        """Check if a response has a schema defined.

        Args:
            path: The OpenAPI path template.
            method: The HTTP method.
            status_code: The response status code.

        Returns:
            True if a response schema is defined.
        """
        return self._get_response_schema(path, method.lower(), status_code) is not None

    def extract_schema_fields(
        self,
        schema: Dict[str, Any],
        schema_path: str,
    ) -> SchemaCoverageInfo:
        """Extract field information from a schema for coverage tracking.

        Args:
            schema: The JSON schema to analyze.
            schema_path: Path identifier for this schema.

        Returns:
            SchemaCoverageInfo with all field details.
        """
        coverage_info = SchemaCoverageInfo(schema_path=schema_path)

        # Resolve $ref if needed
        resolved = self._resolve_schema(schema)
        self._extract_fields_recursive(resolved, "", coverage_info, set())

        return coverage_info

    def _extract_fields_recursive(
        self,
        schema: Dict[str, Any],
        prefix: str,
        coverage_info: SchemaCoverageInfo,
        required_fields: Set[str],
    ) -> None:
        """Recursively extract fields from a schema.

        Args:
            schema: The schema to extract from.
            prefix: Path prefix for nested fields.
            coverage_info: Coverage info to populate.
            required_fields: Set of required field names at this level.
        """
        schema = self._resolve_schema(schema)
        schema_type = schema.get("type", "object")

        # Handle object properties
        if schema_type == "object" or "properties" in schema:
            required = set(schema.get("required", []))
            properties = schema.get("properties", {})

            for prop_name, prop_schema in properties.items():
                field_path = f"{prefix}.{prop_name}" if prefix else prop_name
                prop_schema = self._resolve_schema(prop_schema)
                prop_type = prop_schema.get("type", "any")

                is_required = prop_name in required
                field_info = FieldCoverageInfo(
                    path=field_path,
                    field_type=prop_type,
                    is_required=is_required,
                )

                # Extract constraints
                self._extract_constraints(prop_schema, field_info)

                coverage_info.fields[field_path] = field_info
                coverage_info.total_fields += 1
                if is_required:
                    coverage_info.total_required += 1

                # Count enum values
                if prop_schema.get("enum"):
                    coverage_info.total_enum_values += len(prop_schema["enum"])

                # Recurse for nested objects
                if prop_type == "object" or "properties" in prop_schema:
                    nested_required = set(prop_schema.get("required", []))
                    self._extract_fields_recursive(
                        prop_schema, field_path, coverage_info, nested_required
                    )

                # Handle array items
                if prop_type == "array" and "items" in prop_schema:
                    items_path = f"{field_path}[]"
                    items_schema = self._resolve_schema(prop_schema["items"])
                    self._extract_fields_recursive(
                        items_schema, items_path, coverage_info, set()
                    )

        # Handle array at root level
        elif schema_type == "array" and "items" in schema:
            items_path = f"{prefix}[]" if prefix else "[]"
            items_schema = self._resolve_schema(schema["items"])
            self._extract_fields_recursive(items_schema, items_path, coverage_info, set())

    def _extract_constraints(
        self,
        schema: Dict[str, Any],
        field_info: FieldCoverageInfo,
    ) -> None:
        """Extract constraints from a schema property.

        Args:
            schema: The property schema.
            field_info: Field info to add constraints to.
        """
        # Type constraint
        if "type" in schema:
            field_info.constraints.append(
                FieldConstraint(
                    constraint_type=ConstraintType.TYPE,
                    value=schema["type"],
                )
            )

        # Enum constraint
        if "enum" in schema:
            field_info.constraints.append(
                FieldConstraint(
                    constraint_type=ConstraintType.ENUM,
                    value=schema["enum"],
                )
            )

        # Format constraint
        if "format" in schema:
            field_info.constraints.append(
                FieldConstraint(
                    constraint_type=ConstraintType.FORMAT,
                    value=schema["format"],
                )
            )

        # String constraints
        if "minLength" in schema:
            field_info.constraints.append(
                FieldConstraint(
                    constraint_type=ConstraintType.MIN_LENGTH,
                    value=schema["minLength"],
                )
            )
        if "maxLength" in schema:
            field_info.constraints.append(
                FieldConstraint(
                    constraint_type=ConstraintType.MAX_LENGTH,
                    value=schema["maxLength"],
                )
            )
        if "pattern" in schema:
            field_info.constraints.append(
                FieldConstraint(
                    constraint_type=ConstraintType.PATTERN,
                    value=schema["pattern"],
                )
            )

        # Number constraints
        if "minimum" in schema:
            field_info.constraints.append(
                FieldConstraint(
                    constraint_type=ConstraintType.MINIMUM,
                    value=schema["minimum"],
                )
            )
        if "maximum" in schema:
            field_info.constraints.append(
                FieldConstraint(
                    constraint_type=ConstraintType.MAXIMUM,
                    value=schema["maximum"],
                )
            )

        # Array constraints
        if "minItems" in schema:
            field_info.constraints.append(
                FieldConstraint(
                    constraint_type=ConstraintType.MIN_ITEMS,
                    value=schema["minItems"],
                )
            )
        if "maxItems" in schema:
            field_info.constraints.append(
                FieldConstraint(
                    constraint_type=ConstraintType.MAX_ITEMS,
                    value=schema["maxItems"],
                )
            )
        if "uniqueItems" in schema:
            field_info.constraints.append(
                FieldConstraint(
                    constraint_type=ConstraintType.UNIQUE_ITEMS,
                    value=schema["uniqueItems"],
                )
            )

    def track_field_coverage(
        self,
        data: Any,
        schema: Dict[str, Any],
        schema_path: str,
    ) -> SchemaCoverageInfo:
        """Track which fields and constraints are covered by data.

        Args:
            data: The data being validated.
            schema: The schema to track coverage for.
            schema_path: Path identifier for this schema.

        Returns:
            SchemaCoverageInfo with coverage tracking.
        """
        coverage_info = self.extract_schema_fields(schema, schema_path)

        if data is not None:
            self._track_data_coverage(data, "", coverage_info)

        return coverage_info

    def _track_data_coverage(
        self,
        data: Any,
        prefix: str,
        coverage_info: SchemaCoverageInfo,
    ) -> None:
        """Track which fields in the data are covered.

        Args:
            data: The data to track.
            prefix: Current path prefix.
            coverage_info: Coverage info to update.
        """
        if isinstance(data, dict):
            for key, value in data.items():
                field_path = f"{prefix}.{key}" if prefix else key

                if field_path in coverage_info.fields:
                    field_info = coverage_info.fields[field_path]
                    if not field_info.is_covered:
                        field_info.is_covered = True
                        coverage_info.covered_fields += 1
                        if field_info.is_required:
                            coverage_info.covered_required += 1

                    # Track enum coverage
                    for constraint in field_info.constraints:
                        if constraint.constraint_type == ConstraintType.ENUM:
                            if value in constraint.value and value not in constraint.covered_values:
                                constraint.covered_values.append(value)
                                coverage_info.covered_enum_values += 1
                            constraint.covered = len(constraint.covered_values) > 0
                        elif constraint.constraint_type == ConstraintType.TYPE:
                            # Track type coverage
                            constraint.covered = True

                # Recurse into nested objects
                if isinstance(value, dict):
                    self._track_data_coverage(value, field_path, coverage_info)
                elif isinstance(value, list):
                    for i, item in enumerate(value):
                        array_path = f"{field_path}[]"
                        self._track_data_coverage(item, array_path, coverage_info)

        elif isinstance(data, list):
            for item in data:
                array_path = f"{prefix}[]" if prefix else "[]"
                self._track_data_coverage(item, array_path, coverage_info)

    def validate_with_coverage(
        self,
        data: Any,
        schema: Optional[Dict[str, Any]],
        schema_path: Optional[str] = None,
    ) -> SchemaValidationResult:
        """Validate data and track field coverage.

        Args:
            data: The data to validate.
            schema: The JSON schema to validate against.
            schema_path: Optional path to the schema for reference.

        Returns:
            SchemaValidationResult with validation and coverage info.
        """
        # First do regular validation
        result = self.validate(data, schema, schema_path)

        # Then track coverage if we have valid inputs
        if schema is not None and data is not None:
            coverage = self.track_field_coverage(data, schema, schema_path or "")
            result.field_coverage = coverage

        return result
