# JSON-RPC v2.0 for Trio

[![PyPI](https://img.shields.io/pypi/v/trio-jsonrpc.svg?style=flat-square)](https://pypi.org/project/trio-jsonrpc/)
![Python Versions](https://img.shields.io/pypi/pyversions/trio-jsonrpc.svg?style=flat-square)
![MIT License](https://img.shields.io/github/license/HyperionGray/trio-jsonrpc.svg?style=flat-square)
[![Build Status](https://img.shields.io/travis/com/HyperionGray/trio-jsonrpc.svg?style=flat-square&branch=master)](https://travis-ci.com/HyperionGray/trio-jsonrpc)
[![codecov](https://img.shields.io/codecov/c/github/hyperiongray/trio-jsonrpc?style=flat-square)](https://codecov.io/gh/HyperionGray/trio-jsonrpc)
[![Read the Docs](https://img.shields.io/readthedocs/trio-jsonrpc.svg)](https://trio-jsonrpc.readthedocs.io)

This project provides an implementation of [JSON-RPC v
2.0](https://www.jsonrpc.org/specification) based on
[sansio-jsonrpc](https://github.com/hyperiongray/sansio-jsonrpc) with all of the I/O
implemented using the [Trio asynchronous framework](https://trio.readthedocs.io).

## Quick Start

Install from PyPI:

```
$ pip install trio-jsonrpc
```

The following example shows a basic JSON-RPC client.

```python
from trio_jsonrpc import open_jsonrpc_ws, JsonRpcException

async def main():
    async with open_jsonrpc_ws('ws://example.com/') as client:
        try:
            result = await client.request(
                method='open_vault_door',
                {'employee': 'Mark', 'pin': 1234}
            )
            print('vault open:', result['vault_open'])

            await client.notify(method='hello_world')
        except JsonRpcException as jre:
            print('RPC failed:', jre)

trio.run(main)
```

For more information, see [the complete
documentation](https://trio-jsonrpc.readthedocs.io).
