Dispatch
========

.. currentmodule:: trio_jsonrpc

Usage
-----

The library includes an optional system for dispatching incoming requests to handler
functions and managing connection state. It can also help you generate documentation for
your JSON-RPC API; see :ref:`sphinx-integration`.

This system revolves around the ``Dispatch`` class. First, create a dispatch instance.
Usually you would do this at the top-level of your server module.

.. code:: python3

    from trio_jsonrpc import Dispatch

    dispatch = Dispatch()

Now you can use this instance's decorator to register Python functions as JSON-RPC
methods.

.. code:: python3

    @dispatch.handler
    async def greet(name: str) -> dict:
        return {"greeting": "Hello, {}!".format(name)}

This decorator registers the ``greet(...)`` method as a JSON-RPC method named ``greet``.

.. note::

    Keep in mind that if you define your dispatch and your handlers in separate files,
    there will be a cyclical dependency between them. That's OK, just make sure to import
    your handler modules *after* you create the dispatch instance. That won't be PEP-8
    compliant, but it is necessary.

Finally, your main server loop can dispatch incoming requests:

.. code:: python3

    await dispatch.handle_request(request, result_send)

The ``result_send`` variable is the send side of a Trio channel. The server should read
from the other side of the channel to gather the results from the various handler
functions.

Context
-------

It may be helpful to maintain some connection state that can be accessed or modified by
the handler functions. The dispatch system allows for providing a custom object that is
exposed to handler methods. To use dispatch context, you first need to declare a class
that holds the connection state.

.. code:: python3

    @dataclass
    class ConnectionContext:
        name: typing.Optional[str] = None

This example uses Python's dataclasses_, which are convenient for this purpose. But any
ordinary class will work, too. When your server receives a new connection, you should
create an instance of this context object and expose it to the connection:

.. _dataclasses: https://docs.python.org/3.7/library/dataclasses.html

.. code:: python3

    context = ConnectionContext()
    async with dispatch.connection_context(context):
        # Handle connection here

The context manager :meth:`Dispatch.connection_context` will set your
connection context object to be used by all Trio tasks that execute within that block.
Under the hood, this uses some magic with ``contextvars`` to ensure that all handlers
on a given connection see the same instance.

Now you can write handler functions that access the dispatch context. Here's an example
that adapts the ``greet`` method presented in the previous section.

.. code:: python3

    @dispatch.handler
    async def set_name(name: str) -> None:
        dispatch.ctx.name = name

    @dispatch.handler
    async def greet() -> dict:
        return {"greeting": "Hello, {}!".format(dispatch.ctx.name)}

The ``dispatch.ctx`` object is the same object that you passed into
``connection_context``. This allows all handlers to easily access the connection
context.

API
---

.. autoclass:: Dispatch
    :members:
