"""Tests for the OpenAPI spec parser module."""

import json
import pytest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch, MagicMock

from pytest_synapse.spec_parser import OpenAPISpecParser


@pytest.fixture
def spec_path():
    """Path to the test OpenAPI spec."""
    return str(Path(__file__).parent / "fixtures" / "openapi.yaml")


@pytest.fixture
def sample_openapi_json():
    """Sample OpenAPI spec as JSON string."""
    return json.dumps({
        "openapi": "3.0.3",
        "info": {"title": "Remote API", "version": "1.0.0"},
        "paths": {
            "/items": {
                "get": {
                    "summary": "List items",
                    "responses": {"200": {"description": "OK"}}
                }
            }
        }
    })


@pytest.fixture
def sample_openapi_yaml():
    """Sample OpenAPI spec as YAML string."""
    return """
openapi: "3.0.3"
info:
  title: Remote YAML API
  version: "1.0.0"
paths:
  /products:
    get:
      summary: List products
      responses:
        "200":
          description: OK
"""


@pytest.fixture
def parser(spec_path):
    """Create a parser for the test spec."""
    return OpenAPISpecParser(spec_path)


class TestOpenAPISpecParser:
    def test_load_yaml_spec(self, parser):
        assert parser.version == "3.0.3"
        assert parser.title == "Sample API"

    def test_get_paths(self, parser):
        paths = parser.get_paths()
        assert "/users" in paths
        assert "/users/{userId}" in paths
        assert "/health" in paths

    def test_get_path_templates(self, parser):
        templates = parser.get_path_templates()
        assert len(templates) == 3
        assert "/users" in templates
        assert "/users/{userId}" in templates

    def test_get_operations_for_path(self, parser):
        operations = parser.get_operations_for_path("/users")
        assert "get" in operations
        assert "post" in operations
        assert "delete" not in operations

    def test_get_all_operations(self, parser):
        operations = parser.get_all_operations()
        # /users: GET, POST (2)
        # /users/{userId}: GET, PUT, DELETE (3)
        # /health: GET (1)
        # Total: 6 operations
        assert len(operations) == 6

    def test_get_operation(self, parser):
        operation = parser.get_operation("/users", "get")
        assert operation is not None
        assert operation["operationId"] == "listUsers"

    def test_get_operation_case_insensitive(self, parser):
        operation = parser.get_operation("/users", "GET")
        assert operation is not None

    def test_has_request_body(self, parser):
        assert parser.has_request_body("/users", "post") is True
        assert parser.has_request_body("/users", "get") is False

    def test_get_response_status_codes(self, parser):
        codes = parser.get_response_status_codes("/users", "post")
        assert "201" in codes
        assert "400" in codes

    def test_has_response_schema(self, parser):
        assert parser.has_response_schema("/users", "get", "200") is True
        assert parser.has_response_schema("/users/{userId}", "delete", "204") is False

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            OpenAPISpecParser("/nonexistent/path.yaml")

    def test_get_servers(self, parser):
        servers = parser.get_servers()
        assert len(servers) == 1
        assert servers[0]["url"] == "http://localhost:8000"

    def test_is_from_url_false_for_file(self, parser):
        assert parser.is_from_url is False
        assert parser.source_url is None


class TestOpenAPISpecParserURLLoading:
    """Tests for loading OpenAPI specs from URLs."""

    def test_is_url_detection(self):
        assert OpenAPISpecParser._is_url_path("https://example.com/openapi.json") is True
        assert OpenAPISpecParser._is_url_path("http://localhost:8080/spec.yaml") is True
        assert OpenAPISpecParser._is_url_path("/path/to/openapi.yaml") is False
        assert OpenAPISpecParser._is_url_path("./relative/path.json") is False

    def test_load_from_json_url(self, sample_openapi_json):
        mock_response = MagicMock()
        mock_response.read.return_value = sample_openapi_json.encode("utf-8")
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("pytest_synapse.spec_parser.urlopen", return_value=mock_response):
            parser = OpenAPISpecParser("https://api.example.com/openapi.json")

            assert parser.is_from_url is True
            assert parser.source_url == "https://api.example.com/openapi.json"
            assert parser.title == "Remote API"
            assert parser.version == "3.0.3"
            assert "/items" in parser.get_paths()

    def test_load_from_yaml_url(self, sample_openapi_yaml):
        mock_response = MagicMock()
        mock_response.read.return_value = sample_openapi_yaml.encode("utf-8")
        mock_response.headers = {"Content-Type": "application/yaml"}
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("pytest_synapse.spec_parser.urlopen", return_value=mock_response):
            parser = OpenAPISpecParser("https://api.example.com/openapi.yaml")

            assert parser.is_from_url is True
            assert parser.title == "Remote YAML API"
            assert "/products" in parser.get_paths()

    def test_load_from_url_with_json_extension(self, sample_openapi_json):
        """Test that URL extension is used to determine format."""
        mock_response = MagicMock()
        mock_response.read.return_value = sample_openapi_json.encode("utf-8")
        mock_response.headers = {"Content-Type": "text/plain"}  # Ambiguous content-type
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("pytest_synapse.spec_parser.urlopen", return_value=mock_response):
            parser = OpenAPISpecParser("https://api.example.com/specs/openapi.json")

            assert parser.title == "Remote API"

    def test_load_from_url_with_yaml_extension(self, sample_openapi_yaml):
        """Test that URL extension is used to determine format."""
        mock_response = MagicMock()
        mock_response.read.return_value = sample_openapi_yaml.encode("utf-8")
        mock_response.headers = {"Content-Type": "text/plain"}  # Ambiguous content-type
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("pytest_synapse.spec_parser.urlopen", return_value=mock_response):
            parser = OpenAPISpecParser("https://api.example.com/specs/openapi.yaml")

            assert parser.title == "Remote YAML API"

    def test_url_fetch_error_http_error(self):
        from urllib.error import HTTPError

        with patch("pytest_synapse.spec_parser.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = HTTPError(
                url="https://example.com/openapi.json",
                code=404,
                msg="Not Found",
                hdrs={},
                fp=None
            )

            with pytest.raises(ValueError, match="HTTP 404"):
                OpenAPISpecParser("https://example.com/openapi.json")

    def test_url_fetch_error_connection_error(self):
        from urllib.error import URLError

        with patch("pytest_synapse.spec_parser.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = URLError("Connection refused")

            with pytest.raises(ValueError, match="Failed to fetch"):
                OpenAPISpecParser("https://unreachable.example.com/openapi.json")

    def test_url_with_invalid_spec_content(self):
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"not": "openapi"}'
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("pytest_synapse.spec_parser.urlopen", return_value=mock_response):
            with pytest.raises(ValueError, match="missing 'openapi' or 'swagger' field"):
                OpenAPISpecParser("https://api.example.com/invalid.json")
