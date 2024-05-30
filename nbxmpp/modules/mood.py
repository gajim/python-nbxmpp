# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from nbxmpp.const import MOODS
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.util import finalize
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Message
from nbxmpp.protocol import Node
from nbxmpp.protocol import NodeProcessed
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import MoodData
from nbxmpp.structs import StanzaHandler
from nbxmpp.task import iq_request_task

if TYPE_CHECKING:
    from nbxmpp.client import Client


class Mood(BaseModule):

    _depends = {"publish": "PubSub"}

    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(
                name="message",
                callback=self._process_pubsub_mood,
                ns=Namespace.PUBSUB_EVENT,
                priority=16,
            ),
        ]

    def _process_pubsub_mood(
        self, _client: Client, stanza: Message, properties: MessageProperties
    ) -> None:
        if not properties.is_pubsub_event:
            return

        if properties.pubsub_event.node != Namespace.MOOD:
            return

        item = properties.pubsub_event.item
        if item is None:
            # Retract, Deleted or Purged
            return

        mood_node = item.getTag("mood", namespace=Namespace.MOOD)
        if not mood_node.getChildren():
            self._log.info("Received mood: %s - removed mood", properties.jid)
            return

        mood, text = None, None
        for child in mood_node.getChildren():
            name = child.getName().strip()
            if name == "text":
                text = child.getData()
            elif name in MOODS:
                mood = name

        if mood is None and mood_node.getChildren():
            self._log.warning("No valid mood value found")
            self._log.warning(stanza)
            raise NodeProcessed

        data = MoodData(mood, text)
        pubsub_event = properties.pubsub_event._replace(data=data)
        self._log.info("Received mood: %s - %s", properties.jid, data)

        properties.pubsub_event = pubsub_event

    @iq_request_task
    def set_mood(self, data: MoodData):
        task = yield

        item = Node("mood", {"xmlns": Namespace.MOOD})
        if data is not None and data.mood:
            item.addChild(data.mood)

            if data.text:
                item.addChild("text", payload=data.text)

        result = yield self.publish(Namespace.MOOD, item, id_="current")

        yield finalize(task, result)
