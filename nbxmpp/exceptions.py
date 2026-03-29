# Copyright (C) 2019 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

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
        InvalidJid.__init__(self, "Localpart must be between 1 and 1023 bytes")


class LocalpartNotAllowedChar(InvalidJid):
    def __init__(self):
        InvalidJid.__init__(self, "Not allowed character in localpart")


class ResourcepartByteLimit(InvalidJid):
    def __init__(self):
        InvalidJid.__init__(self, "Resourcepart must be between 1 and 1023 bytes")


class ResourcepartNotAllowedChar(InvalidJid):
    def __init__(self):
        InvalidJid.__init__(self, "Not allowed character in resourcepart")


class DomainpartByteLimit(InvalidJid):
    def __init__(self):
        InvalidJid.__init__(self, "Domainpart must be between 1 and 1023 bytes")


class DomainpartNotAllowedChar(InvalidJid):
    def __init__(self):
        InvalidJid.__init__(self, "Not allowed character in domainpart")


class StanzaMalformed(Exception):
    pass


class DiscoInfoMalformed(Exception):
    pass


class NodeProcessed(Exception):
    """
    Exception that should be raised by handler when the handling should be
    stopped
    """


class FallbackLanguageError(Exception):
    pass


class StanzaDecrypted(Exception):
    pass
