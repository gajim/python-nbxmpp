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
from nbxmpp.protocol import isResultNode
from nbxmpp.protocol import Node
from nbxmpp.util import call_on_response
from nbxmpp.util import callback
from nbxmpp.util import raise_error
from nbxmpp.structs import AdHocCommand
from nbxmpp.structs import AdHocCommandNote
from nbxmpp.const import AdHocStatus
from nbxmpp.const import AdHocAction
from nbxmpp.const import AdHocNoteType
from nbxmpp.modules.discovery import get_disco_request
from nbxmpp.modules.base import BaseModule


class AdHoc(BaseModule):
    def __init__(self, client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = []

    @call_on_response('_command_list_received')
    def request_command_list(self, jid=None):
        if jid is None:
            jid = self._client.get_bound_jid().bare
        return get_disco_request(Namespace.DISCO_ITEMS,
                                 jid,
                                 node=Namespace.COMMANDS)

    @callback
    def _command_list_received(self, stanza):
        if not isResultNode(stanza):
            return raise_error(self._log.info, stanza)

        payload = stanza.getQueryPayload()
        if payload is None:
            return raise_error(self._log.warning, stanza, 'stanza-malformed')

        command_list = []
        for item in payload:
            if item.getName() != 'item':
                continue
            try:
                command_list.append(AdHocCommand(**item.getAttrs()))
            except Exception as error:
                self._log.warning(error)
                return raise_error(self._log.warning,
                                   stanza,
                                   'stanza-malformed')

        return command_list

    @call_on_response('_command_result_received')
    def execute_command(self, command, action=None, dataform=None):
        if action is None:
            action = AdHocAction.EXECUTE
        attrs = {'node': command.node,
                 'xmlns': Namespace.COMMANDS,
                 'action': action.value}
        if command.sessionid is not None:
            attrs['sessionid'] = command.sessionid

        command_node = Node('command', attrs=attrs)
        if dataform is not None:
            command_node.addChild(node=dataform)
        iq = Iq('set', to=command.jid)
        iq.addChild(node=command_node)
        return iq

    @callback
    def _command_result_received(self, stanza):
        if not isResultNode(stanza):
            return raise_error(self._log.info, stanza)

        command = stanza.getTag('command', namespace=Namespace.COMMANDS)
        if command is None:
            return raise_error(self._log.warning, stanza, 'stanza-malformed')

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

            actions_ = command.getTag('actions')
            if actions_ is not None:
                for action in actions_.getChildren():
                    actions.append(AdHocAction(action.getName()))

            return AdHocCommand(
                jid=str(stanza.getFrom()),
                name=None,
                node=attrs['node'],
                sessionid=attrs.get('sessionid'),
                status=AdHocStatus(attrs['status']),
                data=command.getTag('x', namespace=Namespace.DATA),
                actions=actions,
                notes=notes)
        except Exception as error:
            self._log.warning(error)
            return raise_error(self._log.warning, stanza, 'stanza-malformed')
