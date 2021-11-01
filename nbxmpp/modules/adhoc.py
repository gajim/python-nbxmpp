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

from typing import Any, Generator
from typing import Union
from typing import Optional

from nbxmpp import types
from nbxmpp.namespaces import Namespace
from nbxmpp.jid import JID
from nbxmpp.structs import AdHocCommand
from nbxmpp.structs import AdHocCommandNote
from nbxmpp.const import AdHocStatus
from nbxmpp.const import AdHocAction
from nbxmpp.const import AdHocNoteType
from nbxmpp.errors import StanzaError
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.task import iq_request_task
from nbxmpp.builder import Iq
from nbxmpp.elements import Base
from nbxmpp.modules.discovery import get_disco_request
from nbxmpp.modules.base import BaseModule


CommandListGenerator = Generator[Union[types.Iq, list[AdHocCommand]],
                                 types.Iq,
                                 None]

ExcecuteCommandGenerator = Generator[Union[types.Iq, AdHocCommand],
                                     types.Iq,
                                     None]


class AdHoc(BaseModule):
    def __init__(self, client: types.Client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = []

    @iq_request_task
    def request_command_list(self,
                             jid: Optional[JID] = None) -> CommandListGenerator:

        if jid is None:
            jid = self._client.get_bound_jid().new_as_bare()

        response = yield get_disco_request(Namespace.DISCO_ITEMS,
                                           jid,
                                           node=Namespace.COMMANDS)
        if response.is_error():
            raise StanzaError(response)

        query = response.get_query(namespace=Namespace.DISCO_ITEMS,
                                   node=Namespace.COMMANDS)
        if query is None:
            raise MalformedStanzaError('invalid result received', response)

        command_list: list[AdHocCommand] = []

        for item in query.iter_tags('item'):
            try:
                command_list.append(AdHocCommand(**item.get_attribs()))
            except Exception as error:
                raise MalformedStanzaError(f'invalid item attributes: {error}',
                                           response)

        yield command_list

    @iq_request_task
    def execute_command(self,
                        cmd: AdHocCommand,
                        action: Optional[AdHocAction] = None,
                        dataform: Optional[Any] = None) -> ExcecuteCommandGenerator:

        if action is None:
            action = AdHocAction.EXECUTE
        attrs = {'node': cmd.node,
                 'xmlns': Namespace.COMMANDS,
                 'action': action.value}
        if cmd.sessionid is not None:
            attrs['sessionid'] = cmd.sessionid

        response = yield _make_command(cmd, attrs, dataform)
        if response.is_error():
            raise StanzaError(response)

        command = response.find_tag('command', namespace=Namespace.COMMANDS)
        if command is None:
            raise MalformedStanzaError('command node missing', response)

        node = command.get('node')
        if node is None:
            raise MalformedStanzaError('node attribute missing', response)

        status = command.get('status')
        if status is None:
            raise MalformedStanzaError('status attribute missing', response)

        if status not in ('executing', 'completed', 'canceled'):
            raise MalformedStanzaError('invalid status attribute %s' % status,
                                       response)

        status = AdHocStatus(status)

        sessionid = command.get('sessionid')
        if sessionid is None and _expect_sessionid(status, cmd.sessionid):
            raise MalformedStanzaError('sessionid attribute missing', response)

        try:
            notes = _parse_notes(command)
        except ValueError as error:
            raise MalformedStanzaError(error, response)

        try:
            actions, default = _parse_actions(command)
        except ValueError as error:
            raise MalformedStanzaError(error, response)

        yield AdHocCommand(
            jid=response.get_from(),
            name=None,
            node=node,
            sessionid=sessionid,
            status=status,
            data=command.find_tag('x', namespace=Namespace.DATA),
            actions=actions,
            default=default,
            notes=notes)


def _make_command(command: AdHocCommand, attrs, dataform: Any) -> types.Iq:
    iq = Iq(to=command.jid,
            type='set')
    cmd = iq.add_tag('command', **attrs)
    if dataform is not None:
        cmd.append(dataform)
    return iq


def _parse_notes(command: Base) -> list[AdHocCommandNote]:
    notes: list[AdHocCommandNote] = []
    for note in command.find_tags('note'):
        type_ = note.get('type')
        if type_ is None:
            type_ = 'info'

        if type_ not in ('info', 'warn', 'error'):
            raise ValueError('invalid note type %s' % type_)

        notes.append(AdHocCommandNote(text=note.text or '',
                                      type=AdHocNoteType(type_)))
    return notes


def _parse_actions(command: Base) -> tuple[set[AdHocAction], Optional[AdHocAction]]:
    if command.get('status') != 'executing':
        return set(), None

    actions_node = command.find_tag('actions')
    if actions_node is None:
        # If there is no <actions/> element,
        # the user-agent can use a single-stage dialog or view.
        # The action "execute" is equivalent to the action "complete".
        return {AdHocAction.CANCEL, AdHocAction.COMPLETE}, AdHocAction.COMPLETE

    default = actions_node.get('execute')
    if default is None:
        # If the "execute" attribute is absent, it defaults to "next".
        default = 'next'

    if default not in ('prev', 'next', 'complete'):
        raise ValueError('invalid execute attribute %s' % default)

    default = AdHocAction(default)

    # We use a set because it cannot contain duplicates
    actions: set[AdHocAction] = set()
    for action in actions_node.get_children():
        name = action.name
        if name == 'execute':
            actions.add(default)

        if name in ('prev', 'next', 'complete'):
            actions.add(AdHocAction(name))

    if not actions:
        raise ValueError('actions element without actions')

    # The action "cancel" is always allowed.
    actions.add(AdHocAction.CANCEL)

    # A form which has an <actions/> element and an "execute" attribute
    # which evaluates (taking the default into account if absent) to an
    # action which is not allowed is therefore invalid.
    if default not in actions:
        # Some implementations don’t respect this rule.
        # Take the first action so we don’t fail here.
        for act in actions:
            default = act
            break

    return actions, default


def _expect_sessionid(status: AdHocStatus,
                      sent_sessionid: Optional[str]) -> bool:

    # Session id should only be expected for multiple stage commands
    # or when we initialize the session (set the session attribute)
    return status != status.COMPLETED or sent_sessionid is not None
