import unittest

from nbxmpp.modules.vcard4 import LanguageParameter
from nbxmpp.modules.vcard4 import VCard
from nbxmpp.simplexml import Node


class TestVCard4(unittest.TestCase):

    def test_vard4_parsing(self):
        vcard_node = Node(
            node="""
            <vcard xmlns="urn:ietf:params:xml:ns:vcard-4.0">
                <fn><text>Peter Saint-Andre</text></fn>
                <n>
                  <parameters>
                    <language><language-tag>fr</language-tag></language>
                  </parameters>
                  <surname>Saint-Andre</surname>
                  <given>Peter</given>
                  <additional></additional>
                </n>
                <nickname><text>stpeter</text></nickname>
                <nickname><text>psa</text></nickname>
                <photo><uri>https://stpeter.im/images/stpeter_oscon.jpg</uri></photo>
                <bday><date>1966-08-06</date></bday>
                <adr>
                  <parameters>
                    <type><text>work</text><text>voice</text></type>
                    <pref><integer>1</integer></pref>
                  </parameters>
                  <ext>Suite 600</ext>
                  <street>1899 Wynkoop Street</street>
                  <locality>Denver</locality>
                  <region>CO</region>
                  <code>80202</code>
                  <country>USA</country>
                </adr>
                <adr>
                  <parameters><type><text>home</text></type></parameters>
                  <ext></ext>
                  <street></street>
                  <locality>Parker</locality>
                  <region>CO</region>
                  <code>80138</code>
                  <country>USA</country>
                </adr>
                <tel>
                  <parameters>
                    <type><text>work</text><text>voice</text></type>
                    <pref><integer>1</integer></pref>
                  </parameters>
                  <uri>tel:+1-303-308-3282</uri>
                </tel>
                <tel>
                  <parameters><type><text>work</text><text>fax</text></type></parameters>
                  <uri>tel:+1-303-308-3219</uri>
                </tel>
                <tel>
                  <parameters>
                    <type><text>cell</text><text>voice</text><text>text</text></type>
                  </parameters>
                  <uri>tel:+1-720-256-6756</uri>
                </tel>
                <tel>
                  <parameters><type><text>home</text><text>voice</text></type></parameters>
                  <uri>tel:+1-303-555-1212</uri>
                </tel>
                <geo><uri>geo:39.59,-105.01</uri></geo>
                <title><text>Executive Director</text></title>
                <role><text>Patron Saint</text></role>
                <org>
                  <parameters><type><text>work</text></type></parameters>
                  <text>XMPP Standards Foundation</text>
                </org>
                <url><uri>https://stpeter.im/</uri></url>
                <note>
                  <text>
                  More information about me is located on my
                  personal website: https://stpeter.im/
                  </text>
                </note>
                <gender><sex><text>M</text></sex></gender>
                <lang>
                  <parameters><pref>1</pref></parameters>
                  <language-tag>en</language-tag>
                </lang>
                <email>
                  <parameters><type><text>work</text></type></parameters>
                  <text>psaintan@cisco.com</text>
                </email>
                <email>
                  <parameters><type><text>home</text></type></parameters>
                  <text>stpeter@jabber.org</text>
                </email>
                <impp>
                  <parameters><type><text>work</text></type></parameters>
                  <uri>xmpp:psaintan@cisco.com</uri>
                </impp>
                <impp>
                  <parameters><type><text>home</text></type></parameters>
                  <uri>xmpp:stpeter@jabber.org</uri>
                </impp>
                <key>
                  <uri>https://stpeter.im/stpeter.asc</uri>
                </key>
                <pronouns>
                  <text>he/him</text>
                </pronouns>
                <unsupported-element>unsupported</unsupported-element>
            </vcard>
        """
        )

        vcard = VCard.from_node(vcard_node)
        props = vcard.get_properties()

        email_props = list(filter(lambda p: p.name == "email", props))
        self.assertEqual(len(email_props), 2)

        nickname_props = list(filter(lambda p: p.name == "nickname", props))
        self.assertEqual(len(nickname_props), 2)

        n_props = list(filter(lambda p: p.name == "n", props))
        self.assertEqual(len(n_props), 1)
        n_prop = n_props[0]
        lang_param = n_prop.parameters.get_parameter("language")
        assert isinstance(lang_param, LanguageParameter)
        self.assertEqual(lang_param.value, "fr")

        pronouns_props = list(filter(lambda p: p.name == "pronouns", props))
        self.assertEqual(len(pronouns_props), 1)
        self.assertEqual(pronouns_props[0].value, "he/him")

        # Preserve unsupported elements
        node = vcard.to_node()
        self.assertEqual(node.getTagData("unsupported-element"), "unsupported")

    def test_vcard4_pronouns(self):
        vcard_node = Node(
            node="""
            <vcard xmlns="urn:ietf:params:xml:ns:vcard-4.0">
                <fn><text>Cartman</text></fn>
                <pronouns>
                  <parameters>
                    <language><language-tag>fr</language-tag></language>
                    <pref>
                      <integer>1</integer>
                    </pref>
                  </parameters>
                  <text>il/lui</text>
                </pronouns>
                <pronouns>
                  <text>he/him</text>
                </pronouns>
            </vcard>
        """
        )

        vcard = VCard.from_node(vcard_node)
        props = vcard.get_properties()
        pronouns_props = list(filter(lambda p: p.name == "pronouns", props))
        self.assertEqual(len(pronouns_props), 2)
        self.assertEqual(
            pronouns_props[0].parameters.get_parameter("language").value, "fr"
        )
