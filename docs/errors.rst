Errors
======

Base Classes
------------

.. currentmodule:: trio_jsonrpc

This library includes a flexible error-handling system (inherited from the underlying
``sansios-jsonrpc`` project). JSON-RPC exceptions can be thrown and caught like any
other Python exceptions. They all inherit from one base class:

.. autoclass:: JsonRpcException
    :members:

Each exception contains a numeric error code, a string message, and optional arbitrary
data. You generally should not instantiate ``JsonRpcException``, but it is useful as a
catch-all in ``try/except`` blocks.

To communicate an error to the remote peer, a slightly different but related error
object is used:

.. autoclass:: JsonRpcError
    :members:

This error object can be passed into :func:`JsonRpcConnection.respond_with_error`.

An exception object can be converted into an error by calling ``exc.get_error()``. An
error object can be converted into an exception by calling
``JsonRpcException.exc_from_error(err)``. This class method uses some metaclass magic to
find the correct exception subclass and instantiate it. For example, if the error code
is ``-32601``, then the method will raise ``JsonRpcMethodNotFoundError``.

Built-in Exceptions
-------------------

The library includes a hierarchy of built-in exceptions.

::

    JsonRpcException
    +-- JsonRpcReservedError
        +-- JsonRpcInternalError
        +-- JsonRpcInvalidRequestError
        +-- JsonRpcInvalidParamsError
        +-- JsonRpcMethodNotFoundError
        +-- JsonRpcParseError
    +-- JsonRpcApplicationError

The top-most class ``JsonRpcException`` was discussed in the previous section. It has
two direct subclasses. ``JsonRpcReservedError`` covers all of the error codes defined in
or reserved by the JSON-RPC 2.0 specification.

Custom Exceptions
-----------------

The JSON-RPC specification allows implementers to specify their own JSON-RPC error codes
as long as they do not rely in the range of values reserved by the specification. This
capability is exposed in this library through the ``JsonRpcApplicationError`` object.
There are two ways to use this class.

.. autoclass:: JsonRpcApplicationError

The first way is to raise the exception directly and provide a custom error code.

.. code:: python3

    if (some_error_condition):
        raise JsonRpcApplicationError(code=1000, message='Foo error')

The second approach is to declare a custom subclass with the same error code.

.. code:: python3

    class FooError(JsonRpcApplicationError):
        ERROR_CODE = 1000
        ERROR_MESSAGE = "Foo error"

    ...

    if (some_error_condition):
        raise FooError()

Both of these approaches will produce the same error signaling in the JSON-RPC protocol
data, i.e. the remote peer will see the same result. The latter approach is also
compatible with :func:`JsonRpcException.exc_from_error`: if you receive a ``1000`` error
code from the peer, ``exc_from_error()`` will create a ``FooError``!
