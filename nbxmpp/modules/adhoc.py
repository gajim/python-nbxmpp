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
    def execute_command(self, command, action=None, dataform=None):
        _task = yield

        if action is None:
            action = AdHocAction.EXECUTE
        attrs = {'node': command.node,
                 'xmlns': Namespace.COMMANDS,
                 'action': action.value}
        if command.sessionid is not None:
            attrs['sessionid'] = command.sessionid

        response = yield _make_command(command, attrs, dataform)
        if response.isError():
            raise StanzaError(response)

        command = response.getTag('command', namespace=Namespace.COMMANDS)
        if command is None:
            raise MalformedStanzaError('command node missing', response)

        attrs = command.getAttrs()
        notes = []
        actions = []
        try:
            for note in command.getTags('note'):
                type_ = note.getAttr('type')
                if type_ is not None:
                    type_ = AdHocNoteType(note.getAttr('type'))
                notes.append(AdHocCommandNote(text=note.getData(),
                                              type=type_))

            default = None
            actions_ = command.getTag('actions')
            if actions_ is not None:
                for action_ in actions_.getChildren():
                    actions.append(AdHocAction(action_.getName()))

                default = actions_.getAttr('execute')
                if default is not None:
                    default = AdHocAction(default)
                    if default not in actions:
                        default = None

            yield AdHocCommand(
                jid=str(response.getFrom()),
                name=None,
                node=attrs['node'],
                sessionid=attrs.get('sessionid'),
                status=AdHocStatus(attrs['status']),
                data=command.getTag('x', namespace=Namespace.DATA),
                actions=actions,
                default=default,
                notes=notes)
        except Exception as error:
            raise MalformedStanzaError(str(error), response)


def _make_command(command, attrs, dataform):
    command_node = Node('command', attrs=attrs)
    if dataform is not None:
        command_node.addChild(node=dataform)
    iq = Iq('set', to=command.jid)
    iq.addChild(node=command_node)
    return iq
