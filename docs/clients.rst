Clients
=======

.. currentmodule:: trio_jsonrpc

The following example shows a basic JSON-RPC client.

.. code:: python3

    import trio
    from trio_jsonrpc import open_jsonrpc_ws, JsonRpcException

    async def main():
        async with open_jsonrpc_ws('ws://example.com/') as client:
            try:
                result = await client.request(
                    method='open_vault_door',
                    {'employee': 'Mark', 'pin': 1234}
                )
                print('vault open:', result['vault_open'])

                await client.notify(method='hello_world')
            except JsonRpcException as jre:
                print('RPC failed:', jre)

    trio.run(main)

The example begins by opening a JSON-RPC connection using a WebSocket transport.

..note::

    The implementation is designed to support multiple types of transport, but currently
    WebSocket transport is the only one that has been implemented.

The connection is opened inside a context manager that guarantees the connection is
ready when entering the block and automatically closes the connection when leaving the
block.

Within the block, we call the client's :meth:`JsonRpcConnection.request` method to send
a JSON-RPC request. This method sends the request to the server, waits for a response,
and returns a result. If the server indicates that an error occurred, a
`JsonRpcException` will be raised instead. The client multiplexes requests so that it
can be use concurrently from multiple tasks; responses are routed back to the
appropriate task that called `request(...)`.

The client also has a `notify(...)` method which sends a request to the server but does
not expect or wait for a response.

There are two convenience functions for opening a JSON-RPC connection. Alternatively,
you can implement a custom transport class to wrap around some other type of connection,
such as bare TCP socket.

.. note::

    JSON-RPC does not contain any framing logic, i.e. a specification for how to
    identify message boundaries within a stream. Therefore, if you want to use JSON-RPC
    with raw TCP sockets, you either need to add your own framing logic or else use a
    streaming JSON parser. For this reason, we have chosen to focus on WebSocket
    transport initially, because WebSocket does include framing.

.. autofunction:: open_jsonrpc_ws
    :async-with: client

.. autofunction:: open_jsonrpc_memory
    :async-with: client
