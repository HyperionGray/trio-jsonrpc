"""
Most of the testing is done through the in-memory transport, since that's simpler to
test against. For the WebSocket transport we just want to make sure that basic sending,
receiving, and closing features work correctly.
"""
from functools import partial
import logging

import pytest
import trio
from trio_jsonrpc import Dispatch, JsonRpcConnection, JsonRpcException, open_jsonrpc_ws
from trio_jsonrpc.main import JsonRpcConnectionType
from trio_jsonrpc.transport.ws import WebSocketTransport
import trio_websocket

from . import fail_after, parse_bytes


@fail_after(1)
async def test_websocket_roundtrip(nursery):
    """
    Create a WebSocket server and several clients.
    """
    dispatch = Dispatch()
    client_count = 0

    @dispatch.handler
    async def hello_world(n):
        return {"mode": "hello", "client_number": n}

    @dispatch.handler
    async def goodbye_world(n):
        return {"mode": "goodbye", "client_number": n}

    async def client(n):
        nonlocal client_count
        url = f"ws://localhost:{server_port}"
        logging.info("Client #%d: Connecting to %s", n, url)
        async with open_jsonrpc_ws(url) as client_conn:
            logging.info("Client #%d: Sending hello", n)
            resp = await client_conn.request(method="hello_world", params={"n": n})
            logging.info("Client #%d: Got hello response", n)
            assert resp["mode"] == "hello"
            assert resp["client_number"] == n

            logging.info("Client #%d: Sending goodbye", n)
            resp = await client_conn.request(method="goodbye_world", params={"n": n})
            logging.info("Client #%d: Got goodbye response", n)
            assert resp["mode"] == "goodbye"
            assert resp["client_number"] == n
        client_count += 1

    async def responder(recv_channel, conn):
        async for request, result in recv_channel:
            if isinstance(result, JsonRpcException):
                await conn.respond_with_error(request, result)
            else:
                await conn.respond_with_result(request, result)

    async def connection_handler(ws_request):
        ws = await ws_request.accept()
        transport = WebSocketTransport(ws)
        rpc_conn = JsonRpcConnection(transport, JsonRpcConnectionType.SERVER)
        result_send, result_recv = trio.open_memory_channel(10)
        async with trio.open_nursery() as conn_nursery:
            conn_nursery.start_soon(rpc_conn._background_task)
            conn_nursery.start_soon(responder, result_recv, rpc_conn)
            logging.info("Serving requests on new connection...")
            async for request in rpc_conn.iter_requests():
                print(request)
                conn_nursery.start_soon(dispatch.execute, request, result_send)
            conn_nursery.cancel_scope.cancel()

    server = await nursery.start(
        trio_websocket.serve_websocket, connection_handler, "localhost", 0, None
    )
    server_port = server.port
    logging.info("Server is listening on port %d", server_port)

    async with trio.open_nursery() as client_nursery:
        client_nursery.start_soon(client, 1)
        client_nursery.start_soon(client, 2)
        client_nursery.start_soon(client, 3)
        client_nursery.start_soon(client, 4)
        client_nursery.start_soon(client, 5)

    assert client_count == 5
