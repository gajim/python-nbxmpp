
from enum import IntFlag

from typing import Any
from typing import Callable
from typing import Optional

from gi.repository import GLib, GObject


class AsyncResult: ...

AsyncReadyCallback = Callable[[Any, AsyncResult, Any], None]




class ResolverRecordType(IntFlag):
    TXT = ...


class Resolver:

    @classmethod
    def get_default(cls) -> Resolver: ...

    def lookup_records_async(self,
                             rrname: str,
                             record_type: ResolverRecordType,
                             cancellable: Optional[Any] = ...,
                             callback: AsyncReadyCallback = ...,
                             user_data: Any = ...) -> None: ...

    def lookup_records_finish(self, result: AsyncResult) -> list[GLib.Variant]: ...

class Cancellable:
    def cancel(self) -> None: ...

class TlsCertificate: ...

class TlsCertificateFlags(IntFlag):
    VALIDATE_ALL = 127
    UNKNOWN_CA = 1
    REVOKED = 16
    BAD_IDENTITY = 2
    INSECURE = 32
    NOT_ACTIVATED = 4
    GENERIC_ERROR = 64
    EXPIRED = 8


class TlsError(IntFlag):
    MISC = ...
    EOF = ...
    BAD_CERTIFICATE = ...


class IOErrorEnum(IntFlag):
    CANCELLED = ...


class TlsConnection(IOStream):
    def get_peer_certificate(self) -> TlsCertificate: ...
    def get_peer_certificate_errors(self) -> TlsCertificateFlags: ...
    def set_advertised_protocols(self, protocols: Optional[list[str]]) -> None: ...


class TlsClientConnection(TlsConnection):

    @classmethod
    def new(cls,
            base_io_stream: IOStream,
            server_identity: SocketConnectable) -> TlsClientConnection: ...

    def set_validation_flags(self, flags: TlsCertificateFlags) -> None: ...


class Socket:

    def set_timeout(self, timeout: int) -> None: ...
    def set_keepalive(self, keepalive: bool) -> None: ...
    def shutdown(self, shutdown_read: bool, shutdown_write: bool) -> bool: ...

class OutputStream:
    def has_pending(self) -> bool: ...
    def write_all_async(self,
                        buffer: bytes,
                        io_priority: int,
                        cancellable: Optional[Cancellable] = ...,
                        callback: Optional[AsyncReadyCallback] = ...,
                        *user_data: Optional[Any]) -> None: ...
    def write_all_finish(self, result: AsyncResult) -> tuple[bool, int]: ...

class InputStream:
    def read_bytes_async(self,
                         count: int,
                         io_priority: int,
                         cancellable: Optional[Cancellable] = ...,
                         callback: Optional[AsyncReadyCallback] = ...,
                         *user_data: Optional[Any]) -> None: ...
    def read_bytes_finish(self, result: AsyncResult) -> GLib.Bytes: ... 

class IOStream(GObject.Object):
    def get_output_stream(self) -> OutputStream: ...
    def get_input_stream(self) -> InputStream: ...
    def has_pending(self) -> bool: ...


class SocketConnection(IOStream):
    def get_socket(self) -> Socket: ...
    def get_local_address(self) -> SocketAddress: ...


class TcpConnection(SocketConnection):
    def get_remote_address(self) -> InetSocketAddress: ...
    def set_graceful_disconnect(self, graceful_disconnect: bool) -> None: ...


class TcpWrapperConnection(TcpConnection):

    @classmethod
    def new(cls, base_io_stream: IOStream, socket: Socket) -> TcpWrapperConnection: ...


class SocketConnectable:
    def to_string(self) -> str: ...


class NetworkAddress(SocketConnectable):

    @classmethod
    def new(cls, hostname: str, port: int) -> NetworkAddress: ...


class NetworkService(SocketConnectable): ...


class SocketAddress(SocketConnectable): ...


class InetSocketAddress(SocketAddress):
    def get_port(self) -> int: ...


class SocketClientEvent(IntFlag):
    CONNECTING = ...


class SocketClient:

    @classmethod
    def new(cls) -> SocketClient: ...

    def set_timeout(self, timeout: int) -> None: ...

    def set_proxy_resolver(self, proxy_resolver: Optional[ProxyResolver]) -> None: ...

    def connect_to_service_async(self,
                                 domain: str,
                                 service: str,
                                 cancellable: Optional[Cancellable] = ...,
                                 callback: Optional[AsyncReadyCallback] = ...,
                                 *user_data: Any) -> None: ...

    def connect_to_host_async(self,
                              host_and_port: str,
                              default_port: int,
                              cancellable: Optional[Cancellable] = ...,
                              callback: Optional[AsyncReadyCallback] = ...,
                              *user_data: Any) -> None: ...

    def connect_to_host_finish(self, result: AsyncResult) -> TcpConnection: ...
    def connect_to_service_finish(self, result: AsyncResult) -> TcpConnection: ...


class ProxyResolver: ...


class SimpleProxyResolver(ProxyResolver):

    @classmethod
    def new(cls,
            default_proxy: Optional[str],
            ignore_hosts: Optional[str]) -> SimpleProxyResolver: ...
