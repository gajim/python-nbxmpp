import logging

import pytest

from nbxmpp.protocol import JID
from nbxmpp.xml.node import Attr
from nbxmpp.xml.node import Child
from nbxmpp.xml.node import ChildFlag
from nbxmpp.xml.node import ChildList
from nbxmpp.xml.node import ChildText
from nbxmpp.xml.node import logger
from nbxmpp.xml.node import PathValue
from nbxmpp.xml.node import xml_model
from nbxmpp.xml.node import XMLNode

log = logging.getLogger("test")

# Set context logger
logger.set(log)


class TestXMLNode:

    def test_attr_value(self):
        xml = """
            <message
                strattr="somestring"
                jidattr="test@test.com"
                intattr="1"
                boolattr="true"
                boolattr2="1"
                floatattr="1.3"
                noneattr="1.3"
                wrongtypeattr="1.3"
            />
        """

        @xml_model
        class Message(XMLNode):
            TAG = "message"

            strattr: str = Attr()
            jidattr: JID = Attr()
            intattr: int = Attr()
            boolattr: bool = Attr()
            boolattr2: bool = Attr()
            floatattr: float = Attr()
            defaultattr: float = Attr(default=1)
            noneattr: float | None = Attr(default=None)
            wrongtypeattr: int | None = Attr(default=None)

        msg = Message.from_xml(xml)
        assert msg.strattr == "somestring"
        assert msg.jidattr == JID.from_string("test@test.com")
        assert msg.intattr == 1
        assert msg.boolattr is True
        assert msg.boolattr2 is True
        assert msg.floatattr == 1.3
        assert msg.defaultattr == 1
        # Fallback to default on invalid conversion
        assert msg.wrongtypeattr is None

        # Raise on missing attribute
        @xml_model
        class Message2(XMLNode):
            TAG = "message"

            missingattr: str = Attr()

        with pytest.raises(ValueError):
            Message2.from_xml(xml)

        # Raise on invalid type conversion
        @xml_model
        class Message3(XMLNode):
            TAG = "message"

            boolattr: int = Attr()

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
            TAG = "message"

            trueflag: bool = ChildFlag()
            falseflag: bool = ChildFlag(default=False)

        msg = Message.from_xml(xml)
        assert msg.trueflag is True
        assert msg.falseflag is False

        @xml_model
        class Message2(XMLNode):
            TAG = "message"

            missingflag: bool = ChildFlag()

        with pytest.raises(ValueError):
            Message2.from_xml(xml)

    def test_child(self):
        xml = """
            <message>
                <child attr1="1" />
                <exprchild attr1="1" />
            </message>
        """

        @xml_model
        class ChildNode(XMLNode):
            TAG = "child"

            attr1: int = Attr()

        @xml_model
        class ChildNode2(XMLNode):
            TAG = "child2"

        @xml_model
        class ExprChild(XMLNode):
            TAG = "exprchild"

            attr1: int = Attr()

        @xml_model
        class Message(XMLNode):
            TAG = "message"

            missingchild: ChildNode2 = Child()

        with pytest.raises(ValueError):
            Message.from_xml(xml)

        @xml_model
        class Message2(XMLNode):
            TAG = "message"

            child: ChildNode = Child()
            child2: ChildNode2 | None = Child(default=None)
            expr: ExprChild | None = Child(default=None, expr="./exprchild[1]")
            expr2: ExprChild | None = Child(default=None, expr="./exprchild2[1]")

        msg = Message2.from_xml(xml)
        assert isinstance(msg.child, ChildNode)
        assert msg.child.attr1 == 1
        assert msg.child2 is None
        assert isinstance(msg.expr, ExprChild)
        assert msg.expr.attr1 == 1
        assert msg.expr2 is None

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
            TAG = "message"

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
            TAG = "message"

            missingtext: bool = ChildText()

        with pytest.raises(ValueError):
            Message2.from_xml(xml)

    def test_path_value(self):
        xml = """
            <message>
                <child attr="1">test</child>
                <child attr="2">test</child>
            </message>
        """

        @xml_model
        class Message(XMLNode):
            TAG = "message"

            attr: int = PathValue(expr="(./child/@attr)[1]")

        msg = Message.from_xml(xml)
        assert msg.attr == 1

        @xml_model
        class Message2(XMLNode):
            TAG = "message"

            attr: int = PathValue(expr="(./child/@attrmissing)[1]")

        with pytest.raises(ValueError):
            Message2.from_xml(xml)

    def test_child_list(self):
        xml = """
            <message>
                <child attr="1" />
                <child attr="2" />
                <child attr="3" />
                <child2 attr="4" />
            </message>
        """

        @xml_model
        class ChildNode(XMLNode):
            TAG = "child"

            attr: int = Attr()

        @xml_model
        class ChildNode2(XMLNode):
            TAG = "child2"

            attr: int = Attr()

        @xml_model
        class ChildNode3(XMLNode):
            TAG = "child3"

            attr: int = Attr()

        @xml_model
        class Message(XMLNode):
            TAG = "message"

            children: list[ChildNode | ChildNode2] = ChildList()
            children2: list[ChildNode3] = ChildList()

        msg = Message.from_xml(xml)
        assert msg.children[0].attr == 1
        assert msg.children[1].attr == 2
        assert msg.children[2].attr == 3
        assert msg.children[3].attr == 4
        assert not msg.children2
        assert isinstance(msg.children2, list)
