import gi

gi.require_version('Soup', '3.0')

from .protocol import *  # noqa: F403, E402

__version__: str = '5.0.1'
