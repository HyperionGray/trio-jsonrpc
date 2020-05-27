.. _sphinx-integration:

Sphinx Integration
==================

Overview
--------

Trio JSON-RPC includes a Sphinx_ extension that helps you generate API documentation
from source code. This document itself is written in Sphinx/ReStructuredText and may be
found in the repository: ``docs/sphinx.rst``. This document shows how to use the Sphinx
extension to document the API published by the :ref:`server-example`.

.. _Sphinx: https://www.sphinx-doc.org/en/stable/

Methods
-------

To get started, we first need to tell Sphinx where to find the JSON-RPC ``Dispatch``
object.

.. code::

    .. jsonrpc:dispatch:: example.server:dispatch

.. jsonrpc:dispatch:: example.server:dispatch

This directive indicates that the dispatch object for the example server is defined in
the ``example.server`` module in a variable named ``dispatch``. Sphinx will import this
module and access the dispatch object in order to learn what JSON-RPC methods are
registered on it.

Now we can start to document JSON-RPC methods registered with this dispatch object.
Let's start with a simple method: login.

.. code::

    .. jsonrpc:method:: login

The above directive will generate the following documentation:

.. jsonrpc:method:: login

Let's compare the generated documentation with the underlying source code.

.. code:: python3

    @dispatch.handler
    async def login(user: str, pin: int) -> bool:
        """
        Verify the user's pin and update connection context.

        :param user: The user to log in as.
        :param pin: The user's pin number.
        :returns: True if login succeeds or else false.
        """
        if user_pins.get(user) == pin:
            dispatch.ctx.user = user
            return True
        else:
            return False

The generated documentation uses the function's signature, including type annotations,
to generate a JSON-RPC signature. The types are converted from Python types to JSON
types to abstract over the fact that the implementation is written in Python. The
documentation also copies the Python function's docstring and adds any missing types
there, too.

The documentation also includes an item called "Parameter Style" that explains whether
arguments may be passed as an array (i.e. positional arguments to a Python function) or
object (i.e. keyword arguments). By default, Trio JSON-RPC supports both calling styles.
However, if a function uses ``*`` to indicate keyword-only arguments, then the
documentation will reflect that fact. (In a future version of Python, ``/`` will
indicate positional-only arguments.)

Let's take a look at the method to get the user's balance:

.. jsonrpc:method:: get_balance

This method has something that ``login()`` does not: it raises an error. Let's look at
its implementation.

.. code:: python3

    @dispatch.handler
    async def get_balance() -> int:
        """
        Get the user's current balance.

        :error AuthorizationError: if not authorized
        :returns: The current balance.
        """
        if dispatch.ctx.user is None:
            raise AuthorizationError()
        return user_balances[dispatch.ctx.user]

The ``:error:`` directive in the docstring indicates the name of an exception class that
can be raised by a method (which should be a subclass of ``JsonRpcApplicationError``—see
:ref:`custom-errors`).

Finally, let's look at a method to transfer money to another user.

.. jsonrpc:method:: transfer

Notice that the calling style of this method indicates that arguments must be passed as
an object. This is because the signature declares the arguments as keyword-only:

.. code:: python3

    async def transfer(*, to: str, amount: int) -> None:

The same logic applies if *any arguments* are keyword only, since JSON-RPC does not
allow for mixing positional and keyword arguments in a single method call. By extension,
it is invalid to declare a JSON-RPC method with both positional-only and keyword-only
arguments.

You can reference a JSON-RPC method inside text a directive like ``:jsonrpc:ref:`login```,
which renders as a hyperlink: :jsonrpc:ref:`login`.

Errors
------

Sphinx can also document :ref:`custom-errors`.

.. code::

    .. jsonrpc:exception:: example.server.AuthorizationError

The above directive will generate the following documentation:

.. jsonrpc:exception:: example.server.AuthorizationError

It displays the error code and default message for the exception. Let's compare the
documentation to the source code for this exception class.

.. code:: python3

    class AuthorizationError(JsonRpcApplicationError):
        """ The user is not authorized to execute this method. """

        ERROR_CODE = 1000
        ERROR_MESSAGE = "Not authorized"

Finally, here is the other exception in the example API.

.. jsonrpc:exception:: example.server.InsufficientFundsError

Notice that JSON-RPC methods that reference an exception class (such as
:jsonrpc:ref:`get_balance`) are hyperlinked to the documentation for that exception.

Index
-----

Sphinx can generate a list of all JSON-RPC methods, objects, and errors. This is
typically included underneath the main table of contents. You can add this to your
documentation by using the following directive:

.. code::

    :ref:`jsonrpc-index`

The directive produces a link to the JSON-RPC index like this: :ref:`jsonrpc-index`
