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
6. Possibly logging information about each request.

This library cannot feasibly implement a default solution that handles the
aforementioned items in a way that satsifies every downstream project. Instead, the
library gives you the pieces you need to build a server.

```python
from dataclasses import dataclass
import trio
from trio_jsonrpc import Dispatch, JsonRpcApplicationError
import trio_websocket

@dataclass
class RequestContext:
    """ A sample implementation for request context. """
    db: typing.Any = None
    authorized_employee: str = None

dispatch = Dispatch()

@dispatch.handler
async def open_vault_door(context, employee, pin):
    access = await context.db.check_pin(employee, pin)
    if access:
        context.authorized_employee = employee
        return {"door_open": True}
    else:
        context.authorized_employee = None
        raise JsonRpcApplicationError(code=-1, message="Not authorized.")

@dispatch.handler
async def close_vault_door(context):
    context.authorized_employee = None
    return {"door_open": False}

async def main():
    db = ...
    base_context = RequestContext(db=db)

    async def responder(conn, recv_channel):
        async for result in recv_channel:
            if

    async def connection_handler(ws_request):
        ws = await ws_request.accept()
        transport = WebSocketTransport(ws)
        rpc_conn = JsonRpcConnection(transport, JsonRpcConnectionType.SERVER)
        conn_context = copy(base_context)
        async with trio.open_nursery() as nursery:
            nursery.start_soon(rpc_conn._background_task)
            async for request in rpc_conn.iter_requests():
                nursery.start_soon(dispatch, request, conn_context)
            nursery.cancel_scope.cancel()

    await trio_websocket.serve_websocket(connection_handler, 'localhost', 8000, None)

trio.run(main)
```

This example defines a `RequestContext` class which is used to share state between
requests on the same connection. Next, a `Dispatch` object is created, which is used to
map JSON-RPC methods to Python functions. The `@dispatch.handler` decorator
automatically registers a Python function as a JSON-RPC method of the same name. Each
of these handlers takes a `context` object as well as the parameters included in the
JSON-RPC request. The use of the dispatch and/or context systems are entirely optional.

In `main()`, we set up a new WebSocket server. For each new connection, we complete the
WebSocket handshake and then wrap the connection in a `JsonRpcConnection`. Finally, we
iterate over the incoming JSON-RPC requsts and dispatch each one inside a new task.
