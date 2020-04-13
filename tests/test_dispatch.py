import json
import types
from unittest.mock import Mock

import pytest
from sansio_jsonrpc import JsonRpcRequest
import trio
from trio_jsonrpc import (
    Dispatch,
    JsonRpcApplicationError,
    JsonRpcError,
    JsonRpcMethodNotFoundError,
    JsonRpcInternalError,
    serve_jsonrpc_memory,
)

from . import fail_after


async def test_dispatch_requests(nursery):
    dispatch = Dispatch()
    h1_calls = 0
    h1_args = None
    h2_calls = 0
    h2_args = None

    @dispatch.handler
    async def handler1(*args, **kwargs):
        nonlocal h1_calls
        nonlocal h1_args
        h1_calls += 1
        h1_args = args, kwargs
        return {"handled_by": "handler1"}

    @dispatch.handler
    async def handler2(*args, **kwargs):
        nonlocal h2_calls
        nonlocal h2_args
        h2_calls += 1
        h2_args = args, kwargs
        return {"handled_by": "handler2"}

    req1 = JsonRpcRequest(id=0, method="handler1", params={"foo": "bar"})
    result_send1, result_recv1 = trio.open_memory_channel(0)
    nursery.start_soon(dispatch.execute, req1, result_send1)
    _, result1 = await result_recv1.receive()
    assert result1["handled_by"] == "handler1"
    assert h1_calls == 1
    assert h2_calls == 0
    assert h1_args == (tuple(), {"foo": "bar"})

    req2 = JsonRpcRequest(id=0, method="handler2", params=[1, 2, 3])
    result_send2, result_recv2 = trio.open_memory_channel(0)
    nursery.start_soon(dispatch.execute, req2, result_send2)
    _, result2 = await result_recv2.receive()
    assert result2["handled_by"] == "handler2"
    assert h1_calls == 1
    assert h2_calls == 1
    assert h2_args == ((1, 2, 3), {})

    req3 = JsonRpcRequest(id=0, method="handler1")
    result_send3, result_recv3 = trio.open_memory_channel(0)
    nursery.start_soon(dispatch.execute, req3, result_send3)
    _, result3 = await result_recv3.receive()
    assert result3["handled_by"] == "handler1"
    assert h1_calls == 2
    assert h2_calls == 1
    assert h1_args == (tuple(), {})


async def test_dispatch_requires_named_method():
    dispatch = Dispatch()
    with pytest.raises(RuntimeError):
        await dispatch.handler(object())


async def test_dispatch_method_not_found(nursery):
    dispatch = Dispatch()
    result_send, result_recv = trio.open_memory_channel(0)
    nursery.start_soon(
        dispatch.execute, JsonRpcRequest(id=0, method="hello_world"), result_send
    )
    _, result = await result_recv.receive()
    assert isinstance(result, JsonRpcMethodNotFoundError)


async def test_handler_raises_jsonrpc_exc(nursery):
    """ A JSON-RPC exception in a handler should be returned as a result. """
    dispatch = Dispatch()

    @dispatch.handler
    async def foo_bar(*args, **kwargs):
        raise JsonRpcInternalError("foo bar")

    req = JsonRpcRequest(id=0, method="foo_bar")
    result_send, result_recv = trio.open_memory_channel(0)
    nursery.start_soon(dispatch.execute, req, result_send)
    _, result = await result_recv.receive()
    assert isinstance(result, Exception)


async def test_handler_raises_exc(caplog, nursery):
    """
    A non-JSON-RPC exception in a handler should be returned as a result and logged.
    """
    dispatch = Dispatch()

    @dispatch.handler
    async def foo_bar(*args, **kwargs):
        raise Exception("foo bar")

    req = JsonRpcRequest(id=0, method="foo_bar")
    result_send, result_recv = trio.open_memory_channel(0)
    nursery.start_soon(dispatch.execute, req, result_send)
    _, result = await result_recv.receive()
    assert isinstance(result, Exception)
    assert 'An unhandled exception occurred in handler "foo_bar"' in caplog.text


async def test_dispatch_context_inside_request(nursery):
    """
    If a context is provided, it should be passed into the handler.
    """
    dispatch = Dispatch()

    class MyRequestContext:
        pass

    @dispatch.handler
    async def foo_bar(context, *args, **kwargs):
        return isinstance(context, MyRequestContext)

    req = JsonRpcRequest(id=0, method="foo_bar")
    result_send, result_recv = trio.open_memory_channel(0)
    nursery.start_soon(dispatch.execute, req, result_send, MyRequestContext())
    _, result = await result_recv.receive()
    assert result == True
