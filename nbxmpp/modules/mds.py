from __future__ import annotations

from typing import TYPE_CHECKING

from nbxmpp.errors import MalformedStanzaError
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.util import finalize
from nbxmpp.modules.util import raise_if_error
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.protocol import Message
from nbxmpp.protocol import Node
from nbxmpp.protocol import NodeProcessed
from nbxmpp.structs import MDSData
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import StanzaHandler
from nbxmpp.task import iq_request_task

if TYPE_CHECKING:
    from nbxmpp.client import Client

MDS_OPTIONS = {
    "pubsub#persist_items": "true",
    "pubsub#max_items": "max",
    "pubsub#send_last_published_item": "never",
    "pubsub#access_model": "whitelist",
}


class MDS(BaseModule):
    """
    XEP-0490
    """

    _depends = {"publish": "PubSub"}

    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(
                name="message",
                callback=self._process_pubsub_mds,
                ns=Namespace.PUBSUB_EVENT,
                priority=16,
            ),
        ]

    def _process_pubsub_mds(
        self, _client: Client, stanza: Message, properties: MessageProperties
    ) -> None:
        if not properties.is_pubsub_event:
            return

        if properties.pubsub_event.node != Namespace.MDS:
            return

        item = properties.pubsub_event.item
        if item is None:
            return

        try:
            data = self._parse_item(item)
        except MalformedStanzaError as error:
            self._log.warning(error)
            self._log.warning(stanza)
            raise NodeProcessed

        pubsub_event = properties.pubsub_event._replace(data=data)
        self._log.info("Received MDS: %s", data)

        properties.pubsub_event = pubsub_event

    @iq_request_task
    def set_mds(self, jid: JID, stanza_id: str, by: JID | None = None):
        task = yield

        if by is None:
            own_jid = self._client.get_bound_jid()
            assert own_jid is not None
            by = own_jid.new_as_bare()

        displayed = Node("displayed", {"xmlns": Namespace.MDS})
        displayed.addChild(
            "stanza-id", namespace=Namespace.SID, attrs={"id": stanza_id, "by": str(by)}
        )

        result = yield self.publish(
            Namespace.MDS,
            displayed,
            id_=str(jid),
            options=MDS_OPTIONS,
            force_node_options=True,
        )

        yield finalize(task, result)

    @iq_request_task
    def get_mds(self):
        task = yield

        items = yield self.request_items(Namespace.MDS)

        raise_if_error(items)

        if not items:
            yield task.set_result(None)

        data: list[MDSData] = []
        for item in items:
            try:
                data.append(self._parse_item(item))
            except MalformedStanzaError as error:
                self._log.warning(error)
                self._log.warning(item)

        yield data

    def _parse_item(self, item: Node) -> MDSData:

        item_id = item.getAttr("id")
        try:
            jid = JID.from_string(item_id)
        except Exception as e:
            raise MalformedStanzaError(
                f'MDS item ID "{item_id}" is not a valid JID: {e}', item
            )

        displayed = item.getTag("displayed", namespace=Namespace.MDS)
        if not displayed:
            raise MalformedStanzaError("Bad MDS event (no displayed tag)", item)

        sid = displayed.getTag("stanza-id", namespace=Namespace.SID)
        if sid is None:
            raise MalformedStanzaError("Bad MDS event (no stanza-id tag)", item)

        stanza_id = sid.getAttr("id")
        if not stanza_id:
            raise MalformedStanzaError("Bad MDS event (no stanza-id ID)", item)

        by = sid.getAttr("by")
        try:
            stanza_id_by = JID.from_string(by)
        except Exception as e:
            raise MalformedStanzaError(
                f'MDS stanza-id by "{by}" is not a valid JID: {e}', item
            )

        return MDSData(jid=jid, stanza_id=stanza_id, stanza_id_by=stanza_id_by)
