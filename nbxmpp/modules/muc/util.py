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


from dataclasses import dataclass

from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Iq
from nbxmpp.protocol import JID
from nbxmpp.protocol import InvalidJid
from nbxmpp.protocol import StanzaMalformed
from nbxmpp.protocol import Message
from nbxmpp.simplexml import Node
from nbxmpp.const import Affiliation
from nbxmpp.const import Role
from nbxmpp.structs import MucUserData


@dataclass
class MucInfoResult:
    info: object
    vcard: object = None
    redirected: bool = False


def make_affiliation_request(jid, affiliation):
    iq = Iq(typ='get', to=jid, queryNS=Namespace.MUC_ADMIN)
    item = iq.setQuery().setTag('item')
    item.setAttr('affiliation', affiliation)
    return iq


def make_set_affiliation_request(room_jid, users_dict):
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

    return iq


def make_destroy_request(room_jid, reason, jid):
    iq = Iq(typ='set', queryNS=Namespace.MUC_OWNER, to=room_jid)
    destroy = iq.setQuery().setTag('destroy')

    if reason:
        destroy.setTagData('reason', reason)

    if jid:
        destroy.setAttr('jid', jid)

    return iq


def make_set_config_request(room_jid, form):
    iq = Iq(typ='set', to=room_jid, queryNS=Namespace.MUC_OWNER)
    query = iq.setQuery()
    form.setAttr('type', 'submit')
    query.addChild(node=form)
    return iq


def make_config_request(room_jid):
    iq = Iq(typ='get',
            queryNS=Namespace.MUC_OWNER,
            to=room_jid)
    return iq


def make_cancel_config_request(room_jid):
    cancel = Node(tag='x', attrs={'xmlns': Namespace.DATA,
                                  'type': 'cancel'})
    iq = Iq(typ='set',
            queryNS=Namespace.MUC_OWNER,
            payload=cancel,
            to=room_jid)
    return iq


def make_set_role_request(room_jid, nick, role, reason):
    iq = Iq(typ='set', to=room_jid, queryNS=Namespace.MUC_ADMIN)
    item = iq.setQuery().setTag('item')
    item.setAttr('nick', nick)
    item.setAttr('role', role)
    if reason:
        item.addChild(name='reason', payload=reason)

    return iq


def make_captcha_request(room_jid, form_node):
    iq = Iq(typ='set', to=room_jid)
    captcha = iq.addChild(name='captcha', namespace=Namespace.CAPTCHA)
    captcha.addChild(node=form_node)
    return iq


def build_direct_invite(room, to, reason, password, continue_):
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


def build_mediated_invite(room, to, reason, password, continue_):
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


def parse_muc_user(muc_user, is_presence=True):
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
            jid = JID.from_string(jid, force_bare=True)
        except InvalidJid as error:
            raise StanzaMalformed('invalid jid %s, %s' % (jid, error))

    return MucUserData(affiliation=affiliation,
                       jid=jid,
                       nick=item.getAttr('nick'),
                       role=role,
                       actor=item.getTagAttr('actor', 'nick'),
                       reason=item.getTagData('reason'))
