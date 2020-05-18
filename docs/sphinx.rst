.. _sphinx-integration:

Sphinx Integration
==================

Overview
--------

Trio JSON-RPC includes a Sphinx_ extension that helps you generate API documentation
from source code. This document itself is written in Sphinx/ReStructuredText and may be
found in the repository ``docs/sphinx.rst``. This document shows how to use the Sphinx
extension to document the API published by the :ref:`server-example`.

.. _Sphinx: https://www.sphinx-doc.org/en/stable/

Methods
-------

To get started, we first need to tell Sphinx where to find the JSON-RPC ``Dispatch``
object.

.. code::

    .. trio-jsonrpc:dispatch:: example.server:dispatch

.. trio-jsonrpc:dispatch:: example.server:dispatch

This directive indicates that the dispatch object for the example server is defined in
the ``example.server`` module in a variable named ``dispatch``. Sphinx will import this
module and access the dispatch object in order to learn what JSON-RPC methods are
registered on it.

Now we can start to document JSON-RPC methods registered with this dispatch object.
Let's start with a simple method: login. The following directive will generate
documentation automatically:

.. code::

    .. trio-jsonrpc:method:: login

.. trio-jsonrpc:method:: login

Let's compare the generated documentation with the underlying source code.

.. code:: python3

    @dispatch.handler
    async def login(user: str, pin: int) -> bool:
        """ Verify the user's pin and update connection context. """
        if user_pins.get(user) == pin:
            dispatch.ctx.user = user
            return True
        else:
            return False

The generated documentation uses the function's signature, including type annotations,
to generate a JSON-RPC signature. The types are converted from Python types to JSON
types to abstract over the fact that the implementation is written in Python. The
documentation also copies the Python function's docstring.

Objects
-------

TBD

Errors
------
TBD

Index
-----

Sphinx can generate a list of all JSON-RPC methods, objects, and errors. This is
typically included underneath the main table of contents. You can add this to your
documentation by using the following directive:

.. code::

    :ref:`trio-jsonrpc-index`
