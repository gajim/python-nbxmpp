# Copyright (C) 2020 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import Any
from typing import Optional
from typing import ParamSpec
from typing import TYPE_CHECKING
from typing import TypeVar

import inspect
import logging
import weakref
from collections.abc import Callable
from collections.abc import Generator
from enum import IntEnum
from functools import wraps

from gi.repository import GLib

from nbxmpp.errors import BaseError
from nbxmpp.errors import CancelledError
from nbxmpp.errors import is_error
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.errors import StanzaError
from nbxmpp.errors import TimeoutStanzaError
from nbxmpp.http import HTTPRequest
from nbxmpp.modules.util import make_func_arguments_string
from nbxmpp.simplexml import Node

if TYPE_CHECKING:
    from nbxmpp.client import Client
    from nbxmpp.dispatcher import NBXMPPModuleT

log = logging.getLogger("nbxmpp.task")


class _ResultSet:
    pass


ResultSet = _ResultSet()

T = TypeVar("T")
P = ParamSpec("P")


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


def _setup_task(
    task: Task, client: Client, callback: Callable[..., Any] | None, user_data: Any
) -> Task:
    client.add_task(task)
    task.set_finalize_func(client.remove_task)
    task.set_user_data(user_data)
    if callback is not None:
        task.add_done_callback(callback)
    task.start()
    return task


def iq_request_task(func: Callable[P, T]) -> Callable[P, T]:
    @wraps(func)
    def func_wrapper(
        self: NBXMPPModuleT,
        *args: Any,
        timeout: int | None = None,
        callback: Callable[..., Any] | None = None,
        user_data: Any = None,
        **kwargs: Any,
    ) -> T:
        if self._log.isEnabledFor(logging.INFO):  # type: ignore
            self._log.info(make_func_arguments_string(func, self, args, kwargs))  # type: ignore
        task = IqRequestTask(
            func(self, *args, **kwargs), self._log, self._client  # type: ignore
        )
        task.set_timeout(timeout)
        return _setup_task(task, self._client, callback, user_data)  # type: ignore

    return func_wrapper


def http_request_task(func: Callable[P, T]) -> Callable[P, T]:
    @wraps(func)
    def func_wrapper(
        self: NBXMPPModuleT,
        *args: Any,
        callback: Callable[..., Any] | None = None,
        user_data: Any = None,
        **kwargs: Any,
    ) -> T:
        task = HTTPRequestTask(func(self, *args, **kwargs), self._log)  # type: ignore
        return _setup_task(task, self._client, callback, user_data)  # type: ignore

    return func_wrapper


def is_fatal_error(error: BaseError | Exception | Any) -> bool:
    if is_error(error):
        assert isinstance(error, BaseError)
        return error.is_fatal
    return isinstance(error, Exception)


