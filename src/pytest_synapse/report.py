"""Coverage report generation and rendering."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from pytest_synapse.coverage_engine import SynapseCoverageEngine
from pytest_synapse.types import CoverageSummary, CoverageStatus, UncoveredItem


@dataclass
class CoverageReport:
    """Complete coverage report data."""

    summary: CoverageSummary
    details: Dict[str, Any]
    uncovered_items: List[UncoveredItem]

    def to_dict(self) -> Dict[str, Any]:
        """Convert the report to a dictionary."""
        return {
            "summary": self.summary.to_dict(),
            "details": self.details,
            "uncovered_items_list": [item.to_dict() for item in self.uncovered_items],
        }


class ReportRenderer:
    """Renders coverage reports in various formats."""

    def __init__(self, engine: SynapseCoverageEngine) -> None:
        """Initialize the renderer.

        Args:
            engine: The coverage engine with calculated coverage data.
        """
        self._engine = engine

    def generate_report(self) -> CoverageReport:
        """Generate a coverage report.

        Returns:
            A CoverageReport with all coverage data.
        """
        return CoverageReport(
            summary=self._engine.calculate_summary(),
            details=self._engine.get_details_dict(),
            uncovered_items=self._engine.get_uncovered_items(),
        )

    def render_cli_summary(self) -> str:
        """Render a CLI summary of the coverage.

        Returns:
            A formatted string for terminal output.
        """
        summary = self._engine.calculate_summary()

        lines = [
            "",
            "=" * 50,
            "OpenAPI Coverage Report",
            "=" * 50,
            "",
            f"Paths:            {summary.covered_paths}/{summary.total_paths} ({summary.path_coverage_percentage}%)",
            f"Operations:       {summary.covered_operations}/{summary.total_operations} ({summary.operation_coverage_percentage}%)",
            f"Request Bodies:   {summary.covered_request_bodies}/{summary.total_request_bodies} ({summary.request_body_coverage_percentage}%)",
            f"Response Schemas: {summary.covered_response_schemas}/{summary.total_response_schemas} ({summary.response_schema_coverage_percentage}%)",
            "",
        ]

        if summary.uncovered_items_count > 0:
            lines.append(f"Uncovered items: {summary.uncovered_items_count}")
            lines.append("")

        return "\n".join(lines)

    def render_cli_detailed(self) -> str:
        """Render a detailed CLI report of the coverage.

        Returns:
            A formatted string with detailed coverage information.
        """
        lines = [self.render_cli_summary()]
        lines.append("-" * 50)
        lines.append("Detailed Coverage:")
        lines.append("-" * 50)
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
                    lines.append(f"        {rb_icon} Request Body")
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
                        schema_info = f" (Schema: {schema_icon})"
                    lines.append(f"          {resp_icon} {status_code}{schema_info}")

            lines.append("")

        # Add uncovered items list
        uncovered = self._engine.get_uncovered_items()
        if uncovered:
            lines.append("-" * 50)
            lines.append("Uncovered Items:")
            lines.append("-" * 50)
            for item in uncovered:
                if item.method:
                    lines.append(f"  - {item.method} {item.path}: {item.reason}")
                else:
                    lines.append(f"  - {item.path}: {item.reason}")

        return "\n".join(lines)

    def _get_status_icon(self, status: CoverageStatus) -> str:
        """Get an icon for a coverage status."""
        icons = {
            CoverageStatus.COVERED: "[+]",
            CoverageStatus.UNCOVERED: "[-]",
            CoverageStatus.PARTIALLY_COVERED: "[~]",
            CoverageStatus.NOT_APPLICABLE: "[N/A]",
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
            report_format: The format to use (json, cli_summary, cli_detailed).

        Returns:
            The report content if output_path is None, otherwise None.
        """
        if report_format == "json":
            content = self.render_json()
        elif report_format == "cli_detailed":
            content = self.render_cli_detailed()
        else:  # cli_summary or default
            content = self.render_cli_summary()

        if output_path:
            Path(output_path).write_text(content, encoding="utf-8")
            return None
        return content
