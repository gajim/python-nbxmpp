import unittest

from nbxmpp.modules.discovery import parse_disco_info
from nbxmpp.protocol import Iq


class RestrictedReactions(unittest.TestCase):
    def test_form_present(self):
        node = """
        <iq from='benvolio@capulet.lit/230193' id='disco1' to='juliet@capulet.lit/chamber' type='result'>
          <query xmlns='http://jabber.org/protocol/disco#info' node='http://psi-im.org#q07IKJEyjvHSyhy//CH0CxmKi8w='>
            <identity xml:lang='en' category='client' name='Psi 0.11' type='pc'/>
            <identity xml:lang='el' category='client' name='Ψ 0.11' type='pc'/>
            <feature var='http://jabber.org/protocol/caps'/>
            <feature var='http://jabber.org/protocol/disco#info'/>
            <feature var='http://jabber.org/protocol/disco#items'/>
            <feature var='http://jabber.org/protocol/muc'/>
            <x xmlns='jabber:x:data' type='result'>
              <field var='FORM_TYPE' type='hidden'>
                <value>urn:xmpp:dataforms:softwareinfo</value>
              </field>
              <field var='ip_version'>
                <value>ipv4</value>
                <value>ipv6</value>
              </field>
              <field var='os'>
                <value>Mac</value>
              </field>
              <field var='os_version'>
                <value>10.5.1</value>
              </field>
              <field var='software'>
                <value>Psi</value>
              </field>
              <field var='software_version'>
                <value>0.11</value>
              </field>
            </x>
            <x xmlns='jabber:x:data' type='result'>
              <field var='FORM_TYPE' type='hidden'>
                <value>urn:xmpp:reactions:0:restrictions</value>
              </field>
              <field var='max_reactions_per_user'>
                <value>1</value>
              </field>
              <field var='allowlist' type='list-multi'>
                <value>💘</value>
                <value>❤️</value>
                <value>💜</value>
              </field>
            </x>
          </query>
        </iq>"""

        info = parse_disco_info(Iq(node=node))
        self.assertEqual(info.reactions_per_user, 1)
        self.assertEqual(info.reactions_allowlist, ["💘", "❤️", "💜"])

    def test_form_absent(self):
        node = """
        <iq from='benvolio@capulet.lit/230193' id='disco1' to='juliet@capulet.lit/chamber' type='result'>
          <query xmlns='http://jabber.org/protocol/disco#info' node='http://psi-im.org#q07IKJEyjvHSyhy//CH0CxmKi8w='>
            <identity xml:lang='en' category='client' name='Psi 0.11' type='pc'/>
            <identity xml:lang='el' category='client' name='Ψ 0.11' type='pc'/>
            <feature var='http://jabber.org/protocol/caps'/>
            <feature var='http://jabber.org/protocol/disco#info'/>
            <feature var='http://jabber.org/protocol/disco#items'/>
            <feature var='http://jabber.org/protocol/muc'/>
            <x xmlns='jabber:x:data' type='result'>
              <field var='FORM_TYPE' type='hidden'>
                <value>urn:xmpp:dataforms:softwareinfo</value>
              </field>
              <field var='ip_version'>
                <value>ipv4</value>
                <value>ipv6</value>
              </field>
              <field var='os'>
                <value>Mac</value>
              </field>
              <field var='os_version'>
                <value>10.5.1</value>
              </field>
              <field var='software'>
                <value>Psi</value>
              </field>
              <field var='software_version'>
                <value>0.11</value>
              </field>
            </x>
          </query>
        </iq>"""

        info = parse_disco_info(Iq(node=node))
        self.assertIsNone(info.reactions_per_user)
        self.assertIsNone(info.reactions_allowlist)
