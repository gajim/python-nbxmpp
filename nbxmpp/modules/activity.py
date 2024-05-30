# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from nbxmpp.const import ACTIVITIES
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.util import finalize
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Message
from nbxmpp.protocol import Node
from nbxmpp.protocol import NodeProcessed
from nbxmpp.structs import ActivityData
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import StanzaHandler
from nbxmpp.task import iq_request_task

if TYPE_CHECKING:
    from nbxmpp.client import Client


class Activity(BaseModule):

    _depends = {"publish": "PubSub"}

    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(
                name="message",
                callback=self._process_pubsub_activity,
                ns=Namespace.PUBSUB_EVENT,
                priority=16,
            ),
        ]

    def _process_pubsub_activity(
        self, _client: Client, stanza: Message, properties: MessageProperties
    ) -> None:
        if not properties.is_pubsub_event:
            return

        if properties.pubsub_event.node != Namespace.ACTIVITY:
            return

        item = properties.pubsub_event.item
        if item is None:
            # Retract, Deleted or Purged
            return

        activity_node = item.getTag("activity", namespace=Namespace.ACTIVITY)
        if not activity_node.getChildren():
            self._log.info("Received activity: %s - no activity set", properties.jid)
            return

        activity, subactivity, text = None, None, None
        for child in activity_node.getChildren():
            name = child.getName()
            if name == "text":
                text = child.getData()
            elif name in ACTIVITIES:
                activity = name
                subactivity = self._parse_sub_activity(child)

        if activity is None and activity_node.getChildren():
            self._log.warning("No valid activity value found")
            self._log.warning(stanza)
            raise NodeProcessed

        data = ActivityData(activity, subactivity, text)
        pubsub_event = properties.pubsub_event._replace(data=data)
        self._log.info("Received activity: %s - %s", properties.jid, data)

        properties.pubsub_event = pubsub_event

    @staticmethod
    def _parse_sub_activity(activity: Node) -> str | None:
        sub_activities = ACTIVITIES[activity.getName()]
        for sub in activity.getChildren():
            if sub.getName() in sub_activities:
                return sub.getName()
        return None

    @iq_request_task
    def set_activity(self, data: ActivityData):
        task = yield

        item = Node("activity", {"xmlns": Namespace.ACTIVITY})
        if data is not None and data.activity:
            activity_node = item.addChild(data.activity)
            if data.subactivity:
                activity_node.addChild(data.subactivity)
            if data.text:
                item.addChild("text", payload=data.text)

        result = yield self.publish(Namespace.ACTIVITY, item, id_="current")

        yield finalize(task, result)
