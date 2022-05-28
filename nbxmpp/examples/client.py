#!/usr/bin/python3

import os
import logging
import json
from pathlib import Path

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GLib', '2.0')
from gi.repository import Gtk
from gi.repository import GLib

import nbxmpp
from nbxmpp.protocol import JID
from nbxmpp.client import Client
from nbxmpp.structs import ProxyData
from nbxmpp.structs import StanzaHandler
from nbxmpp.const import ConnectionType
from nbxmpp.const import ConnectionProtocol
from nbxmpp.const import StreamError
from nbxmpp.const import Mode

consoleloghandler = logging.StreamHandler()
log = logging.getLogger('nbxmpp')
log.setLevel('INFO')
log.addHandler(consoleloghandler)

formatter = logging.Formatter(
    '%(asctime)s %(levelname)-7s %(name)-25s %(message)s',
    datefmt='%H:%M:%S')
consoleloghandler.setFormatter(formatter)


class Builder:
    def __init__(self, filename):
        file_path = Path(__file__).resolve()
        ui_file_path = file_path.parent / filename
        self._builder = Gtk.Builder()
        self._builder.add_from_file(str(ui_file_path))

    def __getattr__(self, name):
        try:
            return getattr(self._builder, name)
        except AttributeError:
            return self._builder.get_object(name)


class StanzaRow(Gtk.ListBoxRow):
    def __init__(self, stanza, incoming):
        Gtk.ListBoxRow.__init__(self)
        color = 'red' if incoming else 'blue'
        if isinstance(stanza, bytes):
            stanza = str(stanza)
        if not isinstance(stanza, str):
            stanza = stanza.__str__(fancy=True)
        stanza = GLib.markup_escape_text(stanza)
        label = Gtk.Label()
        label.set_markup('<span foreground="%s">%s</span>' % (color, stanza))
        label.set_xalign(0)
        label.set_halign(Gtk.Align.START)
        self.add(label)
        self.show_all()


