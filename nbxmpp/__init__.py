"""
This is a fork of the xmpppy jabber python library. Most of the code is
inherited but has been extended by implementation of non-blocking transports
and new features like BOSH.

Most of the xmpp classes are ancestors of PlugIn class to share a single set of methods in order to compile a featured and extensible XMPP client.

Thanks and credits to the xmpppy developers. See: http://xmpppy.sourceforge.net/
"""

from .protocol import *
from . import simplexml, protocol, auth, transports, roster
from . import dispatcher, features, idlequeue, bosh, tls, proxy_connectors
from .client import NonBlockingClient
from .plugin import PlugIn
from .smacks import Smacks

__version__ = "0.9.91"
