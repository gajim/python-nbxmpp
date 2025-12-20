import unittest

from nbxmpp.simplexml import Node


class TestNode(unittest.TestCase):

    def test_topretty(self):
        string = """<presence xmlns="jabber:client" xml:lang="en" to="somejid@jid.com">
  <c xmlns="http://jabber.org/protocol/caps" ver="iVeWK58IHqW8e1wc9u4OGClblVo="/>
  <x xmlns="vcard-temp:x:update">
    <photo>bb055be7076edf87c9f89e4e0b829f0624aa1cef</photo>
  </x>
  <occupant-id xmlns="urn:xmpp:occupant-id:0" id="yAkJlge8v5CxmIAXT1m3jwuXLcRWidERkCGco9XN5z0="/>
  <x xmlns="http://jabber.org/protocol/muc#user">
    <item affiliation="none" role="participant"/>
  </x>
  <priority>127</priority>
</presence>
"""

        node = Node(node=string)
        self.assertEqual(str(node), string)

        string = """<a xmlns="http://www.gajim.org/xmlns/undeclared">
  abc
  <b/>
  <c/>
  fgh
</a>
"""

        node = Node(node=string)
        self.assertEqual(str(node), string)

        string = """<a xmlns="http://www.gajim.org/xmlns/undeclared">
  <b/>
  abc
  <c/>
  fgh
</a>
"""

        node = Node(node=string)
        self.assertEqual(str(node), string)

        string = """<a xmlns="http://www.gajim.org/xmlns/undeclared">
  <b/>
  abc
  <c>123</c>
  fgh
</a>
"""

        node = Node(node=string)
        self.assertEqual(str(node), string)

        string = """<a xmlns="http://www.gajim.org/xmlns/undeclared">
  <b>
    <c>
      <d/>
      <e/>
      <f/>
    </c>
  </b>
</a>
"""

        node = Node(node=string)
        self.assertEqual(str(node), string)


if __name__ == "__main__":
    unittest.main()
