"""
Most of the testing is done through the in-memory transport, since that's simpler to
test against. For the WebSocket transport we just want to make sure that basic sending,
receiving, and closing features work correctly.
"""
import pytest
from trio_websocket import serve_websocket

from . import fail_after, parse_bytes


HOST = "127.0.0.1"


# TODO after i have a working server, write one test that does a roundtrip from ws
# client to ws server

# @fail_after(1)
# async def test_request_result(nursery, echo_server):
#     """ This test runs a round trip from the client to the server. """
#     async with open_jsonrpc_ws(*server.client_channels()) as client:
#         logging.info("Client is connected")
#         assert client.is_client
#         assert not client.is_server
#         logging.info("Client request()...")
#         result = await client.request(method="hello_world")
#         logging.info("Client request() -> got result")
#         assert result["echo"] == "hello_world"
