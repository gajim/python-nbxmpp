

from typing import Any


class ParamSpec: ...


class Object:

    def connect(self, event: str, callback: Any) -> int: ...