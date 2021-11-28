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

from typing import Any
from typing import Generator
from typing import Optional
from typing import Union

import logging

from nbxmpp import types
from nbxmpp.namespaces import Namespace
from nbxmpp.jid import JID
from nbxmpp.exceptions import NodeProcessed

from nbxmpp.modules.base import BaseModule
from nbxmpp.structs import StanzaHandler
from nbxmpp.const import ErrorCondition
from nbxmpp.const import ErrorType
from nbxmpp.task import iq_request_task
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.errors import StanzaError
from nbxmpp.builder import Iq
from nbxmpp.lookups import register_class_lookup
from nbxmpp.elements import Base


log = logging.getLogger('nbxmpp.m.discovery')


class Discovery(BaseModule):
    def __init__(self, client: types.Client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='iq',
                          callback=self._process_disco_info,
                          typ='get',
                          ns=Namespace.DISCO_INFO,
                          priority=90),
        ]

    @staticmethod
    def _process_disco_info(client: types.Client,
                            iq: types.Iq,
                            properties: Any):

        error = iq.make_error(ErrorType.CANCEL,
                              ErrorCondition.ITEM_NOT_FOUND,
                              Namespace.XMPP_STANZAS)
        client.send_stanza(error)
        raise NodeProcessed

    @iq_request_task
    def disco_info(self,
                   jid: JID,
                   node: Optional[str] = None) -> DiscoInfoGenerator:

        response = yield get_disco_request(Namespace.DISCO_INFO, jid, node)
        if response.is_error():
            raise StanzaError(response)

        query = response.get_query(namespace=Namespace.DISCO_INFO,
                                   node=node)
        if query is None:
            raise MalformedStanzaError('query element missing', response)
        yield query

    @iq_request_task
    def disco_items(self,
                    jid: JID,
                    node: Optional[str] = None) -> DiscoItemsGenerator:

        response = yield get_disco_request(Namespace.DISCO_ITEMS, jid, node)
        if response.is_error():
            raise StanzaError(response)

        query = response.get_query(namespace=Namespace.DISCO_INFO,
                                   node=node)
        if query is None:
            raise MalformedStanzaError('query element missing', response)
        yield query.find_tags('item')


def get_disco_request(namespace: str,
                      jid: JID,
                      node: Optional[str] = None) -> types.Iq:
    iq = Iq(to=jid)
    iq.add_query(namespace=namespace, node=node)
    return iq



