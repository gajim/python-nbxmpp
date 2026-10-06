import pytest

from nbxmpp.protocol import JID
from nbxmpp.xml.node import AttrValue
from nbxmpp.xml.node import Child
from nbxmpp.xml.node import ChildFlag
from nbxmpp.xml.node import ChildText
from nbxmpp.xml.node import xml_model
from nbxmpp.xml.node import XMLNode

# ChildList
# ChildValue
# ChildValueList


class TestXMLNode:

    def test_attrvalue(self):
        xml = """
            <message
                strattr="somestring"
                jidattr="test@test.com"
                intattr="1"
                boolattr="true"
                boolattr2="1"
                floatattr="1.3"
                noneattr="1.3"
            />
        """

        @xml_model
        class Message(XMLNode):
            strattr: str = AttrValue()
            jidattr: JID = AttrValue()
            intattr: int = AttrValue()
            boolattr: bool = AttrValue()
            boolattr2: bool = AttrValue()
            floatattr: float = AttrValue()
            defaultattr: float = AttrValue(default=1)
            noneattr: float | None = AttrValue(default=None)

        msg = Message.from_xml(xml)
        assert msg.strattr == "somestring"
        assert msg.jidattr == JID.from_string("test@test.com")
        assert msg.intattr == 1
        assert msg.boolattr is True
        assert msg.boolattr2 is True
        assert msg.floatattr == 1.3
        assert msg.defaultattr == 1

        @xml_model
        class Message2(XMLNode):
            missingattr: str = AttrValue()

        with pytest.raises(ValueError):
            Message2.from_xml(xml)

    def test_child_flag(self):
        xml = """
            <message>
                <trueflag />
            </message>
        """

        @xml_model
        class Message(XMLNode):
            trueflag: bool = ChildFlag()
            falseflag: bool = ChildFlag(default=False)

        msg = Message.from_xml(xml)
        assert msg.trueflag is True
        assert msg.falseflag is False

        @xml_model
        class Message2(XMLNode):
            missingflag: bool = ChildFlag()

        with pytest.raises(ValueError):
            Message2.from_xml(xml)

    def test_child(self):
        xml = """
            <message>
                <child attr1="1" />
            </message>
        """

        @xml_model
        class ChildNode(XMLNode):
            TAG = ("child", "")

            attr1: int = AttrValue()

        @xml_model
        class ChildNode2(XMLNode):
            TAG = ("child2", "")

        @xml_model
        class Message(XMLNode):
            missingchild: ChildNode2 = Child()

        with pytest.raises(ValueError):
            Message.from_xml(xml)

        @xml_model
        class Message2(XMLNode):
            child: ChildNode = Child()
            child2: ChildNode2 | None = Child(default=None)

        msg = Message2.from_xml(xml)
        assert isinstance(msg.child, ChildNode)
        assert msg.child.attr1 == 1
        assert msg.child2 is None

    def test_child_text(self):
        xml = """
            <message>
                <textstr>test</textstr>
                <textjid>test@test.com</textjid>
                <textint>1</textint>
                <textbool>true</textbool>
                <textfloat>1.3</textfloat>
                <textdefault>2</textdefault>
            </message>
        """

        @xml_model
        class Message(XMLNode):
            textstr: str = ChildText()
            textjid: JID = ChildText()
            textint: int = ChildText()
            textbool: bool = ChildText()
            textfloat: float = ChildText()
            textdefault: int | None = ChildText(default=None)
            textdefault2: int | None = ChildText(default=None)

        msg = Message.from_xml(xml)
        assert msg.textstr == "test"
        assert msg.textjid == JID.from_string("test@test.com")
        assert msg.textint == 1
        assert msg.textbool is True
        assert msg.textfloat == 1.3
        assert msg.textdefault == 2
        assert msg.textdefault2 is None

        @xml_model
        class Message2(XMLNode):
            missingtext: bool = ChildText()

        with pytest.raises(ValueError):
            Message2.from_xml(xml)
