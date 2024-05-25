import typing

from nbxmpp.modules.base import BaseModule
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import NodeProcessed
from nbxmpp.structs import Hat
from nbxmpp.structs import HatData
from nbxmpp.structs import PresenceProperties
from nbxmpp.structs import StanzaHandler

if typing.TYPE_CHECKING:
    from nbxmpp.client import Client
    from nbxmpp.protocol import Presence


class Hats(BaseModule):
    def __init__(self, client):
        BaseModule.__init__(self, client)
        self._client = client
        self.handlers = [
            StanzaHandler(
                name="presence",
                callback=self._process_hats,
                ns=Namespace.HATS,
                priority=15,
            ),
            StanzaHandler(
                name="presence",
                callback=self._process_hats,
                ns=Namespace.HATS_LEGACY,
                priority=15,
            ),
        ]

    def _process_hats(
        self,
        _client: "Client",
        stanza: "Presence",
        properties: PresenceProperties,
    ):
        hats = stanza.getTag("hats", namespace=Namespace.HATS)
        if hats is None:
            hats = stanza.getTag("hats", namespace=Namespace.HATS_LEGACY)
            if hats is None:
                return

        hat_data = HatData()
        for hat in hats.getTags("hat"):
            uri = hat.getAttr("uri")
            title = hat.getAttr("title")
            if not uri or not title:
                self._log.warning("Invalid hat received")
                self._log.warning(stanza)
                raise NodeProcessed

            lang = hat.getAttr("xml:lang")
            hat_data.add_hat(Hat(uri, title), lang)

        properties.hats = hat_data
