from trio_websocket import ConnectionClosed

from . import BaseTransport, TransportClosed


class WebSocketTransport(BaseTransport):
    def __init__(self, ws):
        self._ws = ws

    async def recv(self) -> bytes:
        try:
            return await self._ws.get_message()
        except ConnectionClosed:
            raise TransportClosed()

    async def send(self, data: bytes) -> None:
        try:
            return await self._ws.send_message(data)
        except ConnectionClosed:
            raise TransportClosed()
