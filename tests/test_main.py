"""
All of the tests in this file use in-memory transport since it is simpler to test
against than other transports.
"""

import json
from unittest.mock import Mock

import logging
import pytest
import trio
from trio_jsonrpc import (
    JsonRpcException,
    JsonRpcMethodNotFoundError,
    open_jsonrpc_memory,
    serve_jsonrpc_memory,
)

from . import AsyncMock, fail_after, parse_bytes


class MemoryClient:
    """ An in-memory client used with the MemoryTransport. """

    def __init__(self, channel_size=10):
        self.client_send, self.server_recv = trio.open_memory_channel(channel_size)
        self.server_send, self.client_recv = trio.open_memory_channel(channel_size)

    def server_channels(self):
        return self.server_send, self.server_recv

    async def aclose(self):
        await self.client_send.aclose()
        await self.client_recv.aclose()

    async def recv(self):
        return await self.client_recv.receive()

    async def send(self, data):
        await self.client_send.send(data)


@pytest.fixture
def client():
    """ An in-memory client fixture used with the MemoryTransport. """
    return MemoryClient()


class MemoryServer:
    """ An in-memory server used with the MemoryTransport. """

    def __init__(self, channel_size=10):
        self.client_send, self.server_recv = trio.open_memory_channel(channel_size)
        self.server_send, self.client_recv = trio.open_memory_channel(channel_size)

    def client_channels(self):
        return self.client_send, self.client_recv

    async def recv(self):
        return await self.server_recv.receive()

    async def send(self, data):
        await self.server_send.send(data)


@pytest.fixture
def server():
    """ An in-memory server fixture used with the MemoryTransport. """
    return MemoryServer()


@fail_after(1)
async def test_request_result(nursery, server):
    """ This test runs a round trip from the client to the server. """

    async def background():
        logging.info("Server recv()...")
        server_bytes = await server.recv()
        logging.info("Server recv() -> %d bytes", len(server_bytes))
        assert parse_bytes(server_bytes) == {
            "id": 0,
            "method": "hello_world",
            "jsonrpc": "2.0",
        }
        resp = b'{"id": 0, "result": {"greeting": "hello!"}, "jsonrpc": "2.0"}'
        await server.send(resp)
        logging.info("Server send() -> %d bytes", len(resp))

    nursery.start_soon(background)

    async with open_jsonrpc_memory(*server.client_channels()) as client:
        logging.info("Client is connected")
        assert client.is_client
        assert not client.is_server
        logging.info("Client request()...")
        result = await client.request(method="hello_world")
        logging.info("Client request() -> got result")
        assert result["greeting"] == "hello!"


@fail_after(1)
async def test_request_error(nursery, server):
    """
    This test returns an error from the server, which should raise in the client.
    """

    async def background():
        logging.info("Server recv()...")
        server_bytes = await server.recv()
        logging.info("Server recv() -> %d bytes", len(server_bytes))
        assert parse_bytes(server_bytes) == {
            "id": 0,
            "method": "hello_world",
            "jsonrpc": "2.0",
        }
        resp = (
            b'{"id": 0, "error": {"code": -32601, "message": "Method not found"}, '
            b'"jsonrpc": "2.0"}'
        )
        logging.info("Server send()...")
        await server.send(resp)
        logging.info("Server send() -> %d bytes", len(resp))

    nursery.start_soon(background)

    async with open_jsonrpc_memory(*server.client_channels()) as client:
        logging.info("Client is connected")
        logging.info("Client request()...")
        with pytest.raises(JsonRpcMethodNotFoundError) as exc_info:
            result = await client.request(method="hello_world")
        logging.info("Client request() -> handled exception")
        assert exc_info.value.code == -32601
        assert exc_info.value.message == "Method not found"
        assert exc_info.value.data is None


@fail_after(1)
async def test_client_response_does_not_match_request(
    autojump_clock, caplog, nursery, server
):
    async def background():
        server_bytes = await server.recv()
        resp = b'{"id": 1, "result": {"greeting": "hello!"}, "jsonrpc": "2.0"}'
        await server.send(resp)

    nursery.start_soon(background)

    async with open_jsonrpc_memory(*server.client_channels()) as client:
        with trio.move_on_after(0.5):
            result = await client.request(method="hello_world")

    assert "No in-flight request matches response.id=1" in caplog.text


@fail_after(1)
async def test_client_bg_task_exc(autojump_clock, caplog, nursery, server):
    """
    If the client catches a JSON-RPC error in its background task, it should log the
    event.
    """

    async def background():
        logging.info("Server recv()...")
        server_bytes = await server.recv()
        logging.info("Server recv() -> %d bytes", len(server_bytes))
        await server.send(b"{")

    nursery.start_soon(background)

    async with open_jsonrpc_memory(*server.client_channels()) as client:
        # This request will never return because the server sends back garbage, so we
        # force it to give up quickly (before the test times out).
        with trio.move_on_after(0.5):
            await client.request(method="hello_world")
        assert "JSON-RPC exception in client background task" in caplog.text
        assert client._bg_task_running


