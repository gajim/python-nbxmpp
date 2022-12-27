# This file is part of nbxmpp.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 3
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations

from pathlib import Path

from typing import Any
from typing import cast
from typing import Literal
from typing import Callable
from typing import Optional

import logging

from gi.repository import Soup
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject

import nbxmpp
from .const import HTTPRequestError


log = logging.getLogger('nbxmpp.http')


HTTP_METHODS_T = Literal[
    'CONNECT',
    'DELETE',
    'GET',
    'HEAD',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
    'TRACE',
]
CHUNK_SIZE = 32768
DEFAULT_USER_AGENT = f'nbxmpp/{nbxmpp.__version__}'
SIGNAL_ACTIONS = GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION


class HTTPLogAdapter(logging.LoggerAdapter):
    def process(self, msg: str, kwargs: Any) -> tuple[str, Any]:
        return f'{self.extra["request"]}: {msg}', kwargs


class HTTPSession:
    def __init__(self,
                 user_agent: str = DEFAULT_USER_AGENT,
                 sniffer: bool = False
                 ) -> None:

        self._session = Soup.Session()
        self._session.set_user_agent(user_agent)

        if sniffer:
            self._session.add_feature_by_type(Soup.ContentSniffer)

    def get_soup_session(self) -> Soup.Session:
        return self._session

    def set_proxy_resolver(self,
                           resolver: Optional[Gio.SimpleProxyResolver]
                           ) -> None:

        self._session.set_proxy_resolver(resolver)

    def create_request(self) -> HTTPRequest:
        return HTTPRequest(self)


