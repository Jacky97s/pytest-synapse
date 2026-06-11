"""OpenAPI specification parser."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

import yaml


class OpenAPISpecParser:
    """Parser for OpenAPI specifications.

    Loads and parses OpenAPI 3.x specifications from YAML or JSON files
    or URLs, providing easy access to paths, operations, and schemas.
    """

    HTTP_METHODS = {"get", "post", "put", "delete", "patch", "head", "options", "trace"}

    def __init__(self, spec_path: str) -> None:
        """Initialize the parser with an OpenAPI spec file or URL.

        Args:
            spec_path: Path to the OpenAPI YAML or JSON file, or a URL
                       (http:// or https://) pointing to an OpenAPI spec.

        Raises:
            FileNotFoundError: If the spec file doesn't exist.
            ValueError: If the spec file format is invalid.
            URLError: If the URL cannot be fetched.
        """
        self._spec_path_str = spec_path
        self._is_url = self._is_url_path(spec_path)
        self._spec: Dict[str, Any] = {}
        self._source_url: Optional[str] = spec_path if self._is_url else None
        self._load_spec()

    @staticmethod
    def _is_url_path(path: str) -> bool:
        """Check if the path is a URL."""
        parsed = urlparse(path)
        return parsed.scheme in ("http", "https")

    def _load_spec(self) -> None:
        """Load and parse the OpenAPI specification from file or URL."""
        if self._is_url:
            self._load_from_url()
        else:
            self._load_from_file()

        if not isinstance(self._spec, dict):
            raise ValueError("Invalid OpenAPI spec: root must be an object")

        if "openapi" not in self._spec and "swagger" not in self._spec:
            raise ValueError("Invalid OpenAPI spec: missing 'openapi' or 'swagger' field")

    def _load_from_url(self) -> None:
        """Load and parse the OpenAPI specification from a URL."""
        try:
            req = Request(
                self._spec_path_str,
                headers={"Accept": "application/json, application/yaml, text/yaml, */*"}
            )
            with urlopen(req, timeout=30) as response:
                content = response.read().decode("utf-8")
                content_type = response.headers.get("Content-Type", "")

            # Determine format from content-type or URL extension
            parsed_url = urlparse(self._spec_path_str)
            url_path = parsed_url.path.lower()

            if "json" in content_type or url_path.endswith(".json"):
                self._spec = json.loads(content)
            elif "yaml" in content_type or url_path.endswith((".yaml", ".yml")):
                self._spec = yaml.safe_load(content)
            else:
                # Try JSON first (more strict), then YAML
                try:
                    self._spec = json.loads(content)
                except json.JSONDecodeError:
                    self._spec = yaml.safe_load(content)

        except HTTPError as e:
            raise ValueError(f"Failed to fetch OpenAPI spec from URL: HTTP {e.code} - {e.reason}")
        except URLError as e:
            raise ValueError(f"Failed to fetch OpenAPI spec from URL: {e.reason}")
        except Exception as e:
            raise ValueError(f"Failed to load OpenAPI spec from URL: {e}")

    def _load_from_file(self) -> None:
        """Load and parse the OpenAPI specification from a local file."""
        spec_path = Path(self._spec_path_str)

        if not spec_path.exists():
            raise FileNotFoundError(f"OpenAPI spec not found: {spec_path}")

        content = spec_path.read_text(encoding="utf-8")

        if spec_path.suffix.lower() in (".yaml", ".yml"):
            self._spec = yaml.safe_load(content)
        elif spec_path.suffix.lower() == ".json":
            self._spec = json.loads(content)
        else:
            # Try YAML first, then JSON
            try:
                self._spec = yaml.safe_load(content)
            except yaml.YAMLError:
                self._spec = json.loads(content)

    @property
    def source_url(self) -> Optional[str]:
        """Get the source URL if spec was loaded from a URL."""
        return self._source_url

    @property
    def is_from_url(self) -> bool:
        """Check if the spec was loaded from a URL."""
        return self._is_url

    @property
    def spec(self) -> Dict[str, Any]:
        """Get the raw specification dict."""
        return self._spec

    @property
    def version(self) -> str:
        """Get the OpenAPI version."""
        return self._spec.get("openapi", self._spec.get("swagger", "unknown"))

    @property
    def version_major(self) -> Optional[int]:
        """Get the major version number (2 for Swagger 2.0, 3 for OpenAPI 3.x).

        Returns:
            The leading integer of the version string, or None if unknown.
        """
        version = self.version
        if not isinstance(version, str):
            return None
        head = version.split(".", 1)[0]
        return int(head) if head.isdigit() else None

    @property
    def title(self) -> str:
        """Get the API title."""
        info = self._spec.get("info", {})
        return info.get("title", "Untitled API")

    def get_paths(self) -> Dict[str, Any]:
        """Get all paths defined in the spec.

        Returns:
            Dictionary of path templates to path items.
        """
        return self._spec.get("paths", {})

    def get_path_templates(self) -> List[str]:
        """Get all path templates.

        Returns:
            List of path templates (e.g., ["/users", "/users/{id}"]).
        """
        return list(self.get_paths().keys())

    def get_operations_for_path(self, path: str) -> Dict[str, Any]:
        """Get all operations for a specific path.

        Args:
            path: The path template (e.g., "/users/{id}").

        Returns:
            Dictionary of HTTP methods to operation objects.
        """
        path_item = self.get_paths().get(path, {})
        return {
            method: path_item[method]
            for method in self.HTTP_METHODS
            if method in path_item
        }

    def get_all_operations(self) -> List[Tuple[str, str, Dict[str, Any]]]:
        """Get all operations in the spec.

        Returns:
            List of (path, method, operation) tuples.
        """
        operations = []
        for path, path_item in self.get_paths().items():
            for method in self.HTTP_METHODS:
                if method in path_item:
                    operations.append((path, method.upper(), path_item[method]))
        return operations

    def get_operation(self, path: str, method: str) -> Optional[Dict[str, Any]]:
        """Get a specific operation.

        Args:
            path: The path template.
            method: The HTTP method (case-insensitive).

        Returns:
            The operation object or None if not found.
        """
        return self.get_operations_for_path(path).get(method.lower())

    def has_request_body(self, path: str, method: str) -> bool:
        """Check if an operation has a request body defined.

        Args:
            path: The path template.
            method: The HTTP method.

        Returns:
            True if the operation has a request body.
        """
        operation = self.get_operation(path, method)
        if not operation:
            return False
        if self.version_major == 2:
            return self._swagger2_body_params(path, method) is not None
        return "requestBody" in operation

    def _get_parameters(self, path: str, method: str) -> List[Dict[str, Any]]:
        """Get the merged parameter list for an operation.

        Swagger 2.0 / OpenAPI parameters can be declared on the path item
        (shared across methods) or on the operation. Operation-level
        parameters take precedence over path-level ones with the same
        name/location.

        Returns:
            The merged list of parameter objects.
        """
        path_item = self.get_paths().get(path, {})
        operation = self.get_operation(path, method) or {}

        merged: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for param in path_item.get("parameters", []) + operation.get("parameters", []):
            key = (param.get("name"), param.get("in"))
            merged[key] = param
        return list(merged.values())

    def _swagger2_body_params(
        self, path: str, method: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Get the Swagger 2.0 body or formData parameters for an operation.

        Returns:
            A list with the single ``in: body`` parameter, the list of
            ``in: formData`` parameters, or None if neither is present.
        """
        params = self._get_parameters(path, method)

        body_params = [p for p in params if p.get("in") == "body"]
        if body_params:
            return body_params[:1]

        form_params = [p for p in params if p.get("in") == "formData"]
        if form_params:
            return form_params

        return None

    def get_response_status_codes(self, path: str, method: str) -> Set[str]:
        """Get all response status codes for an operation.

        Args:
            path: The path template.
            method: The HTTP method.

        Returns:
            Set of status code strings (e.g., {"200", "404"}).
        """
        operation = self.get_operation(path, method)
        if not operation:
            return set()
        responses = operation.get("responses", {})
        return set(responses.keys())

    def has_response_schema(self, path: str, method: str, status_code: str) -> bool:
        """Check if a response has a schema defined.

        Args:
            path: The path template.
            method: The HTTP method.
            status_code: The response status code.

        Returns:
            True if the response has a schema.
        """
        operation = self.get_operation(path, method)
        if not operation:
            return False

        responses = operation.get("responses", {})
        response = responses.get(status_code, responses.get("default", {}))

        # OpenAPI 3.x uses content/media-type/schema
        content = response.get("content", {})
        for media_type in content.values():
            if "schema" in media_type:
                return True

        # OpenAPI 2.x uses schema directly
        return "schema" in response

    def resolve_ref(self, ref: str) -> Dict[str, Any]:
        """Resolve a JSON reference.

        Args:
            ref: The $ref string (e.g., "#/components/schemas/User").

        Returns:
            The resolved object.
        """
        if not ref.startswith("#/"):
            raise ValueError(f"Only local references are supported: {ref}")

        parts = ref[2:].split("/")
        current = self._spec

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                raise ValueError(f"Could not resolve reference: {ref}")

        return current

    def get_servers(self) -> List[Dict[str, Any]]:
        """Get the servers defined in the spec.

        Returns:
            List of server objects.
        """
        return self._spec.get("servers", [])

    def get_base_path(self) -> str:
        """Get the base path from the first server.

        Returns:
            The base path or "/" if not defined.
        """
        servers = self.get_servers()
        if servers:
            from urllib.parse import urlparse
            url = servers[0].get("url", "/")
            parsed = urlparse(url)
            return parsed.path.rstrip("/") or "/"
        return "/"

    def get_base_paths(self) -> List[str]:
        """Get the distinct non-root base paths across all servers.

        Server URLs like "https://api.example.com/api/v2" yield "/api/v2".
        Relative server URLs are resolved against the spec URL when the
        spec was loaded from a URL.

        Returns:
            List of base paths without trailing slash (root base paths
            and paths containing server variables are omitted).
        """
        # Swagger 2.0 uses a top-level basePath instead of servers[].url
        if self.version_major == 2:
            base_path = self._spec.get("basePath", "")
            if isinstance(base_path, str):
                base_path = base_path.rstrip("/")
                if base_path and base_path != "/":
                    return [base_path]
            return []

        base_paths: List[str] = []
        for server in self.get_servers():
            url = server.get("url", "")
            if not url:
                continue
            if self._source_url:
                url = urljoin(self._source_url, url)
            path = urlparse(url).path
            if "{" in path:
                # Server variables in the path can't be stripped literally
                continue
            path = path.rstrip("/")
            if path and not path.startswith("/"):
                path = "/" + path
            if path and path not in base_paths:
                base_paths.append(path)
        return base_paths

    def get_request_body_schema(
        self, path: str, method: str, content_type: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get the request body schema for an operation.

        Args:
            path: The path template.
            method: The HTTP method.
            content_type: Optional content type to match.

        Returns:
            The schema dictionary or None if not found.
        """
        operation = self.get_operation(path, method)
        if not operation:
            return None

        if self.version_major == 2:
            return self._swagger2_request_body_schema(path, method)

        request_body = operation.get("requestBody", {})
        content = request_body.get("content", {})

        return self._extract_schema_from_content(content, content_type)

    def _swagger2_request_body_schema(
        self, path: str, method: str
    ) -> Optional[Dict[str, Any]]:
        """Build the request body schema for a Swagger 2.0 operation.

        An ``in: body`` parameter carries an explicit schema. ``in: formData``
        parameters are synthesised into a single object schema so that form
        fields get the same field-level coverage as a JSON body.

        Returns:
            The schema dictionary or None if there is no body.
        """
        params = self._swagger2_body_params(path, method)
        if not params:
            return None

        if params[0].get("in") == "body":
            return params[0].get("schema")

        # formData parameters → synthesise an object schema
        properties: Dict[str, Any] = {}
        required: List[str] = []
        for param in params:
            name = param.get("name")
            if not name:
                continue
            field_schema: Dict[str, Any] = {}
            for key in ("type", "format", "enum", "items"):
                if key in param:
                    field_schema[key] = param[key]
            properties[name] = field_schema
            if param.get("required"):
                required.append(name)

        schema: Dict[str, Any] = {"type": "object", "properties": properties}
        if required:
            schema["required"] = required
        return schema

    def get_response_schema(
        self, path: str, method: str, status_code: str, content_type: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get the response schema for an operation and status code.

        Args:
            path: The path template.
            method: The HTTP method.
            status_code: The response status code.
            content_type: Optional content type to match.

        Returns:
            The schema dictionary or None if not found.
        """
        operation = self.get_operation(path, method)
        if not operation:
            return None

        responses = operation.get("responses", {})
        response = responses.get(status_code, responses.get("default", {}))
        content = response.get("content", {})

        # Handle OpenAPI 2.x schema directly on response
        if "schema" in response and not content:
            return response["schema"]

        return self._extract_schema_from_content(content, content_type)

    def _extract_schema_from_content(
        self, content: Dict[str, Any], content_type: Optional[str] = None
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
            base_type = content_type.split(";")[0].strip().lower()
            if base_type in content:
                return content[base_type].get("schema")
            for ct, media in content.items():
                if ct.lower() == base_type or ct == "*/*":
                    return media.get("schema")

        # Default to application/json or first available
        if "application/json" in content:
            return content["application/json"].get("schema")

        for media in content.values():
            if "schema" in media:
                return media["schema"]

        return None
