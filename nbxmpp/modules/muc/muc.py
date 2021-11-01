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


from __future__ import annotations

from typing import Any, Optional
from nbxmpp import types
from nbxmpp.client import Client

from nbxmpp.namespaces import Namespace
from nbxmpp.jid import JID
from nbxmpp.exceptions import NodeProcessed
from nbxmpp.exceptions import StanzaMalformed
from nbxmpp.structs import StanzaHandler
from nbxmpp.const import ErrorCondition, ErrorType, InviteType
from nbxmpp.const import MessageType
from nbxmpp.const import StatusCode
from nbxmpp.structs import DeclineData
from nbxmpp.structs import InviteData
from nbxmpp.structs import VoiceRequest
from nbxmpp.structs import AffiliationResult
from nbxmpp.structs import MucConfigResult
from nbxmpp.structs import MucDestroyed
from nbxmpp.task import iq_request_task
from nbxmpp.errors import is_error
from nbxmpp.errors import StanzaError
from nbxmpp.builder import Message
from nbxmpp.builder import DataForm
from nbxmpp.modules.util import raise_if_error
from nbxmpp.modules.util import parse_xmpp_uri
from nbxmpp.modules.util import process_response
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.muc.util import MucInfoResult
from nbxmpp.modules.muc.util import make_affiliation_request
from nbxmpp.modules.muc.util import make_destroy_request
from nbxmpp.modules.muc.util import make_set_config_request
from nbxmpp.modules.muc.util import make_config_request
from nbxmpp.modules.muc.util import make_cancel_config_request
from nbxmpp.modules.muc.util import make_set_affiliation_request
from nbxmpp.modules.muc.util import make_set_role_request
from nbxmpp.modules.muc.util import make_captcha_request
from nbxmpp.modules.muc.util import build_direct_invite
from nbxmpp.modules.muc.util import build_mediated_invite
from nbxmpp.modules.muc.util import parse_muc_user
from nbxmpp.util import get_dataform


