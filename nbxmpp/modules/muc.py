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

from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import ERR_NOT_ACCEPTABLE
from nbxmpp.protocol import JID
from nbxmpp.protocol import Iq
from nbxmpp.protocol import Message
from nbxmpp.protocol import DataForm
from nbxmpp.protocol import DataField
from nbxmpp.protocol import isResultNode
from nbxmpp.protocol import NodeProcessed
from nbxmpp.protocol import StanzaMalformed
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
from nbxmpp.util import call_on_response
from nbxmpp.util import callback
from nbxmpp.util import raise_error
from nbxmpp.modules.dataforms import extend_form
from nbxmpp.modules.base import BaseModule


class MUC(BaseModule):
    def __init__(self, client):
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
    def _process_muc_presence(_client, stanza, properties):
        muc = stanza.getTag('x', namespace=Namespace.MUC)
        if muc is None:
            return
        properties.from_muc = True
        properties.muc_jid = properties.jid.new_as_bare()
        properties.muc_nickname = properties.jid.resource

    def _process_muc_user_presence(self, _client, stanza, properties):
        muc_user = stanza.getTag('x', namespace=Namespace.MUC_USER)
        if muc_user is None:
            return
        properties.from_muc = True
        properties.muc_jid = properties.jid.new_as_bare()

        destroy = muc_user.getTag('destroy')
        if destroy is not None:
            alternate = destroy.getAttr('jid')
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
                reason=muc_user.getTagData('reason'),
                password=muc_user.getTagData('password'))
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
        for status in muc_user.getTags('status'):
            try:
                code = StatusCode(status.getAttr('code'))
            except ValueError:
                self._log.warning('Received invalid status code: %s',
                                  status.getAttr('code'))
                self._log.warning(stanza)
                continue
            if code in message_status_codes:
                codes.add(code)

        if codes:
            properties.muc_status_codes = codes

        try:
            properties.muc_user = self._parse_muc_user(muc_user)
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

    def _process_groupchat_message(self, _client, stanza, properties):
        properties.from_muc = True
        properties.muc_jid = properties.jid.new_as_bare()
        properties.muc_nickname = properties.jid.resource

        muc_user = stanza.getTag('x', namespace=Namespace.MUC_USER)
        if muc_user is not None:
            try:
                properties.muc_user = self._parse_muc_user(muc_user,
                                                           is_presence=False)
            except StanzaMalformed as error:
                self._log.warning(error)
                self._log.warning(stanza)
                raise NodeProcessed

        addresses = stanza.getTag('addresses', namespace=Namespace.ADDRESS)
        if addresses is not None:
            address = addresses.getTag('address', attrs={'type': 'ofrom'})
            if address is not None:
                properties.muc_ofrom = JID.from_string(address.getAttr('jid'))

    def _process_message(self, _client, stanza, properties):
        muc_user = stanza.getTag('x', namespace=Namespace.MUC_USER)
        if muc_user is None:
            return

        # MUC Private message
        if (properties.type.is_chat or
                properties.type.is_error and
                not muc_user.getChildren()):
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
        for status in muc_user.getTags('status'):
            try:
                code = StatusCode(status.getAttr('code'))
            except ValueError:
                self._log.warning('Received invalid status code: %s',
                                  status.getAttr('code'))
                self._log.warning(stanza)
                continue
            if code in message_status_codes:
                codes.add(code)

        if codes:
            properties.muc_status_codes = codes

    @staticmethod
    def _process_direct_invite(_client, stanza, properties):
        direct = stanza.getTag('x', namespace=Namespace.CONFERENCE)
        if direct is None:
            return

        if stanza.getTag('x', namespace=Namespace.MUC_USER) is not None:
            # not a direct invite
            # See https://xmpp.org/extensions/xep-0045.html#example-57
            # read implementation notes
            return

        data = {}
        data['muc'] = JID.from_string(direct.getAttr('jid'))
        data['from_'] = properties.jid
        data['reason'] = direct.getAttr('reason')
        data['password'] = direct.getAttr('password')
        data['continued'] = direct.getAttr('continue') == 'true'
        data['thread'] = direct.getAttr('thread')
        data['type'] = InviteType.DIRECT
        properties.muc_invite = InviteData(**data)

    @staticmethod
    def _process_mediated_invite(_client, stanza, properties):
        muc_user = stanza.getTag('x', namespace=Namespace.MUC_USER)
        if muc_user is None:
            return

        if properties.type != MessageType.NORMAL:
            return

        properties.from_muc = True
        properties.muc_jid = properties.jid.new_as_bare()

        data = {}

        invite = muc_user.getTag('invite')
        if invite is not None:
            data['muc'] = properties.jid.new_as_bare()
            data['from_'] = JID.from_string(invite.getAttr('from'))
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
            data['muc'] = properties.jid.new_as_bare()
            data['from_'] = JID.from_string(decline.getAttr('from'))
            data['reason'] = decline.getTagData('reason')
            properties.muc_decline = DeclineData(**data)
            return

    def _process_voice_request(self, _client, stanza, properties):
        data_form = stanza.getTag('x', namespace=Namespace.DATA)
        if data_form is None:
            return

        data_form = extend_form(data_form)
        try:
            if data_form['FORM_TYPE'].value != Namespace.MUC_REQUEST:
                return
        except KeyError:
            return

        nick = data_form['muc#roomnick'].value

        try:
            jid = JID.from_string(data_form['muc#jid'].value)
        except Exception:
            self._log.warning('Invalid JID on voice request')
            self._log.warning(stanza)
            raise NodeProcessed

        properties.voice_request = VoiceRequest(jid=jid,
                                                nick=nick,
                                                form=data_form)
        properties.from_muc = True
        properties.muc_jid = properties.jid.new_as_bare()

    def approve_voice_request(self, muc_jid, voice_request):
        form = voice_request.form
        form.type_ = 'submit'
        form['muc#request_allow'].value = True
        self._client.send_stanza(Message(to=muc_jid, payload=form))

    @call_on_response('_affiliation_received')
    def get_affiliation(self, jid, affiliation):
        iq = Iq(typ='get', to=jid, queryNS=Namespace.MUC_ADMIN)
        item = iq.setQuery().setTag('item')
        item.setAttr('affiliation', affiliation)
        return iq

    @callback
    def _affiliation_received(self, stanza):
        if not isResultNode(stanza):
            return raise_error(self._log.info, stanza)

        room_jid = stanza.getFrom()
        query = stanza.getTag('query', namespace=Namespace.MUC_ADMIN)
        items = query.getTags('item')
        users_dict = {}
        for item in items:
            try:
                jid = JID.from_string(item.getAttr('jid'))
            except Exception as error:
                self._log.warning('Invalid JID: %s, %s',
                                  item.getAttr('jid'), error)
                continue

            users_dict[jid] = {}
            if item.has_attr('nick'):
                users_dict[jid]['nick'] = item.getAttr('nick')
            if item.has_attr('role'):
                users_dict[jid]['role'] = item.getAttr('role')
            reason = item.getTagData('reason')
            if reason:
                users_dict[jid]['reason'] = reason

        self._log.info('Affiliations received from %s: %s',
                       room_jid, users_dict)

        return AffiliationResult(jid=room_jid, users=users_dict)

    @call_on_response('_default_response')
    def destroy(self, room_jid, reason='', jid=''):
        iq = Iq(typ='set', queryNS=Namespace.MUC_OWNER, to=room_jid)
        destroy = iq.setQuery().setTag('destroy')
        if reason:
            destroy.setTagData('reason', reason)
        if jid:
            destroy.setAttr('jid', jid)
        self._log.info('Destroy room: %s, reason: %s, alternate: %s',
                       room_jid, reason, jid)
        return iq

    @call_on_response('_default_response')
    def set_config(self, room_jid, form):
        iq = Iq(typ='set', to=room_jid, queryNS=Namespace.MUC_OWNER)
        query = iq.setQuery()
        form.setAttr('type', 'submit')
        query.addChild(node=form)
        self._log.info('Set config for %s', room_jid)
        return iq

    @call_on_response('_config_received')
    def request_config(self, room_jid):
        iq = Iq(typ='get',
                queryNS=Namespace.MUC_OWNER,
                to=room_jid)
        self._log.info('Request config for %s', room_jid)
        return iq

    @callback
    def _config_received(self, stanza):
        if not isResultNode(stanza):
            return raise_error(self._log.info, stanza)

        jid = stanza.getFrom()
        payload = stanza.getQueryPayload()

        for form in payload:
            if form.getNamespace() == Namespace.DATA:
                dataform = extend_form(node=form)
                self._log.info('Config form received for %s', jid)
                return MucConfigResult(jid=jid,
                                       form=dataform)
        return MucConfigResult(jid=jid)

    @call_on_response('_default_response')
    def cancel_config(self, room_jid):
        cancel = Node(tag='x', attrs={'xmlns': Namespace.DATA,
                                      'type': 'cancel'})
        iq = Iq(typ='set',
                queryNS=Namespace.MUC_OWNER,
                payload=cancel,
                to=room_jid)
        self._log.info('Cancel config for %s', room_jid)
        return iq

    @call_on_response('_default_response')
    def set_affiliation(self, room_jid, users_dict):
        iq = Iq(typ='set', to=room_jid, queryNS=Namespace.MUC_ADMIN)
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
        self._log.info('Set affiliation for %s: %s', room_jid, users_dict)
        return iq

    @call_on_response('_default_response')
    def set_role(self, room_jid, nick, role, reason=''):
        iq = Iq(typ='set', to=room_jid, queryNS=Namespace.MUC_ADMIN)
        item = iq.setQuery().setTag('item')
        item.setAttr('nick', nick)
        item.setAttr('role', role)
        if reason:
            item.addChild(name='reason', payload=reason)
        self._log.info('Set role for %s: %s %s %s',
                       room_jid, nick, role, reason)
        return iq

    def set_subject(self, room_jid, subject):
        message = Message(room_jid, typ='groupchat', subject=subject)
        self._log.info('Set subject for %s', room_jid)
        self._client.send_stanza(message)

    def decline(self, room, to, reason=None):
        message = Message(to=room)
        muc_user = message.addChild('x', namespace=Namespace.MUC_USER)
        decline = muc_user.addChild('decline', attrs={'to': to})
        if reason:
            decline.setTagData('reason', reason)
        self._client.send_stanza(message)

    def request_voice(self, room):
        message = Message(to=room)
        xdata = DataForm(typ='submit')
        xdata.addChild(node=DataField(name='FORM_TYPE',
                                      value=Namespace.MUC_REQUEST))
        xdata.addChild(node=DataField(name='muc#role',
                                      value='participant',
                                      typ='text-single'))
        message.addChild(node=xdata)
        self._client.send_stanza(message)

    def invite(self, room, to, password, reason=None, continue_=False,
               type_=InviteType.MEDIATED):
        if type_ == InviteType.DIRECT:
            invite = self._build_direct_invite(
                room, to, reason, password, continue_)
        else:
            invite = self._build_mediated_invite(
                room, to, reason, password, continue_)
        return self._client.send_stanza(invite)

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
                         namespace=Namespace.CONFERENCE)
        return message

    @staticmethod
    def _build_mediated_invite(room, to, reason, password, continue_):
        message = Message(to=room)
        muc_user = message.addChild('x', namespace=Namespace.MUC_USER)
        invite = muc_user.addChild('invite', attrs={'to': to})
        if continue_:
            invite.addChild(name='continue')
        if reason:
            invite.setTagData('reason', reason)
        if password:
            muc_user.setTagData('password', password)
        return message

    @call_on_response('_default_response')
    def send_captcha(self, room_jid, form_node):
        iq = Iq(typ='set', to=room_jid)
        captcha = iq.addChild(name='captcha', namespace=Namespace.CAPTCHA)
        captcha.addChild(node=form_node)
        return iq

    def cancel_captcha(self, room_jid, message_id):
        message = Message(typ='error', to=room_jid)
        message.setID(message_id)
        message.setError(ERR_NOT_ACCEPTABLE)
        self._client.send_stanza(message)

    @callback
    def _default_response(self, stanza):
        if not isResultNode(stanza):
            return raise_error(self._log.info, stanza)
        return CommonResult(jid=stanza.getFrom())

    @staticmethod
    def _parse_muc_user(muc_user, is_presence=True):
        item = muc_user.getTag('item')
        if item is None:
            return None

        item_dict = item.getAttrs()

        role = item_dict.get('role')
        if role is not None:
            try:
                role = Role(role)
            except ValueError:
                raise StanzaMalformed('invalid role %s' % role)

        elif is_presence:
            # role attr MUST be included in all presence broadcasts
            raise StanzaMalformed('role attr missing')

        affiliation = item_dict.get('affiliation')
        if affiliation is not None:
            try:
                affiliation = Affiliation(affiliation)
            except ValueError:
                raise StanzaMalformed('invalid affiliation %s' % affiliation)

        elif is_presence:
            # affiliation attr MUST be included in all presence broadcasts
            raise StanzaMalformed('affiliation attr missing')

        jid = item_dict.get('jid')
        if jid is not None:
            try:
                jid = JID.from_string(jid)
            except InvalidJid as error:
                raise StanzaMalformed('invalid jid %s, %s' % (jid, error))

        return MucUserData(affiliation=affiliation,
                           jid=jid,
                           nick=item.getAttr('nick'),
                           role=role,
                           actor=item.getTagAttr('actor', 'nick'),
                           reason=item.getTagData('reason'))
