# Copyright (C) 2019 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later


class EndOfConnection(Exception):
    pass


class NonFatalSSLError(Exception):
    pass


class FallbackLanguageError(Exception):
    pass


class StanzaDecrypted(Exception):
    pass
