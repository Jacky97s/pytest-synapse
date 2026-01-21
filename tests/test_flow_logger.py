"""Tests for the flow logger module."""

import pytest
from datetime import datetime

from pytest_synapse.flow_logger import SynapseFlowLogger
from pytest_synapse.types import CapturedTrafficEvent, HttpRequest, HttpResponse


@pytest.fixture(autouse=True)
def reset_logger():
    """Reset the singleton logger before and after each test."""
    SynapseFlowLogger.destroy()
    yield
    SynapseFlowLogger.destroy()


class TestSynapseFlowLogger:
    def test_singleton_pattern(self):
        logger1 = SynapseFlowLogger()
        logger2 = SynapseFlowLogger()
        assert logger1 is logger2

    def test_log_event(self):
        logger = SynapseFlowLogger()
        event = CapturedTrafficEvent(
            test_id="test::example",
            request=HttpRequest(method="GET", path="/users"),
            response=HttpResponse(status_code=200),
        )
        logger.log_event(event)
        assert len(logger) == 1

    def test_get_events(self):
        logger = SynapseFlowLogger()
        event = CapturedTrafficEvent(
            test_id="test::example",
            request=HttpRequest(method="GET", path="/users"),
            response=HttpResponse(status_code=200),
        )
        logger.log_event(event)
        events = logger.get_events()
        assert len(events) == 1
        assert events[0].test_id == "test::example"

    def test_get_events_for_test(self):
        logger = SynapseFlowLogger()
        event1 = CapturedTrafficEvent(
            test_id="test::one",
            request=HttpRequest(method="GET", path="/users"),
            response=HttpResponse(status_code=200),
        )
        event2 = CapturedTrafficEvent(
            test_id="test::two",
            request=HttpRequest(method="POST", path="/users"),
            response=HttpResponse(status_code=201),
        )
        logger.log_event(event1)
        logger.log_event(event2)

        events = logger.get_events_for_test("test::one")
        assert len(events) == 1
        assert events[0].request.method == "GET"

    def test_set_and_get_current_test(self):
        logger = SynapseFlowLogger()
        logger.set_current_test("test::current")
        assert logger.get_current_test() == "test::current"

    def test_clear(self):
        logger = SynapseFlowLogger()
        event = CapturedTrafficEvent(
            test_id="test::example",
            request=HttpRequest(method="GET", path="/users"),
            response=HttpResponse(status_code=200),
        )
        logger.log_event(event)
        assert len(logger) == 1
        logger.clear()
        assert len(logger) == 0

    def test_reset(self):
        logger = SynapseFlowLogger()
        logger.set_current_test("test::current")
        event = CapturedTrafficEvent(
            test_id="test::example",
            request=HttpRequest(method="GET", path="/users"),
            response=HttpResponse(status_code=200),
        )
        logger.log_event(event)

        SynapseFlowLogger.reset()

        assert len(logger) == 0
        assert logger.get_current_test() is None
