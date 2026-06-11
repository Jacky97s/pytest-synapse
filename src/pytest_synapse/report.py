"""Coverage report generation and rendering."""

import fnmatch
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pytest_synapse.coverage_engine import SynapseCoverageEngine
from pytest_synapse.types import (
    CoverageSummary,
    CoverageStatus,
    SchemaValidationStatus,
    UncoveredItem,
)


# Risk patterns - operations that are inherently higher risk
HIGH_RISK_METHODS = {"DELETE", "POST", "PUT", "PATCH"}
HIGH_RISK_PATH_PATTERNS = [
    r"/admin.*",
    r"/payment.*",
    r"/billing.*",
    r"/subscription.*",
    r"/auth.*",
    r"/user.*",
    r"/account.*",
    r".*password.*",
    r".*token.*",
    r".*secret.*",
]


@dataclass
class CoverageSuggestion:
    """A suggestion for improving coverage."""

    priority: str  # HIGH, MEDIUM, LOW
    category: str  # operation, status_code, request_body, response_schema, field
    path: str
    method: Optional[str] = None
    message: str = ""
    action: str = ""  # What test to write

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "priority": self.priority,
            "category": self.category,
            "path": self.path,
            "message": self.message,
            "action": self.action,
        }
        if self.method:
            result["method"] = self.method
        return result


@dataclass
class RiskAssessment:
    """Risk assessment for an endpoint."""

    path: str
    method: str
    risk_level: str  # HIGH, MEDIUM, LOW
    coverage_status: str
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "path": self.path,
            "method": self.method,
            "risk_level": self.risk_level,
            "coverage_status": self.coverage_status,
            "reasons": self.reasons,
        }


@dataclass
class RiskSummary:
    """Summary statistics for risk assessment."""

    total_endpoints: int
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int
    high_risk_uncovered: int
    critical_gaps: List[str] = field(default_factory=list)

    @property
    def risk_score(self) -> float:
        """Calculate overall risk score (0-100, higher = riskier)."""
        if self.total_endpoints == 0:
            return 0.0
        weighted = (self.high_risk_count * 3 + self.medium_risk_count * 2 + self.low_risk_count)
        max_possible = self.total_endpoints * 3
        return round((weighted / max_possible) * 100, 1)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_endpoints": self.total_endpoints,
            "high_risk_count": self.high_risk_count,
            "medium_risk_count": self.medium_risk_count,
            "low_risk_count": self.low_risk_count,
            "high_risk_uncovered": self.high_risk_uncovered,
            "risk_score": self.risk_score,
            "critical_gaps": self.critical_gaps,
        }


