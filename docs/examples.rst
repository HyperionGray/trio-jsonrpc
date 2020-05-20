Examples
========

The repository includes an example server and client that implement a very simplified
banking API over JSON-RPC.

.. _server-example:

Server Example
--------------

To run the example server, make sure that the project root is
in the path (this happens automatically if you run ``poetry shell`` first), and then
run:

..  code::

    (trio-jsonrpc-py3.7) $ python -m example.server --port 8080
    INFO:server:Listening on port 8000 (Type ctrl+c to exit)

This starts the server on localhost port 8080.

.. _client-example:

Client Example
--------------

Next, run the client. The client requires the URL to the server, the username to login
as, the pin for that user, followed by the subcommand to run.

.. code::

    (trio-jsonrpc-py3.7) $ python -m example.client ws://localhost:80 john 1234 get_balance

Use the ``-help`` flag on the server or client for additional details about supports
flags and subcommands.
