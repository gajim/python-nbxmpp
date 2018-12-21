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
from collections import namedtuple

import precis_i18n.codec

from nbxmpp.protocol import JID
from nbxmpp.protocol import InvalidJid
from nbxmpp.stringprepare import nameprep

log = logging.getLogger('nbxmpp.util')

StanzaHandler = namedtuple('StanzaHandler', 'name callback typ ns xmlns system priority')
StanzaHandler.__new__.__defaults__ = ('', '', None, False, 50)


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


class Properties:
    pass


class MessageProperties:
    def __init__(self):
        self.carbon_type = None
        self.eme = None
        self.http_auth = None
        self.nickname = None

    @property
    def is_http_auth(self):
        return self.http_auth is not None


class IqProperties:
    def __init__(self):
        self.http_auth = None

    @property
    def is_http_auth(self):
        return self.http_auth is not None


class PresenceProperties:
    def __init__(self):
        self.type = None
        self.priority = None
        self.show = None
        self.jid = None
        self.resource = None
        self.id = None
        self.nickname = None
        self.self_presence = False
        self.from_muc = False
        self.status = ''
        self.error_message = ''
        self.error_code = ''


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
    return prep(jid.getNode(),
                jid.getDomain(),
                jid.getResource())


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