class TestClient(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self, title='Test Client')
        self.set_default_size(500, 500)

        self._builder = Builder('client.ui')
        self._builder.connect_signals(self)

        self.add(self._builder.grid)

        self._client = None
        self._scroll_timeout = None
        self._create_paths()
        self._load_config()

    def _create_client(self):
        self._client = Client(log_context='TEST')
        self._client.set_domain(self.address.domain)
        self._client.set_username(self.address.localpart)
        self._client.set_resource('test')

        proxy_ip = self._builder.proxy_ip.get_text()
        if proxy_ip:
            proxy_port = int(self._builder.proxy_port.get_text())
            proxy_host = '%s:%s' % (proxy_ip, proxy_port)
            proxy = ProxyData(self._builder.proxy_type.get_active_text().lower(),
                              proxy_host,
                              self._builder.proxy_username.get_text() or None,
                              self._builder.proxy_password.get_text() or None)
            self._client.set_proxy(proxy)

        if self._builder.login_mode.get_active():
            self._client.set_mode(Mode.LOGIN_TEST)
        elif self._builder.client_mode.get_active():
            self._client.set_mode(Mode.CLIENT)
        elif self._builder.register_mode.get_active():
            self._client.set_mode(Mode.REGISTER)
        elif self._builder.anon_mode.get_active():
            self._client.set_mode(Mode.ANONYMOUS_TEST)
        else:
            raise ValueError('No mode selected')

        self._client.set_connection_types(self._get_connection_types())
        self._client.set_protocols(self._get_connection_protocols())

        self._client.set_password(self.password)

        self._client.subscribe('resume-failed', self._on_signal)
        self._client.subscribe('resume-successful', self._on_signal)
        self._client.subscribe('disconnected', self._on_signal)
        self._client.subscribe('connection-lost', self._on_signal)
        self._client.subscribe('connection-failed', self._on_signal)
        self._client.subscribe('connected', self._on_connected)

        self._client.subscribe('stanza-sent', self._on_stanza_sent)
        self._client.subscribe('stanza-received', self._on_stanza_received)

        self._client.register_handler(StanzaHandler('message', self._on_message))

    @property
    def password(self):
        return self._builder.password.get_text()

    @property
    def address(self):
        return JID.from_string(self._builder.address.get_text())

    @property
    def xml_box(self):
        return self._builder.xml_box

    def scroll_to_end(self):
        adj_v = self._builder.scrolledwin.get_vadjustment()
        if adj_v is None:
            # This can happen when the Widget is already destroyed when called
            # from GLib.idle_add
            self._scroll_timeout = None
            return
        max_scroll_pos = adj_v.get_upper() - adj_v.get_page_size()
        adj_v.set_value(max_scroll_pos)

        adj_h = self._builder.scrolledwin.get_hadjustment()
        adj_h.set_value(0)
        self._scroll_timeout = None

    def _on_signal(self, _client, signal_name, *args, **kwargs):
        log.info('%s, Error: %s', signal_name, self._client.get_error())
        if signal_name == 'disconnected':
            if self._client.get_error() is None:
                return
            domain, error, text = self._client.get_error()
            if domain == StreamError.BAD_CERTIFICATE:
                self._client.set_ignore_tls_errors(True)
                self._client.connect()

    def _on_connected(self, _client, _signal_name):
        self.send_presence()

    def _on_message(self, _stream, stanza, _properties):
        log.info('Message received')
        log.info(stanza.getBody())

    def _on_stanza_sent(self, _stream, _signal_name, data):
        self.xml_box.add(StanzaRow(data, False))
        self._add_scroll_timeout()

    def _on_stanza_received(self, _stream, _signal_name, data):
        self.xml_box.add(StanzaRow(data, True))
        self._add_scroll_timeout()

    def _add_scroll_timeout(self):
        if self._scroll_timeout is not None:
            return
        self._scroll_timeout = GLib.timeout_add(50, self.scroll_to_end)

    def _connect_clicked(self, *args):
        if self._client is not None:
            self._client.destroy()

        self._create_client()

        self._client.connect()

    def _disconnect_clicked(self, *args):
        if self._client is not None:
            self._client.disconnect()

    def _clear_clicked(self, *args):
        self.xml_box.foreach(self._remove)

    def _on_reconnect_clicked(self, *args):
        if self._client is not None:
            self._client.reconnect()

    def _get_connection_types(self):
        types = []
        if self._builder.directtls.get_active():
            types.append(ConnectionType.DIRECT_TLS)
        if self._builder.starttls.get_active():
            types.append(ConnectionType.START_TLS)
        if self._builder.plain.get_active():
            types.append(ConnectionType.PLAIN)
        return types

    def _get_connection_protocols(self):
        protocols = []
        if self._builder.tcp.get_active():
            protocols.append(ConnectionProtocol.TCP)
        if self._builder.websocket.get_active():
            protocols.append(ConnectionProtocol.WEBSOCKET)
        return protocols

    def _on_save_clicked(self, *args):
        data = {}
        data['jid'] = self._builder.address.get_text()
        data['password'] = self._builder.password.get_text()
        data['proxy_type'] = self._builder.proxy_type.get_active_text()
        data['proxy_ip'] = self._builder.proxy_ip.get_text()
        data['proxy_port'] = self._builder.proxy_port.get_text()
        data['proxy_username'] = self._builder.proxy_username.get_text()
        data['proxy_password'] = self._builder.proxy_password.get_text()

        data['directtls'] = self._builder.directtls.get_active()
        data['starttls'] = self._builder.starttls.get_active()
        data['plain'] = self._builder.plain.get_active()
        data['tcp'] = self._builder.tcp.get_active()
        data['websocket'] = self._builder.websocket.get_active()

        path = self._get_config_dir() / 'config'
        with path.open('w') as fp:
            json.dump(data, fp)

    def _load_config(self):
        path = self._get_config_dir() / 'config'
        if not path.exists():
            return

        with path.open('r') as fp:
            data = json.load(fp)

        self._builder.address.set_text(data.get('jid', ''))
        self._builder.password.set_text(data.get('password', ''))
        self._builder.proxy_type.set_active_id(data.get('proxy_type', 'HTTP'))
        self._builder.proxy_ip.set_text(data.get('proxy_ip', ''))
        self._builder.proxy_port.set_text(data.get('proxy_port', ''))
        self._builder.proxy_username.set_text(data.get('proxy_username', ''))
        self._builder.proxy_password.set_text(data.get('proxy_password', ''))

        self._builder.directtls.set_active(data.get('directtls', False))
        self._builder.starttls.set_active(data.get('starttls', False))
        self._builder.plain.set_active(data.get('plain', False))
        self._builder.tcp.set_active(data.get('tcp', False))
        self._builder.websocket.set_active(data.get('websocket', False))

    @staticmethod
    def _get_config_dir():
        if os.name == 'nt':
            return Path(os.path.join(os.environ['appdata'], 'nbxmpp'))

        expand = os.path.expanduser
        base = os.getenv('XDG_CONFIG_HOME')
        if base is None or base[0] != '/':
            base = expand('~/.config')
        return Path(os.path.join(base, 'nbxmpp'))

    def _create_paths(self):
        path_ = self._get_config_dir()
        if not path_.exists():
            for parent_path in reversed(path_.parents):
                # Create all parent folders
                # don't use mkdir(parent=True), as it ignores `mode`
                # when creating the parents
                if not parent_path.exists():
                    print('creating %s directory' % parent_path)
                    parent_path.mkdir(mode=0o700)
            print('creating %s directory' % path_)
            path_.mkdir(mode=0o700)

    def _remove(self, item):
        self.xml_box.remove(item)
        item.destroy()

    def send_presence(self):
        presence = nbxmpp.Presence()
        self._client.send_stanza(presence)


win = TestClient()
win.connect("delete-event", Gtk.main_quit)
win.show_all()
Gtk.main()
