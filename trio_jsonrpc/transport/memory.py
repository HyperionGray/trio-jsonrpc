import trio

from . import BaseTransport, TransportClosed


class MemoryTransport(BaseTransport):
    def __init__(self, send_channel, recv_channel):
        self._send_channel = send_channel
        self._recv_channel = recv_channel

    async def recv(self) -> bytes:
        try:
            return await self._recv_channel.receive()
        except (trio.EndOfChannel, trio.ClosedResourceError):
            raise TransportClosed()

    async def send(self, data: bytes) -> None:
        try:
            return await self._send_channel.send(data)
        except trio.BrokenResourceError:
            raise TransportClosed()
