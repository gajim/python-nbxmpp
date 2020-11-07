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

import weakref
import inspect
import logging
from enum import IntEnum
from functools import wraps

from gi.repository import Soup

from nbxmpp.errors import is_error
from nbxmpp.errors import CancelledError
from nbxmpp.errors import TimeoutStanzaError
from nbxmpp.simplexml import Node


log = logging.getLogger('nbxmpp.task')


class _ResultSet:
    pass

ResultSet = _ResultSet()


class NoType:
    pass


class TaskState(IntEnum):
    INIT = 0
    RUNNING = 1
    FINISHED = 2
    CANCELLED = 3

    @property
    def is_init(self):
        return self == TaskState.INIT

    @property
    def is_running(self):
        return self == TaskState.RUNNING

    @property
    def is_finished(self):
        return self == TaskState.FINISHED

    @property
    def is_cancelled(self):
        return self == TaskState.CANCELLED


def _setup_task(task, client, callback, user_data):
    client.add_task(task)
    task.set_finalize_func(client.remove_task)
    task.set_user_data(user_data)
    if callback is not None:
        task.add_done_callback(callback)
    task.start()
    return task


def iq_request_task(func):
    @wraps(func)
    def func_wrapper(self, *args, timeout=None, callback=None, user_data=None, **kwargs):
        task = IqRequestTask(func(self, *args, **kwargs),
                             self._log,
                             self._client)
        task.set_timeout(timeout)
        return _setup_task(task, self._client, callback, user_data)
    return func_wrapper


def http_request_task(func):
    @wraps(func)
    def func_wrapper(self, *args, callback=None, user_data=None, **kwargs):
        task = HTTPRequestTask(func(self, *args, **kwargs),
                               self._log,
                               self._soup_session)
        return _setup_task(task, self._client, callback, user_data)
    return func_wrapper


def is_fatal_error(error):
    if is_error(error):
        return error.is_fatal
    return isinstance(error, Exception)


class Task:

    '''
    Base class for wrapping a generator method.

    It runs the generator depending on what the generator yields. If the
    generator yields another generator a sub task is created. If it yields
    a type defined in _process_types, _run_async() is called which needs to
    be implemented by classes.

    the implementation of _run_async() must be really async, means it should
    not call _async_finished() in the same mainloop cycle. Otherwise sub tasks
    may break. _async_finished() needs to call _next_step(result).
    '''

    _process_types = (NoType,)

    def __init__(self, gen, logger=log):
        self._logger = logger
        self._gen = gen
        self._done_callbacks = []
        self._sub_task = None
        self._result = None
        self._error = None
        self._user_data = None
        self._timeout = None
        self._finalize_func = None
        self._finalize_context = None
        self._state = TaskState.INIT

    @property
    def state(self):
        return self._state

    def add_done_callback(self, callback, weak=True):
        if self._state.is_finished or self._state.is_cancelled:
            raise RuntimeError('Task is finished')

        if weak:
            if inspect.ismethod(callback):
                callback = weakref.WeakMethod(callback)
            elif inspect.isfunction(callback):
                callback = weakref.ref(callback)
            else:
                ValueError('Unknown callback object')

        self._done_callbacks.append(callback)

    def set_timeout(self, timeout):
        self._timeout = timeout

    def start(self):
        if not self._state.is_init:
            raise RuntimeError('Task already started')

        self._state = TaskState.RUNNING
        next(self._gen)
        self._next_step(self)

    def _run_async(self, data):
        raise NotImplementedError

    def _async_finished(self, *args, **kwargs):
        raise NotImplementedError

    def _sub_task_completed(self, task):
        self._sub_task = None
        if not self._state.is_running:
            return

        result = task.get_result()
        if is_fatal_error(result):
            self._error = result
            self._set_finished()
        else:
            self._next_step(result)

    def _next_step(self, result):
        try:
            res = self._gen.send(result)
        except StopIteration:
            self._set_finished()
            return

        except Exception as error:
            self._log_if_fatal(error)
            self._error = error
            self._set_finished()
            return

        if isinstance(res, self._process_types):
            self._run_async(res)

        elif isinstance(res, Task):
            if self._sub_task is not None:
                RuntimeError('Only one sub task can be active')

            self._sub_task = res
            self._sub_task.add_done_callback(self._sub_task_completed,
                                             weak=False)

        else:
            if res is not ResultSet:
                self._result = res
            self._set_finished()

    def _set_finished(self):
        self._state = TaskState.FINISHED
        self._invoke_callbacks()
        self._finalize()

    def _log_if_fatal(self, error):
        if is_error(error):
            if error.is_fatal:
                self._logger.log(error.log_level, error)

        elif isinstance(error, Exception):
            self._logger.exception('Fatal Exception')

    def _invoke_callbacks(self):
        for callback in self._done_callbacks:
            if isinstance(callback, weakref.WeakMethod):
                callback = callback()
                if callback is None:
                    return

            # Be conservative with catching exceptions here
            # For example unittests raise Assertion errors
            # which should not be catched here
            try:
                callback(self)
            except CancelledError:
                pass

    def set_result(self, result):
        self._result = result
        return ResultSet

    def get_result(self):
        # if self._error is None, there was no error
        # but None is a valid value for self._result
        if self._error is not None:
            return self._error
        return self._result

    def finish(self):
        if self._error is not None:
            raise self._error  # pylint: disable=raising-bad-type
        return self._result

    def set_user_data(self, user_data):
        self._user_data = user_data

    def get_user_data(self):
        return self._user_data

    def set_finalize_func(self, func, context=None):
        self._finalize_func = func
        self._finalize_context = context

    def cancel(self):
        if not self._state.is_running:
            return

        self._state = TaskState.CANCELLED
        if self._sub_task is not None:
            self._sub_task.cancel()

        self._error = CancelledError()
        self._invoke_callbacks()
        self._finalize()

    def _finalize(self):
        self._done_callbacks.clear()
        self._sub_task = None
        self._error = None
        self._result = None
        self._user_data = None
        self._gen.close()
        if self._finalize_func is not None:
            self._finalize_func(self, self._finalize_context)


class IqRequestTask(Task):

    '''
    A Task for running IQ requests

    '''

    _process_types = (Node,)

    def __init__(self, gen, logger, client):
        super().__init__(gen, logger)
        self._client = client
        self._iq_id = None

    def _run_async(self, stanza):
        self._iq_id = self._client.send_stanza(stanza,
                                               callback=self._async_finished,
                                               timeout=self._timeout)

    def _async_finished(self, _client, result, *args, **kwargs):
        if self._state == TaskState.CANCELLED:
            return

        if result is None:
            self._error = TimeoutStanzaError()
            self._set_finished()
            return

        self._next_step(result)

    def _finalize(self):
        if self._iq_id is not None:
            self._client._dispatcher.remove_iq_callback(self._iq_id)
        self._client = None
        super()._finalize()


class HTTPRequestTask(Task):

    '''
    A Task for running HTTP requests

    '''

    _process_types = (Soup.Message,)

    def __init__(self, gen, logger, session):
        super().__init__(gen, logger)
        self._session = session

    def _run_async(self, message):
        self._session.queue_message(message, self._async_finished, None)

    def _async_finished(self, _session, message, _user_data):
        if self._state != TaskState.CANCELLED:
            self._next_step(message)

    def _finalize(self):
        self._session = None
        super()._finalize()
