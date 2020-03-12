# Welcome to python-nbxmpp

`python-nbxmpp` is a Python library that provides a way for Python applications to use the Jabber/XMPP network in a non-blocking way. This library was initially a fork of `xmpppy`, but is now using non-blocking sockets.

## Runtime Requirements

- PyGObject
- GLib >= 2.60
- libsoup
- precis-i18n

## Features

* List of [supported XEPs](https://dev.gajim.org/gajim/python-nbxmpp/-/wikis/Supported-XEPs-in-python-nbxmpp/)

## Starting Points

* [Downloads](https://dev.gajim.org/gajim/python-nbxmpp/tags)
* You can also clone the [git repository](https://dev.gajim.org/gajim/python-nbxmpp.git)

### Setup

Run the following:

    pip install .

### Usage

To use python-nbxmpp, `import nbxmpp` in your application.

or use the example client `python3 -m nbxmpp.examples.client`