@dataclass
class CoverageReport:
    """Complete coverage report data."""

    summary: CoverageSummary
    details: Dict[str, Any]
    uncovered_items: List[UncoveredItem]
    validation_errors: Dict[str, Any]
    suggestions: List[CoverageSuggestion] = field(default_factory=list)
    risk_assessments: List[RiskAssessment] = field(default_factory=list)
    risk_summary: Optional[RiskSummary] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert the report to a dictionary."""
        result = {
            "summary": self.summary.to_dict(),
            "details": self.details,
            "uncovered_items_list": [item.to_dict() for item in self.uncovered_items],
            "validation_errors": self.validation_errors,
            "suggestions": [s.to_dict() for s in self.suggestions],
            "risk_assessments": [r.to_dict() for r in self.risk_assessments],
        }
        if self.risk_summary:
            result["risk_summary"] = self.risk_summary.to_dict()
        return result


class ReportRenderer:
    """Renders coverage reports in various formats."""

    def __init__(
        self,
        engine: SynapseCoverageEngine,
        verbosity: int = 0,
        show_suggestions: bool = False,
        show_risk: bool = False,
        focus_pattern: Optional[str] = None,
        custom_risk_paths: Optional[List[str]] = None,
        custom_risk_methods: Optional[List[str]] = None,
    ) -> None:
        """Initialize the renderer.

        Args:
            engine: The coverage engine with calculated coverage data.
            verbosity: Output verbosity level (0=summary, 1=verbose, 2=detailed, 3=full).
            show_suggestions: Whether to include coverage suggestions.
            show_risk: Whether to include risk assessment report.
            focus_pattern: Pattern to filter endpoints (e.g., "/users/*", "POST /orders").
            custom_risk_paths: Additional path patterns to consider high-risk.
            custom_risk_methods: Additional HTTP methods to consider high-risk.
        """
        self._engine = engine
        self._verbosity = verbosity
        self._show_suggestions = show_suggestions
        self._show_risk = show_risk
        self._focus_pattern = focus_pattern
        self._custom_risk_paths = custom_risk_paths or []
        self._custom_risk_methods = {m.upper() for m in (custom_risk_methods or [])}

    def generate_report(self) -> CoverageReport:
        """Generate a coverage report.

        Returns:
            A CoverageReport with all coverage data.
        """
        suggestions = self.generate_suggestions() if self._show_suggestions else []
        risk_assessments = self.generate_risk_assessments() if self._show_risk else []
        risk_summary = self.generate_risk_summary(risk_assessments) if self._show_risk else None
        return CoverageReport(
            summary=self._engine.calculate_summary(),
            details=self._engine.get_details_dict(),
            uncovered_items=self._engine.get_uncovered_items(),
            validation_errors=self._engine.get_validation_errors(),
            suggestions=suggestions,
            risk_assessments=risk_assessments,
            risk_summary=risk_summary,
        )

    def generate_risk_summary(self, assessments: List[RiskAssessment]) -> RiskSummary:
        """Generate summary statistics from risk assessments.

        Args:
            assessments: List of risk assessments.

        Returns:
            RiskSummary with statistics.
        """
        high_risk = [a for a in assessments if a.risk_level == "HIGH"]
        medium_risk = [a for a in assessments if a.risk_level == "MEDIUM"]
        low_risk = [a for a in assessments if a.risk_level == "LOW"]

        # Find high-risk endpoints that are uncovered
        high_risk_uncovered = [
            a for a in high_risk
            if a.coverage_status == CoverageStatus.UNCOVERED.value
        ]

        # Identify critical gaps (high-risk + uncovered + sensitive patterns)
        critical_gaps = []
        for a in high_risk_uncovered:
            critical_gaps.append(f"{a.method} {a.path}")

        return RiskSummary(
            total_endpoints=len(assessments),
            high_risk_count=len(high_risk),
            medium_risk_count=len(medium_risk),
            low_risk_count=len(low_risk),
            high_risk_uncovered=len(high_risk_uncovered),
            critical_gaps=critical_gaps[:10],  # Limit to top 10
        )

    def _matches_focus_pattern(self, path: str, method: Optional[str] = None) -> bool:
        """Check if an endpoint matches the focus pattern.

        Args:
            path: The endpoint path.
            method: The HTTP method (optional).

        Returns:
            True if matches focus pattern or no pattern set.
        """
        if not self._focus_pattern:
            return True

        pattern = self._focus_pattern.strip()

        # Check if pattern includes method (e.g., "POST /orders")
        if " " in pattern:
            parts = pattern.split(None, 1)
            pattern_method = parts[0].upper()
            pattern_path = parts[1] if len(parts) > 1 else "*"

            # Method must match exactly
            if method and method.upper() != pattern_method:
                return False

            pattern = pattern_path

        # Convert glob pattern to regex for path matching
        # Handle common patterns like /users/*, /admin/**, etc.
        if "*" in pattern:
            # Convert ** to match any path segments
            regex_pattern = pattern.replace("**", ".*")
            # Convert * to match single path segment (not /)
            regex_pattern = re.sub(r"(?<!\.)(\*)(?!\*)", r"[^/]*", regex_pattern)
            # Escape special characters but keep our replacements
            regex_pattern = "^" + regex_pattern + "$"
            try:
                return bool(re.match(regex_pattern, path))
            except re.error:
                # Fall back to fnmatch on regex error
                return fnmatch.fnmatch(path, pattern)
        else:
            # Exact match
            return path == pattern

    def generate_risk_assessments(self) -> List[RiskAssessment]:
        """Generate risk assessments for all endpoints.

        Returns:
            List of RiskAssessment objects sorted by risk level.
        """
        assessments: List[RiskAssessment] = []
        coverage_map = self._engine.get_coverage_map()

        # Combine default and custom risk patterns
        all_risk_methods = HIGH_RISK_METHODS | self._custom_risk_methods
        all_risk_paths = HIGH_RISK_PATH_PATTERNS + self._custom_risk_paths

        for path, path_coverage in coverage_map.items():
            for method, op_coverage in path_coverage.operations.items():
                # Skip if doesn't match focus pattern
                if not self._matches_focus_pattern(path, method):
                    continue

                reasons: List[str] = []
                risk_score = 0  # Higher = riskier

                # Check method risk
                method_upper = method.upper()
                if method_upper in all_risk_methods:
                    reasons.append(f"{method_upper} method can modify data")
                    risk_score += 2
                    if method_upper == "DELETE":
                        reasons.append("Data destruction operation")
                        risk_score += 2

                # Check path patterns for sensitive areas
                for pattern in all_risk_paths:
                    # Support both regex and glob patterns
                    try:
                        if re.match(pattern, path, re.IGNORECASE):
                            reasons.append(f"Matches sensitive path pattern: {pattern}")
                            risk_score += 2
                            break
                    except re.error:
                        # Fall back to fnmatch for glob patterns
                        if fnmatch.fnmatch(path.lower(), pattern.lower()):
                            reasons.append(f"Matches sensitive path pattern: {pattern}")
                            risk_score += 2
                            break

                # Check coverage status
                coverage_status = op_coverage.status.value
                if op_coverage.status == CoverageStatus.UNCOVERED:
                    reasons.append("No test coverage")
                    risk_score += 3
                elif op_coverage.status == CoverageStatus.PARTIALLY_COVERED:
                    reasons.append("Partial test coverage")
                    risk_score += 1

                # Check response code coverage
                uncovered_responses = []
                for status_code, resp_coverage in op_coverage.responses.items():
                    if resp_coverage.status == CoverageStatus.UNCOVERED:
                        uncovered_responses.append(status_code)

                if uncovered_responses:
                    # Error responses being untested is higher risk
                    error_codes = [c for c in uncovered_responses if c.startswith(("4", "5"))]
                    if error_codes:
                        reasons.append(f"Error responses untested: {', '.join(error_codes)}")
                        risk_score += 2
                    else:
                        reasons.append(f"Response codes untested: {', '.join(uncovered_responses)}")
                        risk_score += 1

                # Determine risk level
                if risk_score >= 5:
                    risk_level = "HIGH"
                elif risk_score >= 2:
                    risk_level = "MEDIUM"
                else:
                    risk_level = "LOW"

                assessments.append(
                    RiskAssessment(
                        path=path,
                        method=method_upper,
                        risk_level=risk_level,
                        coverage_status=coverage_status,
                        reasons=reasons,
                    )
                )

        # Sort by risk level (HIGH first, then MEDIUM, then LOW)
        risk_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        assessments.sort(key=lambda a: (risk_order.get(a.risk_level, 3), a.path, a.method))

        return assessments

    def generate_suggestions(self) -> List[CoverageSuggestion]:
        """Generate coverage improvement suggestions.

        Returns:
            List of CoverageSuggestion objects.
        """
        suggestions: List[CoverageSuggestion] = []
        coverage_map = self._engine.get_coverage_map()

        for path, path_coverage in coverage_map.items():
            for method, op_coverage in path_coverage.operations.items():
                # Skip if doesn't match focus pattern
                if not self._matches_focus_pattern(path, method):
                    continue

                # HIGH priority: Uncovered operations
                if op_coverage.status == CoverageStatus.UNCOVERED:
                    suggestions.append(
                        CoverageSuggestion(
                            priority="HIGH",
                            category="operation",
                            path=path,
                            method=method.upper(),
                            message=f"Operation {method.upper()} {path} is not covered",
                            action=f"Write a test that makes a {method.upper()} request to {path}",
                        )
                    )
                    continue

                # MEDIUM priority: Uncovered request body
                if op_coverage.request_body == CoverageStatus.UNCOVERED:
                    suggestions.append(
                        CoverageSuggestion(
                            priority="MEDIUM",
                            category="request_body",
                            path=path,
                            method=method.upper(),
                            message=f"Request body for {method.upper()} {path} is not tested",
                            action=f"Add a request body to your {method.upper()} {path} test",
                        )
                    )

                # MEDIUM priority: Uncovered response status codes
                for status_code, resp_coverage in op_coverage.responses.items():
                    if resp_coverage.status == CoverageStatus.UNCOVERED:
                        suggestions.append(
                            CoverageSuggestion(
                                priority="MEDIUM",
                                category="status_code",
                                path=path,
                                method=method.upper(),
                                message=f"Response {status_code} for {method.upper()} {path} not observed",
                                action=f"Write a test that triggers a {status_code} response from {method.upper()} {path}",
                            )
                        )

                    # LOW priority: Uncovered response schemas
                    if (
                        resp_coverage.schema is not None
                        and resp_coverage.schema.get("status") == CoverageStatus.UNCOVERED.value
                    ):
                        suggestions.append(
                            CoverageSuggestion(
                                priority="LOW",
                                category="response_schema",
                                path=path,
                                method=method.upper(),
                                message=f"Response schema for {status_code} not validated",
                                action=f"Ensure {method.upper()} {path} returns a body for {status_code}",
                            )
                        )

        # Sort by priority
        priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        suggestions.sort(key=lambda s: priority_order.get(s.priority, 3))

        return suggestions

    def render_cli_summary(self) -> str:
        """Render a CLI summary of the coverage.

        Returns:
            A formatted string for terminal output.
        """
        summary = self._engine.calculate_summary()

        lines = [
            "",
            "=" * 60,
            "OpenAPI Coverage Report",
            "=" * 60,
            "",
            f"Paths:            {summary.covered_paths}/{summary.total_paths} ({summary.path_coverage_percentage}%)",
            f"Operations:       {summary.covered_operations}/{summary.total_operations} ({summary.operation_coverage_percentage}%)",
            f"Request Bodies:   {summary.covered_request_bodies}/{summary.total_request_bodies} ({summary.request_body_coverage_percentage}%)",
            f"Response Schemas: {summary.covered_response_schemas}/{summary.total_response_schemas} ({summary.response_schema_coverage_percentage}%)",
            "",
        ]

        # Add schema validation summary
        total_req_validations = summary.total_request_body_validations
        total_resp_validations = summary.total_response_schema_validations

        if total_req_validations > 0 or total_resp_validations > 0:
            lines.append("-" * 60)
            lines.append("Schema Validation:")
            lines.append("-" * 60)

            if total_req_validations > 0:
                lines.append(
                    f"  Request Bodies:   {summary.request_body_valid_count} valid, "
                    f"{summary.request_body_invalid_count} invalid "
                    f"(of {total_req_validations} total)"
                )

            if total_resp_validations > 0:
                lines.append(
                    f"  Response Schemas: {summary.response_schema_valid_count} valid, "
                    f"{summary.response_schema_invalid_count} invalid "
                    f"(of {total_resp_validations} total)"
                )
            lines.append("")

        if summary.uncovered_items_count > 0:
            lines.append(f"Uncovered items: {summary.uncovered_items_count}")
            lines.append("")

        # Add suggestions section if enabled
        if self._show_suggestions or self._verbosity >= 3:
            suggestions = self.generate_suggestions()
            if suggestions:
                lines.append("-" * 60)
                lines.append("Coverage Suggestions:")
                lines.append("-" * 60)
                for suggestion in suggestions[:10]:  # Limit to top 10
                    priority_icon = {"HIGH": "[!]", "MEDIUM": "[*]", "LOW": "[-]"}.get(
                        suggestion.priority, "[?]"
                    )
                    lines.append(f"  {priority_icon} {suggestion.message}")
                    lines.append(f"      Action: {suggestion.action}")
                if len(suggestions) > 10:
                    lines.append(f"  ... and {len(suggestions) - 10} more suggestions")
                lines.append("")

        # Add risk assessment section if enabled
        if self._show_risk:
            lines.append(self.render_risk_report())

        return "\n".join(lines)

    def render_risk_report(self) -> str:
        """Render a risk assessment report for the API.

        Returns:
            A formatted string with risk assessment by category.
        """
        assessments = self.generate_risk_assessments()

        if not assessments:
            return ""

        lines = [
            "=" * 60,
            "API RISK ASSESSMENT",
            "=" * 60,
            "",
        ]

        # Add focus pattern notice if set
        if self._focus_pattern:
            lines.append(f"Focus: {self._focus_pattern}")
            lines.append("")

        # Group by risk level
        high_risk = [a for a in assessments if a.risk_level == "HIGH"]
        medium_risk = [a for a in assessments if a.risk_level == "MEDIUM"]
        low_risk = [a for a in assessments if a.risk_level == "LOW"]

        # HIGH RISK section
        if high_risk:
            lines.append("[!] HIGH RISK (Untested + Critical):")
            lines.append("-" * 40)
            for assessment in high_risk:
                lines.append(f"  {assessment.method} {assessment.path}")
                lines.append(f"    Coverage: {assessment.coverage_status}")
                for reason in assessment.reasons:
                    lines.append(f"    - {reason}")
            lines.append("")

        # MEDIUM RISK section
        if medium_risk:
            lines.append("[*] MEDIUM RISK (Partial coverage or sensitive):")
            lines.append("-" * 40)
            for assessment in medium_risk:
                lines.append(f"  {assessment.method} {assessment.path}")
                lines.append(f"    Coverage: {assessment.coverage_status}")
                for reason in assessment.reasons:
                    lines.append(f"    - {reason}")
            lines.append("")

        # LOW RISK section
        if low_risk:
            lines.append("[-] LOW RISK (Well covered):")
            lines.append("-" * 40)
            for assessment in low_risk:
                lines.append(f"  {assessment.method} {assessment.path}")
                lines.append(f"    Coverage: {assessment.coverage_status}")
            lines.append("")

        # Summary with risk score
        risk_summary = self.generate_risk_summary(assessments)
        lines.append("-" * 60)
        lines.append("RISK SUMMARY")
        lines.append("-" * 60)
        lines.append(f"  Total Endpoints:     {risk_summary.total_endpoints}")
        lines.append(f"  High Risk:           {risk_summary.high_risk_count}")
        lines.append(f"  Medium Risk:         {risk_summary.medium_risk_count}")
        lines.append(f"  Low Risk:            {risk_summary.low_risk_count}")
        lines.append(f"  Risk Score:          {risk_summary.risk_score}/100")
        lines.append("")

        if risk_summary.critical_gaps:
            lines.append("CRITICAL GAPS (High-risk + Uncovered):")
            for gap in risk_summary.critical_gaps:
                lines.append(f"  [!] {gap}")
            lines.append("")

        return "\n".join(lines)

    def render_risk_report_json(self) -> str:
        """Render risk report as JSON.

        Returns:
            JSON string with risk assessments and summary.
        """
        assessments = self.generate_risk_assessments()
        risk_summary = self.generate_risk_summary(assessments)

        report = {
            "risk_summary": risk_summary.to_dict(),
            "assessments": [a.to_dict() for a in assessments],
            "high_risk": [a.to_dict() for a in assessments if a.risk_level == "HIGH"],
            "medium_risk": [a.to_dict() for a in assessments if a.risk_level == "MEDIUM"],
            "low_risk": [a.to_dict() for a in assessments if a.risk_level == "LOW"],
        }

        return json.dumps(report, indent=2)

    def render_cli_verbose(self) -> str:
        """Render a verbose CLI report showing covered/uncovered APIs.

        Returns:
            A formatted string with API coverage status.
        """
        lines = [self.render_cli_summary()]
        lines.append("-" * 60)
        lines.append("API Coverage Status:")
        lines.append("-" * 60)
        lines.append("")

        coverage_map = self._engine.get_coverage_map()

        # Group by coverage status
        covered_ops = []
        uncovered_ops = []

        for path, path_coverage in sorted(coverage_map.items()):
            for method, op_coverage in sorted(path_coverage.operations.items()):
                op_str = f"{method.upper()} {path}"
                if op_coverage.status == CoverageStatus.COVERED:
                    covered_ops.append(op_str)
                else:
                    uncovered_ops.append(op_str)

        # Show covered APIs
        lines.append("Covered APIs:")
        if covered_ops:
            for op in covered_ops:
                lines.append(f"  [+] {op}")
        else:
            lines.append("  (none)")
        lines.append("")

        # Show uncovered APIs
        lines.append("Uncovered APIs:")
        if uncovered_ops:
            for op in uncovered_ops:
                lines.append(f"  [-] {op}")
        else:
            lines.append("  (none)")
        lines.append("")

        return "\n".join(lines)

    def render_cli_detailed(self) -> str:
        """Render a detailed CLI report of the coverage.

        Returns:
            A formatted string with detailed coverage information.
        """
        lines = [self.render_cli_summary()]
        lines.append("-" * 60)
        lines.append("Detailed Coverage:")
        lines.append("-" * 60)
        lines.append("")

        coverage_map = self._engine.get_coverage_map()

        for path, path_coverage in sorted(coverage_map.items()):
            # Check if path has any coverage
            path_status = CoverageStatus.UNCOVERED
            for op in path_coverage.operations.values():
                if op.status == CoverageStatus.COVERED:
                    path_status = CoverageStatus.COVERED
                    break

            status_icon = self._get_status_icon(path_status)
            lines.append(f"{status_icon} {path}")

            for method, op_coverage in sorted(path_coverage.operations.items()):
                op_icon = self._get_status_icon(op_coverage.status)
                lines.append(f"    {op_icon} {method.upper()}")

                # Request body
                if op_coverage.request_body != CoverageStatus.NOT_APPLICABLE:
                    rb_icon = self._get_status_icon(op_coverage.request_body)
                    validation_info = ""
                    if op_coverage.request_body_coverage:
                        valid = op_coverage.request_body_coverage.valid_count
                        invalid = op_coverage.request_body_coverage.invalid_count
                        if valid > 0 or invalid > 0:
                            validation_info = f" (Valid: {valid}, Invalid: {invalid})"
                    lines.append(f"        {rb_icon} Request Body{validation_info}")

                    # Show field coverage at verbosity >= 3
                    if self._verbosity >= 3 and op_coverage.request_body_coverage:
                        lines.extend(
                            self._render_field_coverage(op_coverage.request_body_coverage)
                        )
                else:
                    lines.append("        - Request Body: N/A")

                # Responses
                lines.append("        Responses:")
                for status_code, resp_coverage in sorted(op_coverage.responses.items()):
                    resp_icon = self._get_status_icon(resp_coverage.status)
                    schema_info = ""
                    if resp_coverage.schema is not None:
                        schema_status = CoverageStatus(resp_coverage.schema.get("status", "UNCOVERED"))
                        schema_icon = self._get_status_icon(schema_status)
                        schema_info = f" (Schema: {schema_icon}"

                        # Add validation stats
                        if resp_coverage.schema_coverage:
                            valid = resp_coverage.schema_coverage.valid_count
                            invalid = resp_coverage.schema_coverage.invalid_count
                            if valid > 0 or invalid > 0:
                                schema_info += f", Valid: {valid}, Invalid: {invalid}"

                        schema_info += ")"
                    lines.append(f"          {resp_icon} {status_code}{schema_info}")

                    # Show field coverage at verbosity >= 3
                    if self._verbosity >= 3 and resp_coverage.schema_coverage:
                        lines.extend(
                            self._render_field_coverage(resp_coverage.schema_coverage, indent=12)
                        )

            lines.append("")

        # Add validation errors section
        validation_errors = self._engine.get_validation_errors()
        if validation_errors:
            lines.append("-" * 60)
            lines.append("Schema Validation Errors:")
            lines.append("-" * 60)
            for operation, errors in validation_errors.items():
                lines.append(f"\n  {operation}:")
                for error_type, error_list in errors.items():
                    lines.append(f"    {error_type}:")
                    for error in error_list:
                        for err_msg in error.get("errors", []):
                            lines.append(f"      - {err_msg}")
            lines.append("")

        # Add uncovered items list
        uncovered = self._engine.get_uncovered_items()
        if uncovered:
            lines.append("-" * 60)
            lines.append("Uncovered Items:")
            lines.append("-" * 60)
            for item in uncovered:
                if item.method:
                    lines.append(f"  - {item.method} {item.path}: {item.reason}")
                else:
                    lines.append(f"  - {item.path}: {item.reason}")

        return "\n".join(lines)

    def _render_field_coverage(
        self,
        coverage: Any,
        indent: int = 10,
    ) -> List[str]:
        """Render field-level coverage details.

        Args:
            coverage: RequestBodyCoverage or ResponseSchemaCoverage object.
            indent: Number of spaces for indentation.

        Returns:
            List of formatted strings.
        """
        lines: List[str] = []
        prefix = " " * indent

        # Check if we have field coverage info from validation results
        for result in getattr(coverage, "validation_results", []):
            if hasattr(result, "field_coverage") and result.field_coverage:
                fc = result.field_coverage
                lines.append(f"{prefix}Fields: {fc.covered_fields}/{fc.total_fields}")
                if fc.total_required > 0:
                    lines.append(
                        f"{prefix}Required: {fc.covered_required}/{fc.total_required}"
                    )
                if fc.total_enum_values > 0:
                    lines.append(
                        f"{prefix}Enum values: {fc.covered_enum_values}/{fc.total_enum_values}"
                    )

                # Show uncovered fields at highest verbosity
                if self._verbosity >= 3:
                    uncovered_fields = [
                        f for f in fc.fields.values() if not f.is_covered
                    ]
                    if uncovered_fields:
                        lines.append(f"{prefix}Uncovered fields:")
                        for field in uncovered_fields[:5]:
                            req_marker = "*" if field.is_required else ""
                            lines.append(
                                f"{prefix}  - {field.path}{req_marker} ({field.field_type})"
                            )
                        if len(uncovered_fields) > 5:
                            lines.append(
                                f"{prefix}  ... and {len(uncovered_fields) - 5} more"
                            )
                break  # Only show first result's coverage

        return lines

    def _get_status_icon(self, status: CoverageStatus) -> str:
        """Get an icon for a coverage status."""
        icons = {
            CoverageStatus.COVERED: "[+]",
            CoverageStatus.UNCOVERED: "[-]",
            CoverageStatus.PARTIALLY_COVERED: "[~]",
            CoverageStatus.NOT_APPLICABLE: "[N/A]",
        }
        return icons.get(status, "[?]")

    def _get_validation_icon(self, status: SchemaValidationStatus) -> str:
        """Get an icon for a validation status."""
        icons = {
            SchemaValidationStatus.VALID: "[V]",
            SchemaValidationStatus.INVALID: "[X]",
            SchemaValidationStatus.NO_SCHEMA: "[N/A]",
            SchemaValidationStatus.NO_BODY: "[-]",
            SchemaValidationStatus.VALIDATION_ERROR: "[!]",
        }
        return icons.get(status, "[?]")

    def render_json(self, pretty: bool = True) -> str:
        """Render the coverage report as JSON.

        Args:
            pretty: Whether to format the JSON with indentation.

        Returns:
            A JSON string of the coverage report.
        """
        report = self.generate_report()
        if pretty:
            return json.dumps(report.to_dict(), indent=2)
        return json.dumps(report.to_dict())

    def render_csv(self) -> str:
        """Render the coverage report as CSV.

        Returns:
            A CSV string of the coverage report.
        """
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow([
            "Path",
            "Method",
            "Operation Status",
            "Request Body Status",
            "Request Valid",
            "Request Invalid",
            "Status Code",
            "Response Status",
            "Schema Status",
            "Response Valid",
            "Response Invalid",
        ])

        coverage_map = self._engine.get_coverage_map()

        for path, path_coverage in sorted(coverage_map.items()):
            for method, op_coverage in sorted(path_coverage.operations.items()):
                # Get request body info
                rb_status = op_coverage.request_body.value
                rb_valid = 0
                rb_invalid = 0
                if op_coverage.request_body_coverage:
                    rb_valid = op_coverage.request_body_coverage.valid_count
                    rb_invalid = op_coverage.request_body_coverage.invalid_count

                # Write a row for each response status code
                if op_coverage.responses:
                    for status_code, resp_coverage in sorted(op_coverage.responses.items()):
                        resp_status = resp_coverage.status.value
                        schema_status = ""
                        resp_valid = 0
                        resp_invalid = 0

                        if resp_coverage.schema is not None:
                            schema_status = resp_coverage.schema.get("status", "UNCOVERED")
                        if resp_coverage.schema_coverage:
                            resp_valid = resp_coverage.schema_coverage.valid_count
                            resp_invalid = resp_coverage.schema_coverage.invalid_count

                        writer.writerow([
                            path,
                            method.upper(),
                            op_coverage.status.value,
                            rb_status,
                            rb_valid,
                            rb_invalid,
                            status_code,
                            resp_status,
                            schema_status,
                            resp_valid,
                            resp_invalid,
                        ])
                else:
                    # No responses defined, write single row
                    writer.writerow([
                        path,
                        method.upper(),
                        op_coverage.status.value,
                        rb_status,
                        rb_valid,
                        rb_invalid,
                        "",
                        "",
                        "",
                        0,
                        0,
                    ])

        return output.getvalue()

    def render_html(self) -> str:
        """Render the coverage report as HTML.

        Returns:
            An HTML string of the coverage report.
        """
        summary = self._engine.calculate_summary()
        coverage_map = self._engine.get_coverage_map()
        suggestions = self.generate_suggestions() if self._show_suggestions else []

        html_parts = [
            "<!DOCTYPE html>",
            "<html lang=\"en\">",
            "<head>",
            "  <meta charset=\"UTF-8\">",
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">",
            "  <title>OpenAPI Coverage Report</title>",
            "  <style>",
            "    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }",
            "    .container { max-width: 1200px; margin: 0 auto; }",
            "    h1 { color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }",
            "    h2 { color: #555; margin-top: 30px; }",
            "    .summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }",
            "    .summary-card { background: white; border-radius: 8px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }",
            "    .summary-card h3 { margin: 0 0 10px 0; color: #666; font-size: 14px; text-transform: uppercase; }",
            "    .summary-card .value { font-size: 28px; font-weight: bold; color: #333; }",
            "    .summary-card .percentage { color: #4CAF50; font-size: 16px; }",
            "    .covered { color: #4CAF50; }",
            "    .uncovered { color: #f44336; }",
            "    .partial { color: #ff9800; }",
            "    table { width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin: 20px 0; }",
            "    th, td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #eee; }",
            "    th { background: #333; color: white; font-weight: 500; }",
            "    tr:hover { background: #f9f9f9; }",
            "    .status-badge { display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: 500; }",
            "    .status-covered { background: #e8f5e9; color: #2e7d32; }",
            "    .status-uncovered { background: #ffebee; color: #c62828; }",
            "    .status-partial { background: #fff3e0; color: #ef6c00; }",
            "    .status-na { background: #f5f5f5; color: #757575; }",
            "    .suggestion { background: white; border-left: 4px solid #ff9800; padding: 15px; margin: 10px 0; border-radius: 0 8px 8px 0; }",
            "    .suggestion.high { border-color: #f44336; }",
            "    .suggestion.medium { border-color: #ff9800; }",
            "    .suggestion.low { border-color: #2196F3; }",
            "    .suggestion-priority { font-size: 12px; font-weight: bold; text-transform: uppercase; }",
            "    .suggestion-message { margin: 5px 0; font-weight: 500; }",
            "    .suggestion-action { color: #666; font-size: 14px; }",
            "    .risk-section { margin-top: 30px; }",
            "    .risk-summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin: 20px 0; }",
            "    .risk-card { background: white; border-radius: 8px; padding: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; }",
            "    .risk-card.high { border-top: 4px solid #f44336; }",
            "    .risk-card.medium { border-top: 4px solid #ff9800; }",
            "    .risk-card.low { border-top: 4px solid #4CAF50; }",
            "    .risk-card.score { border-top: 4px solid #2196F3; }",
            "    .risk-card .label { font-size: 12px; color: #666; text-transform: uppercase; margin-bottom: 5px; }",
            "    .risk-card .value { font-size: 24px; font-weight: bold; }",
            "    .risk-card.high .value { color: #f44336; }",
            "    .risk-card.medium .value { color: #ff9800; }",
            "    .risk-card.low .value { color: #4CAF50; }",
            "    .risk-card.score .value { color: #2196F3; }",
            "    .risk-item { background: white; border-radius: 8px; padding: 15px; margin: 10px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }",
            "    .risk-item.high { border-left: 4px solid #f44336; }",
            "    .risk-item.medium { border-left: 4px solid #ff9800; }",
            "    .risk-item.low { border-left: 4px solid #4CAF50; }",
            "    .risk-item-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }",
            "    .risk-item-endpoint { font-family: monospace; font-weight: bold; }",
            "    .risk-badge { display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }",
            "    .risk-badge.high { background: #ffebee; color: #c62828; }",
            "    .risk-badge.medium { background: #fff3e0; color: #ef6c00; }",
            "    .risk-badge.low { background: #e8f5e9; color: #2e7d32; }",
            "    .risk-reasons { font-size: 13px; color: #666; }",
            "    .risk-reasons li { margin: 3px 0; }",
            "    .critical-gaps { background: #ffebee; border-radius: 8px; padding: 15px; margin: 20px 0; }",
            "    .critical-gaps h4 { color: #c62828; margin: 0 0 10px 0; }",
            "    .critical-gaps ul { margin: 0; padding-left: 20px; }",
            "    .critical-gaps li { color: #c62828; font-family: monospace; margin: 5px 0; }",
            "  </style>",
            "</head>",
            "<body>",
            "  <div class=\"container\">",
            "    <h1>OpenAPI Coverage Report</h1>",
            "",
            "    <div class=\"summary-grid\">",
            f"      <div class=\"summary-card\">",
            f"        <h3>Paths</h3>",
            f"        <div class=\"value\">{summary.covered_paths}/{summary.total_paths}</div>",
            f"        <div class=\"percentage\">{summary.path_coverage_percentage}%</div>",
            f"      </div>",
            f"      <div class=\"summary-card\">",
            f"        <h3>Operations</h3>",
            f"        <div class=\"value\">{summary.covered_operations}/{summary.total_operations}</div>",
            f"        <div class=\"percentage\">{summary.operation_coverage_percentage}%</div>",
            f"      </div>",
            f"      <div class=\"summary-card\">",
            f"        <h3>Request Bodies</h3>",
            f"        <div class=\"value\">{summary.covered_request_bodies}/{summary.total_request_bodies}</div>",
            f"        <div class=\"percentage\">{summary.request_body_coverage_percentage}%</div>",
            f"      </div>",
            f"      <div class=\"summary-card\">",
            f"        <h3>Response Schemas</h3>",
            f"        <div class=\"value\">{summary.covered_response_schemas}/{summary.total_response_schemas}</div>",
            f"        <div class=\"percentage\">{summary.response_schema_coverage_percentage}%</div>",
            f"      </div>",
            "    </div>",
            "",
        ]

        # Validation summary if available
        total_req_validations = summary.total_request_body_validations
        total_resp_validations = summary.total_response_schema_validations
        if total_req_validations > 0 or total_resp_validations > 0:
            html_parts.append("    <h2>Schema Validation</h2>")
            html_parts.append("    <div class=\"summary-grid\">")
            if total_req_validations > 0:
                html_parts.append(f"      <div class=\"summary-card\">")
                html_parts.append(f"        <h3>Request Bodies</h3>")
                html_parts.append(f"        <div class=\"value\"><span class=\"covered\">{summary.request_body_valid_count}</span> / <span class=\"uncovered\">{summary.request_body_invalid_count}</span></div>")
                html_parts.append(f"        <div>Valid / Invalid</div>")
                html_parts.append(f"      </div>")
            if total_resp_validations > 0:
                html_parts.append(f"      <div class=\"summary-card\">")
                html_parts.append(f"        <h3>Response Schemas</h3>")
                html_parts.append(f"        <div class=\"value\"><span class=\"covered\">{summary.response_schema_valid_count}</span> / <span class=\"uncovered\">{summary.response_schema_invalid_count}</span></div>")
                html_parts.append(f"        <div>Valid / Invalid</div>")
                html_parts.append(f"      </div>")
            html_parts.append("    </div>")

        # Coverage details table
        html_parts.extend([
            "",
            "    <h2>API Coverage Details</h2>",
            "    <table>",
            "      <thead>",
            "        <tr>",
            "          <th>Path</th>",
            "          <th>Method</th>",
            "          <th>Status</th>",
            "          <th>Request Body</th>",
            "          <th>Responses</th>",
            "        </tr>",
            "      </thead>",
            "      <tbody>",
        ])

        for path, path_coverage in sorted(coverage_map.items()):
            for method, op_coverage in sorted(path_coverage.operations.items()):
                status_class = self._get_html_status_class(op_coverage.status)
                rb_class = self._get_html_status_class(op_coverage.request_body)

                # Build responses string
                resp_parts = []
                for status_code, resp_coverage in sorted(op_coverage.responses.items()):
                    resp_class = self._get_html_status_class(resp_coverage.status)
                    resp_parts.append(f"<span class=\"status-badge status-{resp_class}\">{status_code}</span>")
                responses_html = " ".join(resp_parts) if resp_parts else "-"

                html_parts.extend([
                    "        <tr>",
                    f"          <td><code>{path}</code></td>",
                    f"          <td><strong>{method.upper()}</strong></td>",
                    f"          <td><span class=\"status-badge status-{status_class}\">{op_coverage.status.value}</span></td>",
                    f"          <td><span class=\"status-badge status-{rb_class}\">{op_coverage.request_body.value}</span></td>",
                    f"          <td>{responses_html}</td>",
                    "        </tr>",
                ])

        html_parts.extend([
            "      </tbody>",
            "    </table>",
        ])

        # Suggestions section
        if suggestions:
            html_parts.extend([
                "",
                "    <h2>Coverage Suggestions</h2>",
            ])
            for suggestion in suggestions[:15]:  # Limit to top 15
                priority_class = suggestion.priority.lower()
                html_parts.extend([
                    f"    <div class=\"suggestion {priority_class}\">",
                    f"      <div class=\"suggestion-priority\">{suggestion.priority}</div>",
                    f"      <div class=\"suggestion-message\">{suggestion.message}</div>",
                    f"      <div class=\"suggestion-action\">💡 {suggestion.action}</div>",
                    "    </div>",
                ])

        # Risk Assessment section (always included in HTML)
        assessments = self.generate_risk_assessments()
        if assessments:
            risk_summary = self.generate_risk_summary(assessments)
            high_risk = [a for a in assessments if a.risk_level == "HIGH"]
            medium_risk = [a for a in assessments if a.risk_level == "MEDIUM"]
            low_risk = [a for a in assessments if a.risk_level == "LOW"]

            html_parts.extend([
                "",
                "    <div class=\"risk-section\">",
                "    <h2>API Risk Assessment</h2>",
                "",
                "    <div class=\"risk-summary-grid\">",
                f"      <div class=\"risk-card score\">",
                f"        <div class=\"label\">Risk Score</div>",
                f"        <div class=\"value\">{risk_summary.risk_score}</div>",
                f"      </div>",
                f"      <div class=\"risk-card high\">",
                f"        <div class=\"label\">High Risk</div>",
                f"        <div class=\"value\">{risk_summary.high_risk_count}</div>",
                f"      </div>",
                f"      <div class=\"risk-card medium\">",
                f"        <div class=\"label\">Medium Risk</div>",
                f"        <div class=\"value\">{risk_summary.medium_risk_count}</div>",
                f"      </div>",
                f"      <div class=\"risk-card low\">",
                f"        <div class=\"label\">Low Risk</div>",
                f"        <div class=\"value\">{risk_summary.low_risk_count}</div>",
                f"      </div>",
                "    </div>",
            ])

            # Critical gaps warning
            if risk_summary.critical_gaps:
                html_parts.extend([
                    "",
                    "    <div class=\"critical-gaps\">",
                    "      <h4>⚠️ Critical Gaps (High-Risk + Uncovered)</h4>",
                    "      <ul>",
                ])
                for gap in risk_summary.critical_gaps:
                    html_parts.append(f"        <li>{gap}</li>")
                html_parts.extend([
                    "      </ul>",
                    "    </div>",
                ])

            # High risk endpoints
            if high_risk:
                html_parts.extend([
                    "",
                    "    <h3>High Risk Endpoints</h3>",
                ])
                for assessment in high_risk[:10]:
                    html_parts.extend([
                        f"    <div class=\"risk-item high\">",
                        f"      <div class=\"risk-item-header\">",
                        f"        <span class=\"risk-item-endpoint\">{assessment.method} {assessment.path}</span>",
                        f"        <span class=\"risk-badge high\">HIGH RISK</span>",
                        f"      </div>",
                        f"      <div>Coverage: <span class=\"status-badge status-{self._get_html_status_class(CoverageStatus(assessment.coverage_status))}\">{assessment.coverage_status}</span></div>",
                        f"      <ul class=\"risk-reasons\">",
                    ])
                    for reason in assessment.reasons:
                        html_parts.append(f"        <li>{reason}</li>")
                    html_parts.extend([
                        "      </ul>",
                        "    </div>",
                    ])

            # Medium risk endpoints (collapsed view)
            if medium_risk:
                html_parts.extend([
                    "",
                    "    <h3>Medium Risk Endpoints</h3>",
                ])
                for assessment in medium_risk[:10]:
                    html_parts.extend([
                        f"    <div class=\"risk-item medium\">",
                        f"      <div class=\"risk-item-header\">",
                        f"        <span class=\"risk-item-endpoint\">{assessment.method} {assessment.path}</span>",
                        f"        <span class=\"risk-badge medium\">MEDIUM</span>",
                        f"      </div>",
                        f"      <div>Coverage: <span class=\"status-badge status-{self._get_html_status_class(CoverageStatus(assessment.coverage_status))}\">{assessment.coverage_status}</span></div>",
                        "    </div>",
                    ])

            # Low risk summary
            if low_risk:
                html_parts.extend([
                    "",
                    f"    <h3>Low Risk Endpoints ({len(low_risk)} total)</h3>",
                    f"    <p style=\"color: #666;\">These endpoints have good coverage and low risk characteristics.</p>",
                ])

            html_parts.append("    </div>")  # Close risk-section

        # Close HTML
        html_parts.extend([
            "",
            "  </div>",
            "</body>",
            "</html>",
        ])

        return "\n".join(html_parts)

    def _get_html_status_class(self, status: CoverageStatus) -> str:
        """Get CSS class for a coverage status."""
        class_map = {
            CoverageStatus.COVERED: "covered",
            CoverageStatus.UNCOVERED: "uncovered",
            CoverageStatus.PARTIALLY_COVERED: "partial",
            CoverageStatus.NOT_APPLICABLE: "na",
        }
        return class_map.get(status, "na")

    def write_json_report(self, output_path: str) -> None:
        """Write the coverage report to a JSON file.

        Args:
            output_path: The path to write the report to.
        """
        report_json = self.render_json()
        Path(output_path).write_text(report_json, encoding="utf-8")

    def write_report(
        self, output_path: Optional[str], report_format: str = "json"
    ) -> Optional[str]:
        """Write the coverage report in the specified format.

        Args:
            output_path: The path to write the report to. If None, returns the content.
            report_format: The format to use (json, csv, html, cli_summary, cli_detailed).

        Returns:
            The report content if output_path is None, otherwise None.
        """
        if report_format == "json":
            content = self.render_json()
        elif report_format == "csv":
            content = self.render_csv()
        elif report_format == "html":
            content = self.render_html()
        elif report_format == "cli_detailed":
            content = self.render_cli_detailed()
        else:  # cli_summary or default
            content = self.render_cli_summary()

        if output_path:
            Path(output_path).write_text(content, encoding="utf-8")
            return None
        return content
