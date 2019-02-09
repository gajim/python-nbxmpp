# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
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

import logging
import socket
import base64
import weakref
from functools import wraps

import precis_i18n.codec

from nbxmpp.protocol import JID
from nbxmpp.protocol import InvalidJid
from nbxmpp.stringprepare import nameprep
from nbxmpp.structs import Properties
from nbxmpp.structs import IqProperties
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import PresenceProperties
from nbxmpp.structs import CommonError

log = logging.getLogger('nbxmpp.util')


def b64decode(data, return_type=str):
    if isinstance(data, str):
        data = data.encode()
    result = base64.b64decode(data)
    if return_type == bytes:
        return result
    return result.decode()


def b64encode(data, return_type=str):
    if isinstance(data, str):
        data = data.encode()
    result = base64.b64encode(data)
    if return_type == bytes:
        return result
    return result.decode()


def get_properties_struct(name):
    if name == 'message':
        return MessageProperties()
    if name == 'iq':
        return IqProperties()
    if name == 'presence':
        return PresenceProperties()
    return Properties()


def validate_jid(jid_string):
    jid = JID(jid_string)
    return prep(jid.getNode() or None,
                jid.getDomain() or None,
                jid.getResource() or None)


def prep(user, server, resource):
    """
    Perform stringprep on all JID fragments and return the full jid
    """

    ip_address = False

    try:
        socket.inet_aton(server)
        ip_address = True
    except socket.error:
        pass

    if not ip_address and hasattr(socket, 'inet_pton'):
        try:
            socket.inet_pton(socket.AF_INET6, server.strip('[]'))
            server = '[%s]' % server.strip('[]')
            ip_address = True
        except (socket.error, ValueError):
            pass

    if not ip_address:
        if server is not None:
            if server.endswith('.'):  # RFC7622, 3.2
                server = server[:-1]
            if not server or len(server.encode('utf-8')) > 1023:
                raise InvalidJid('Server must be between 1 and 1023 bytes')
            try:
                server = nameprep.prepare(server)
            except UnicodeError:
                raise InvalidJid('Invalid character in hostname')
        else:
            raise InvalidJid('Server address required')

    if user is not None:
        if not user or len(user.encode('utf-8')) > 1023:
            raise InvalidJid('Username must be between 1 and 1023 bytes')
        try:
            user = user.encode('UsernameCaseMapped').decode('utf-8')
        except UnicodeError:
            raise InvalidJid('Invalid character in username')
    else:
        user = None

    if resource is not None:
        if not resource or len(resource.encode('utf-8')) > 1023:
            raise InvalidJid('Resource must be between 1 and 1023 bytes')
        try:
            resource = resource.encode('OpaqueString').decode('utf-8')
        except UnicodeError:
            raise InvalidJid('Invalid character in resource')
    else:
        resource = None

    if user:
        if resource:
            return '%s@%s/%s' % (user, server, resource)
        return '%s@%s' % (user, server)

    if resource:
        return '%s/%s' % (server, resource)
    return server


def call_on_response(cb):
    def response_decorator(func):
        @wraps(func)
        def func_wrapper(self, *args, **kwargs):
            user_data = kwargs.pop('user_data', None)
            callback_ = kwargs.pop('callback', None)

            stanza = func(self, *args, **kwargs)
            if isinstance(stanza, tuple):
                stanza, attrs = stanza
            else:
                stanza, attrs = stanza, {}

            if user_data is not None:
                attrs['user_data'] = user_data

            if callback_ is not None:
                attrs['callback'] = weakref.WeakMethod(callback_)

            self._client.SendAndCallForResponse(stanza,
                                                getattr(self, cb),
                                                attrs)
        return func_wrapper
    return response_decorator


def callback(func):
    @wraps(func)
    def func_wrapper(self, _con, stanza, **kwargs):
        cb = kwargs.pop('callback', None)
        user_data = kwargs.pop('user_data', None)

        result = func(self, stanza, **kwargs)
        if cb is not None and cb() is not None:
            if user_data is not None:
                cb()(result, user_data)
            else:
                cb()(result)
    return func_wrapper


def from_xs_boolean(value):
    if value in ('1', 'true', 'True'):
        return True

    if value in ('0', 'false', 'False', ''):
        return False

    raise ValueError('Cant convert %s to python boolean' % value)


def to_xs_boolean(value):
    # Convert to xs:boolean ('true', 'false')
    # from a python boolean (True, False) or None
    if value is True:
        return 'true'

    if value is False:
        return 'false'

    if value is None:
        return 'false'

    raise ValueError(
        'Cant convert %s to xs:boolean' % value)


def raise_error(log_method, stanza, type_=None, message=None):
    if message is not None:
        message = str(message)
    if type_ is None:
        type_ = stanza.getError()
        message = stanza.getErrorMsg()
    error = CommonError(type_, message)
    log_method(error)
    if log_method.__name__ in ('warning', 'error'):
        log_method(stanza)
    return error


def is_error_result(result):
    return isinstance(result, CommonError)
