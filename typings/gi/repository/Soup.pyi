

from typing import Any, Optional

from gi.repository import GObject
from gi.repository import Gio

from enum import IntEnum, IntFlag

from gi.repository.Gio import AsyncReadyCallback, AsyncResult, Cancellable

class LoggerLogLevel(IntFlag):
    BODY = ...

class WebsocketCloseCode(IntFlag):
    NORMAL = ...

class WebsocketConnection(GObject.Object):
    def set_keepalive_interval(self, interval: int) -> None: ...
    def send_binary(self, data: Optional[bytes]) -> None: ...
    def close(self, code: WebsocketCloseCode, data: Optional[bytes]) -> None: ...


class Session:
    def add_feature(self, type: Any) -> bool: ...
    def websocket_connect_async(self,
                                msg: Message,
                                origin: Optional[str],
                                protocols: Optional[list[str]],
                                cancellable: Optional[Cancellable],
                                callback: Optional[AsyncReadyCallback],
                                *user_data: Optional[Any]) -> None: ...
    def websocket_connect_finish(self, result: AsyncResult) -> WebsocketConnection: ...
    def abort(self) -> None: ...


class Logger:

    @classmethod
    def new(cls, level: LoggerLogLevel, max_body_size: int) -> Logger: ...


class MessageFlags(IntEnum):
    NO_REDIRECT = ...

class Message(GObject.Object):
    @classmethod
    def new(cls, method: str, uri_string: str) -> Optional[Message]: ...
    def set_flags(self, flags: MessageFlags) -> None: ...
    def get_https_status(self) -> tuple[bool, Gio.TlsCertificate, Gio.TlsCertificateFlags]: ...

