

from enum import IntFlag


class Session:
    def add_feature(self) -> None: ...
    def websocket_connect_finish(self) -> None: ...


class Logger:
    @classmethod
    def new(cls) -> Logger: ...


class Message:
    @classmethod
    def new(cls) -> Message: ...


class MessageFlags(IntFlag):
    NO_REDIRECT = ...
