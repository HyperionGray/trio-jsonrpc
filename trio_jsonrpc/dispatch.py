"""
This module contains a flexible dispatch system for routing requests to a JSON-RPC
server to specific handler functions. Use of this module is completely optional, and it
is entirely possible to dispatch JSON-RPC methods yourself by directly calling the
server's ``iter_requests()`` method.
"""
from contextlib import asynccontextmanager
import contextvars
from functools import partial
from itertools import count
import logging
import types
import typing

from sansio_jsonrpc import JsonRpcRequest
import trio
from trio_jsonrpc import (
    JsonRpcConnection,
    JsonRpcInternalError,
    JsonRpcException,
    JsonRpcMethodNotFoundError,
)

# A sentinel value indicating that a connection context has not been set.
ContextNotSet = type("ContextNotSet", (object,), dict())()

logger = logging.getLogger(__name__)
contexts: typing.Dict[int, typing.Any] = dict()
connection_id = contextvars.ContextVar("connection_id", default=ContextNotSet)
connection_id_gen = count()


class Dispatch:
    """
    This class assists with dispatching JSON-RPC methods to specific handler functions.

    Each handler is registered using a decorator. When a method is executed on the
    dispatcher, it looks up the registered handler and calls it in a new task.
    """

    def __init__(self):
        """
        Constructor.

        :param nursery: A Nursery to launch handler tasks in.
        """
        self._handlers = dict()

    @property
    def ctx(self) -> typing.Any:
        """ Get the connection context for the current task. """
        id_ = connection_id.get()
        if id_ is ContextNotSet:
            raise RuntimeError(
                "The .context property is only valid in a connection context."
            )
        return contexts[id_]

    @asynccontextmanager
    async def connection_context(self, context):
        """ Set the connection context for the current task and all child tasks. """
        if connection_id.get() is not ContextNotSet:
            raise RuntimeError("The context has already been set.")
        id_ = next(connection_id_gen)
        token = connection_id.set(id_)
        contexts[id_] = context
        try:
            yield
        finally:
            connection_id.reset(token)
            del contexts[id_]

    def handler(self, fn):
        """
        A decorator that registers an async function as a handler.

        :param fn: The function to decorate.
        """
        try:
            name = fn.__name__
        except AttributeError:
            raise RuntimeError(
                "The Dispatch.handler() decorator must be applied to a named function."
            )
        self._handlers[name] = fn

    async def execute(self, request: JsonRpcRequest) -> typing.Any:
        """
        A helper for running a single JSON-RPC command and getting the result.

        This is mainly helpful for testing, since it returns the result directly rather
        than via channel.

        :param request:
        :returns: The result of the command.
        :raises: JsonRpcException if the command returned an error.
        """
        send_channel, recv_channel = trio.open_memory_channel(1)
        await self.handle_request(request, send_channel)
        _, result = await recv_channel.receive()
        print("execute", result)
        if isinstance(result, JsonRpcException):
            raise result
        return result

    async def handle_request(
        self, request: JsonRpcRequest, result_channel: trio.MemorySendChannel,
    ) -> None:
        """
        Dispatch a JSON-RPC request and send its result to the given channel.

        :param request:
        :param result_channel:
        :returns: The outcome of executing the JSON-RPC method, either a result or an
            error.
        """
        try:
            handler = self._get_handler(request.method)
            params = request.params
            if isinstance(params, list):
                result = await handler(*params)
            elif isinstance(params, dict):
                result = await handler(**params)
            else:
                result = await handler()
        except JsonRpcException as jre:
            result = jre
        except Exception as exc:
            logger.exception(
                'An unhandled exception occurred in handler "%s"', handler.__name__,
            )
            result = JsonRpcInternalError("An unhandled exception occurred.")
        await result_channel.send((request, result))

    def _get_handler(self, method: str):
        """ Find the handler function for a given JSON-RPC method name. """
        try:
            return self._handlers[method]
        except KeyError:
            raise JsonRpcMethodNotFoundError(f'Method "{method}" not found.') from None