class MUC(BaseModule):

    _depends = {
        'disco_info': 'Discovery',
        'request_vcard': 'VCardTemp',
        'send_retract_request': 'Moderation',
    }

    def __init__(self, client: Client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='presence',
                          callback=self._process_muc_presence,
                          ns=Namespace.MUC,
                          priority=11),
            StanzaHandler(name='presence',
                          callback=self._process_muc_user_presence,
                          ns=Namespace.MUC_USER,
                          priority=11),
            StanzaHandler(name='message',
                          callback=self._process_groupchat_message,
                          typ='groupchat',
                          priority=6),
            StanzaHandler(name='message',
                          callback=self._process_mediated_invite,
                          typ='normal',
                          ns=Namespace.MUC_USER,
                          priority=11),
            StanzaHandler(name='message',
                          callback=self._process_direct_invite,
                          typ='normal',
                          ns=Namespace.CONFERENCE,
                          priority=12),
            StanzaHandler(name='message',
                          callback=self._process_voice_request,
                          ns=Namespace.DATA,
                          priority=11),
            StanzaHandler(name='message',
                          callback=self._process_message,
                          ns=Namespace.MUC_USER,
                          priority=13),
        ]

    @staticmethod
    def _process_muc_presence(_client: Client,
                              stanza: types.Presence,
                              properties: Any):

        muc = stanza.find_tag('x', namespace=Namespace.MUC)
        if muc is None:
            return
        properties.from_muc = True
        properties.muc_jid = properties.jid.new_as_bare()
        properties.muc_nickname = properties.jid.resource

    def _process_muc_user_presence(self,
                                   _client: Client,
                                   stanza: types.Presence,
                                   properties: Any):

        muc_user = stanza.find_tag('x', namespace=Namespace.MUC_USER)
        if muc_user is None:
            return
        properties.from_muc = True
        properties.muc_jid = properties.jid.new_as_bare()

        destroy = muc_user.find_tag('destroy')
        if destroy is not None:
            alternate = destroy.get('jid')
            if alternate is not None:
                try:
                    alternate = JID.from_string(alternate)
                except Exception as error:
                    self._log.warning('Invalid alternate JID provided: %s',
                                      error)
                    self._log.warning(stanza)
                    alternate = None
            properties.muc_destroyed = MucDestroyed(
                alternate=alternate,
                reason=muc_user.find_tag_text('reason'),
                password=muc_user.find_tag_text('password'))
            return

        properties.muc_nickname = properties.jid.resource

        # https://xmpp.org/extensions/xep-0045.html#registrar-statuscodes
        message_status_codes = [
            StatusCode.NON_ANONYMOUS,
            StatusCode.SELF,
            StatusCode.CONFIG_ROOM_LOGGING,
            StatusCode.CREATED,
            StatusCode.NICKNAME_MODIFIED,
            StatusCode.REMOVED_BANNED,
            StatusCode.NICKNAME_CHANGE,
            StatusCode.REMOVED_KICKED,
            StatusCode.REMOVED_AFFILIATION_CHANGE,
            StatusCode.REMOVED_NONMEMBER_IN_MEMBERS_ONLY,
            StatusCode.REMOVED_SERVICE_SHUTDOWN,
            StatusCode.REMOVED_ERROR,
        ]

        codes = set()
        for status in muc_user.find_tags('status'):
            try:
                code = StatusCode(status.get('code'))
            except ValueError:
                self._log.warning('Received invalid status code: %s',
                                  status.get('code'))
                self._log.warning(stanza)
                continue
            if code in message_status_codes:
                codes.add(code)

        if codes:
            properties.muc_status_codes = codes

        try:
            properties.muc_user = parse_muc_user(muc_user)
        except StanzaMalformed as error:
            self._log.warning(error)
            self._log.warning(stanza)
            raise NodeProcessed

        if (properties.muc_user is not None and
                properties.muc_user.role.is_none and
                not properties.type.is_unavailable):
            self._log.warning('Malformed Stanza')
            self._log.warning(stanza)
            raise NodeProcessed

    def _process_groupchat_message(self,
                                   _client: Client,
                                   stanza: types.Message,
                                   properties: Any):

        properties.from_muc = True
        properties.muc_jid = properties.jid.new_as_bare()
        properties.muc_nickname = properties.jid.resource

        muc_user = stanza.find_tag('x', namespace=Namespace.MUC_USER)
        if muc_user is not None:
            try:
                properties.muc_user = parse_muc_user(muc_user,
                                                     is_presence=False)
            except StanzaMalformed as error:
                self._log.warning(error)
                self._log.warning(stanza)
                raise NodeProcessed

        addresses = stanza.find_tag('addresses', namespace=Namespace.ADDRESS)
        if addresses is not None:
            address = addresses.find_tag('address')
            if address is not None and address.get('type') == 'ofrom':
                properties.muc_ofrom = JID.from_string(address.get('jid'))

    def _process_message(self,
                         _client: Client,
                         stanza: types.Message,
                         properties: Any):

        muc_user = stanza.find_tag('x', namespace=Namespace.MUC_USER)
        if muc_user is None:
            return

        # MUC Private message
        if (properties.type.is_chat or
                properties.type.is_error and
                not muc_user.get_children()):
            properties.muc_private_message = True
            return

        if properties.is_muc_invite_or_decline:
            return

        properties.from_muc = True
        properties.muc_jid = properties.jid.new_as_bare()

        if not properties.jid.is_bare:
            return

        # MUC Config change
        # https://xmpp.org/extensions/xep-0045.html#registrar-statuscodes
        message_status_codes = [
            StatusCode.SHOWING_UNAVAILABLE,
            StatusCode.NOT_SHOWING_UNAVAILABLE,
            StatusCode.CONFIG_NON_PRIVACY_RELATED,
            StatusCode.CONFIG_ROOM_LOGGING,
            StatusCode.CONFIG_NO_ROOM_LOGGING,
            StatusCode.CONFIG_NON_ANONYMOUS,
            StatusCode.CONFIG_SEMI_ANONYMOUS,
            StatusCode.CONFIG_FULL_ANONYMOUS
        ]

        codes = set()
        for status in muc_user.find_tags('status'):
            try:
                code = StatusCode(status.get('code'))
            except ValueError:
                self._log.warning('Received invalid status code: %s',
                                  status.get('code'))
                self._log.warning(stanza)
                continue
            if code in message_status_codes:
                codes.add(code)

        if codes:
            properties.muc_status_codes = codes

    @staticmethod
    def _process_direct_invite(_client: Client,
                               stanza: types.Message,
                               properties: Any):

        direct = stanza.find_tag('x', namespace=Namespace.CONFERENCE)
        if direct is None:
            return

        if stanza.find_tag('x', namespace=Namespace.MUC_USER) is not None:
            # not a direct invite
            # See https://xmpp.org/extensions/xep-0045.html#example-57
            # read implementation notes
            return

        data = {}
        data['muc'] = JID.from_string(direct.get('jid'))
        data['from_'] = properties.jid
        data['reason'] = direct.get('reason')
        data['password'] = direct.get('password')
        data['continued'] = direct.get('continue') == 'true'
        data['thread'] = direct.get('thread')
        data['type'] = InviteType.DIRECT
        properties.muc_invite = InviteData(**data)

    @staticmethod
    def _process_mediated_invite(_client: Client,
                                 stanza: types.Message,
                                 properties: Any):

        muc_user = stanza.find_tag('x', namespace=Namespace.MUC_USER)
        if muc_user is None:
            return

        if properties.type != MessageType.NORMAL:
            return

        properties.from_muc = True
        properties.muc_jid = properties.jid.new_as_bare()

        data = {}

        invite = muc_user.find_tag('invite')
        if invite is not None:
            data['muc'] = properties.jid.new_as_bare()
            data['from_'] = JID.from_string(invite.get('from'))
            data['reason'] = invite.find_tag_text('reason')
            data['password'] = muc_user.find_tag_text('password')
            data['type'] = InviteType.MEDIATED

            data['continued'] = False
            data['thread'] = None
            continue_ = invite.find_tag('continue')
            if continue_ is not None:
                data['continued'] = True
                data['thread'] = continue_.get('thread')
            properties.muc_invite = InviteData(**data)
            return

        decline = muc_user.find_tag('decline')
        if decline is not None:
            data['muc'] = properties.jid.new_as_bare()
            data['from_'] = JID.from_string(decline.get('from'))
            data['reason'] = decline.find_tag_text('reason')
            properties.muc_decline = DeclineData(**data)
            return

    def _process_voice_request(self,
                               _client: Client,
                               stanza: types.Message,
                               properties: Any):

        data_form = get_dataform(stanza, Namespace.MUC_REQUEST)
        if data_form is None:
            return

        nick = data_form.get_field('muc#roomnick').value
        jid = data_form.get_field('muc#jid').value

        try:
            jid = JID.from_string(jid)
        except Exception:
            self._log.warning('Invalid JID on voice request')
            self._log.warning(stanza)
            raise NodeProcessed

        properties.voice_request = VoiceRequest(jid=jid,
                                                nick=nick,
                                                form=data_form)
        properties.from_muc = True
        properties.muc_jid = properties.jid.new_as_bare()

    def approve_voice_request(self, muc_jid: JID, voice_request: VoiceRequest):
        form = voice_request.form
        form.set_type('submit')
        form.get_field('muc#request_allow').set_value(True)
        message = Message(to=muc_jid)
        message.append(form)
        self._client.send_stanza(message)

    @iq_request_task
    def get_affiliation(self, jid: JID, affiliation: str):
        response = yield make_affiliation_request(jid, affiliation)
        if response.is_error():
            raise StanzaError(response)

        room_jid = response.get_from()
        query = response.get_query(namespace=Namespace.MUC_ADMIN)
        items = query.find_tags('item')
        users_dict: dict[JID, dict[str, str]] = {}
        for item in items:
            try:
                jid = JID.from_string(item.get('jid'))
            except Exception as error:
                self._log.warning('Invalid JID: %s, %s',
                                  item.get('jid'), error)
                continue

            users_dict[jid] = {}
            if item.has_attr('nick'):
                users_dict[jid]['nick'] = item.get('nick')
            if item.has_attr('role'):
                users_dict[jid]['role'] = item.get('role')
            reason = item.find_tag_text('reason')
            if reason:
                users_dict[jid]['reason'] = reason

        self._log.info('Affiliations received from %s: %s',
                       room_jid, users_dict)

        yield AffiliationResult(jid=room_jid, users=users_dict)

    @iq_request_task
    def destroy(self,
                room_jid: JID,
                reason: Optional[str] = None,
                jid: Optional[JID] = None):

        response = yield make_destroy_request(room_jid, reason, jid)
        yield process_response(response)

    @iq_request_task
    def request_info(self,
                     jid: JID,
                     request_vcard: bool = True,
                     allow_redirect: bool = False):

        redirected = False

        disco_info = yield self.disco_info(jid)
        if is_error(disco_info):
            error_response = disco_info

            if not allow_redirect:
                raise error_response

            if error_response.condition != 'gone':
                raise error_response

            try:
                jid = parse_xmpp_uri(error_response.condition_data)[0]
            except Exception:
                raise error_response

            redirected = True
            disco_info = yield self.disco_info(jid)
            raise_if_error(disco_info)

        if not request_vcard or not disco_info.supports(Namespace.VCARD):
            yield MucInfoResult(info=disco_info, redirected=redirected)

        vcard = yield self.request_vcard(jid)
        if is_error(vcard):
            yield MucInfoResult(info=disco_info, redirected=redirected)

        yield MucInfoResult(info=disco_info,
                            vcard=vcard,
                            redirected=redirected)

    @iq_request_task
    def set_config(self, room_jid: JID, form: types.DataForm):

        response = yield make_set_config_request(room_jid, form)
        yield process_response(response)

    @iq_request_task
    def request_config(self, room_jid: JID):

        response = yield make_config_request(room_jid)
        if response.is_error():
            raise StanzaError(response)

        query = response.get_query()

        self._log.info('Config form received for %s', jid)

        form = get_dataform(query, Namespace.MUC_CONFIG)
        yield MucConfigResult(jid=room_jid, form=form)

    @iq_request_task
    def cancel_config(self, room_jid: JID):

        response = yield make_cancel_config_request(room_jid)
        yield process_response(response)

    @iq_request_task
    def set_affiliation(self, room_jid: JID, users_dict):

        response = yield make_set_affiliation_request(room_jid, users_dict)
        yield process_response(response)

    @iq_request_task
    def set_role(self,
                 room_jid: JID,
                 nick: str,
                 role: str,
                 reason: Optional[str] = None):

        response = yield make_set_role_request(room_jid, nick, role, reason)
        yield process_response(response)

    def retract_message(self, room_jid: JID, stanza_id: str,
                        reason: Optional[str] = None) -> None:
        self.send_retract_request(room_jid, stanza_id, reason)

    def set_subject(self, room_jid: JID, subject: str):
        message = Message(room_jid, type='groupchat')
        message.add_tag_text('subject', subject)

        self._log.info('Set subject for %s', room_jid)
        self._client.send_stanza(message)

    def decline(self, room: JID, to: JID, reason: Optional[str] = None):
        message = Message(room)
        muc_user = message.add_tag('x', namespace=Namespace.MUC_USER)
        decline = muc_user.add_tag('decline', to=str(to))
        if reason:
            decline.add_tag_text('reason', reason)
        self._client.send_stanza(message)

    def request_voice(self, room: JID):
        message = Message(to=room)
        dataform = DataForm('submit')
        dataform.set_form_type(Namespace.MUC_REQUEST)
        field = dataform.add_field('text-single', var='muc#role')
        field.set_value('participant')
        message.append(dataform)
        self._client.send_stanza(message)

    def invite(self,
               room: JID,
               to: JID,
               password: str,
               reason: Optional[str] = None,
               continue_: bool = False,
               type_: InviteType = InviteType.MEDIATED):

        if type_ == InviteType.DIRECT:
            invite = build_direct_invite(
                room, to, reason, password, continue_)
        else:
            invite = build_mediated_invite(
                room, to, reason, password, continue_)
        return self._client.send_stanza(invite)

    @iq_request_task
    def send_captcha(self, room_jid: JID, form_node: types.DataForm):

        response = yield make_captcha_request(room_jid, form_node)
        yield process_response(response)

    def cancel_captcha(self, room_jid: JID, message_id: str):
        message = Message(room_jid, id=message_id)
        message.add_error(ErrorType.CANCEL,
                          ErrorCondition.NOT_ACCEPTABLE,
                          Namespace.XMPP_STANZAS)
        self._client.send_stanza(message)
