from contextlib import asynccontextmanager
import enum
import json
import logging
import ssl
import typing

from sansio_jsonrpc import (
    JsonRpcException,
    JsonRpcInternalError,
    JsonRpcPeer,
    JsonRpcRequest,
    JsonRpcResponse,
)
import trio
import trio_websocket

from .transport import BaseTransport, TransportClosed
from .transport.memory import MemoryTransport
from .transport.ws import WebSocketTransport


logger = logging.getLogger("trio_jsonrpc")


class JsonRpcConnectionType(enum.Enum):
    """
    An enumeration that identifies whether the peer is a client role or a server role.
    """

    CLIENT = 0
    SERVER = 1


class JsonRpcConnection:
    """ A JSON-RPC client. """

    def __init__(self, transport, peer_type):
        """ Constructor. """
        self._transport = transport
        self._peer_type = peer_type
        self._sansio_peer = JsonRpcPeer()
        self._bg_task_running = False
        self._outbound_requests = dict()
        irsend, irrecv = trio.open_memory_channel(0)
        self._inbound_requests_send = irsend
        self._inbound_requests_recv = irrecv

    @property
    def is_server(self):
        """ Returns True if this peer is in the server role. """
        return self._peer_type == JsonRpcConnectionType.SERVER

    @property
    def is_client(self):
        """ Returns True if this peer is in the client role. """
        return self._peer_type == JsonRpcConnectionType.CLIENT

    async def request(
        self, method: str, params: typing.Union[dict, list] = None
    ) -> typing.Any:
        """
        Send a request to the server and return its result.

        :returns: a response from the server
        :raises: a subclass of class:`JsonRpcException` if the server returns an error
        """
        request_id, bytes_to_send = self._sansio_peer.request(
            method=method, params=params
        )
        # The background task provides a response to this task using a one-time channel.
        response_send, response_recv = trio.open_memory_channel(0)
        self._outbound_requests[request_id] = response_send
        await self._transport.send(bytes_to_send)
        response = await response_recv.receive()
        if response.success:
            return response.result
        else:
            raise JsonRpcException.exc_from_error(response.error)

    async def notify(
        self, method: str, params: typing.Union[dict, list] = None
    ) -> None:
        """
        Send a notification.

        This does expect or wait for any response.
        """
        bytes_to_send = self._sansio_peer.notify(method, params)
        await self._transport.send(bytes_to_send)

    async def iter_requests(self):
        """
        An asynchronous iterator that yields each request (including notifications) as
        it is received.

        This is intended to be called on server objects, but this restriction is not
        enforced.
        """
        async for request in self._inbound_requests_recv:
            yield request

    async def respond_with_result(self, request, result):
        bytes_to_send = self._sansio_peer.respond_with_result(request, result)
        await self._transport.send(bytes_to_send)

    async def respond_with_error(self, request, error):
        bytes_to_send = self._sansio_peer.respond_with_error(request, error)
        await self._transport.send(bytes_to_send)

    async def _background_task(self):
        """
        The background task handles incoming messages.
        """
        self._bg_task_running = True

        while self._bg_task_running:
            try:
                bytes_received = await self._transport.recv()
                messages = self._sansio_peer.parse(bytes_received)
                for message in messages:
                    # sansio-jsonrpc guarantees that each message is either a request
                    # or a response.
                    if isinstance(message, JsonRpcRequest):
                        await self._inbound_requests_send.send(message)
                    else:
                        assert isinstance(message, JsonRpcResponse)
                        try:
                            response_send = self._outbound_requests.pop(message.id)
                            await response_send.send(message)
                        except KeyError:
                            id_ = message.id
                            msg = f"No in-flight request matches response.id={id_}"
                            logger.error(msg)
                            await self._background_send_error(JsonRpcInternalError(msg))
            except JsonRpcException as jre:
                if self.is_client:
                    # As client, we don't need to send a response, so we just log the
                    # error.
                    logger.exception("JSON-RPC exception in client background task.")
                else:
                    # As server, we should try to send an error response.
                    logger.exception("JSON-RPC exception in server background task.")
                    await self._background_send_error(jre)
            except trio.Cancelled:
                # If cancelled, end the loop.
                break
            except TransportClosed:
                # If the transport is closed on the receive side, we need to exit the
                # loop.
                logger.info(
                    "Background task is exiting because the receive transport is closed."
                )
                # We also close our requests channel so that any callers inside
                # `iter_requests()` will move on.
                await self._inbound_requests_send.aclose()
                break
            except Exception:
                # An uncaught exception shouldn't crash the background task, but we also
                # don't have any useful handling we can perform here.
                logger.exception("Unhandled exception in JSON-RPC background task.")

        self._bg_task_running = False

    async def _background_send_error(self, exc, request=None):
        try:
            bytes_to_send = self._sansio_peer.respond_with_error(
                request, exc.get_error()
            )
            await self._transport.send(bytes_to_send)
        except TransportClosed:
            # If the transport is closed on the send() side, then we keep the loop
            # running in case the transport is half-closed and we might still be able to
            # receive data.
            logger.error(
                "Server cannot send error response because the transport is closed."
            )


def jsonrpc_client(
    transport: BaseTransport, nursery: trio.Nursery,
) -> JsonRpcConnection:
    """ Create a JSON-RPC peer instance using the specified transport. """
    peer = JsonRpcConnection(transport, JsonRpcConnectionType.CLIENT)
    nursery.start_soon(peer._background_task)
    return peer


def jsonrpc_server(
    transport: BaseTransport, nursery: trio.Nursery, request_buffer_len: int = 1,
) -> JsonRpcConnection:
    """ Create a JSON-RPC peer instance using the specified transport. """
    request_buffer_send, request_buffer_recv = trio.open_memory_channel(
        request_buffer_len
    )

    peer = JsonRpcConnection(transport, JsonRpcConnectionType.SERVER)
    nursery.start_soon(peer._background_task)
    return peer


@asynccontextmanager
async def open_jsonrpc_memory(
    send_channel: trio.abc.SendChannel, recv_channel: trio.abc.ReceiveChannel,
) -> typing.AsyncIterator[JsonRpcConnection]:
    """
    Open a JSON-RPC connection using Trio channels as transport.

    This is mainly intended for testing, since the client and server must be running
    inside the same process.
    """
    async with trio.open_nursery() as nursery:
        transport = MemoryTransport(send_channel, recv_channel)
        yield jsonrpc_client(transport, nursery)
        nursery.cancel_scope.cancel()


@asynccontextmanager
async def serve_jsonrpc_memory(
    send_channel: trio.abc.SendChannel, recv_channel: trio.abc.ReceiveChannel,
):
    """
    Serve a JSON-RPC connection using Trio channels as transport.

    This is mainly intended for testing, since the client and server must be running
    inside the same process. Note that this only accepts 1 "connection": the one passed
    to this function.
    """
    async with trio.open_nursery() as nursery:
        transport = MemoryTransport(send_channel, recv_channel)
        yield jsonrpc_server(transport, nursery)
        nursery.cancel_scope.cancel()


@asynccontextmanager
async def open_jsonrpc_ws(url: str) -> typing.AsyncIterator[JsonRpcConnection]:
    """ Open a JSON-RPC connection using WebSocket transport. """
    async with trio_websocket.open_websocket_url(url) as ws:
        async with trio.open_nursery() as nursery:
            transport = WebSocketTransport(ws)
            yield jsonrpc_client(transport, nursery)
            nursery.cancel_scope.cancel()
