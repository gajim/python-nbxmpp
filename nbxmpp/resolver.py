# Copyright (C) 2020 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 3
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; If not, see <http://www.gnu.org/licenses/>.

import logging

from gi.repository import Gio
from gi.repository import GLib


log = logging.getLogger('nbxmpp.resolver')


class DNSResolveRequest:
    def __init__(self, cache, domain, callback):
        self._domain = domain
        self._result = self._lookup_cache(cache)
        self._callback = callback

    @property
    def result(self):
        return self._result

    @result.setter
    def result(self, value):
        self._result = value

    @property
    def is_cached(self):
        return self.result is not None

    def _lookup_cache(self, cache):
        cached_request = cache.get(self)
        if cached_request is None:
            return None
        return cached_request.result

    def finalize(self):
        GLib.idle_add(self._callback, self.result)
        self._callback = None

    def __hash__(self):
        raise NotImplementedError

    def __eq__(self, other):
        return hash(other) == hash(self)


class AlternativeMethods(DNSResolveRequest):
    def __init__(self, *args, **kwargs):
        DNSResolveRequest.__init__(self, *args, **kwargs)

    @property
    def hostname(self):
        return '_xmppconnect.%s' % self._domain

    def __hash__(self):
        return hash(self.hostname)


class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args,
                                                                 **kwargs)
        return cls._instances[cls]


class GioResolver(metaclass=Singleton):
    def __init__(self):
        self._cache = {}

    def _cache_request(self, request):
        self._cache[request] = request

    def resolve_alternatives(self, domain, callback):
        request = AlternativeMethods(self._cache, domain, callback)
        if request.is_cached:
            request.finalize()
            return

        Gio.Resolver.get_default().lookup_records_async(
            request.hostname,
            Gio.ResolverRecordType.TXT,
            None,
            self._on_alternatives_result,
            request)

    def _on_alternatives_result(self, resolver, result, request):
        try:
            results = resolver.lookup_records_finish(result)
        except GLib.Error as error:
            log.info(error)
            request.finalize()
            return

        try:
            websocket_uri = self._parse_alternative_methods(results)
        except Exception:
            log.exception('Failed to parse alternative '
                          'connection methods: %s', results)
            request.finalize()
            return

        request.result = websocket_uri
        self._cache_request(request)
        request.finalize()

    @staticmethod
    def _parse_alternative_methods(variant_results):
        result_list = [res[0][0] for res in variant_results]
        for result in result_list:
            if result.startswith('_xmpp-client-websocket'):
                return result.split('=')[1]
        return None


if __name__ == '__main__':
    import sys

    try:
        domain_ = sys.argv[1]
    except Exception:
        print('Provide domain name as argument')
        sys.exit()

    # Execute:
    # > python3 -m nbxmpp.resolver domain

    def on_result(result):
        print('Result: ', result)
        mainloop.quit()

    GioResolver().resolve_alternatives(domain_, on_result)
    mainloop = GLib.MainLoop()
    mainloop.run()
