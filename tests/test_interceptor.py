"""Tests for the interceptor module."""

import pytest

from pytest_synapse.flow_logger import SynapseFlowLogger
from pytest_synapse.interceptor import (
    HttpxInterceptionStrategy,
    RequestsInterceptionStrategy,
    SynapseInterceptor,
)


@pytest.fixture(autouse=True)
def reset_logger():
    """Reset the singleton logger before and after each test."""
    SynapseFlowLogger.destroy()
    yield
    SynapseFlowLogger.destroy()


class TestRequestsInterceptionStrategy:
    def test_is_available(self):
        strategy = RequestsInterceptionStrategy()
        # requests should be installed for tests
        assert strategy.is_available() is True

    def test_activate_and_deactivate(self):
        import requests

        strategy = RequestsInterceptionStrategy()
        logger = SynapseFlowLogger()
        original_send = requests.Session.send

        strategy.activate(logger)
        assert requests.Session.send != original_send

        strategy.deactivate()
        assert requests.Session.send == original_send


class TestHttpxInterceptionStrategy:
    def test_is_available(self):
        strategy = HttpxInterceptionStrategy()
        # httpx should be installed for tests
        assert strategy.is_available() is True


class TestSynapseInterceptor:
    def test_activate_returns_strategy_names(self):
        interceptor = SynapseInterceptor()
        logger = SynapseFlowLogger()

        activated = interceptor.activate(logger)
        assert len(activated) > 0
        assert "Requests" in activated

        interceptor.deactivate()

    def test_is_active(self):
        interceptor = SynapseInterceptor()
        logger = SynapseFlowLogger()

        assert interceptor.is_active is False
        interceptor.activate(logger)
        assert interceptor.is_active is True
        interceptor.deactivate()
        assert interceptor.is_active is False

    def test_get_active_strategies(self):
        interceptor = SynapseInterceptor()
        logger = SynapseFlowLogger()

        interceptor.activate(logger)
        strategies = interceptor.get_active_strategies()
        assert "Requests" in strategies

        interceptor.deactivate()
        assert len(interceptor.get_active_strategies()) == 0


class TestRequestsInterception:
    """Integration tests for requests interception using responses mock."""

    @pytest.fixture
    def interceptor(self):
        interceptor = SynapseInterceptor()
        logger = SynapseFlowLogger()
        logger.set_current_test("test::integration")
        interceptor.activate(logger)
        yield interceptor, logger
        interceptor.deactivate()

    def test_capture_get_request(self, interceptor):
        import requests
        import responses

        _, logger = interceptor

        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                "http://localhost:8000/users",
                json=[{"id": 1, "name": "Alice"}],
                status=200,
            )

            response = requests.get("http://localhost:8000/users")
            assert response.status_code == 200

        events = logger.get_events()
        assert len(events) == 1

        event = events[0]
        assert event.request.method == "GET"
        assert event.request.path == "/users"
        assert event.response.status_code == 200

    def test_capture_post_request_with_body(self, interceptor):
        import requests
        import responses

        _, logger = interceptor

        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.POST,
                "http://localhost:8000/users",
                json={"id": 2, "name": "Bob", "email": "bob@example.com"},
                status=201,
            )

            response = requests.post(
                "http://localhost:8000/users",
                json={"name": "Bob", "email": "bob@example.com"},
            )
            assert response.status_code == 201

        events = logger.get_events()
        assert len(events) == 1

        event = events[0]
        assert event.request.method == "POST"
        assert event.request.body is not None
        assert event.response.status_code == 201

    def test_capture_multiple_requests(self, interceptor):
        import requests
        import responses

        _, logger = interceptor

        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                "http://localhost:8000/users",
                json=[],
                status=200,
            )
            rsps.add(
                responses.GET,
                "http://localhost:8000/users/1",
                json={"id": 1, "name": "Alice"},
                status=200,
            )

            requests.get("http://localhost:8000/users")
            requests.get("http://localhost:8000/users/1")

        events = logger.get_events()
        assert len(events) == 2
