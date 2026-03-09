"""In-memory state store for hook pipelines."""

from typing import Any, Dict


class StateStore:
    def __init__(self) -> None:
        self._state: Dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        self._state[key] = value

    def get(self, key: str, default=None) -> Any:
        return self._state.get(key, default)

    def as_dict(self) -> Dict[str, Any]:
        return dict(self._state)
