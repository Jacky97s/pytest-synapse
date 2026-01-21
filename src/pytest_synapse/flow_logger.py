"""Thread-safe flow logger for captured HTTP traffic."""

import threading
from typing import List, Optional

from pytest_synapse.types import CapturedTrafficEvent


class SynapseFlowLogger:
    """Thread-safe storage for captured HTTP traffic events.

    This class provides a centralized, thread-safe store for all HTTP traffic
    captured during a pytest session. It associates each event with the
    originating test's node ID.
    """

    _instance: Optional["SynapseFlowLogger"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "SynapseFlowLogger":
        """Singleton pattern to ensure one logger per session."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._events: List[CapturedTrafficEvent] = []
                    cls._instance._events_lock = threading.Lock()
                    cls._instance._current_test_id: Optional[str] = None
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance. Used between test sessions."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance._events = []
                cls._instance._current_test_id = None

    @classmethod
    def destroy(cls) -> None:
        """Destroy the singleton instance completely."""
        with cls._lock:
            cls._instance = None

    def set_current_test(self, test_id: str) -> None:
        """Set the current test being executed."""
        self._current_test_id = test_id

    def get_current_test(self) -> Optional[str]:
        """Get the current test ID."""
        return self._current_test_id

    def log_event(self, event: CapturedTrafficEvent) -> None:
        """Log a captured traffic event.

        Args:
            event: The captured HTTP traffic event to store.
        """
        with self._events_lock:
            self._events.append(event)

    def get_events(self) -> List[CapturedTrafficEvent]:
        """Get all captured events.

        Returns:
            A copy of the list of all captured events.
        """
        with self._events_lock:
            return list(self._events)

    def get_events_for_test(self, test_id: str) -> List[CapturedTrafficEvent]:
        """Get all events for a specific test.

        Args:
            test_id: The pytest node ID.

        Returns:
            List of events for the specified test.
        """
        with self._events_lock:
            return [e for e in self._events if e.test_id == test_id]

    def clear(self) -> None:
        """Clear all stored events."""
        with self._events_lock:
            self._events = []

    def __len__(self) -> int:
        """Return the number of stored events."""
        with self._events_lock:
            return len(self._events)
