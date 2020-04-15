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


async def test_dispatch_requests():
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
    result1 = await dispatch.execute(req1)
    assert result1["handled_by"] == "handler1"
    assert h1_calls == 1
    assert h2_calls == 0
    assert h1_args == (tuple(), {"foo": "bar"})

    req2 = JsonRpcRequest(id=0, method="handler2", params=[1, 2, 3])
    result2 = await dispatch.execute(req2)
    assert result2["handled_by"] == "handler2"
    assert h1_calls == 1
    assert h2_calls == 1
    assert h2_args == ((1, 2, 3), {})

    req3 = JsonRpcRequest(id=0, method="handler1")
    result3 = await dispatch.execute(req3)
    assert result3["handled_by"] == "handler1"
    assert h1_calls == 2
    assert h2_calls == 1
    assert h1_args == (tuple(), {})


async def test_dispatch_requires_named_method():
    dispatch = Dispatch()
    with pytest.raises(RuntimeError):
        await dispatch.handler(object())


async def test_dispatch_method_not_found():
    dispatch = Dispatch()
    with pytest.raises(JsonRpcMethodNotFoundError):
        await dispatch.execute(JsonRpcRequest(id=0, method="hello_world"))


async def test_handler_raises_jsonrpc_exc():
    """ A JSON-RPC exception in a handler should be raised. """
    dispatch = Dispatch()

    @dispatch.handler
    async def foo_bar(*args, **kwargs):
        raise JsonRpcInternalError("foo bar")

    with pytest.raises(JsonRpcInternalError):
        result = await dispatch.execute(JsonRpcRequest(id=0, method="foo_bar"))


async def test_handler_raises_exc(caplog):
    """
    A non-JSON-RPC exception in a handler should be raised and logged.
    """
    dispatch = Dispatch()

    @dispatch.handler
    async def foo_bar(*args, **kwargs):
        raise Exception("foo bar")

    with pytest.raises(JsonRpcInternalError):
        await dispatch.execute(JsonRpcRequest(id=0, method="foo_bar"))
    assert 'An unhandled exception occurred in handler "foo_bar"' in caplog.text


async def test_dispatch_context_inside_request():
    """
    If a context is set, it should be visible inside the handler and the handler should
    be able to modify the state in ways that are visible to other handlers.
    """
    dispatch = Dispatch()

    class MyRequestContext:
        x: int = 0

    @dispatch.handler
    async def increment():
        dispatch.ctx.x += 1
        return {"x": dispatch.ctx.x}

    context = MyRequestContext()
    async with dispatch.connection_context(context):
        result = await dispatch.execute(JsonRpcRequest(id=0, method="increment"))
        assert result["x"] == 1
        result = await dispatch.execute(JsonRpcRequest(id=1, method="increment"))
        assert result["x"] == 2
    assert context.x == 2


async def test_context_fails_if_not_set(caplog):
    """ If a handler accesses the connection context but the context was never set,
    then it should raise a RuntimeError. Since it occurs in a handler, execute()
    converts it to an internal error and also logs it. """
    dispatch = Dispatch()

    @dispatch.handler
    async def increment():
        dispatch.ctx.x += 1
        return {"x": dispatch.ctx.x}

    with pytest.raises(JsonRpcInternalError):
        await dispatch.execute(JsonRpcRequest(id=0, method="increment"))
        assert (
            "The .context property is only valid in a connection context" in caplog.text
        )


async def test_cannot_nest_contexts():
    dispatch = Dispatch()

    class MyRequestContext:
        x: int = 0

    context = MyRequestContext()

    with pytest.raises(RuntimeError):
        async with dispatch.connection_context(context):
            async with dispatch.connection_context(context):
                pass
