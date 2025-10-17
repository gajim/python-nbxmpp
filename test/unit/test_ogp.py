from test.lib.util import StanzaHandlerTest

from nbxmpp.modules.ogp import OpenGraph
from nbxmpp.protocol import Message
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import OpenGraphData


class MockOpenGraph(OpenGraph):
    def __init__(self) -> None:
        pass


class OpenGraphTest(StanzaHandlerTest):
    def test_parse_ogp(self) -> None:
        msg = Message(node=_DATA)
        self._parse_and_assert_values(msg)

    def test_parse_wikipedia(self) -> None:
        msg = Message(
            node="""
        <message xmlns="jabber:client" id="ef1bee13-ada9-4de8-8d1d-5ccce250116d" from="gajim-unnamed-chat@rooms.slidge.im/nicoco" type="groupchat" xml:lang="en" to="test@slidge.im/gajim.M7JMH3QS">
          <markable xmlns="urn:xmpp:chat-markers:0" />
          <Description xmlns="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:ns1="http://www.w3.org/1999/02/22-rdf-syntax-ns#" ns1:about="https://fr.wikipedia.org">
            <title xmlns="https://ogp.me/ns#">Wikipédia, l'encyclopédie libre</title>
            <url xmlns="https://ogp.me/ns#">https://fr.wikipedia.org/wiki/Wikip%C3%A9dia:Accueil_principal</url>
        </Description>
          <body>https://fr.wikipedia.org</body>
          <occupant-id xmlns="urn:xmpp:occupant-id:0" id="5QLCTSehDZCqSoQznCE5puX3OfkZENjjCsFb35m6Gyw=" />
          <stanza-id id="068e5132-780b-75c4-82cb-cbed329a08a5" xmlns="urn:xmpp:sid:0" by="gajim-unnamed-chat@rooms.slidge.im" />
        </message>
        """
        )
        props = self._parse(msg)
        ogp = props["https://fr.wikipedia.org"]
        self.assertEqual(ogp.title, "Wikipédia, l'encyclopédie libre")
        self.assertEqual(
            ogp.url, "https://fr.wikipedia.org/wiki/Wikip%C3%A9dia:Accueil_principal"
        )

    def test_parse_youtube(self) -> None:
        msg = Message(
            node="""
        <message xmlns="jabber:client" id="200bd533-99c6-4d0a-818d-b3ed9289d405" from="gajim-unnamed-chat@rooms.slidge.im/nicoco" type="groupchat" xml:lang="en" to="test@slidge.im/gajim.M7JMH3QS">
          <markable xmlns="urn:xmpp:chat-markers:0" />
          <Description xmlns="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:ns1="http://www.w3.org/1999/02/22-rdf-syntax-ns#" ns1:about="https://www.youtube.com/watch?v=45V5qdjhbGI&amp;t=1">
            <title xmlns="https://ogp.me/ns#">Pierre Lapointe - Je déteste ma vie (Paris tristesse) - YouTube</title>
            <description xmlns="https://ogp.me/ns#">Paris tristesse en vente maintenant: http://smarturl.it/paristristesseRéalisation | montage : Pascal Grandmaison et Philippe CraigDirection photo: Pascal Gra...</description>
            <url xmlns="https://ogp.me/ns#">https://www.youtube.com/watch?v=45V5qdjhbGI&amp;t=1</url>
            <site_name xmlns="https://ogp.me/ns#">YouTube</site_name>
        </Description>
          <body>https://www.youtube.com/watch?v=45V5qdjhbGI&amp;t=1</body>
          <occupant-id xmlns="urn:xmpp:occupant-id:0" id="5QLCTSehDZCqSoQznCE5puX3OfkZENjjCsFb35m6Gyw=" />
          <stanza-id id="068e51c3-04f6-7560-96ae-45c83f4bce1c" xmlns="urn:xmpp:sid:0" by="gajim-unnamed-chat@rooms.slidge.im" />
        </message>
        """
        )
        props = self._parse(msg)
        ogp = props["https://www.youtube.com/watch?v=45V5qdjhbGI&t=1"]
        self.assertEqual(
            ogp.title, "Pierre Lapointe - Je déteste ma vie (Paris tristesse) - YouTube"
        )
        self.assertEqual(
            ogp.description,
            "Paris tristesse en vente maintenant: http://smarturl.it/paristristesseRéalisation | montage : Pascal Grandmaison et Philippe CraigDirection photo: Pascal Gra...",
        )
        self.assertEqual(ogp.site_name, "YouTube")

    def test_set_ogp(self) -> None:
        msg1 = Message(node=_DATA)
        msg2 = Message(to=msg1.getTo(), body=msg1.getBody())
        msg2.addOpenGraph(
            "https://the.link.example.com/what-was-linked-to",
            OpenGraphData(
                title="Page Title",
                url="Canonical URL",
                image="https://link.to.example.com/image.png",
                type="website",
                site_name="Some Website",
                description="Page Description",
            ),
        )
        self._parse_and_assert_values(msg2)

    def _parse(self, msg: Message) -> dict[str, OpenGraphData]:
        properties = MessageProperties("whatever@whatever.com")
        parser = MockOpenGraph()
        parser._process_message_opengraph(None, msg, properties)
        self.assertEqual(len(properties.open_graph), 1)

        return properties.open_graph

    def _parse_and_assert_values(self, msg: Message) -> None:
        props = self._parse(msg)
        ogp = props["https://the.link.example.com/what-was-linked-to"]
        self.assertEqual(ogp.title, "Page Title")
        self.assertEqual(ogp.url, "Canonical URL")
        self.assertEqual(ogp.image, "https://link.to.example.com/image.png")
        self.assertEqual(ogp.type, "website")
        self.assertEqual(ogp.site_name, "Some Website")
        self.assertEqual(ogp.description, "Page Description")


_DATA = """
<message xmlns="jabber:client"
         to="whoever@example.com">
    <body>I wanted to mention https://the.link.example.com/what-was-linked-to</body>
    <rdf:Description xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
                     xmlns:og="https://ogp.me/ns#"
                     rdf:about="https://the.link.example.com/what-was-linked-to">
        <og:title>Page Title</og:title>
        <og:description>Page Description</og:description>
        <og:url>Canonical URL</og:url>
        <og:image>https://link.to.example.com/image.png</og:image>
        <og:type>website</og:type>
        <og:site_name>Some Website</og:site_name>
    </rdf:Description>
</message>
"""
