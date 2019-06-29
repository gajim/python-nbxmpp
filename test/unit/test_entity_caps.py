import unittest

from nbxmpp.util import compute_caps_hash
from nbxmpp.modules.discovery import parse_disco_info
from nbxmpp.protocol import Iq
from nbxmpp.protocol import DiscoInfoMalformed

class EntityCaps(unittest.TestCase):

    def test_multiple_field_values(self):
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
        hash_ = compute_caps_hash(info)
        self.assertEqual(hash_, 'q07IKJEyjvHSyhy//CH0CxmKi8w=')

    def test_ignore_invalid_forms(self):
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
              <field var='FORM_TYPE'>
                <value>urn:xmpp:dataforms:softwareinfo</value>
              </field>
              <field var='ip_version'>
                <value>ipv4</value>
                <value>ipv6</value>
              </field>
            </x>
            <x xmlns='jabber:x:data' type='result'>
              <field var='ip_version'>
                <value>ipv4</value>
                <value>ipv6</value>
              </field>
            </x>
          </query>
        </iq>"""

        info = parse_disco_info(Iq(node=node))
        hash_ = compute_caps_hash(info)
        self.assertEqual(hash_, 'q07IKJEyjvHSyhy//CH0CxmKi8w=')

    def test_multiple_form_type_values(self):
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
                <value>urn:xmpp:dataforms:softwareinfo_test</value>
              </field>
              <field var='ip_version'>
                <value>ipv4</value>
                <value>ipv6</value>
              </field>
            </x>
          </query>
        </iq>"""

        info = parse_disco_info(Iq(node=node))
        with self.assertRaises(DiscoInfoMalformed):
            hash_ = compute_caps_hash(info)

    def test_non_unique_form_type_value(self):
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
            </x>
            <x xmlns='jabber:x:data' type='result'>
              <field var='FORM_TYPE' type='hidden'>
                <value>urn:xmpp:dataforms:softwareinfo</value>
              </field>
              <field var='ip_version'>
                <value>ipv4</value>
                <value>ipv6</value>
              </field>
            </x>
          </query>
        </iq>"""

        info = parse_disco_info(Iq(node=node))
        with self.assertRaises(DiscoInfoMalformed):
            hash_ = compute_caps_hash(info)

    def test_non_unique_feature(self):
        node = """
        <iq from='benvolio@capulet.lit/230193' id='disco1' to='juliet@capulet.lit/chamber' type='result'>
          <query xmlns='http://jabber.org/protocol/disco#info' node='http://psi-im.org#q07IKJEyjvHSyhy//CH0CxmKi8w='>
            <identity xml:lang='en' category='client' name='Psi 0.11' type='pc'/>
            <identity xml:lang='el' category='client' name='Ψ 0.11' type='pc'/>
            <feature var='http://jabber.org/protocol/caps'/>
            <feature var='http://jabber.org/protocol/muc'/>
            <feature var='http://jabber.org/protocol/disco#info'/>
            <feature var='http://jabber.org/protocol/disco#items'/>
            <feature var='http://jabber.org/protocol/muc'/>
          </query>
        </iq>"""

        info = parse_disco_info(Iq(node=node))
        with self.assertRaises(DiscoInfoMalformed):
            hash_ = compute_caps_hash(info)

    def test_non_unique_identity(self):
        node = """
        <iq from='benvolio@capulet.lit/230193' id='disco1' to='juliet@capulet.lit/chamber' type='result'>
          <query xmlns='http://jabber.org/protocol/disco#info' node='http://psi-im.org#q07IKJEyjvHSyhy//CH0CxmKi8w='>
            <identity xml:lang='en' category='client' name='Psi 0.11' type='pc'/>
            <identity xml:lang='en' category='client' name='Psi 0.11' type='pc'/>
            <feature var='http://jabber.org/protocol/caps'/>
            <feature var='http://jabber.org/protocol/muc'/>
            <feature var='http://jabber.org/protocol/disco#info'/>
            <feature var='http://jabber.org/protocol/disco#items'/>
            <feature var='http://jabber.org/protocol/muc'/>
          </query>
        </iq>"""

        info = parse_disco_info(Iq(node=node))
        with self.assertRaises(DiscoInfoMalformed):
            hash_ = compute_caps_hash(info)
