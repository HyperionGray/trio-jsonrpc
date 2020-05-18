Servers
=======

.. currentmodule:: trio_jsonrpc

The following example shows a basic JSON-RPC server. The server is more DIY (do it
yourself) than the client because a server has more responsibilties:

1. Setting up the transport, especially if the transport requires a handshake as
   WebSocket does.
2. Handling new connections to the server.
3. Multiplexing requests on a single connection.
4. Managing connection state over the course of multiple requests.
5. Applying pre-handler or post-handler logic to each request.

This library cannot feasibly implement a default solution that handles the
aforementioned items in a way that satsifies every downstream project. Instead, the
library gives you the pieces you need to build a server. We will go through each piece
one at a time.

.. code:: python3

    import trio
    from trio_jsonrpc import (
        JsonRpcConnection,
        JsonRpcConnectionType,
        JsonRpcMethodNotFoundError,
    )
    import trio_websocket

    async def greet(name: str) -> dict:
        return {"greeting": "Hello, {}!".format(name)}

We import a few things we need to make a server. We also declare a function that we will
use as a JSON-RPC method.

.. code:: python3

    async def run_server(host, port):
        async def connection_handler(ws_request):
            ws = await ws_request.accept()
            transport = WebSocketTransport(ws)
            rpc_conn = JsonRpcConnection(transport, JsonRpcConnectionType.SERVER)
            async with trio.open_nursery() as nursery:
                nursery.start_soon(rpc_conn._background_task)
                async for request in rpc_conn.iter_requests():
                    if request.method == 'greet':
                        result = await greet(*request.params)
                        await rpc_conn.reply_with_result(request, result)
                    else:
                        err = JsonRpcMethodNotFoundError().get_error()
                        await rpc_conn.reply_with_error(request, err)
                nursery.cancel_scope.cancel()

        await trio_websocket.serve_websocket(connection_handler, host, port, None)

The main server loop gets started by creating a new WebSocket (``serve_websocket(...)``)
and passing in a handler that gets invoked for each new connection. This handler
completes the WebSocket handshake and wraps it up in a
:class:`trio_jsonrpc.transport.ws.WebSocketTransport`. The server starts a nursery so
that it can run the connection's background task. In the foreground task, the server
iterates over the incoming requests and dispatches them, using the ``request.method``
to figure out which method is being requested, and using ``request.params`` to pass the
JSON-RPC parameters to the Python handler function.

To serve JSON-RPC over a WebSocket, you'll need to instantiate transport and connection
objects.

.. autoclass:: trio_jsonrpc.transport.ws.WebSocketTransport
    :members:

.. autoclass:: trio_jsonrpc.main.JsonRpcConnection
    :members:

You can also serve JSON-RPC over in-memory channels, to pair with
:meth:`open_jsonrpc_memory`.

.. autofunction:: serve_jsonrpc_memory
