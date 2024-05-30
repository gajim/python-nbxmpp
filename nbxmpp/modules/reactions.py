# Copyright (C) 2022 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from nbxmpp.modules.base import BaseModule
from nbxmpp.namespaces import Namespace
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import Reactions as ReactionStruct
from nbxmpp.structs import StanzaHandler

if TYPE_CHECKING:
    from nbxmpp.client import Client
    from nbxmpp.protocol import Message


class Reactions(BaseModule):
    def __init__(self, client: Client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(
                name="message",
                callback=self._process_message_reaction,
                ns=Namespace.REACTIONS,
                priority=15,
            ),
        ]

    def _process_message_reaction(
        self, _client: Client, stanza: Message, properties: MessageProperties
    ) -> None:
        reactions = stanza.getTag("reactions", namespace=Namespace.REACTIONS)

        if reactions is None:
            return

        id_ = reactions.getAttr("id")
        if not id_:
            self._log.warning("Reactions without ID")
            return

        emojis: set[str] = set()
        for reaction in reactions.getTags("reaction"):
            # we strip for clients that might add white spaces and/or
            # new lines in the reaction content.
            emoji = reaction.getData().strip()
            if emoji:
                emojis.add(emoji)
            else:
                self._log.warning("Empty reaction")
                self._log.warning(stanza)

        properties.reactions = ReactionStruct(id_, emojis)
