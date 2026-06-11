"""Core data types for pytest-synapse."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class CoverageStatus(str, Enum):
    """Coverage status for an element in the OpenAPI spec."""

    COVERED = "COVERED"
    UNCOVERED = "UNCOVERED"
    PARTIALLY_COVERED = "PARTIALLY_COVERED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


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
    ADDITIONAL_PROPERTIES = "additionalProperties"


@dataclass
class ConstraintCoverage:
    """Coverage tracking for a specific schema constraint."""

    constraint_type: ConstraintType
    field_path: str  # e.g., "user.email" or "items[0].id"
    expected_values: List[Any] = field(default_factory=list)  # For enum: all possible values
    covered_values: List[Any] = field(default_factory=list)  # Values actually seen
    is_covered: bool = False
    valid_count: int = 0  # Times the constraint was satisfied
    invalid_count: int = 0  # Times the constraint was violated

    @property
    def coverage_percentage(self) -> float:
        """Calculate coverage percentage for enum values."""
        if not self.expected_values:
            return 100.0 if self.is_covered else 0.0
        if len(self.expected_values) == 0:
            return 100.0
        return round(len(self.covered_values) / len(self.expected_values) * 100, 1)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "constraint_type": self.constraint_type.value,
            "field_path": self.field_path,
            "is_covered": self.is_covered,
            "valid_count": self.valid_count,
            "invalid_count": self.invalid_count,
        }
        if self.expected_values:
            result["expected_values"] = self.expected_values
            result["covered_values"] = self.covered_values
            result["coverage_percentage"] = self.coverage_percentage
        return result


@dataclass
class FieldCoverage:
    """Coverage tracking for a schema field/property."""

    field_path: str
    field_type: str  # string, number, integer, boolean, array, object
    is_required: bool = False
    is_covered: bool = False
    enum_values: Optional[List[Any]] = None
    covered_enum_values: List[Any] = field(default_factory=list)
    format_type: Optional[str] = None  # email, date-time, uri, etc.
    constraints: List[ConstraintCoverage] = field(default_factory=list)

    @property
    def enum_coverage_percentage(self) -> float:
        """Calculate enum value coverage percentage."""
        if not self.enum_values:
            return 100.0
        if len(self.enum_values) == 0:
            return 100.0
        return round(len(self.covered_enum_values) / len(self.enum_values) * 100, 1)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "field_path": self.field_path,
            "field_type": self.field_type,
            "is_required": self.is_required,
            "is_covered": self.is_covered,
        }
        if self.enum_values:
            result["enum_values"] = self.enum_values
            result["covered_enum_values"] = self.covered_enum_values
            result["enum_coverage_percentage"] = self.enum_coverage_percentage
        if self.format_type:
            result["format_type"] = self.format_type
        if self.constraints:
            result["constraints"] = [c.to_dict() for c in self.constraints]
        return result


@dataclass
class SchemaCoverage:
    """Coverage tracking for an entire schema."""

    schema_path: str  # e.g., "/users.POST.requestBody"
    fields: Dict[str, FieldCoverage] = field(default_factory=dict)
    total_fields: int = 0
    covered_fields: int = 0
    total_required_fields: int = 0
    covered_required_fields: int = 0
    total_enum_values: int = 0
    covered_enum_values: int = 0

    @property
    def field_coverage_percentage(self) -> float:
        """Calculate field coverage percentage."""
        if self.total_fields == 0:
            return 100.0
        return round(self.covered_fields / self.total_fields * 100, 1)

    @property
    def required_coverage_percentage(self) -> float:
        """Calculate required field coverage percentage."""
        if self.total_required_fields == 0:
            return 100.0
        return round(self.covered_required_fields / self.total_required_fields * 100, 1)

    @property
    def enum_coverage_percentage(self) -> float:
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
            "field_coverage_percentage": self.field_coverage_percentage,
            "total_required_fields": self.total_required_fields,
            "covered_required_fields": self.covered_required_fields,
            "required_coverage_percentage": self.required_coverage_percentage,
            "total_enum_values": self.total_enum_values,
            "covered_enum_values": self.covered_enum_values,
            "enum_coverage_percentage": self.enum_coverage_percentage,
            "fields": {k: v.to_dict() for k, v in self.fields.items()},
        }


@dataclass
class SchemaValidationResult:
    """Result of validating data against a JSON schema."""

    status: SchemaValidationStatus
    errors: List[str] = field(default_factory=list)
    schema_path: Optional[str] = None
    schema_coverage: Optional[SchemaCoverage] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {"status": self.status.value}
        if self.errors:
            result["errors"] = self.errors
        if self.schema_path:
            result["schema_path"] = self.schema_path
        if self.schema_coverage:
            result["schema_coverage"] = self.schema_coverage.to_dict()
        return result


@dataclass
class RequestBodyCoverage:
    """Coverage info for a request body including schema validation."""

    status: CoverageStatus = CoverageStatus.NOT_APPLICABLE
    valid_count: int = 0
    invalid_count: int = 0
    validation_results: List[SchemaValidationResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "status": self.status.value,
            "valid_count": self.valid_count,
            "invalid_count": self.invalid_count,
        }
        if self.validation_results:
            result["validation_results"] = [r.to_dict() for r in self.validation_results]
        return result


@dataclass
class HttpRequest:
    """Normalized HTTP request data."""

    method: str
    path: str
    query: Dict[str, List[str]] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[Any] = None
    content_type: Optional[str] = None

    @property
    def full_url(self) -> str:
        """Get the full URL path with query string."""
        if not self.query:
            return self.path
        query_str = "&".join(
            f"{k}={v}" for k, values in self.query.items() for v in values
        )
        return f"{self.path}?{query_str}"


@dataclass
class HttpResponse:
    """Normalized HTTP response data."""

    status_code: int
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[Any] = None
    content_type: Optional[str] = None


@dataclass
class CapturedTrafficEvent:
    """A captured HTTP traffic event with test context."""

    test_id: str
    request: HttpRequest
    response: HttpResponse
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ResponseSchemaCoverage:
    """Coverage info for a response body schema including validation."""

    status: CoverageStatus = CoverageStatus.UNCOVERED
    valid_count: int = 0
    invalid_count: int = 0
    validation_results: List[SchemaValidationResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "status": self.status.value,
            "valid_count": self.valid_count,
            "invalid_count": self.invalid_count,
        }
        if self.validation_results:
            result["validation_results"] = [r.to_dict() for r in self.validation_results]
        return result


@dataclass
class ResponseCoverage:
    """Coverage info for a specific response status code."""

    status: CoverageStatus = CoverageStatus.UNCOVERED
    schema: Optional[Dict[str, Any]] = None
    schema_coverage: Optional[ResponseSchemaCoverage] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {"status": self.status.value}
        if self.schema is not None:
            # Legacy format for backward compatibility
            result["schema"] = {"status": self.schema.get("status", CoverageStatus.UNCOVERED.value)}
        if self.schema_coverage is not None:
            result["schema_validation"] = self.schema_coverage.to_dict()
        return result


@dataclass
class OperationCoverage:
    """Coverage info for an OpenAPI operation (path + method)."""

    status: CoverageStatus = CoverageStatus.UNCOVERED
    request_body: CoverageStatus = CoverageStatus.NOT_APPLICABLE
    request_body_coverage: Optional[RequestBodyCoverage] = None
    responses: Dict[str, ResponseCoverage] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "status": self.status.value,
            "request_body": {"status": self.request_body.value},
            "responses": {
                code: resp.to_dict() for code, resp in self.responses.items()
            },
        }
        if self.request_body_coverage is not None:
            result["request_body_validation"] = self.request_body_coverage.to_dict()
        return result


@dataclass
class PathCoverage:
    """Coverage info for an OpenAPI path."""

    operations: Dict[str, OperationCoverage] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {method: op.to_dict() for method, op in self.operations.items()}


@dataclass
class UncoveredItem:
    """An uncovered element in the OpenAPI spec."""

    item_type: str
    path: str
    method: Optional[str] = None
    status_code: Optional[str] = None
    reason: str = "No traffic intercepted"

    def to_dict(self) -> Dict[str, Any]:
        result = {"type": self.item_type, "path": self.path, "reason": self.reason}
        if self.method:
            result["method"] = self.method
        if self.status_code:
            result["status_code"] = self.status_code
        return result


@dataclass
class CoverageSummary:
    """Summary statistics for coverage."""

    total_paths: int = 0
    covered_paths: int = 0
    total_operations: int = 0
    covered_operations: int = 0
    total_request_bodies: int = 0
    covered_request_bodies: int = 0
    total_response_schemas: int = 0
    covered_response_schemas: int = 0
    uncovered_items_count: int = 0

    # Schema validation statistics
    request_body_valid_count: int = 0
    request_body_invalid_count: int = 0
    response_schema_valid_count: int = 0
    response_schema_invalid_count: int = 0

    @property
    def path_coverage_percentage(self) -> float:
        if self.total_paths == 0:
            return 100.0
        return round(self.covered_paths / self.total_paths * 100, 1)

    @property
    def operation_coverage_percentage(self) -> float:
        if self.total_operations == 0:
            return 100.0
        return round(self.covered_operations / self.total_operations * 100, 1)

    @property
    def request_body_coverage_percentage(self) -> float:
        if self.total_request_bodies == 0:
            return 100.0
        return round(self.covered_request_bodies / self.total_request_bodies * 100, 1)

    @property
    def response_schema_coverage_percentage(self) -> float:
        if self.total_response_schemas == 0:
            return 100.0
        return round(self.covered_response_schemas / self.total_response_schemas * 100, 1)

    @property
    def total_request_body_validations(self) -> int:
        return self.request_body_valid_count + self.request_body_invalid_count

    @property
    def total_response_schema_validations(self) -> int:
        return self.response_schema_valid_count + self.response_schema_invalid_count

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_paths": self.total_paths,
            "covered_paths": self.covered_paths,
            "path_coverage_percentage": self.path_coverage_percentage,
            "total_operations": self.total_operations,
            "covered_operations": self.covered_operations,
            "operation_coverage_percentage": self.operation_coverage_percentage,
            "total_request_bodies": self.total_request_bodies,
            "covered_request_bodies": self.covered_request_bodies,
            "request_body_coverage_percentage": self.request_body_coverage_percentage,
            "total_response_schemas": self.total_response_schemas,
            "covered_response_schemas": self.covered_response_schemas,
            "response_schema_coverage_percentage": self.response_schema_coverage_percentage,
            "uncovered_items_count": self.uncovered_items_count,
            "schema_validation": {
                "request_body": {
                    "valid_count": self.request_body_valid_count,
                    "invalid_count": self.request_body_invalid_count,
                    "total": self.total_request_body_validations,
                },
                "response_schema": {
                    "valid_count": self.response_schema_valid_count,
                    "invalid_count": self.response_schema_invalid_count,
                    "total": self.total_response_schema_validations,
                },
            },
        }
