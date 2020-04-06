import logging
import typing

from sansio_jsonrpc import JsonRpcException, JsonRpcMethodNotFoundError, JsonRpcRequest
import trio


logger = logging.getLogger(__name__)


class Dispatch:
    """
    This class assists with dispatching JSON-RPC methods to specific handler functions.

    Each handler is registered using a decorator. When a method is executed on the
    dispatcher, it looks up the registered handler and calls it in a new task.
    """

    def __init__(self, nursery):
        self._handlers = dict()
        self._nursery = nursery

    # TODO add context variable

    def handler(self, fn):
        try:
            name = fn.__name__
        except AttributeError:
            raise RuntimeError(
                "The Dispatch.handler() decorator must be applied to a named function."
            )
        self._handlers[name] = fn

    async def execute(
        self, request: JsonRpcRequest, result_channel: trio.MemorySendChannel
    ):
        try:
            handler = self._handlers[request.method]
        except KeyError:
            msg = f'Method "{request.method}" not found.'
            raise JsonRpcMethodNotFoundError(msg) from None

        self._nursery.start_soon(self._execute, result_channel, handler, request.params)

    async def _execute(self, result_channel, handler, params):
        try:
            # sansio-jsonrpc guarantees that params are either a list, dict, or None.
            if isinstance(params, list):
                result = await handler(*params)
            elif isinstance(params, dict):
                result = await handler(**params)
            else:
                result = await handler()
        except Exception as exc:
            result = exc
            if not isinstance(exc, JsonRpcException):
                logger.exception(
                    "An unhandled exception occurred in handler %s.", handler.__name__
                )
        await result_channel.send(result)
