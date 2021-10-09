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

from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Iq
from nbxmpp.protocol import Node
from nbxmpp.structs import AdHocCommand
from nbxmpp.structs import AdHocCommandNote
from nbxmpp.const import AdHocStatus
from nbxmpp.const import AdHocAction
from nbxmpp.const import AdHocNoteType
from nbxmpp.errors import StanzaError
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.task import iq_request_task
from nbxmpp.modules.discovery import get_disco_request
from nbxmpp.modules.base import BaseModule


class AdHoc(BaseModule):
    def __init__(self, client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = []

    @iq_request_task
    def request_command_list(self, jid=None):
        _task = yield

        if jid is None:
            jid = self._client.get_bound_jid().bare
        response = yield get_disco_request(Namespace.DISCO_ITEMS,
                                           jid,
                                           node=Namespace.COMMANDS)
        if response.isError():
            raise StanzaError(response)

        payload = response.getQueryPayload()
        if payload is None:
            raise MalformedStanzaError('query payload missing', response)

        command_list = []
        for item in payload:
            if item.getName() != 'item':
                continue
            try:
                command_list.append(AdHocCommand(**item.getAttrs()))
            except Exception as error:
                raise MalformedStanzaError(f'invalid item attributes: {error}',
                                           response)

        yield command_list

    @iq_request_task
    def execute_command(self, cmd, action=None, dataform=None):
        _task = yield

        if action is None:
            action = AdHocAction.EXECUTE
        attrs = {'node': cmd.node,
                 'xmlns': Namespace.COMMANDS,
                 'action': action.value}
        if cmd.sessionid is not None:
            attrs['sessionid'] = cmd.sessionid

        response = yield _make_command(cmd, attrs, dataform)
        if response.isError():
            raise StanzaError(response)

        command = response.getTag('command', namespace=Namespace.COMMANDS)
        if command is None:
            raise MalformedStanzaError('command node missing', response)

        node = command.getAttr('node')
        if node is None:
            raise MalformedStanzaError('node attribute missing', response)

        status = command.getAttr('status')
        if status is None:
            raise MalformedStanzaError('status attribute missing', response)

        if status not in ('executing', 'completed', 'canceled'):
            raise MalformedStanzaError('invalid status attribute %s' % status,
                                       response)

        status = AdHocStatus(status)

        sessionid = command.getAttr('sessionid')
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
            jid=response.getFrom(),
            name=None,
            node=node,
            sessionid=sessionid,
            status=status,
            data=command.getTag('x', namespace=Namespace.DATA),
            actions=actions,
            default=default,
            notes=notes)


def _make_command(command, attrs, dataform):
    command_node = Node('command', attrs=attrs)
    if dataform is not None:
        command_node.addChild(node=dataform)
    iq = Iq('set', to=command.jid)
    iq.addChild(node=command_node)
    return iq


def _parse_notes(command):
    notes = []
    for note in command.getTags('note'):
        type_ = note.getAttr('type')
        if type_ is None:
            type_ = 'info'

        if type_ not in ('info', 'warn', 'error'):
            raise ValueError('invalid note type %s' % type_)

        notes.append(AdHocCommandNote(text=note.getData(),
                                      type=AdHocNoteType(type_)))
    return notes


def _parse_actions(command):
    if command.getAttr('status') != 'executing':
        return set(), None

    actions_node = command.getTag('actions')
    if actions_node is None:
        # If there is no <actions/> element,
        # the user-agent can use a single-stage dialog or view.
        # The action "execute" is equivalent to the action "complete".
        return {AdHocAction.CANCEL, AdHocAction.COMPLETE}, AdHocAction.COMPLETE

    default = actions_node.getAttr('execute')
    if default is None:
        # If the "execute" attribute is absent, it defaults to "next".
        default = 'next'

    if default not in ('prev', 'next', 'complete'):
        raise ValueError('invalid execute attribute %s' % default)

    default = AdHocAction(default)

    # We use a set because it cannot contain duplicates
    actions = set()
    for action in actions_node.getChildren():
        name = action.getName()
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


def _expect_sessionid(status, sent_sessionid):
    # Session id should only be expected for multiple stage commands
    # or when we initialize the session (set the session attribute)
    return status != status.COMPLETED or sent_sessionid is not None
