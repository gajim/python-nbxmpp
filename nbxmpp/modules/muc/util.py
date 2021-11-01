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

from typing import Optional

from dataclasses import dataclass

from nbxmpp import types
from nbxmpp.namespaces import Namespace
from nbxmpp.builder import Iq
from nbxmpp.jid import JID
from nbxmpp.exceptions import InvalidJid
from nbxmpp.exceptions import StanzaMalformed
from nbxmpp.builder import Message
from nbxmpp.const import Affiliation
from nbxmpp.const import Role
from nbxmpp.structs import MucUserData


@dataclass
class MucInfoResult:
    info: object
    vcard: object = None
    redirected: bool = False


def make_affiliation_request(jid: JID, affiliation: str) -> types.Iq:
    iq = Iq(to=jid)
    query = iq.add_query(namespace=Namespace.MUC_ADMIN)
    item = query.add_tag('item')
    item.set('affiliation', affiliation)
    return iq


def make_set_affiliation_request(room_jid: JID,
                                 users_dict: dict[JID, dict[str, str]]) -> types.Iq:

    iq = Iq(to=room_jid, type='set')
    query = iq.add_query(namespace=Namespace.MUC_ADMIN)

    for jid, values in users_dict.items():
        affiliation = values.get('affiliation')
        reason = values.get('reason')
        nick = values.get('nick')

        item = query.add_tag('item', jid=str(jid), affiliation=affiliation)
        if reason is not None:
            item.add_tag_text('reason', reason)

        if nick is not None:
            item.set('nick', nick)

    return iq


def make_destroy_request(room_jid: JID,
                         reason: Optional[str],
                         jid: Optional[JID]) -> types.Iq:

    iq = Iq(to=room_jid, type='set')
    query = iq.add_query(namespace=Namespace.MUC_OWNER)
    destroy = query.add_tag('destroy')

    if reason:
        destroy.add_tag_text('reason', reason)

    if jid:
        destroy.set('jid', str(jid))

    return iq


def make_set_config_request(room_jid: JID, form: types.DataForm) -> types.Iq:
    iq = Iq(to=room_jid, type='set')
    query = iq.add_query(namespace=Namespace.MUC_OWNER)
    form.set_type('submit')
    query.append(form)
    return iq


def make_config_request(room_jid: JID) -> types.Iq:
    iq = Iq(to=room_jid)
    iq.add_query(namespace=Namespace.MUC_OWNER)
    return iq


def make_cancel_config_request(room_jid: JID) -> types.Iq:
    iq = Iq(to=room_jid, type='set')
    query = iq.add_query(namespace=Namespace.MUC_OWNER)
    query.add_tag('x', namespace=Namespace.DATA, type='cancel')
    return iq


def make_set_role_request(room_jid: JID, nick: str, role: str, reason: Optional[str]) -> types.Iq:
    iq = Iq(to=room_jid, type='set')
    query = iq.add_query(namespace=Namespace.MUC_ADMIN)
    item = query.add_tag('item', nick=nick, role=role)
    if reason:
        item.add_tag_text('reason', reason)

    return iq


def make_captcha_request(room_jid: JID, form_node: types.DataForm) -> types.Iq:
    iq = Iq(to=room_jid, type='set')
    captcha = iq.add_tag('captcha', namespace=Namespace.CAPTCHA)
    captcha.append(form_node)
    return iq


def build_direct_invite(room: JID,
                        to: JID,
                        reason: Optional[str],
                        password: str,
                        continue_: bool) -> types.Message:

    message = Message(to=to)
    conference = message.add_tag('x',
                                 namespace=Namespace.CONFERENCE,
                                 jid=str(room))
    if reason:
        conference.set('reason', reason)
    if continue_:
        conference.set('continue', 'true')
    if password:
        conference.set('password', password)

    return message


def build_mediated_invite(room: JID,
                          to: JID,
                          reason: Optional[str],
                          password: str,
                          continue_: bool) -> types.Message:

    message = Message(to=room)
    muc_user = message.add_tag('x', namespace=Namespace.MUC_USER)
    invite = muc_user.add_tag('invite', to=str(to))
    if continue_:
        invite.add_tag('continue')
    if reason:
        invite.add_tag_text('reason', reason)
    if password:
        muc_user.add_tag_text('password', password)
    return message


def parse_muc_user(muc_user: types.Base,
                   is_presence: bool = True) -> Optional[MucUserData]:

    item = muc_user.find_tag('item')
    if item is None:
        return None

    item_dict = item.get_attribs()

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
                       nick=item.get('nick'),
                       role=role,
                       actor=item.find_tag_attr('actor', 'nick'),
                       reason=item.find_tag_text('reason'))
