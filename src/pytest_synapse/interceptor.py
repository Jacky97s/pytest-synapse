"""Synapse Interceptor: Transparent HTTP traffic capture via monkey-patching."""

import json
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Type
from urllib.parse import parse_qs, urlparse

from pytest_synapse.flow_logger import SynapseFlowLogger
from pytest_synapse.types import CapturedTrafficEvent, HttpRequest, HttpResponse


class InterceptionStrategy(ABC):
    """Base class for HTTP client interception strategies."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the HTTP client is available for interception."""
        ...

    @abstractmethod
    def activate(self, logger: SynapseFlowLogger) -> None:
        """Activate the interception for this client."""
        ...

    @abstractmethod
    def deactivate(self) -> None:
        """Deactivate the interception and restore original behavior."""
        ...


class RequestsInterceptionStrategy(InterceptionStrategy):
    """Interception strategy for the requests library."""

    def __init__(self) -> None:
        self._original_send: Optional[Callable[..., Any]] = None
        self._logger: Optional[SynapseFlowLogger] = None

    def is_available(self) -> bool:
        """Check if requests library is available."""
        try:
            import requests  # noqa: F401
            return True
        except ImportError:
            return False

    def activate(self, logger: SynapseFlowLogger) -> None:
        """Monkey-patch requests.Session.send to capture traffic."""
        import requests

        self._logger = logger
        self._original_send = requests.Session.send

        strategy = self

        def patched_send(
            self_session: requests.Session,
            request: requests.PreparedRequest,
            **kwargs: Any,
        ) -> requests.Response:
            # Call the original send method
            response = strategy._original_send(self_session, request, **kwargs)

            # Capture the traffic
            strategy._capture_traffic(request, response)

            return response

        requests.Session.send = patched_send

    def deactivate(self) -> None:
        """Restore the original requests.Session.send method."""
        if self._original_send is not None:
            import requests
            requests.Session.send = self._original_send
            self._original_send = None
            self._logger = None

    def _capture_traffic(
        self, request: Any, response: Any
    ) -> None:
        """Capture and normalize traffic from requests library."""
        if self._logger is None:
            return

        # Parse the request URL
        parsed = urlparse(request.url)
        path = parsed.path or "/"
        query = parse_qs(parsed.query)

        # Normalize headers to dict
        req_headers = dict(request.headers) if request.headers else {}
        resp_headers = dict(response.headers) if response.headers else {}

        # Get content type
        req_content_type = req_headers.get("Content-Type", req_headers.get("content-type"))
        resp_content_type = resp_headers.get("Content-Type", resp_headers.get("content-type"))

        # Parse request body
        req_body = None
        if request.body:
            if isinstance(request.body, bytes):
                try:
                    req_body = json.loads(request.body.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    req_body = request.body.decode("utf-8", errors="replace")
            elif isinstance(request.body, str):
                try:
                    req_body = json.loads(request.body)
                except json.JSONDecodeError:
                    req_body = request.body

        # Parse response body
        resp_body = None
        try:
            resp_body = response.json()
        except (json.JSONDecodeError, ValueError):
            if response.text:
                resp_body = response.text

        # Create normalized objects
        http_request = HttpRequest(
            method=request.method.upper(),
            path=path,
            query=query,
            headers=req_headers,
            body=req_body,
            content_type=req_content_type,
        )

        http_response = HttpResponse(
            status_code=response.status_code,
            headers=resp_headers,
            body=resp_body,
            content_type=resp_content_type,
        )

        # Create and log the event
        test_id = self._logger.get_current_test() or "unknown"
        event = CapturedTrafficEvent(
            test_id=test_id,
            request=http_request,
            response=http_response,
            timestamp=datetime.now(),
        )

        self._logger.log_event(event)


class HttpxInterceptionStrategy(InterceptionStrategy):
    """Interception strategy for the httpx library (sync mode)."""

    def __init__(self) -> None:
        self._original_handle_request: Optional[Callable[..., Any]] = None
        self._logger: Optional[SynapseFlowLogger] = None

    def is_available(self) -> bool:
        """Check if httpx library is available."""
        try:
            import httpx  # noqa: F401
            return True
        except ImportError:
            return False

    def activate(self, logger: SynapseFlowLogger) -> None:
        """Monkey-patch httpx to capture traffic."""
        import httpx

        self._logger = logger
        self._original_handle_request = httpx.HTTPTransport.handle_request

        strategy = self

        def patched_handle_request(
            self_transport: httpx.HTTPTransport,
            request: httpx.Request,
        ) -> httpx.Response:
            # Call the original method
            response = strategy._original_handle_request(self_transport, request)

            # Capture the traffic
            strategy._capture_traffic(request, response)

            return response

        httpx.HTTPTransport.handle_request = patched_handle_request

    def deactivate(self) -> None:
        """Restore the original httpx method."""
        if self._original_handle_request is not None:
            import httpx
            httpx.HTTPTransport.handle_request = self._original_handle_request
            self._original_handle_request = None
            self._logger = None

    def _capture_traffic(self, request: Any, response: Any) -> None:
        """Capture and normalize traffic from httpx library."""
        if self._logger is None:
            return

        # Parse the request URL
        path = request.url.path or "/"
        query: Dict[str, List[str]] = {}
        for key, value in request.url.params.multi_items():
            if key not in query:
                query[key] = []
            query[key].append(value)

        # Normalize headers
        req_headers = dict(request.headers)
        resp_headers = dict(response.headers)

        # Get content type
        req_content_type = req_headers.get("content-type")
        resp_content_type = resp_headers.get("content-type")

        # Parse request body
        req_body = None
        if request.content:
            try:
                req_body = json.loads(request.content.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                req_body = request.content.decode("utf-8", errors="replace")

        # Parse response body
        resp_body = None
        try:
            response.read()  # Ensure the response is fully read
            resp_body = json.loads(response.content.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            if response.content:
                resp_body = response.content.decode("utf-8", errors="replace")

        # Create normalized objects
        http_request = HttpRequest(
            method=request.method.upper(),
            path=path,
            query=query,
            headers=req_headers,
            body=req_body,
            content_type=req_content_type,
        )

        http_response = HttpResponse(
            status_code=response.status_code,
            headers=resp_headers,
            body=resp_body,
            content_type=resp_content_type,
        )

        # Create and log the event
        test_id = self._logger.get_current_test() or "unknown"
        event = CapturedTrafficEvent(
            test_id=test_id,
            request=http_request,
            response=http_response,
            timestamp=datetime.now(),
        )

        self._logger.log_event(event)


class SynapseInterceptor:
    """Main interceptor that manages multiple interception strategies.

    This class provides a unified interface for activating and deactivating
    HTTP traffic interception across multiple HTTP client libraries.
    """

    # Registry of available strategies
    STRATEGY_CLASSES: List[Type[InterceptionStrategy]] = [
        RequestsInterceptionStrategy,
        HttpxInterceptionStrategy,
    ]

    def __init__(self) -> None:
        self._strategies: List[InterceptionStrategy] = []
        self._active = False
        self._logger: Optional[SynapseFlowLogger] = None

    def activate(self, logger: SynapseFlowLogger) -> List[str]:
        """Activate all available interception strategies.

        Args:
            logger: The flow logger to use for storing captured events.

        Returns:
            List of names of activated strategies.
        """
        if self._active:
            return []

        self._logger = logger
        activated = []

        for strategy_cls in self.STRATEGY_CLASSES:
            strategy = strategy_cls()
            if strategy.is_available():
                strategy.activate(logger)
                self._strategies.append(strategy)
                activated.append(strategy_cls.__name__.replace("InterceptionStrategy", ""))

        self._active = True
        return activated

    def deactivate(self) -> None:
        """Deactivate all active interception strategies."""
        if not self._active:
            return

        for strategy in self._strategies:
            strategy.deactivate()

        self._strategies = []
        self._active = False
        self._logger = None

    @property
    def is_active(self) -> bool:
        """Check if the interceptor is currently active."""
        return self._active

    def get_active_strategies(self) -> List[str]:
        """Get names of currently active strategies."""
        return [
            s.__class__.__name__.replace("InterceptionStrategy", "")
            for s in self._strategies
        ]
