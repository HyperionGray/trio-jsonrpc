from abc import ABC, abstractmethod


class BaseTransport(ABC):
    """ A base class for JSON-RPC transports. """

    @abstractmethod
    async def recv(self) -> bytes:
        """ Receive data from the transport. """

    @abstractmethod
    async def send(self, data: bytes):
        """ Send data through the transport."""


class TransportClosed(Exception):
    pass
