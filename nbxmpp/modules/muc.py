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

from nbxmpp.protocol import NS_MUC_USER
from nbxmpp.protocol import NS_MUC
from nbxmpp.protocol import NS_CONFERENCE
from nbxmpp.protocol import NS_DATA
from nbxmpp.protocol import NS_MUC_REQUEST
from nbxmpp.protocol import NS_MUC_ADMIN
from nbxmpp.protocol import NS_MUC_OWNER
from nbxmpp.protocol import NS_CAPTCHA
from nbxmpp.protocol import NS_ADDRESS
from nbxmpp.protocol import JID
from nbxmpp.protocol import Iq
from nbxmpp.protocol import Message
from nbxmpp.protocol import DataForm
from nbxmpp.protocol import DataField
from nbxmpp.protocol import isResultNode
from nbxmpp.protocol import InvalidJid
from nbxmpp.simplexml import Node
from nbxmpp.structs import StanzaHandler
from nbxmpp.const import InviteType
from nbxmpp.const import MessageType
from nbxmpp.const import StatusCode
from nbxmpp.const import Affiliation
from nbxmpp.const import Role
from nbxmpp.structs import DeclineData
from nbxmpp.structs import InviteData
from nbxmpp.structs import VoiceRequest
from nbxmpp.structs import AffiliationResult
from nbxmpp.structs import CommonResult
from nbxmpp.structs import MucConfigResult
from nbxmpp.structs import MucUserData
from nbxmpp.structs import MucDestroyed
from nbxmpp.util import validate_jid
from nbxmpp.util import call_on_response
from nbxmpp.util import callback
from nbxmpp.util import raise_error
from nbxmpp.modules.dataforms import extend_form

log = logging.getLogger('nbxmpp.m.muc')


