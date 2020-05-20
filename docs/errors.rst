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

.. _custom-errors:

Custom Errors
-------------

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

To illustrate this point, consider the :ref:`client-example`.

::

    $ python -m example.client ws://localhost:8000 john 1234 transfer jane 10
    INFO:client:Login success=True
    INFO:client:Current balance: 90
    INFO:client:New balance: 80

    $ python -m example.client ws://localhost:8000 john 1234 transfer jane 100
    INFO:client:Login success=True
    INFO:client:Current balance: 80
    Traceback (most recent call last):
    File "/usr/lib/python3.7/runpy.py", line 193, in _run_module_as_main
        "__main__", mod_spec)
    File "/usr/lib/python3.7/runpy.py", line 85, in _run_code
        exec(code, run_globals)
    File "/home/mhaase/code/hyperiongray/trio-jsonrpc/example/client.py", line 70, in <module>
        trio.run(main, args)
    File "/home/mhaase/.cache/pypoetry/virtualenvs/trio-jsonrpc-rezRQjTp-py3.7/lib/python3.7/site-packages/trio/_core/_run.py", line 1804, in run
        raise runner.main_task_outcome.error
    File "/home/mhaase/code/hyperiongray/trio-jsonrpc/example/client.py", line 34, in main
        await args.func(client, args)
    File "/home/mhaase/code/hyperiongray/trio-jsonrpc/example/client.py", line 21, in transfer
        await client.request("transfer", [args.dest_account, args.amount])
    File "/home/mhaase/code/hyperiongray/trio-jsonrpc/trio_jsonrpc/main.py", line 79, in request
        raise JsonRpcException.exc_from_error(response.error)
    example.shared.InsufficientFundsError: Insufficient funds

In the first command, we see that the user's final balance is 80. In the second command,
they try to transfer 100. The server raises ``InsufficientFundsError`` and then the
client catches the same type of exception. Under the hood, the server converts the
exception into a JSON-RPC error using the error code specified in
``InsufficientFundsError`` class. The client reads the error code from the JSON-RPC
response, looks up the error class with the same error code, and raises it.
