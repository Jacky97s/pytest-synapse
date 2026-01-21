"""Coverage engine for mapping traffic to OpenAPI specifications."""

import re
from typing import Any, Dict, List, Optional, Tuple

from werkzeug.routing import Map, Rule, RequestRedirect
from werkzeug.exceptions import MethodNotAllowed

from pytest_synapse.spec_parser import OpenAPISpecParser
from pytest_synapse.types import (
    CapturedTrafficEvent,
    CoverageStatus,
    CoverageSummary,
    HttpRequest,
    OperationCoverage,
    PathCoverage,
    ResponseCoverage,
    UncoveredItem,
)


class SynapseCoverageEngine:
    """Engine for calculating OpenAPI coverage from captured traffic.

    This engine matches captured HTTP traffic events to OpenAPI spec operations
    and calculates coverage metrics at multiple granularity levels.
    """

    def __init__(self, spec: OpenAPISpecParser) -> None:
        """Initialize the coverage engine.

        Args:
            spec: The parsed OpenAPI specification.
        """
        self._spec = spec
        self._coverage_map: Dict[str, PathCoverage] = {}
        self._url_map: Optional[Map] = None
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

            # Initialize response coverage for all defined status codes
            responses: Dict[str, ResponseCoverage] = {}
            for status_code in self._spec.get_response_status_codes(path, method):
                has_schema = self._spec.has_response_schema(path, method, status_code)
                responses[status_code] = ResponseCoverage(
                    status=CoverageStatus.UNCOVERED,
                    schema={"status": CoverageStatus.UNCOVERED.value} if has_schema else None,
                )

            self._coverage_map[path].operations[method] = OperationCoverage(
                status=CoverageStatus.UNCOVERED,
                request_body=request_body_status,
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

        Args:
            request: The HTTP request to match.

        Returns:
            A tuple of (path_template, method) if matched, None otherwise.
        """
        if self._url_map is None:
            return None

        adapter = self._url_map.bind("localhost")

        try:
            endpoint, _ = adapter.match(request.path, method=request.method)
            return (endpoint, request.method)
        except (RequestRedirect, MethodNotAllowed, Exception):
            return None

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

        # Check request body coverage
        if op_coverage.request_body == CoverageStatus.UNCOVERED:
            if event.request.body is not None:
                op_coverage.request_body = CoverageStatus.COVERED

        # Check response status code and schema coverage
        status_code = str(event.response.status_code)

        # Check exact match first, then default
        response_coverage = op_coverage.responses.get(status_code)
        if response_coverage is None:
            response_coverage = op_coverage.responses.get("default")

        if response_coverage is not None:
            response_coverage.status = CoverageStatus.COVERED
            if response_coverage.schema is not None and event.response.body is not None:
                response_coverage.schema["status"] = CoverageStatus.COVERED.value

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

                # Count request bodies
                if op_coverage.request_body != CoverageStatus.NOT_APPLICABLE:
                    summary.total_request_bodies += 1
                    if op_coverage.request_body == CoverageStatus.COVERED:
                        summary.covered_request_bodies += 1

                # Count response schemas
                for status_code, resp_coverage in op_coverage.responses.items():
                    if resp_coverage.schema is not None:
                        summary.total_response_schemas += 1
                        if resp_coverage.schema.get("status") == CoverageStatus.COVERED.value:
                            summary.covered_response_schemas += 1

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
