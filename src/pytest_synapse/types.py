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
class ResponseCoverage:
    """Coverage info for a specific response status code."""

    status: CoverageStatus = CoverageStatus.UNCOVERED
    schema: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {"status": self.status.value}
        if self.schema is not None:
            result["schema"] = {"status": self.schema.get("status", CoverageStatus.UNCOVERED.value)}
        return result


@dataclass
class OperationCoverage:
    """Coverage info for an OpenAPI operation (path + method)."""

    status: CoverageStatus = CoverageStatus.UNCOVERED
    request_body: CoverageStatus = CoverageStatus.NOT_APPLICABLE
    responses: Dict[str, ResponseCoverage] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "request_body": {"status": self.request_body.value},
            "responses": {
                code: resp.to_dict() for code, resp in self.responses.items()
            },
        }


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
        }
