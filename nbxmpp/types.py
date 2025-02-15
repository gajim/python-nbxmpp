from typing import Literal

from nbxmpp.const import ConnectionProtocol
from nbxmpp.const import ConnectionType

BlockingReportValues = Literal["spam", "abuse"]
CustomHostT = tuple[str, ConnectionProtocol, ConnectionType]
