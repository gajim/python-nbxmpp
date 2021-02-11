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

import logging

from nbxmpp.namespaces import Namespace


def is_error(error):
    return isinstance(error, BaseError)


class BaseError(Exception):
    def __init__(self, is_fatal=False):
        self.is_fatal = is_fatal
        self.text = ''

    def __str__(self):
        return self.text

    def get_text(self):
        return self.text


class StanzaError(BaseError):

    log_level = logging.INFO
    app_namespace = None

    def __init__(self, stanza):
        BaseError.__init__(self)
        self.stanza = stanza
        self._stanza_name = stanza.getName()
        self._error_node = stanza.getTag('error')
        self.condition = stanza.getError()
        self.condition_data = self._error_node.getTagData(self.condition)
        self.app_condition = self._get_app_condition()
        self.type = stanza.getErrorType()
        self.jid = stanza.getFrom()
        self.id = stanza.getID()
        self._text = {}

        text_elements = self._error_node.getTags('text',
                                                 namespace=Namespace.STANZAS)
        for element in text_elements:
            lang = element.getXmlLang()
            text = element.getData()
            self._text[lang] = text

    def _get_app_condition(self):
        if self.app_namespace is None:
            return None

        for node in self._error_node.getChildren():
            if node.getNamespace() == self.app_namespace:
                return node.getName()
        return None

    def get_text(self, pref_lang=None):
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

    def get_max_file_size(self):
        if self.app_condition != 'file-too-large':
            return None

        node = self._error_node.getTag(self.app_condition)
        try:
            return float(node.getTagData('max-file-size'))
        except Exception:
            return None

    def get_retry_date(self):
        if self.app_condition != 'retry':
            return None
        return self._error_node.getTagAttr('stamp')


class MalformedStanzaError(BaseError):

    log_level = logging.WARNING

    def __init__(self, text, stanza, is_fatal=True):
        BaseError.__init__(self, is_fatal=is_fatal)
        self.stanza = stanza
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
    def __init__(self, stanza, data):
        StanzaError.__init__(self, stanza)
        self._data = data

    def get_data(self):
        return self._data


class ChangePasswordStanzaError(StanzaError):
    def __init__(self, stanza, form):
        StanzaError.__init__(self, stanza)
        self._form = form

    def get_form(self):
        return self._form