class HTTPRequest(GObject.GObject):

    __gtype_name__ = "HTTPRequest"

    __gsignals__ = {
        'starting-response-body': (SIGNAL_ACTIONS, None, ()),
        'response-progress': (SIGNAL_ACTIONS, None, (float,)),
        'request-progress': (SIGNAL_ACTIONS, None, (float,)),
        'finished': (SIGNAL_ACTIONS, None, ()),
        'destroy': (SIGNAL_ACTIONS, None, ()),
    }

    def __init__(self, session: HTTPSession) -> None:
        GObject.GObject.__init__(self)

        self._log = HTTPLogAdapter(log, extra={'request': self})

        self._session = session

        self._received_size = 0
        self._sent_size = 0

        self._cancellable = Gio.Cancellable()
        self._input_stream = cast(Gio.InputStream, None)
        self._output_stream: Optional[Gio.OutputStream] = None
        self._is_finished = False
        self._error: Optional[HTTPRequestError] = None
        self._is_complete = False
        self._timeout_reached = False
        self._timeout_id = None

        self._response_body_file: Optional[Gio.File] = None
        self._response_body_data = b''

        self._request_body_file: Optional[Gio.File] = None
        self._request_body_data: Optional[bytes] = None

        self._request_content_type = ''
        self._request_content_length = 0

        self._response_content_type = ''
        self._response_content_length = 0

        self._emit_request_progress = False
        self._emit_response_progress = False

        self._message = Soup.Message()
        self._user_data = None

        self._log.info('Created')

    def is_finished(self) -> bool:
        return self._is_finished

    def is_complete(self) -> bool:
        return self._is_complete

    def get_error(self) -> Optional[HTTPRequestError]:
        return self._error

    def get_error_string(self) -> str:
        if self._error == HTTPRequestError.STATUS_NOT_OK:
            return self._message.get_reason_phrase()
        return f'{self._error}'

    def get_response_headers(self) -> Soup.MessageHeaders:
        return self._message.get_response_headers()

    def get_request_headers(self) -> Soup.MessageHeaders:
        return self._message.get_request_headers()

    def get_data(self) -> bytes:
        if not self._is_finished:
            raise ValueError('Process not finished, data not available')
        return self._response_body_data

    def get_uri(self) -> Optional[GLib.Uri]:
        return self._message.get_uri()

    def get_status(self) -> Soup.Status:
        return self._message.get_status()

    def get_soup_message(self) -> Soup.Message:
        return self._message

    def set_user_data(self, user_data: Any) -> None:
        self._user_data = user_data

    def get_user_data(self) -> Any:
        return self._user_data

    def cancel(self) -> None:
        if self._is_finished:
            raise ValueError('Session already finished')

        self._cancellable.cancel()

    def set_request_body_from_path(self, content_type: str, path: Path) -> None:
        if not path.exists():
            raise ValueError('%s does not exist' % path)

        if not path.is_file():
            raise ValueError('%s is not a file' % path)

        self._request_body_file = Gio.File.new_for_path(str(path))
        self._request_content_type = content_type
        self._request_content_length = path.stat().st_size

    def set_request_body(self, content_type: str, data: bytes) -> None:
        self._request_body_data = data
        self._request_content_type = content_type
        self._request_content_length = len(data)

    def set_response_body_from_path(self, path: Path) -> None:
        self._response_body_file = Gio.File.new_for_path(str(path))

    def connect(self,
                signal_name: str,
                callback: Any,
                *args: Any
                ) -> None:

        if signal_name == 'response-progress':
            self._emit_response_progress = True

        if signal_name == 'request-progress':
            self._emit_request_progress = True

        if signal_name in GObject.signal_list_names(HTTPRequest):
            GObject.GObject.connect(self, signal_name, callback, *args)
            return

        user_data = (callback, args)

        self._message.connect(signal_name,
                              self._on_connect_callback,
                              user_data)

    def _on_connect_callback(self, _message: Soup.Message, *args: Any) -> None:
        signal_args = args[:-1]
        callback, user_data = args[-1]
        callback(self, *signal_args, *user_data)

    def send(self,
             method: HTTP_METHODS_T,
             uri_string: str,
             timeout: Optional[int] = None,
             callback: Optional[Callable[[HTTPRequest], Any]] = None
             ) -> None:

        if callback:
            self.connect('finished', callback)
        self._send(method, uri_string, timeout)

    def _send(self,
              method: HTTP_METHODS_T,
              uri_string: str,
              timeout: Optional[int] = None
              ) -> None:

        if self._is_finished:
            raise ValueError('Session already finished')

        self._message.set_method(method)

        if self._response_body_file is not None:
            self._output_stream = self._response_body_file.replace(
                None,
                False,
                Gio.FileCreateFlags.REPLACE_DESTINATION,
                self._cancellable)

        uri = GLib.Uri.parse(uri_string, GLib.UriFlags.HAS_PASSWORD)
        self._message.set_uri(uri)

        if self._request_body_data is not None:
            self._message.set_request_body_from_bytes(
                self._request_content_type,
                GLib.Bytes.new(self._request_body_data)
            )
            if self._emit_request_progress:
                self._message.connect('wrote-body-data',
                                      self._on_request_body_progress)

        if self._request_body_file is not None:
            request_input_stream = self._request_body_file.read(
                self._cancellable)
            self._message.set_request_body(self._request_content_type,
                                           request_input_stream,
                                           self._request_content_length)
            if self._emit_request_progress:
                self._message.connect('wrote-body-data',
                                      self._on_request_body_progress)

        self._message.connect('finished', self._on_finished)

        soup_session = self._session.get_soup_session()
        soup_session.send_async(self._message,
                                GLib.PRIORITY_DEFAULT,
                                self._cancellable,
                                self._on_response)

        if timeout is not None:
            self._timeout_id = GLib.timeout_add_seconds(
                timeout, self._on_timeout)

        self._log.info('Request sent')

    def _on_request_body_progress(self,
                                  _message: Soup.Message,
                                  chunk: int) -> None:

        self._sent_size += chunk
        self.emit('request-progress',
                  self._sent_size / self._request_content_length)

    def _on_timeout(self) -> None:
        self._timeout_reached = True
        self.cancel()

    def _on_response(self,
                     session: Soup.Session,
                     result: Gio.AsyncResult
                     ) -> None:

        self._log.info('Request response received')
        try:
            self._input_stream = session.send_finish(result)
        except GLib.Error as error:
            self._log.error(error)
            quark = GLib.quark_try_string('g-io-error-quark')
            if error.matches(quark, Gio.IOErrorEnum.CANCELLED):
                self._set_failed(HTTPRequestError.CANCELLED)
            else:
                self._set_failed(HTTPRequestError.UNKNOWN)
            return

        if self._message.get_status() not in (Soup.Status.OK, Soup.Status.CREATED):
            self._set_failed(HTTPRequestError.STATUS_NOT_OK)
            return

        headers = self.get_response_headers()
        self._response_content_length = headers.get_content_length()
        self._response_content_type, _params = headers.get_content_type()
        if self._response_content_length == 0:
            self._set_failed(HTTPRequestError.MISSING_CONTENT_LENGTH)
            return

        self._log.info('Start downloading response body')
        self.emit('starting-response-body')

        self._read_async()

    def _read_async(self) -> None:
        self._input_stream.read_bytes_async(CHUNK_SIZE,
                                            GLib.PRIORITY_LOW,
                                            self._cancellable,
                                            self._on_bytes_read_result)

    def _on_bytes_read_result(self,
                              input_stream: Gio.InputStream,
                              result: Gio.AsyncResult) -> None:
        try:
            data = input_stream.read_bytes_finish(result)
        except GLib.Error as error:
            self._log.error(error)
            quark = GLib.quark_try_string('g-io-error-quark')
            if error.matches(quark, Gio.IOErrorEnum.CANCELLED):
                self._finish_read(HTTPRequestError.CANCELLED)
            else:
                self._finish_read(HTTPRequestError.UNKNOWN)

            return

        bytes_ = data.get_data()
        if not bytes_:
            self._finish_read()
            return

        length = len(bytes_)
        self._received_size += length
        if self._received_size > self._response_content_length:
            self._finish_read(HTTPRequestError.CONTENT_OVERFLOW)
            return

        if self._output_stream is None:
            self._response_body_data += bytes_

        else:
            try:
                self._output_stream.write_all(bytes_, self._cancellable)
            except GLib.Error as error:
                self._log.error(error)
                quark = GLib.quark_try_string('g-io-error-quark')
                if error.matches(quark, Gio.IOErrorEnum.CANCELLED):
                    self._finish_read(HTTPRequestError.CANCELLED)
                else:
                    self._finish_read(HTTPRequestError.UNKNOWN)
                return

        self._read_async()

        if (self._emit_response_progress and
                self._message.get_method() == 'GET'):
            self.emit('response-progress',
                      self._received_size / self._response_content_length)


    def _finish_read(self, error: Optional[HTTPRequestError] = None) -> None:
        self._log.info('Finished reading')
        if error is None:
            self._close_all_streams()
            return

        self._set_failed(error)

    def _on_finished(self, _message: Soup.Message) -> None:
        self._set_finished()

    def _set_finished(self) -> None:
        status = self._message.get_status()
        if status == Soup.Status.NONE:
            # Message has not been sent, can happen when we cancel the message
            # before it is sent. The finished signal triggers before the
            # cancelled exception.
            return

        if self._is_finished:
            return

        headers = self._message.get_response_headers()
        content_length = headers.get_content_length()
        if self._received_size != content_length:
            self._set_failed(HTTPRequestError.INCOMPLETE)
            return

        if status not in (Soup.Status.OK, Soup.Status.CREATED):
            self._set_failed(HTTPRequestError.STATUS_NOT_OK)
            return

        self._set_complete()

    def _set_failed(self, error: HTTPRequestError) -> None:
        self._is_finished = True
        if self._timeout_reached:
            self._timeout_id = None
            self._error = HTTPRequestError.TIMEOUT
        else:
            self._error = error
        self._close_all_streams()
        self.emit('finished')
        self._cleanup()

    def _set_complete(self) -> None:
        self._is_finished = True
        self._is_complete = True
        self._close_all_streams()
        self.emit('finished')
        self._cleanup()

    def _close_all_streams(self) -> None:
        if self._input_stream is not None:
            if not self._input_stream.is_closed():
                self._input_stream.close(None)

        if self._output_stream is not None:
            if not self._output_stream.is_closed():
                self._output_stream.close(None)

    def _cleanup(self) -> None:
        self._log.info('Run cleanup')

        self._response_body_data = b''
        self._message.run_dispose()

        del self._cancellable
        del self._session
        del self._input_stream
        del self._output_stream
        del self._user_data

        if self._timeout_id is not None:
            GLib.source_remove(self._timeout_id)

        self.emit('destroy')
        self.run_dispose()

    def __repr__(self) -> str:
        return f'Request({id(self)})'
