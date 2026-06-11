"""pytest-synapse: OpenAPI contract test coverage for pytest."""

__version__ = "1.0.1"

from pytest_synapse.types import (
    CapturedTrafficEvent,
    HttpRequest,
    HttpResponse,
    CoverageStatus,
    SchemaValidationStatus,
    SchemaValidationResult,
    RequestBodyCoverage,
    ResponseSchemaCoverage,
)
from pytest_synapse.flow_logger import SynapseFlowLogger
from pytest_synapse.spec_parser import OpenAPISpecParser
from pytest_synapse.coverage_engine import SynapseCoverageEngine
from pytest_synapse.report import ReportRenderer, CoverageReport, CoverageSuggestion
from pytest_synapse.schema_validator import (
    OpenAPISchemaValidator,
    ConstraintType,
    FieldConstraint,
    FieldCoverageInfo,
    SchemaCoverageInfo,
)

__all__ = [
    "__version__",
    "CapturedTrafficEvent",
    "HttpRequest",
    "HttpResponse",
    "CoverageStatus",
    "SchemaValidationStatus",
    "SchemaValidationResult",
    "RequestBodyCoverage",
    "ResponseSchemaCoverage",
    "SynapseFlowLogger",
    "OpenAPISpecParser",
    "SynapseCoverageEngine",
    "ReportRenderer",
    "CoverageReport",
    "CoverageSuggestion",
    "OpenAPISchemaValidator",
    "ConstraintType",
    "FieldConstraint",
    "FieldCoverageInfo",
    "SchemaCoverageInfo",
]
