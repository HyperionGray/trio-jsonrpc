import argparse
import logging

import trio
from trio_jsonrpc import open_jsonrpc_ws, JsonRpcException

from .shared import AuthorizationError, InsufficientFundsError


logger = logging.getLogger("client")


async def get_balance(client, args):
    result = await client.request("get_balance", [args.username, args.pin])
    logger.info("Current balance: %d", result)


async def main(args):
    """ The client's main entry point. """
    async with open_jsonrpc_ws(args.server) as client:
        # Log in first
        result = await client.request("login", [args.username, args.pin])
        logger.info("Login success=%s", result)

        # If login is okay, then run the requested command
        await args.func(client, args)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trio JSON-RPC Client Example")
    parser.add_argument(
        "--log-level",
        default="info",
        metavar="LEVEL",
        choices=["debug", "info", "warning", "error", "critical"],
        help="Set logging verbosity (default: info)",
    )
    parser.add_argument(
        "server", help="The server's URL",
    )
    parser.add_argument(
        "username", help="The username to log in as",
    )
    parser.add_argument(
        "pin", help="The pin to use for authentication", type=int,
    )
    subparsers = parser.add_subparsers(
        title="commands", dest="subcommand", required=True
    )

    subparsers.add_parser("get_balance", help="Display current balance").set_defaults(
        func=get_balance
    )

    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper()))
    trio.run(main, args)
