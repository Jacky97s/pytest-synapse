"""Coverage engine for mapping traffic to OpenAPI specifications."""

import re
from typing import Any, Dict, List, Optional, Tuple

from werkzeug.routing import Map, Rule, RequestRedirect
from werkzeug.exceptions import MethodNotAllowed

from pytest_synapse.spec_parser import OpenAPISpecParser
from pytest_synapse.schema_validator import OpenAPISchemaValidator, SchemaValidationStatus
from pytest_synapse.types import (
    CapturedTrafficEvent,
    CoverageStatus,
    CoverageSummary,
    HttpRequest,
    OperationCoverage,
    PathCoverage,
    RequestBodyCoverage,
    ResponseCoverage,
    ResponseSchemaCoverage,
    SchemaValidationResult,
    SchemaValidationStatus as TypeSchemaValidationStatus,
    UncoveredItem,
)


class SynapseCoverageEngine:
    """Engine for calculating OpenAPI coverage from captured traffic.

    This engine matches captured HTTP traffic events to OpenAPI spec operations
    and calculates coverage metrics at multiple granularity levels.
    """

    def __init__(self, spec: OpenAPISpecParser, validate_schemas: bool = True) -> None:
        """Initialize the coverage engine.

        Args:
            spec: The parsed OpenAPI specification.
            validate_schemas: Whether to perform schema validation (default: True).
        """
        self._spec = spec
        self._validate_schemas = validate_schemas
        self._coverage_map: Dict[str, PathCoverage] = {}
        self._url_map: Optional[Map] = None
        self._base_paths: List[str] = spec.get_base_paths()
        self._schema_validator: Optional[OpenAPISchemaValidator] = None

        if validate_schemas:
            self._schema_validator = OpenAPISchemaValidator(spec.spec)

        self._initialize_coverage_map()
        self._build_url_map()

    def _initialize_coverage_map(self) -> None:
        """Initialize the coverage map from the OpenAPI spec."""
        for path, method, operation in self._spec.get_all_operations():
            if path not in self._coverage_map:
                self._coverage_map[path] = PathCoverage()

            # Determine if request body is applicable
            has_request_body = self._spec.has_request_body(path, method)
            request_body_status = (
                CoverageStatus.UNCOVERED if has_request_body else CoverageStatus.NOT_APPLICABLE
            )

            # Initialize request body coverage with validation tracking
            request_body_coverage = None
            if has_request_body:
                request_body_coverage = RequestBodyCoverage(
                    status=CoverageStatus.UNCOVERED,
                    valid_count=0,
                    invalid_count=0,
                    validation_results=[],
                )

            # Initialize response coverage for all defined status codes
            responses: Dict[str, ResponseCoverage] = {}
            for status_code in self._spec.get_response_status_codes(path, method):
                has_schema = self._spec.has_response_schema(path, method, status_code)

                # Initialize response schema coverage if schema exists
                schema_coverage = None
                if has_schema:
                    schema_coverage = ResponseSchemaCoverage(
                        status=CoverageStatus.UNCOVERED,
                        valid_count=0,
                        invalid_count=0,
                        validation_results=[],
                    )

                responses[status_code] = ResponseCoverage(
                    status=CoverageStatus.UNCOVERED,
                    schema={"status": CoverageStatus.UNCOVERED.value} if has_schema else None,
                    schema_coverage=schema_coverage,
                )

            self._coverage_map[path].operations[method] = OperationCoverage(
                status=CoverageStatus.UNCOVERED,
                request_body=request_body_status,
                request_body_coverage=request_body_coverage,
                responses=responses,
            )

    def _build_url_map(self) -> None:
        """Build a werkzeug URL map for path matching."""
        rules = []
        for path in self._spec.get_path_templates():
            # Convert OpenAPI path params {param} to werkzeug <param>
            werkzeug_path = re.sub(r"\{([^}]+)\}", r"<\1>", path)

            # Get all methods for this path
            methods = list(self._spec.get_operations_for_path(path).keys())
            methods = [m.upper() for m in methods]

            rules.append(Rule(werkzeug_path, methods=methods, endpoint=path))

        self._url_map = Map(rules)

    def match_request(self, request: HttpRequest) -> Optional[Tuple[str, str]]:
        """Match a request to an OpenAPI operation.

        The path is matched as captured first, then with each server base
        path stripped, so requests sent to servers with a path prefix
        (e.g. https://api.example.com/api/v2) still match spec path keys.

        Args:
            request: The HTTP request to match.

        Returns:
            A tuple of (path_template, method) if matched, None otherwise.
        """
        if self._url_map is None:
            return None

        adapter = self._url_map.bind("localhost")

        for path in self._candidate_paths(request.path):
            try:
                endpoint, _ = adapter.match(path, method=request.method)
                return (endpoint, request.method)
            except (RequestRedirect, MethodNotAllowed, Exception):
                continue
        return None

    def _candidate_paths(self, path: str) -> List[str]:
        """Paths to try when matching: as captured, then base-path-stripped."""
        candidates = [path]
        for base in self._base_paths:
            if path == base:
                candidates.append("/")
            elif path.startswith(base + "/"):
                candidates.append(path[len(base):])
        return candidates

    def process_events(self, events: List[CapturedTrafficEvent]) -> None:
        """Process a list of captured traffic events.

        Args:
            events: List of captured HTTP traffic events.
        """
        for event in events:
            self._process_event(event)

    def _process_event(self, event: CapturedTrafficEvent) -> None:
        """Process a single captured traffic event.

        Args:
            event: The captured HTTP traffic event.
        """
        match = self.match_request(event.request)
        if not match:
            return

        path_template, method = match

        # Get the coverage entry
        path_coverage = self._coverage_map.get(path_template)
        if not path_coverage:
            return

        op_coverage = path_coverage.operations.get(method)
        if not op_coverage:
            return

        # Mark operation as covered
        op_coverage.status = CoverageStatus.COVERED

        # Check request body coverage and validation
        self._process_request_body(op_coverage, event, path_template, method)

        # Check response status code and schema coverage
        self._process_response(op_coverage, event, path_template, method)

    def _process_request_body(
        self,
        op_coverage: OperationCoverage,
        event: CapturedTrafficEvent,
        path_template: str,
        method: str,
    ) -> None:
        """Process request body coverage and validation.

        Args:
            op_coverage: The operation coverage to update.
            event: The captured traffic event.
            path_template: The OpenAPI path template.
            method: The HTTP method.
        """
        if op_coverage.request_body == CoverageStatus.NOT_APPLICABLE:
            return

        if event.request.body is not None:
            op_coverage.request_body = CoverageStatus.COVERED

            # Perform schema validation if enabled
            if self._validate_schemas and self._schema_validator and op_coverage.request_body_coverage:
                # Extract the schema via the parser so version-specific shapes
                # (Swagger 2.0 body / formData params) flow through validation.
                schema = self._spec.get_request_body_schema(
                    path_template, method.lower(), event.request.content_type
                )
                schema_path = f"{path_template}.{method.upper()}.requestBody"

                # Use validate_with_coverage for field-level tracking
                validation_result = self._schema_validator.validate_with_coverage(
                    event.request.body,
                    schema,
                    schema_path,
                )

                # Convert to types.SchemaValidationResult
                result = SchemaValidationResult(
                    status=TypeSchemaValidationStatus(validation_result.status.value),
                    errors=validation_result.errors,
                    schema_path=validation_result.schema_path,
                )

                # Store field coverage info if available
                if validation_result.field_coverage:
                    # Store as a custom attribute for detailed reporting
                    # Using setattr to add dynamic attribute for field-level coverage
                    setattr(result, "field_coverage", validation_result.field_coverage)

                op_coverage.request_body_coverage.validation_results.append(result)
                op_coverage.request_body_coverage.status = CoverageStatus.COVERED

                if validation_result.status == SchemaValidationStatus.VALID:
                    op_coverage.request_body_coverage.valid_count += 1
                elif validation_result.status == SchemaValidationStatus.INVALID:
                    op_coverage.request_body_coverage.invalid_count += 1

    def _process_response(
        self,
        op_coverage: OperationCoverage,
        event: CapturedTrafficEvent,
        path_template: str,
        method: str,
    ) -> None:
        """Process response status code and schema coverage.

        Args:
            op_coverage: The operation coverage to update.
            event: The captured traffic event.
            path_template: The OpenAPI path template.
            method: The HTTP method.
        """
        status_code = str(event.response.status_code)

        # Check exact match first, then default
        response_coverage = op_coverage.responses.get(status_code)
        if response_coverage is None:
            response_coverage = op_coverage.responses.get("default")

        if response_coverage is not None:
            response_coverage.status = CoverageStatus.COVERED

            # Update legacy schema tracking
            if response_coverage.schema is not None and event.response.body is not None:
                response_coverage.schema["status"] = CoverageStatus.COVERED.value

            # Perform schema validation if enabled
            if (
                self._validate_schemas
                and self._schema_validator
                and response_coverage.schema_coverage
                and event.response.body is not None
            ):
                # Extract the schema via the parser (single source of truth,
                # handles 2.x schema-on-response and 3.x content/media-type).
                schema = self._spec.get_response_schema(
                    path_template, method.lower(), status_code, event.response.content_type
                )
                schema_path = f"{path_template}.{method.upper()}.responses.{status_code}"

                # Use validate_with_coverage for field-level tracking
                validation_result = self._schema_validator.validate_with_coverage(
                    event.response.body,
                    schema,
                    schema_path,
                )

                # Convert to types.SchemaValidationResult
                result = SchemaValidationResult(
                    status=TypeSchemaValidationStatus(validation_result.status.value),
                    errors=validation_result.errors,
                    schema_path=validation_result.schema_path,
                )

                # Store field coverage info if available
                if validation_result.field_coverage:
                    # Store as a custom attribute for detailed reporting
                    # Using setattr to add dynamic attribute for field-level coverage
                    setattr(result, "field_coverage", validation_result.field_coverage)

                response_coverage.schema_coverage.validation_results.append(result)
                response_coverage.schema_coverage.status = CoverageStatus.COVERED

                if validation_result.status == SchemaValidationStatus.VALID:
                    response_coverage.schema_coverage.valid_count += 1
                elif validation_result.status == SchemaValidationStatus.INVALID:
                    response_coverage.schema_coverage.invalid_count += 1

    def calculate_summary(self) -> CoverageSummary:
        """Calculate coverage summary statistics.

        Returns:
            A CoverageSummary with all coverage metrics.
        """
        summary = CoverageSummary()

        covered_paths: set = set()
        all_paths: set = set()

        for path, path_coverage in self._coverage_map.items():
            all_paths.add(path)
            path_has_coverage = False

            for method, op_coverage in path_coverage.operations.items():
                summary.total_operations += 1

                if op_coverage.status == CoverageStatus.COVERED:
                    summary.covered_operations += 1
                    path_has_coverage = True

                # Count request bodies and validation stats
                if op_coverage.request_body != CoverageStatus.NOT_APPLICABLE:
                    summary.total_request_bodies += 1
                    if op_coverage.request_body == CoverageStatus.COVERED:
                        summary.covered_request_bodies += 1

                    # Aggregate validation stats
                    if op_coverage.request_body_coverage:
                        summary.request_body_valid_count += op_coverage.request_body_coverage.valid_count
                        summary.request_body_invalid_count += op_coverage.request_body_coverage.invalid_count

                # Count response schemas and validation stats
                for status_code, resp_coverage in op_coverage.responses.items():
                    if resp_coverage.schema is not None:
                        summary.total_response_schemas += 1
                        if resp_coverage.schema.get("status") == CoverageStatus.COVERED.value:
                            summary.covered_response_schemas += 1

                    # Aggregate validation stats
                    if resp_coverage.schema_coverage:
                        summary.response_schema_valid_count += resp_coverage.schema_coverage.valid_count
                        summary.response_schema_invalid_count += resp_coverage.schema_coverage.invalid_count

            if path_has_coverage:
                covered_paths.add(path)

        summary.total_paths = len(all_paths)
        summary.covered_paths = len(covered_paths)
        summary.uncovered_items_count = self._count_uncovered_items()

        return summary

    def _count_uncovered_items(self) -> int:
        """Count the number of uncovered items."""
        count = 0
        for path, path_coverage in self._coverage_map.items():
            for method, op_coverage in path_coverage.operations.items():
                if op_coverage.status == CoverageStatus.UNCOVERED:
                    count += 1
                if op_coverage.request_body == CoverageStatus.UNCOVERED:
                    count += 1
                for status_code, resp_coverage in op_coverage.responses.items():
                    if resp_coverage.status == CoverageStatus.UNCOVERED:
                        count += 1
                    if (
                        resp_coverage.schema is not None
                        and resp_coverage.schema.get("status") == CoverageStatus.UNCOVERED.value
                    ):
                        count += 1
        return count

    def get_uncovered_items(self) -> List[UncoveredItem]:
        """Get a list of all uncovered items.

        Returns:
            List of UncoveredItem objects.
        """
        uncovered = []

        for path, path_coverage in self._coverage_map.items():
            for method, op_coverage in path_coverage.operations.items():
                if op_coverage.status == CoverageStatus.UNCOVERED:
                    uncovered.append(
                        UncoveredItem(
                            item_type="path_method",
                            path=path,
                            method=method,
                            reason="No traffic intercepted",
                        )
                    )
                    continue  # Don't list sub-items if the whole operation is uncovered

                if op_coverage.request_body == CoverageStatus.UNCOVERED:
                    uncovered.append(
                        UncoveredItem(
                            item_type="request_body",
                            path=path,
                            method=method,
                            reason="No request body observed",
                        )
                    )

                for status_code, resp_coverage in op_coverage.responses.items():
                    if resp_coverage.status == CoverageStatus.UNCOVERED:
                        uncovered.append(
                            UncoveredItem(
                                item_type="response_status_code",
                                path=path,
                                method=method,
                                status_code=status_code,
                                reason=f"No {status_code} response observed",
                            )
                        )

        return uncovered

    def get_coverage_map(self) -> Dict[str, PathCoverage]:
        """Get the full coverage map.

        Returns:
            Dictionary of path templates to PathCoverage objects.
        """
        return self._coverage_map

    def get_details_dict(self) -> Dict[str, Any]:
        """Get the coverage details as a dictionary.

        Returns:
            Dictionary suitable for JSON serialization.
        """
        return {
            path: path_cov.to_dict()
            for path, path_cov in self._coverage_map.items()
        }

    def get_validation_errors(self) -> Dict[str, Any]:
        """Get all schema validation errors across all operations.

        Returns:
            Dictionary of validation errors organized by path/method/type.
        """
        errors: Dict[str, Any] = {}

        for path, path_coverage in self._coverage_map.items():
            for method, op_coverage in path_coverage.operations.items():
                key = f"{method.upper()} {path}"
                op_errors: Dict[str, List[Dict[str, Any]]] = {}

                # Request body validation errors
                if op_coverage.request_body_coverage:
                    invalid_results = [
                        r for r in op_coverage.request_body_coverage.validation_results
                        if r.status == TypeSchemaValidationStatus.INVALID
                    ]
                    if invalid_results:
                        op_errors["request_body"] = [r.to_dict() for r in invalid_results]

                # Response schema validation errors
                for status_code, resp_coverage in op_coverage.responses.items():
                    if resp_coverage.schema_coverage:
                        invalid_results = [
                            r for r in resp_coverage.schema_coverage.validation_results
                            if r.status == TypeSchemaValidationStatus.INVALID
                        ]
                        if invalid_results:
                            op_errors[f"response_{status_code}"] = [r.to_dict() for r in invalid_results]

                if op_errors:
                    errors[key] = op_errors

        return errors
