# Copyright (C) 2020 Philipp Hörist <philipp AT hoerist.com>
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

import typing
from typing import Any
from typing import Optional

import logging

from nbxmpp.namespaces import Namespace

if typing.TYPE_CHECKING:
    from nbxmpp import types


def is_error(error: Any) -> bool:
    return isinstance(error, BaseError)


class BaseError(Exception):
    def __init__(self, is_fatal: bool = False):
        self.is_fatal = is_fatal
        self.text = ''

    def __str__(self):
        return self.text

    def get_text(self):
        return self.text


class StanzaError(BaseError):

    log_level = logging.INFO
    app_namespace = None

    def __init__(self, stanza: types.Base):
        BaseError.__init__(self)
        self.stanza = stanza
        self._error_node = stanza.find_tag('error')
        self.condition = stanza.getError()
        self.condition_data = self._error_node.find_tag_text(self.condition)
        self.app_condition = self._get_app_condition()
        self.type = stanza.getErrorType()
        self.jid = stanza.get_from()
        self.id = stanza.get('id')
        self._text: dict[Optional[str], str] = {}

        text_elements = self._error_node.find_tags('text',
                                                   namespace=Namespace.STANZAS)
        for element in text_elements:
            lang = element.getXmlLang()
            text = element.text or ''
            self._text[lang] = text

    def _get_app_condition(self):
        if self.app_namespace is None:
            return None

        for node in self._error_node.get_children():
            if node.namespace == self.app_namespace:
                return node.localname
        return None

    def get_text(self, pref_lang: Optional[str] = None):
        if pref_lang is not None:
            text = self._text.get(pref_lang)
            if text is not None:
                return text

        if self._text:
            text = self._text.get('en')
            if text is not None:
                return text

            text = self._text.get(None)
            if text is not None:
                return text
            return self._text.popitem()[1]
        return ''

    def set_text(self, lang, text):
        self._text[lang] = text

    def __str__(self):
        condition = self.condition
        if self.app_condition is not None:
            condition = '%s (%s)' % (self.condition, self.app_condition)
        text = self.get_text('en') or ''
        if text:
            text = ' - %s' % text
        return 'Error from %s: %s%s' % (self.jid, condition, text)


class PubSubStanzaError(StanzaError):

    app_namespace = Namespace.PUBSUB_ERROR


class HTTPUploadStanzaError(StanzaError):

    app_namespace = Namespace.HTTPUPLOAD_0

    def get_max_file_size(self) -> Optional[float]:
        condition = self._error_node.find_tag('file-too-large',
                                              namespace=self.app_namespace)
        if condition is None:
            return None

        size = condition.find_tag_text('max-file-size')
        if size is None:
            return None

        try:
            return float(size)
        except Exception:
            return None

    def get_retry_date(self) -> Optional[str]:
        return self._error_node.find_tag_attr('retry',
                                              'stamp',
                                              namespace=self.app_namespace)


class MalformedStanzaError(BaseError):

    log_level = logging.WARNING

    def __init__(self, text: str, stanza: types.Base, is_fatal: bool = True):
        BaseError.__init__(self, is_fatal=is_fatal)
        self.stanza = stanza
        self.text = str(text)


class NotSupportedError(BaseError):

    log_level = logging.WARNING

    def __init__(self, text: str):
        BaseError.__init__(self)
        self.text = str(text)


class CancelledError(BaseError):

    log_level = logging.INFO

    def __init__(self):
        BaseError.__init__(self, is_fatal=True)
        self.text = 'Task has been cancelled'


class TimeoutStanzaError(BaseError):

    log_level = logging.INFO

    def __init__(self):
        BaseError.__init__(self)
        self.text = 'Timeout reached'


class RegisterStanzaError(StanzaError):
    def __init__(self, stanza: types.Base, data: Any):
        StanzaError.__init__(self, stanza)
        self._data = data

    def get_data(self):
        return self._data


class ChangePasswordStanzaError(StanzaError):
    def __init__(self, stanza: types.Base, form: types.DataForm):
        StanzaError.__init__(self, stanza)
        self._form = form

    def get_form(self):
        return self._form
