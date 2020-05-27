from __future__ import annotations
import argparse
from copy import copy
from dataclasses import dataclass
import logging
import typing

import trio
from trio_jsonrpc import (
    Dispatch,
    JsonRpcApplicationError,
    JsonRpcConnection,
    JsonRpcConnectionType,
    JsonRpcException,
)
from trio_jsonrpc.transport.ws import WebSocketTransport
import trio_websocket

from .shared import AuthorizationError, InsufficientFundsError


user_pins = {
    "john": 1234,
    "jane": 5678,
}
user_balances = {
    "john": 100,
    "jane": 100,
}
dispatch = Dispatch()
logger = logging.getLogger("server")


@dataclass
class ConnectionContext:
    """ This object stores the context data for each connection. """

    user: typing.Optional[str] = None


@dispatch.handler
async def login(user: str, pin: int) -> bool:
    """
    Verify the user's pin and update connection context.

    :param user: The user to log in as.
    :param pin: The user's pin number.
    :returns: True if login succeeds or else false.
    """
    try:
        user_pin = user_pins[user]
    except KeyError:
        return False
    if user_pin == pin:
        dispatch.ctx.user = user
        return True
    else:
        return False


@dispatch.handler
async def get_balance() -> int:
    """
    Get the user's current balance.

    :error AuthorizationError: if not authorized
    :returns: The current balance.
    """
    if dispatch.ctx.user is None:
        raise AuthorizationError()
    return user_balances[dispatch.ctx.user]


@dispatch.handler
async def transfer(*, to: str, amount: int) -> None:
    """
    Transfer some money to another user.

    :param to: The name of the user to transfer money to.
    :param amount: The amount of money to transfer.
    :error AuthorizationError: if not authorized
    :error InsufficientFundsError: if not authorized
    """
    from_ = dispatch.ctx.user
    if from_ is None:
        raise AuthorizationError()
    if user_balances[from_] < amount:
        raise InsufficientFundsError()
    user_balances[to] += amount
    user_balances[from_] -= amount


async def run_server(port):
    """ The main entry point for the server. """
    base_context = ConnectionContext()

    async def responder(conn, recv_channel):
        """ This task reads results from finished method handlers and sends them back
        to the client. """
        async for request, result in recv_channel:
            if isinstance(result, JsonRpcException):
                await conn.respond_with_error(request, result.get_error())
            else:
                await conn.respond_with_result(request, result)

    async def connection_handler(ws_request):
        """ Handle a new connection by completing the WebSocket handshake and then
        iterating over incoming messages. """
        ws = await ws_request.accept()
        transport = WebSocketTransport(ws)
        rpc_conn = JsonRpcConnection(transport, JsonRpcConnectionType.SERVER)
        conn_context = copy(base_context)
        result_send, result_recv = trio.open_memory_channel(10)
        async with trio.open_nursery() as nursery:
            nursery.start_soon(responder, rpc_conn, result_recv)
            nursery.start_soon(rpc_conn._background_task)
            async with dispatch.connection_context(conn_context):
                async for request in rpc_conn.iter_requests():
                    nursery.start_soon(dispatch.handle_request, request, result_send)
            nursery.cancel_scope.cancel()

    logger.info("Listening on port %d (Type ctrl+c to exit) ", port)
    await trio_websocket.serve_websocket(connection_handler, "localhost", port, None)


async def main(args):
    try:
        await run_server(args.port)
    except KeyboardInterrupt:
        logger.info("Received SIGINT: quitting")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trio JSON-RPC Server Example")
    parser.add_argument(
        "--log-level",
        default="info",
        metavar="LEVEL",
        choices=["debug", "info", "warning", "error", "critical"],
        help="Set logging verbosity (default: info)",
    )
    parser.add_argument("--port", default=8000, type=int, help="Port to listen on")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper()))
    trio.run(main, args)