class MUC:
    def __init__(self, client):
        self._client = client
        self.handlers = [
            StanzaHandler(name='presence',
                          callback=self._process_muc_presence,
                          ns=NS_MUC,
                          priority=11),
            StanzaHandler(name='presence',
                          callback=self._process_muc_user_presence,
                          ns=NS_MUC_USER,
                          priority=11),
            StanzaHandler(name='message',
                          callback=self._process_groupchat_message,
                          typ='groupchat',
                          priority=6),
            StanzaHandler(name='message',
                          callback=self._process_mediated_invite,
                          typ='normal',
                          ns=NS_MUC_USER,
                          priority=11),
            StanzaHandler(name='message',
                          callback=self._process_direct_invite,
                          typ='normal',
                          ns=NS_CONFERENCE,
                          priority=11),
            StanzaHandler(name='message',
                          callback=self._process_voice_request,
                          ns=NS_DATA,
                          priority=11),
            StanzaHandler(name='message',
                          callback=self._process_message,
                          ns=NS_MUC_USER,
                          priority=12),
        ]

    @staticmethod
    def _process_muc_presence(_con, stanza, properties):
        muc = stanza.getTag('x', namespace=NS_MUC)
        if muc is None:
            return
        properties.from_muc = True
        properties.muc_nickname = properties.jid.getResource()

    def _process_muc_user_presence(self, _con, stanza, properties):
        muc_user = stanza.getTag('x', namespace=NS_MUC_USER)
        if muc_user is None:
            return
        properties.from_muc = True

        destroy = muc_user.getTag('destroy')
        if destroy is not None:
            alternate = destroy.getAttr('jid')
            if alternate is not None:
                try:
                    alternate = JID(validate_jid(alternate))
                except InvalidJid:
                    log.warning('Invalid alternate JID provided')
                    log.warning(stanza)
                    alternate = None
            properties.muc_destroyed = MucDestroyed(
                alternate=alternate,
                reason=muc_user.getTagData('reason'),
                password=muc_user.getTagData('password'))
            return

        properties.muc_nickname = properties.jid.getResource()

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
        for status in muc_user.getTags('status'):
            try:
                code = StatusCode(status.getAttr('code'))
            except ValueError:
                log.warning('Received invalid status code: %s',
                            status.getAttr('code'))
                log.warning(stanza)
                continue
            if code in message_status_codes:
                codes.add(code)

        if codes:
            properties.muc_status_codes = codes

        properties.muc_user = self._parse_muc_user(muc_user)

    def _process_groupchat_message(self, _con, stanza, properties):
        properties.from_muc = True
        properties.muc_nickname = properties.jid.getResource() or None

        muc_user = stanza.getTag('x', namespace=NS_MUC_USER)
        if muc_user is not None:
            properties.muc_user = self._parse_muc_user(muc_user)

        addresses = stanza.getTag('addresses', namespace=NS_ADDRESS)
        if addresses is not None:
            address = addresses.getTag('address', attrs={'type': 'ofrom'})
            if address is not None:
                properties.muc_ofrom = JID(address.getAttr('jid'))

    @staticmethod
    def _process_message(_con, stanza, properties):
        muc_user = stanza.getTag('x', namespace=NS_MUC_USER)
        if muc_user is None:
            return

        # MUC Private message
        if properties.type == MessageType.CHAT and not muc_user.getChildren():
            properties.muc_private_message = True
            return

        if properties.is_muc_invite_or_decline:
            return

        properties.from_muc = True

        if not properties.jid.isBare:
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
        for status in muc_user.getTags('status'):
            try:
                code = StatusCode(status.getAttr('code'))
            except ValueError:
                log.warning('Received invalid status code: %s',
                            status.getAttr('code'))
                log.warning(stanza)
                continue
            if code in message_status_codes:
                codes.add(code)

        if codes:
            properties.muc_status_codes = codes

    @staticmethod
    def _process_direct_invite(_con, stanza, properties):
        direct = stanza.getTag('x', namespace=NS_CONFERENCE)
        if direct is None:
            return

        muc_jid = direct.getAttr('jid')
        if muc_jid is None:
            # Not a direct invite
            # See https://xmpp.org/extensions/xep-0045.html#example-57
            # read implementation notes
            return

        data = {}
        data['muc'] = JID(muc_jid)
        data['from_'] = properties.jid
        data['reason'] = direct.getAttr('reason')
        data['password'] = direct.getAttr('password')
        data['continued'] = direct.getAttr('continue') == 'true'
        data['thread'] = direct.getAttr('thread')
        data['type'] = InviteType.DIRECT
        properties.muc_invite = InviteData(**data)

    @staticmethod
    def _process_mediated_invite(_con, stanza, properties):
        muc_user = stanza.getTag('x', namespace=NS_MUC_USER)
        if muc_user is None:
            return

        if properties.type != MessageType.NORMAL:
            return

        properties.from_muc = True

        data = {}

        invite = muc_user.getTag('invite')
        if invite is not None:
            data['muc'] = JID(properties.jid.getBare())
            data['from_'] = JID(invite.getAttr('from'))
            data['reason'] = invite.getTagData('reason')
            data['password'] = muc_user.getTagData('password')
            data['type'] = InviteType.MEDIATED

            data['continued'] = False
            data['thread'] = None
            continue_ = invite.getTag('continue')
            if continue_ is not None:
                data['continued'] = True
                data['thread'] = continue_.getAttr('thread')
            properties.muc_invite = InviteData(**data)
            return

        decline = muc_user.getTag('decline')
        if decline is not None:
            data['muc'] = JID(properties.jid.getBare())
            data['from_'] = JID(decline.getAttr('from'))
            data['reason'] = decline.getTagData('reason')
            properties.muc_decline = DeclineData(**data)
            return

    @staticmethod
    def _process_voice_request(_con, stanza, properties):
        data_form = stanza.getTag('x', namespace=NS_DATA)
        if data_form is None:
            return

        data_form = extend_form(data_form)
        try:
            if data_form['FORM_TYPE'].value != NS_MUC_REQUEST:
                return
        except KeyError:
            return

        properties.voice_request = VoiceRequest(form=data_form)

    @call_on_response('_affiliation_received')
    def get_affiliation(self, jid, affiliation):
        iq = Iq(typ='get', to=jid, queryNS=NS_MUC_ADMIN)
        item = iq.setQuery().setTag('item')
        item.setAttr('affiliation', affiliation)
        return iq

    @callback
    def _affiliation_received(self, stanza):
        if not isResultNode(stanza):
            return raise_error(log.info, stanza)

        room_jid = stanza.getFrom()
        query = stanza.getTag('query', namespace=NS_MUC_ADMIN)
        items = query.getTags('item')
        users_dict = {}
        for item in items:
            try:
                jid = validate_jid(item.getAttr('jid'))
            except InvalidJid as error:
                log.exception(error)
                continue

            users_dict[jid] = {}
            if item.has_attr('nick'):
                users_dict[jid]['nick'] = item.getAttr('nick')
            if item.has_attr('role'):
                users_dict[jid]['role'] = item.getAttr('role')
            reason = item.getTagData('reason')
            if reason:
                users_dict[jid]['reason'] = reason

        log.info('Affiliations received from %s: %s',
                 room_jid, users_dict)

        return AffiliationResult(jid=room_jid, users=users_dict)

    @call_on_response('_default_response')
    def destroy(self, room_jid, reason='', jid=''):
        iq = Iq(typ='set', queryNS=NS_MUC_OWNER, to=room_jid)
        destroy = iq.setQuery().setTag('destroy')
        if reason:
            destroy.setTagData('reason', reason)
        if jid:
            destroy.setAttr('jid', jid)
        log.info('Destroy room: %s, reason: %s, alternate: %s',
                 room_jid, reason, jid)
        return iq

    @call_on_response('_default_response')
    def set_config(self, room_jid, form):
        iq = Iq(typ='set', to=room_jid, queryNS=NS_MUC_OWNER)
        query = iq.setQuery()
        form.setAttr('type', 'submit')
        query.addChild(node=form)
        log.info('Set config for %s', room_jid)
        return iq

    @call_on_response('_config_received')
    def request_config(self, room_jid):
        iq = Iq(typ='get',
                queryNS=NS_MUC_OWNER,
                to=room_jid)
        log.info('Request config for %s', room_jid)
        return iq

    @callback
    def _config_received(self, stanza):
        if not isResultNode(stanza):
            return raise_error(log.info, stanza)

        jid = stanza.getFrom()
        payload = stanza.getQueryPayload()

        for form in payload:
            if form.getNamespace() == NS_DATA:
                dataform = extend_form(node=form)
                log.info('Config form received for %s', jid)
                return MucConfigResult(jid=jid,
                                       form=dataform)
        return MucConfigResult(jid=jid)

    @call_on_response('_default_response')
    def cancel_config(self, room_jid):
        cancel = Node(tag='x', attrs={'xmlns': NS_DATA, 'type': 'cancel'})
        iq = Iq(typ='set',
                queryNS=NS_MUC_OWNER,
                payload=cancel,
                to=room_jid)
        log.info('Cancel config for %s', room_jid)
        return iq

    @call_on_response('_default_response')
    def set_affiliation(self, room_jid, users_dict):
        iq = Iq(typ='set', to=room_jid, queryNS=NS_MUC_ADMIN)
        item = iq.setQuery()
        for jid in users_dict:
            affiliation = users_dict[jid].get('affiliation')
            reason = users_dict[jid].get('reason')
            nick = users_dict[jid].get('nick')
            item_tag = item.addChild('item', {'jid': jid,
                                              'affiliation': affiliation})
            if reason is not None:
                item_tag.setTagData('reason', reason)

            if nick is not None:
                item_tag.setAttr('nick', nick)
        log.info('Set affiliation for %s: %s', room_jid, users_dict)
        return iq

    @call_on_response('_default_response')
    def set_role(self, room_jid, nick, role, reason=''):
        iq = Iq(typ='set', to=room_jid, queryNS=NS_MUC_ADMIN)
        item = iq.setQuery().setTag('item')
        item.setAttr('nick', nick)
        item.setAttr('role', role)
        if reason:
            item.addChild(name='reason', payload=reason)
        log.info('Set role for %s: %s %s %s', room_jid, nick, role, reason)
        return iq

    def set_subject(self, room_jid, subject):
        message = Message(room_jid, typ='groupchat', subject=subject)
        log.info('Set subject for %s', room_jid)
        self._client.send(message)

    def decline(self, room, to, reason=None):
        message = Message(to=room)
        muc_user = message.addChild('x', namespace=NS_MUC_USER)
        decline = muc_user.addChild('decline', attrs={'to': to})
        if reason:
            decline.setTagData('reason', reason)
        self._client.send(message)

    def request_voice(self, room):
        message = Message(to=room)
        xdata = DataForm(typ='submit')
        xdata.addChild(node=DataField(name='FORM_TYPE',
                                      value=NS_MUC_REQUEST))
        xdata.addChild(node=DataField(name='muc#role',
                                      value='participant',
                                      typ='text-single'))
        message.addChild(node=xdata)
        self._client.send(message)

    def invite(self, room, to, password, reason=None, continue_=False,
               type_=InviteType.MEDIATED):
        if type_ == InviteType.DIRECT:
            invite = self._build_direct_invite(
                room, to, reason, password, continue_)
        else:
            invite = self._build_mediated_invite(
                room, to, reason, password, continue_)
        self._client.send(invite)

    @staticmethod
    def _build_direct_invite(room, to, reason, password, continue_):
        message = Message(to=to)
        attrs = {'jid': room}
        if reason:
            attrs['reason'] = reason
        if continue_:
            attrs['continue'] = 'true'
        if password:
            attrs['password'] = password
        message.addChild(name='x', attrs=attrs,
                         namespace=NS_CONFERENCE)
        return message

    @staticmethod
    def _build_mediated_invite(room, to, reason, password, continue_):
        message = Message(to=room)
        muc_user = message.addChild('x', namespace=NS_MUC_USER)
        invite = muc_user.addChild('invite', attrs={'to': to})
        if continue_:
            invite.addChild(name='continue')
        if reason:
            invite.setTagData('reason', reason)
        if password:
            muc_user.setTagData('password', password)
        return message

    def send_captcha(self, room_jid, form_node):
        iq = Iq(typ='set', to=room_jid)
        captcha = iq.addChild(name='captcha', namespace=NS_CAPTCHA)
        captcha.addChild(node=form_node)
        self._client.send(iq)

    @callback
    def _default_response(self, stanza):
        if not isResultNode(stanza):
            return raise_error(log.info, stanza)
        return CommonResult(jid=stanza.getFrom())

    @staticmethod
    def _parse_muc_user(muc_user):
        item = muc_user.getTag('item')
        if item is not None:
            item_dict = item.getAttrs(copy=True)
            if 'role' in item_dict:
                item_dict['role'] = Role(item_dict['role'])
            else:
                item_dict['role'] = None

            if 'affiliation' in item_dict:
                item_dict['affiliation'] = Affiliation(item_dict['affiliation'])
            else:
                item_dict['affiliation'] = None

            if 'jid' in item_dict:
                item_dict['jid'] = JID(item_dict['jid'])
            else:
                item_dict['jid'] = None

            item_dict['actor'] = item.getTagAttr('actor', 'nick')
            item_dict['reason'] = item.getTagData('reason')
            return MucUserData(**item_dict)
