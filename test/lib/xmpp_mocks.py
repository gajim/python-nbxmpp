"""
Module with dummy classes for unit testing of XMPP and related code.
"""

from unittest.mock import Mock


class MockConnection(Mock):
    """
    Class simulating Connection class from src/common/connection.py

    It is derived from Mock in order to avoid defining all methods
    from real Connection that are called from NBClient or Dispatcher
    ( _event_dispatcher for example)
    """

    def __init__(self, *args):
        self.connect_succeeded = True
        Mock.__init__(self, *args)

    def on_connect(self, success, *args):
        """
        Method called after connecting - after receiving <stream:features>
        from server (NOT after TLS stream restart) or connect failure
        """
        self.connect_succeeded = success

    def on_auth(self, con, auth):
        """
        Method called after authentication, regardless of the result.

        :Parameters:
                con : NonBlockingClient
                        reference to authenticated object
                auth : string
                        type of authetication in case of success ('old_auth', 'sasl') or
                        None in case of auth failure
        """
        self.auth_connection = con
        self.auth = auth
