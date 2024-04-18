from test.lib.util import StanzaHandlerTest

from nbxmpp import Presence
from nbxmpp.language import LanguageRange
from nbxmpp.modules.muc.hats import Hats
from nbxmpp.structs import Hat
from nbxmpp.structs import PresenceProperties


class TestHats(StanzaHandlerTest):
    def test_parse_hats(self):
        # language=XML
        xml = """
        <presence
            from='meeting123@meetings.example.com/Harry'
            id='D568A74F-E062-407C-83E9-531E91526516'
            to='someone@example.com/foo'>
          <x xmlns='http://jabber.org/protocol/muc#user'>
            <item affiliation='owner' role='moderator'/>
          </x>
          <hats xmlns='urn:xmpp:hats:0'>
            <hat title='Member' uri='http://schemas.example.com/hats#member' xml:lang='en-us' />
            <hat title='Mitglied' uri='http://schemas.example.com/hats#member' xml:lang='de-de' />
            <hat title='Owner' uri='http://schemas.example.com/hats#owner' xml:lang='en-us' />
            <hat title='Eigentümer' uri='http://schemas.example.com/hats#owner' xml:lang='de-de' />
          </hats>
        </presence>
        """

        props = PresenceProperties("mockjid")
        presence = Presence(node=xml)
        Hats._process_hats(None, None, presence, props)

        hat_list_en = [
            Hat(uri="http://schemas.example.com/hats#member", title="Member"),
            Hat(uri="http://schemas.example.com/hats#owner", title="Owner"),
        ]

        hat_list_de = [
            Hat(uri="http://schemas.example.com/hats#member", title="Mitglied"),
            Hat(uri="http://schemas.example.com/hats#owner", title="Eigentümer"),
        ]

        lang_range_en = [LanguageRange(tag="en")]
        lang_range_de = [LanguageRange(tag="de")]

        assert props.hats is not None

        hats_en = props.hats.get_hats(lang_range_en)
        self.assertSequenceEqual(hat_list_en, hats_en)

        hats_de = props.hats.get_hats(lang_range_de)
        self.assertSequenceEqual(hat_list_de, hats_de)

        hats_any = props.hats.get_hats()
        self.assertSequenceEqual(hat_list_de, hats_any)
