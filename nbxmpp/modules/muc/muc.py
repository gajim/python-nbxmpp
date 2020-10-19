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
from nbxmpp.protocol import Message
from nbxmpp.protocol import DataForm
from nbxmpp.protocol import DataField
from nbxmpp.protocol import NodeProcessed
from nbxmpp.protocol import StanzaMalformed
from nbxmpp.structs import StanzaHandler
from nbxmpp.const import InviteType
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
from nbxmpp.modules.util import raise_if_error
from nbxmpp.modules.util import parse_xmpp_uri
from nbxmpp.modules.util import process_response
from nbxmpp.modules.dataforms import extend_form
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


class MUC(BaseModule):

    _depends = {
        'disco_info': 'Discovery',
        'request_vcard': 'VCardTemp',
    }

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

    def _process_groupchat_message(self, _client, stanza, properties):
        properties.from_muc = True
        properties.muc_jid = properties.jid.new_as_bare()
        properties.muc_nickname = properties.jid.resource

        muc_user = stanza.getTag('x', namespace=Namespace.MUC_USER)
        if muc_user is not None:
            try:
                properties.muc_user = parse_muc_user(muc_user,
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

    @iq_request_task
    def get_affiliation(self, jid, affiliation):
        _task = yield

        response = yield make_affiliation_request(jid, affiliation)
        if response.isError():
            raise StanzaError(response)

        room_jid = response.getFrom()
        query = response.getTag('query', namespace=Namespace.MUC_ADMIN)
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

        yield AffiliationResult(jid=room_jid, users=users_dict)

    @iq_request_task
    def destroy(self, room_jid, reason=None, jid=None):
        _task = yield

        response = yield make_destroy_request(room_jid, reason, jid)
        yield process_response(response)

    @iq_request_task
    def request_info(self, jid, request_vcard=True, allow_redirect=False):
        _task = yield

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
    def set_config(self, room_jid, form):
        _task = yield

        response = yield make_set_config_request(room_jid, form)
        yield process_response(response)

    @iq_request_task
    def request_config(self, room_jid):
        task = yield

        response = yield make_config_request(room_jid)
        if response.isError():
            raise StanzaError(response)

        jid = response.getFrom()
        payload = response.getQueryPayload()

        for form in payload:
            if form.getNamespace() == Namespace.DATA:
                dataform = extend_form(node=form)
                self._log.info('Config form received for %s', jid)
                yield MucConfigResult(jid=jid, form=dataform)

        yield MucConfigResult(jid=jid)

    @iq_request_task
    def cancel_config(self, room_jid):
        _task = yield

        response = yield make_cancel_config_request(room_jid)
        yield process_response(response)

    @iq_request_task
    def set_affiliation(self, room_jid, users_dict):
        _task = yield

        response = yield make_set_affiliation_request(room_jid, users_dict)
        yield process_response(response)

    @iq_request_task
    def set_role(self, room_jid, nick, role, reason=None):
        _task = yield

        response = yield make_set_role_request(room_jid, nick, role, reason)
        yield process_response(response)

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
            invite = build_direct_invite(
                room, to, reason, password, continue_)
        else:
            invite = build_mediated_invite(
                room, to, reason, password, continue_)
        return self._client.send_stanza(invite)

    @iq_request_task
    def send_captcha(self, room_jid, form_node):
        _task = yield

        response = yield make_captcha_request(room_jid, form_node)
        yield process_response(response)

    def cancel_captcha(self, room_jid, message_id):
        message = Message(typ='error', to=room_jid)
        message.setID(message_id)
        message.setError(ERR_NOT_ACCEPTABLE)
        self._client.send_stanza(message)
