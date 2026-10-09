from typing import Literal

from lxml import etree

from nbxmpp.const import ConnectionProtocol
from nbxmpp.const import ConnectionType

BlockingReportValues = Literal["spam", "abuse"]
CustomHostT = tuple[str, ConnectionProtocol, ConnectionType]

ETreeElementT = etree._Element  # type: ignore
