# Welcome to python-nbxmpp

`python-nbxmpp` is a Python library that provides a way for Python applications to use the Jabber/XMPP network in a non-blocking way. This library was initially a fork of `xmpppy`, but is now using non-blocking sockets.

## Features

* Asynchronous
* Supports ANONYMOUS, EXTERNAL, GSSAPI, SCRAM-SHA-1, DIGEST-MD5, PLAIN, and X-MESSENGER-OAUTH2 authentication mechanisms.
* Supports connection via proxies
* Supports TLS
* Supports [BOSH (XEP-0124)](https://xmpp.org/extensions/xep-0124.html)
* Supports [Stream Management (XEP-0198)](https://xmpp.org/extensions/xep-0198.html)
* List of [supported XEPs](https://dev.gajim.org/gajim/python-nbxmpp/-/wikis/Supported-XEPs-in-python-nbxmpp/)

## Starting Points

* [Downloads](https://dev.gajim.org/gajim/python-nbxmpp/tags)
* You can also clone the [git repository](https://dev.gajim.org/gajim/python-nbxmpp.git)

### Setup

Run the following:

    pip install .

### Usage

To use python-nbxmpp, `import nbxmpp` in your application.
