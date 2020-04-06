# JSON-RPC v2.0 for Trio

This project provides an implementation of [JSON-RPC v
2.0](https://www.jsonrpc.org/specification) based on
`[sansio-jsonrpc](https://github.com/hyperiongray/sansio-jsonrpc)` with all of the I/O
implemented using the [Trio asynchronous framework](https://trio.readthedocs.io).

## Client Example

The following example shows a basic JSON-RPC client.

```python
from trio_jsonrpc import open_jsonrpc_ws, JsonRpcException

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

The following example shows a basic JSON-RPC server.

```python
from trio_jsonrpc import serve_jsonrpc_ws, JsonRpcException, JsonRpcMethodNotFoundException

async with serve_jsonrpc_ws('ws://example.com/') as server:
    async for request in server.listen():
        if request.method == 'open_vault_door':
            await server.respond_with_result({"door_status": "open"})
        else:
            await server.respond_with_error({})
```

The server looks similar to the client, except it uses a different method to set up the
context manager. Inside the context manager, we enter a loop that gets each request as
it comes in. From there we can handle the request or send back an error to the client.

This example is pretty simplistic and contains some limitations. For example, the server
can only respond to one request at a time. If it takes a while to complete a request,
all of the requests received after it will be blocked. Also, the approach for checking
the requested method name won't scale well to large projects.

The next example introduces a new abstraction that solves both of these issues.

```python
import trio
from trio_jsonrpc import Dispatch, serve_jsonrpc_ws, JsonRpcException

app_dispatch = Dispatch()

@app_dispatch.handler
async def open_vault_door():
    return {"door_status": "open"}

async with serve_jsonrpc_ws('ws://example.com/') as server:
    async with trio.open_nursery() as nursery:
        async for request in server.listen():
            nursery.start_soon(app_dispatch.dispatch, server, request)
```

The first change here is that we've moved the handler code into a separate function. We
have also instantiated a `Dispatch` object. The dispatch object is used to map a
JSON-RPC method name to a Python handler function by decorating each handler function.

The other change is that inside the server we are creating a new nursery. Each time we
get a request, we spawn a new task to handle it so that the main task can go back to
listening for new reqests. The dispatch object takes care of figuring out which handler
to call, passing in the correct arguments, and converting the return value (or raised
exception) into an appropriate JSON-RPC response.
