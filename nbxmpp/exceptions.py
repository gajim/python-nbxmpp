# Copyright (C) 2019 Philipp Hörist <philipp AT hoerist.com>
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


from __future__ import annotations


class EndOfConnection(Exception):
    pass


class NonFatalSSLError(Exception):
    pass


class WrongFieldValue(Exception):
    pass


class InvalidStanza(Exception):
    pass


class InvalidFrom(Exception):
    pass


class InvalidJid(Exception):
    pass


class LocalpartByteLimit(InvalidJid):
    def __init__(self):
        InvalidJid.__init__(self, 'Localpart must be between 1 and 1023 bytes')


class LocalpartNotAllowedChar(InvalidJid):
    def __init__(self):
        InvalidJid.__init__(self, 'Not allowed character in localpart')


class ResourcepartByteLimit(InvalidJid):
    def __init__(self):
        InvalidJid.__init__(self,
                            'Resourcepart must be between 1 and 1023 bytes')


class ResourcepartNotAllowedChar(InvalidJid):
    def __init__(self):
        InvalidJid.__init__(self, 'Not allowed character in resourcepart')


class DomainpartByteLimit(InvalidJid):
    def __init__(self):
        InvalidJid.__init__(self, 'Domainpart must be between 1 and 1023 bytes')


class DomainpartNotAllowedChar(InvalidJid):
    def __init__(self):
        InvalidJid.__init__(self, 'Not allowed character in domainpart')


class StanzaMalformed(Exception):
    pass


class DiscoInfoMalformed(Exception):
    pass


class NodeProcessed(Exception):
    """
    Exception that should be raised by handler when the handling should be
    stopped
    """