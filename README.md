# JSON-RPC v2.0 for Trio

[![PyPI](https://img.shields.io/pypi/v/trio-jsonrpc.svg?style=flat-square)](https://pypi.org/project/trio-jsonrpc/)
![Python Versions](https://img.shields.io/pypi/pyversions/trio-jsonrpc.svg?style=flat-square)
![MIT License](https://img.shields.io/github/license/HyperionGray/trio-jsonrpc.svg?style=flat-square)
[![Build Status](https://img.shields.io/travis/com/HyperionGray/trio-jsonrpc.svg?style=flat-square&branch=master)](https://travis-ci.com/HyperionGray/trio-jsonrpc)
[![codecov](https://codecov.io/gh/HyperionGray/trio-jsonrpc/branch/master/graph/badge.svg)](https://codecov.io/gh/HyperionGray/trio-jsonrpc)

This project provides an implementation of [JSON-RPC v
2.0](https://www.jsonrpc.org/specification) based on
[sansio-jsonrpc](https://github.com/hyperiongray/sansio-jsonrpc) with all of the I/O
implemented using the [Trio asynchronous framework](https://trio.readthedocs.io).

## Client Example

The following example shows a basic JSON-RPC client.

```python
from trio_jsonrpc import open_jsonrpc_ws, JsonRpcException

async def main():
    async with open_jsonrpc_ws('ws://example.com/') as client:
        try:
            resp = await client.request(
                method='open_vault_door',
                {'employee': 'Mark', 'pin': 1234}
            )
            print(resp.result)

            await client.notify(method='hello_world')
        except JsonRpcException as jre:
            print('RPC failed:', jre)

trio.run(main)
```

The example begins by opening a JSON-RPC connection using a WebSocket transport. The
implementation is designed to support multiple types of transport, but currently
WebSocket transport is the only one that has been implemented.

> Note that JSON-RPC does not contain any framing logic, i.e. a specification for how to
> identify message boundaries within a stream. Therefore, if you want to use JSON-RPC
> with raw TCP sockets, you either need to add your own framing logic or else use a
> streaming JSON parser. For this reason, we have chosen to focus on WebSocket transport
> initially, because WebSocket does include framing.

The connection is opened inside a context manager that guarantees the connection is
ready when entering the block and automatically closes the connection when leaving the
block.

Within the block, we call the client's `request(...)` method to send a JSON-RPC request.
This method sends the request to the server, waits for a response, and returns a
`JsonRpcResponse` object. If the server indicates that an error occurred, a
`JsonRpcException` will be raised instead. The client multiplexes requests so that it
can be use concurrently from multiple tasks; responses are routed back to the
appropriate task that called `request(...)`.

The client also has a `notify(...)` method which sends a request to the server but does
not expect or wait for a response.

## Server Example

The following example shows a basic JSON-RPC server. The server is more DIY (do it
yourself) than the client because a server has to incorporate several disparate
functionalities:

1. Setting up the transport, especially if the transport requires a handshake as
   WebSocket does.
2. Handling new connections to the server.
3. Multiplexing requests on a single connection.
4. Dispatching a request to an appropriate handler.
5. Managing connection state over the course of multiple requests. (I.e. allowing one
   handler to indicate that the connection is authorized, so other handlers can use that
   authorization information to make access control decisions.)
6. Applying pre-handler or post-handler logic to each request, for example logging
   each request before it is dispatched.

This library cannot feasibly implement a default solution that handles the
aforementioned items in a way that satsifies every downstream project. Instead, the
library gives you the pieces you need to build a server. We will go through each piece
one at a time.

```python
from dataclasses import dataclass
import trio
from trio_jsonrpc import Dispatch, JsonRpcApplicationError
import trio_websocket

@dataclass
class ConnectionContext:
    """ A sample implementation for request context. """
    db: typing.Any = None
    authorized_employee: str = None

dispatch = Dispatch()
```

In this first piece, we import a few things we need. We also define a
`ConnectionContext` class. The purpose of this class is to share mutable connection
state between different handlers on the same connection. For example, we can have one
handler that authenticates a user and then sets authorization data in the connection
context. Later, another handler can check that authorization data to make access control
decisions.

You are free to pass any object as a connection context, as long as it can be copied
with `copy.copy()`. A dataclass is often convenient for this purpose.

```python
@dispatch.handler
async def open_vault_door(employee, pin):
    access = await dispatch.ctx.db.check_pin(employee, pin)
    if access:
        dispatch.ctx.authorized_employee = employee
        return {"door_open": True}
    else:
        dispatch.ctx.authorized_employee = None
        raise JsonRpcApplicationError(code=-1, message="Not authorized.")

@dispatch.handler
async def close_vault_door():
    dispatch.ctx.authorized_employee = None
    return {"door_open": False}
```

In this section, we define two JSON-RPC methods. Each one is annotated with
`@dispatch.handler`, which means when we dispatch an incoming request, it will look up
the Python function that matches the JSON-RPC method name. The JSON-RPC parameters are
passed as arguments to the handler function.

Each handler can access the connection context as `dispatch.ctx`.

Also note that if a handler needs to signal an error, it can raise
`JsonRpcApplicationError` (or any subclass of it). The dispatcher will automatically
convert the exception into a JSON-RPC error to send back to the client. If a handler
raises any exception that is not a subclass of `JsonRpcException`—i.e. if your handler
is buggy and raises something like `KeyError`—then a generic `JsonRpcInternalError` is
sent back to the client, and the entire exception is logged.

```
async def main():
    db = ...
    base_context = ConnectionContext(db=db)

    async def responder(conn, recv_channel):
        async for result in recv_channel:
            if isinstance(result, JsonRpcException):
                await conn.respond_with_error(result.get_error())
            else:
                await conn.respond_with_result(result)

    async def connection_handler(ws_request):
        ws = await ws_request.accept()
        transport = WebSocketTransport(ws)
        rpc_conn = JsonRpcConnection(transport, JsonRpcConnectionType.SERVER)
        conn_context = copy(base_context)
        result_send, result_recv = trio.open_memory_channel(10)
        async with trio.open_nursery() as nursery:
            nursery.start_soon(responder, result_recv)
            nursery.start_soon(rpc_conn._background_task)
            async with dispatch.connection_context(conn_context):
                async for request in rpc_conn.iter_requests():
                    nursery.start_soon(dispatch.handle_request, request, result_send)
            nursery.cancel_scope.cancel()

    await trio_websocket.serve_websocket(connection_handler, 'localhost', 8000, None)

trio.run(main)
```

The final section has a lot going on. First of all, we set up a base connection context.
This base object is used as a blueprint: for each new connection, the context is copied
and then set as the context for that connection. As long as that connection stays alive,
all handlers will share that same context object.

At the end of `main()`, the server is started by calling
`trio_websocket.serve_websocket()`. For each new connection, the
`connection_handler(...)` is called. This function finishes the WebSocket handshake and
then wraps the WebSocket connection into a JSON-RPC connection. Then it iterates over
the incoming requests and uses the dispatcher to handle each one.

Since each JSON-RPC request is dispatched in a new task, it isn't possible to directly
`await` the result of each task. Instead, we create a Trio channel and pass it into the
dispatcher. When the handler finishes, its result will be written to this channel. We
use a background task called `responder(...)` to read from this channel and actually
send the response to the client.
