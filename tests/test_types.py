"""Tests for the types module."""

from pytest_synapse.types import (
    CapturedTrafficEvent,
    CoverageStatus,
    CoverageSummary,
    HttpRequest,
    HttpResponse,
    OperationCoverage,
    PathCoverage,
    ResponseCoverage,
    UncoveredItem,
)


class TestHttpRequest:
    def test_full_url_without_query(self):
        request = HttpRequest(method="GET", path="/users")
        assert request.full_url == "/users"

    def test_full_url_with_query(self):
        request = HttpRequest(
            method="GET",
            path="/users",
            query={"page": ["1"], "limit": ["10"]},
        )
        assert "page=1" in request.full_url
        assert "limit=10" in request.full_url


class TestCoverageSummary:
    def test_path_coverage_percentage(self):
        summary = CoverageSummary(total_paths=10, covered_paths=6)
        assert summary.path_coverage_percentage == 60.0

    def test_path_coverage_percentage_zero_total(self):
        summary = CoverageSummary(total_paths=0, covered_paths=0)
        assert summary.path_coverage_percentage == 100.0

    def test_to_dict(self):
        summary = CoverageSummary(
            total_paths=5,
            covered_paths=3,
            total_operations=8,
            covered_operations=5,
        )
        result = summary.to_dict()
        assert result["total_paths"] == 5
        assert result["covered_paths"] == 3
        assert result["path_coverage_percentage"] == 60.0


class TestOperationCoverage:
    def test_to_dict(self):
        op_coverage = OperationCoverage(
            status=CoverageStatus.COVERED,
            request_body=CoverageStatus.NOT_APPLICABLE,
            responses={
                "200": ResponseCoverage(
                    status=CoverageStatus.COVERED,
                    schema={"status": "COVERED"},
                )
            },
        )
        result = op_coverage.to_dict()
        assert result["status"] == "COVERED"
        assert result["request_body"]["status"] == "NOT_APPLICABLE"
        assert result["responses"]["200"]["status"] == "COVERED"


class TestUncoveredItem:
    def test_to_dict_with_method(self):
        item = UncoveredItem(
            item_type="path_method",
            path="/users",
            method="GET",
            reason="No traffic",
        )
        result = item.to_dict()
        assert result["type"] == "path_method"
        assert result["path"] == "/users"
        assert result["method"] == "GET"

    def test_to_dict_without_method(self):
        item = UncoveredItem(item_type="path", path="/users")
        result = item.to_dict()
        assert "method" not in result