@fail_after(1)
async def test_bg_task_transport_closed(autojump_clock, caplog, nursery, server):
    """
    If the background task cannot receive data due a closed transport, it should log
    and exit.
    """
    client_send, client_recv = server.client_channels()
    async with open_jsonrpc_memory(client_send, client_recv) as client:
        await server.server_send.aclose()
        with trio.move_on_after(0.5):
            await client.request("hello_world")
        assert (
            "Background task is exiting because the receive transport is closed"
            in caplog.text
        )
        assert not client._bg_task_running


@fail_after(1)
async def test_bg_task_unhandled_exc(autojump_clock, caplog, nursery, server):
    """
    If the background task catches an unhandled exception, it should log it and keep
    running.
    """
    async with open_jsonrpc_memory(*server.client_channels()) as client:
        client._sansio_peer.parse = Mock(side_effect=RuntimeError)
        await server.server_send.send(b"foo")
        with trio.move_on_after(0.5):
            await client.request("hello_world")
        assert "Unhandled exception in JSON-RPC background task" in caplog.text
        assert client._bg_task_running


async def test_notify(nursery, server):
    async def background():
        server_bytes = await server.recv()
        logging.info("Server recv() -> %d bytes", len(server_bytes))
        assert parse_bytes(server_bytes) == {
            "method": "hello_world",
            "params": {"foo": "bar"},
            "jsonrpc": "2.0",
        }

    nursery.start_soon(background)

    async with open_jsonrpc_memory(*server.client_channels()) as client:
        result = await client.notify(method="hello_world", params={"foo": "bar"})
        await trio.sleep(0)


@fail_after(1)
async def test_serve_two_responses(nursery, client):
    async def background():
        await client.send(b'{"id": 0, "method": "foo", "jsonrpc": "2.0"}')
        client_bytes = await client.recv()
        assert parse_bytes(client_bytes) == {
            "id": 0,
            "result": {"foo": 0},
            "jsonrpc": "2.0",
        }

        await client.send(b'{"id": 1, "method": "foo", "jsonrpc": "2.0"}')
        client_bytes2 = await client.recv()
        assert parse_bytes(client_bytes2) == {
            "id": 1,
            "result": {"foo": 1},
            "jsonrpc": "2.0",
        }

    nursery.start_soon(background)

    async with serve_jsonrpc_memory(*client.server_channels()) as server:
        async for request in server.iter_requests():
            await server.respond_with_result(request, {"foo": request.id})
            if request.id == 1:
                break


@fail_after(1)
async def test_serve_respond_with_error(nursery, client):
    async def background():
        await client.send(b'{"id": 0, "method": "foo", "jsonrpc": "2.0"}')
        client_bytes = await client.recv()
        assert parse_bytes(client_bytes) == {
            "id": 0,
            "error": {"code": -32601, "message": "method foo does not exist"},
            "jsonrpc": "2.0",
        }

    nursery.start_soon(background)

    async with serve_jsonrpc_memory(*client.server_channels()) as server:
        async for request in server.iter_requests():
            try:
                raise JsonRpcMethodNotFoundError("method foo does not exist")
            except JsonRpcException as jre:
                await server.respond_with_error(request, jre.get_error())
            break


@fail_after(1)
async def test_server_bg_task_exc(nursery, client):
    """
    If the server catches a JSON-RPC error in its background task, it should try to send
    a response.
    """

    async def background():
        async with seq(0):
            await client.send(b"{")
            client_bytes = await client.recv()
            assert parse_bytes(client_bytes) == {
                "id": None,
                "error": {"code": -32700, "message": "Invalid JSON format"},
                "jsonrpc": "2.0",
            }

    seq = trio.testing.Sequencer()
    nursery.start_soon(background)

    async with serve_jsonrpc_memory(*client.server_channels()) as server:
        async with seq(1):
            pass


@fail_after(1)
async def test_server_bg_task_exc_transport_closed(caplog, nursery, client):
    """
    If the server catches a JSON-RPC error in its background task and the transport is
    closed, then it should log the exception.
    """

    async def background():
        async with seq(0):
            # The client sends a message that will trigger a server error, but the
            # server can't send a response because the client closed its receive
            # channel.
            await client.client_recv.aclose()
            await client.send(b"{")

    seq = trio.testing.Sequencer()
    nursery.start_soon(background)

    async with serve_jsonrpc_memory(*client.server_channels()) as server:
        async with seq(1):
            pass

    assert (
        "Server cannot send error response because the transport is closed"
        in caplog.text
    )
