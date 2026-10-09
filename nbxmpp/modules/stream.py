from nbxmpp.namespaces import Namespace
from nbxmpp.util import QName
from nbxmpp.xml.node import Child
from nbxmpp.xml.node import ChildFlag
from nbxmpp.xml.node import ChildList
from nbxmpp.xml.node import ChildText
from nbxmpp.xml.node import xml_model
from nbxmpp.xml.node import XMLNode


@xml_model
class StreamStartTLS(XMLNode):
    TAG = QName("starttls", "urn:ietf:params:xml:ns:xmpp-tls")

    required: bool = ChildFlag()


@xml_model
class StreamLimits(XMLNode):
    TAG = QName("limits", "urn:xmpp:stream-limits:0")

    max_bytes: int = ChildText(qname=QName("max-bytes"))
    idle_seconds: int = ChildText(qname=QName("idle-seconds"))


@xml_model
class SASLMechanism(XMLNode):
    TAG = QName("mechanism", Namespace.SASL)


@xml_model
class SASLMechanisms(XMLNode):
    TAG = QName("mechanisms", Namespace.SASL)

    mechanisms: list[SASLMechanism] = ChildList()


@xml_model
class StreamFeatures(XMLNode):
    TAG = QName("features", "http://etherx.jabber.org/streams")

    register: bool = ChildFlag(
        default=False, qname=QName("register", Namespace.REGISTER_FEATURE)
    )
    starttls: StreamStartTLS | None = Child(default=None)
    limits: StreamLimits | None = Child(default=None)
    mechanisms: SASLMechanisms | None = Child(default=None)


# dispatch <stream:features xmlns:stream="http://etherx.jabber.org/streams" xmlns="jabber:client">
#   <mechanisms xmlns="urn:ietf:params:xml:ns:xmpp-sasl">
#     <mechanism>PLAIN</mechanism>
#     <mechanism>SCRAM-SHA-1-PLUS</mechanism>
#     <mechanism>SCRAM-SHA-1</mechanism>
#     <mechanism>X-OAUTH2</mechanism>
#   </mechanisms>
#   <sasl-channel-binding xmlns="urn:xmpp:sasl-cb:0">
#     <channel-binding type="tls-exporter"/>
#     <channel-binding type="tls-server-end-point"/>
#   </sasl-channel-binding>
#   <register xmlns="http://jabber.org/features/iq-register"/>
# </stream:features>