class Task:
    """
    Base class for wrapping a generator method.

    It runs the generator depending on what the generator yields. If the
    generator yields another generator a sub task is created. If it yields
    a type defined in _process_types, _run_async() is called which needs to
    be implemented by classes.

    the implementation of _run_async() must be really async, means it should
    not call _async_finished() in the same mainloop cycle. Otherwise sub tasks
    may break. _async_finished() needs to call _next_step(result).
    """

    _process_types = (NoType,)

    def __init__(
        self, gen: Generator[Any, Any, Any], logger: logging.Logger = log
    ) -> None:
        self._logger = logger
        self._gen = gen
        self._done_callbacks: list[Callable[..., Any]] = []
        self._sub_task: Task | None = None
        self._result = None
        self._error = None
        self._user_data: Optional[Any] = None
        self._timeout: int | None = None
        self._timeout_id: int | None = None
        self._finalize_func: Callable[..., Any] | None = None
        self._finalize_context: Any = None
        self._state = TaskState.INIT

    @property
    def state(self) -> TaskState:
        return self._state

    def add_done_callback(
        self, callback: Callable[..., Any], weak: bool = True
    ) -> None:
        if self._state.is_finished or self._state.is_cancelled:
            raise RuntimeError("Task is finished")

        if weak:
            if inspect.ismethod(callback):
                callback = weakref.WeakMethod(callback)
            elif inspect.isfunction(callback):
                callback = weakref.ref(callback)
            else:
                raise ValueError("Unknown callback object")

        self._done_callbacks.append(callback)

    def set_timeout(self, timeout: int | None) -> None:
        self._timeout = timeout

    def start(self) -> None:
        if not self._state.is_init:
            raise RuntimeError("Task already started")

        if self._timeout is not None:
            self._logger.info(
                "Add timeout for task: %s s, task id: %s", self._timeout, id(self)
            )
            self._timeout_id = GLib.timeout_add_seconds(self._timeout, self._on_timeout)

        self._state = TaskState.RUNNING
        next(self._gen)
        self._next_step(self)

    def _run_async(self, data: Any) -> None:
        raise NotImplementedError

    def _async_finished(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError

    def _sub_task_completed(self, task: Task) -> None:
        self._sub_task = None
        if not self._state.is_running:
            return

        result = task.get_result()
        if is_fatal_error(result):
            self._error = result
            self._set_finished()
        else:
            self._next_step(result)

    def _next_step(self, result: Any) -> None:
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
                raise RuntimeError("Only one sub task can be active")

            self._sub_task = res
            self._sub_task.add_done_callback(self._sub_task_completed, weak=False)

        else:
            if res is not ResultSet:
                self._result = res
            self._set_finished()

    def _set_finished(self) -> None:
        self._state = TaskState.FINISHED
        self._invoke_callbacks()
        self._finalize()

    def _log_if_fatal(self, error: BaseError | Exception | Any) -> None:
        if is_error(error):
            assert isinstance(
                error,
                StanzaError
                | MalformedStanzaError
                | TimeoutStanzaError
                | CancelledError,
            )
            if error.is_fatal:
                self._logger.log(error.log_level, error)

        elif isinstance(error, Exception):
            self._logger.exception("Fatal Exception")

    def _invoke_callbacks(self) -> None:
        for callback in self._done_callbacks:
            if isinstance(callback, weakref.WeakMethod | weakref.ref):
                callback = callback()  # type: ignore
                if callback is None:
                    return

            # Be conservative with catching exceptions here
            # For example unittests raise Assertion errors
            # which should not be catched here
            try:
                callback(self)
            except CancelledError:
                pass

    def set_result(self, result: Any):
        self._result = result
        return ResultSet

    def get_result(self) -> Any:
        # if self._error is None, there was no error
        # but None is a valid value for self._result
        if self._error is not None:
            return self._error
        return self._result

    def finish(self) -> Any:
        if self._error is not None:
            raise self._error
        return self._result

    def set_user_data(self, user_data: Any) -> None:
        self._user_data = user_data

    def get_user_data(self) -> Any:
        return self._user_data

    def set_finalize_func(self, func: Callable[..., Any], context: Any = None) -> None:
        self._finalize_func = func
        self._finalize_context = context

    def _on_timeout(self) -> None:
        self._logger.info("Timeout reached, task id: %s", id(self))
        if not self._state.is_running:
            return

        self._timeout_id = None

        if self._sub_task is not None:
            self._sub_task.cancel(invoke_callbacks=False)

        self._error = TimeoutStanzaError()
        self._set_finished()

    def cancel(self, invoke_callbacks: bool = True) -> None:
        if not self._state.is_running:
            return

        self._state = TaskState.CANCELLED
        if self._sub_task is not None:
            self._sub_task.cancel(invoke_callbacks=False)

        self._error = CancelledError()
        if invoke_callbacks:
            self._invoke_callbacks()
        self._finalize()

    def _finalize(self) -> None:
        if self._timeout_id is not None:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = None
        self._done_callbacks.clear()
        self._sub_task = None
        self._error = None
        self._result = None
        self._user_data = None
        self._gen.close()
        if self._finalize_func is not None:
            self._finalize_func(self, self._finalize_context)


class IqRequestTask(Task):
    """
    A Task for running IQ requests

    """

    _process_types = (Node,)

    def __init__(
        self, gen: Generator[Any, Any, Any], logger: logging.Logger, client: Client
    ) -> None:
        super().__init__(gen, logger)
        self._client = client
        self._iq_id: str | None = None

    def _run_async(self, data: Node) -> None:
        assert self._client is not None
        self._iq_id = self._client.send_stanza(
            data, callback=self._async_finished, timeout=self._timeout
        )

    def _async_finished(
        self, _client: Client, result: Any, *args: Any, **kwargs: Any
    ) -> None:
        if self._state == TaskState.CANCELLED:
            return

        if result is None:
            self._error = TimeoutStanzaError()
            self._set_finished()
            return

        self._next_step(result)

    def _finalize(self) -> None:
        if self._iq_id is not None:
            self._client._dispatcher.remove_iq_callback(self._iq_id)  # type: ignore
        self._client = None
        super()._finalize()


class HTTPRequestTask(Task):
    """
    A Task for running HTTP requests

    """

    _process_types = (HTTPRequest,)

    def __init__(self, gen: Generator[Any, Any, Any], logger: logging.Logger) -> None:
        super().__init__(gen, logger)

    def _run_async(self, data: HTTPRequest) -> None:
        data.connect("finished", self._async_finished)

    def _async_finished(self, request: HTTPRequest) -> None:
        if self._state == TaskState.CANCELLED:
            return

        self._next_step(request)

    def _finalize(self) -> None:
        self._session = None
        super()._finalize()
