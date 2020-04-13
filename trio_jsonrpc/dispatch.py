"""
This module contains a flexible dispatch system for routing requests to a JSON-RPC
server to specific handler functions. Use of this module is completely optional, and it
is entirely possible to dispatch JSON-RPC methods yourself by directly calling the
server's ``iter_requests()`` method.
"""
from copy import copy
from functools import partial
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


logger = logging.getLogger(__name__)


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

    async def execute(
        self,
        request: JsonRpcRequest,
        result_channel: trio.MemorySendChannel,
        context: typing.Any = None,
    ) -> typing.Any:
        """
        Dispatch a JSON-RPC request and send its result to the given channel.

        :param request:
        :param result_channel:
        :param context:
        """
        try:
            handler = self._get_handler(request.method)
            params = request.params
            if context is None:
                if isinstance(params, list):
                    fn = partial(handler, *params)
                elif isinstance(params, dict):
                    fn = partial(handler, **params)
                else:
                    fn = handler
            else:
                if isinstance(params, list):
                    fn = partial(handler, context, *params)
                elif isinstance(params, dict):
                    fn = partial(handler, context, **params)
                else:
                    fn = partial(handler, context)
            result = await fn()
        except JsonRpcException as jre:
            result = jre
        except Exception as exc:
            logger.exception(
                'An unhandled exception occurred in handler "%s" context=%r',
                handler.__name__,
                context,
            )
            result = JsonRpcInternalError("An unhandled exception occurred.")
        await result_channel.send((request, result))

    def _get_handler(self, method: str):
        """ Find the handler function for a given JSON-RPC method name. """
        try:
            return self._handlers[method]
        except KeyError:
            raise JsonRpcMethodNotFoundError(f'Method "{method}" not found.') from None
