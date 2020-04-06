import pytest
import trio
from trio_jsonrpc.transport import TransportClosed
from trio_jsonrpc.transport.memory import MemoryTransport


async def test_memory_transport_recv_closed():
    client_send, server_recv = trio.open_memory_channel(0)
    server_send, client_recv = trio.open_memory_channel(0)
    mt = MemoryTransport(client_send, client_recv)
    await server_send.aclose()
    with pytest.raises(TransportClosed):
        await mt.recv()


async def test_memory_transport_send_closed():
    client_send, server_recv = trio.open_memory_channel(0)
    server_send, client_recv = trio.open_memory_channel(0)
    mt = MemoryTransport(client_send, client_recv)
    await server_recv.aclose()
    with pytest.raises(TransportClosed):
        await mt.send(b"foo")