class DiscoInfo(Base):
    def get_caps_hash(self) -> Optional[str]:
        try:
            return self.node.split('#')[1]
        except Exception:
            return None

    def _get_form(self, form_type: str) -> Optional[types.DataForm]:
        for dataform in self.find_tags('x', namespace=Namespace.DATA):
            field = dataform.get_field('FORM_TYPE')
            if field is None:
                continue

            if field.value == form_type:
                return dataform

    def has_field(self, form_type: str, var: str) -> bool:
        dataform = self._get_form(form_type)
        if dataform is None:
            return False
        return dataform.get_field(var) is not None

    def get_field_value(self, form_type: str, var: str) -> Optional[Any]:
        dataform = self._get_form(form_type)
        if dataform is None:
            return None

        field = dataform.get_field(var)
        if field is None:
            return None

        if field.is_multi_value_field:
            return field.values or None
        return field.value

    def supports(self, feature: str) -> bool:
        for feature_tag in self.find_tags('feature'):
            if feature == feature_tag.get('var'):
                return True
        return False

    @property
    def node(self) -> Optional[str]:
        return self.get('node')

    @property
    def mam_namespace(self) -> Optional[str]:
        if self.supports(Namespace.MAM_2):
            return Namespace.MAM_2
        if self.supports(Namespace.MAM_1):
            return Namespace.MAM_1
        return None

    @property
    def has_mam_2(self) -> bool:
        return self.supports(Namespace.MAM_2)

    @property
    def has_mam_1(self) -> bool:
        return self.supports(Namespace.MAM_1)

    @property
    def has_mam(self) -> bool:
        return self.has_mam_1 or self.has_mam_2

    @property
    def has_httpupload(self) -> bool:
        return self.supports(Namespace.HTTPUPLOAD_0)

    @property
    def has_message_moderation(self) -> bool:
        return self.supports(Namespace.MESSAGE_MODERATE)

    @property
    def is_muc(self) -> bool:
        for identity in self.find_tags('identity'):
            if identity.category == 'conference':
                if self.supports(Namespace.MUC):
                    return True
        return False

    @property
    def is_irc(self) -> bool:
        for identity in self.find_tags('identity'):
            if identity.category == 'conference' and identity.type == 'irc':
                return True
        return False

    @property
    def muc_name(self) -> Optional[str]:
        if self.muc_room_name:
            return self.muc_room_name

        if self.muc_identity_name:
            return self.muc_identity_name

        if self.jid is not None:
            return self.jid.localpart
        return None

    @property
    def muc_identity_name(self) -> Optional[str]:
        for identity in self.find_tags('identity'):
            if identity.category == 'conference':
                return identity.name
        return None

    @property
    def muc_room_name(self) -> Optional[Any]:
        return self.get_field_value(Namespace.MUC_INFO, 'muc#roomconfig_roomname')

    @property
    def muc_description(self) -> Optional[Any]:
        return self.get_field_value(Namespace.MUC_INFO, 'muc#roominfo_description')

    @property
    def muc_log_uri(self) -> Optional[Any]:
        return self.get_field_value(Namespace.MUC_INFO, 'muc#roominfo_logs')

    @property
    def muc_users(self) -> Optional[Any]:
        return self.get_field_value(Namespace.MUC_INFO, 'muc#roominfo_occupants')

    @property
    def muc_contacts(self) -> Optional[Any]:
        return self.get_field_value(Namespace.MUC_INFO, 'muc#roominfo_contactjid')

    @property
    def muc_subject(self) -> Optional[Any]:
        return self.get_field_value(Namespace.MUC_INFO, 'muc#roominfo_subject')

    @property
    def muc_subjectmod(self) -> Optional[Any]:
        # muc#roominfo_changesubject stems from a wrong example in the MUC XEP
        # Ejabberd and Prosody use this value
        return (self.get_field_value(Namespace.MUC_INFO, 'muc#roominfo_subjectmod') or
                self.get_field_value(Namespace.MUC_INFO, 'muc#roominfo_changesubject'))

    @property
    def muc_lang(self) -> Optional[Any]:
        return self.get_field_value(Namespace.MUC_INFO, 'muc#roominfo_lang')

    @property
    def muc_is_persistent(self) -> bool:
        return self.supports('muc_persistent')

    @property
    def muc_is_moderated(self) -> bool:
        return self.supports('muc_moderated')

    @property
    def muc_is_open(self) -> bool:
        return self.supports('muc_open')

    @property
    def muc_is_members_only(self) -> bool:
        return self.supports('muc_membersonly')

    @property
    def muc_is_hidden(self) -> bool:
        return self.supports('muc_hidden')

    @property
    def muc_is_nonanonymous(self) -> bool:
        return self.supports('muc_nonanonymous')

    @property
    def muc_is_passwordprotected(self) -> bool:
        return self.supports('muc_passwordprotected')

    @property
    def muc_is_public(self) -> bool:
        return self.supports('muc_public')

    @property
    def muc_is_semianonymous(self) -> bool:
        return self.supports('muc_semianonymous')

    @property
    def muc_is_temporary(self) -> bool:
        return self.supports('muc_temporary')

    @property
    def muc_is_unmoderated(self) -> bool:
        return self.supports('muc_unmoderated')

    @property
    def muc_is_unsecured(self) -> bool:
        return self.supports('muc_unsecured')

    @property
    def is_gateway(self) -> bool:
        for identity in self.find_tags('identity'):
            if identity.category == 'gateway':
                return True
        return False

    @property
    def gateway_name(self) -> Optional[str]:
        for identity in self.find_tags('identity'):
            if identity.category == 'gateway':
                return identity.name
        return None

    @property
    def gateway_type(self) -> Optional[str]:
        for identity in self.find_tags('identity'):
            if identity.category == 'gateway':
                return identity.type
        return None

    def has_category(self, category: str) -> bool:
        for identity in self.find_tags('identity'):
            if identity.category == category:
                return True
        return False

    @property
    def httpupload_max_file_size(self) -> Optional[float]:
        size = self.get_field_value(Namespace.HTTPUPLOAD_0, 'max-file-size')
        try:
            return float(size)
        except Exception:
            return None


class DiscoIdentity(Base):

    @property
    def category(self) -> str:
        return self.get('category')

    @property
    def type(self) -> str:
        return self.get('type')

    @property
    def name(self) -> Optional[str]:
        return self.get('name')


class DiscoItem(Base):
    @property
    def jid(self) -> str:
        return self.get('jid')

    @property
    def name(self) -> Optional[str]:
        return self.get('name')

    @property
    def node(self) -> Optional[str]:
        return self.get('node')


DiscoInfoGenerator = Generator[Union[types.Iq, DiscoInfo], types.Iq, None]
DiscoItemsGenerator = Generator[Union[types.Iq, list[DiscoItem]], types.Iq, None]


register_class_lookup('query', Namespace.DISCO_INFO, DiscoInfo)
register_class_lookup('identity', Namespace.DISCO_INFO, DiscoIdentity)
register_class_lookup('item', Namespace.DISCO_ITEMS, DiscoItem)
