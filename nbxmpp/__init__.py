import gi
gi.require_version('Soup', '3.0')

from .protocol import *  # pylint: disable=wrong-import-position

__version__: str = '4.3.1'
