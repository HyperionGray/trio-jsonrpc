import argparse
import logging

import trio
from trio_jsonrpc import open_jsonrpc_ws, JsonRpcException

from .shared import AuthorizationError, InsufficientFundsError


logger = logging.getLogger("client")


async def get_balance(client, args):
    result = await client.request("get_balance", [])
    logger.info("Current balance: %d", result)


async def transfer(client, args):
    result = await client.request("get_balance", [])
    logger.info("Current balance: %d", result)
    await client.request("transfer", {"to": args.dest_account, "amount": args.amount})
    result = await client.request("get_balance", [])
    logger.info("New balance: %d", result)


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

    xfr = subparsers.add_parser("transfer", help="Display current balance")
    xfr.add_argument("dest_account", help="The name of the account to transfer into")
    xfr.add_argument("amount", type=int, help="The amount to transfer")
    xfr.set_defaults(func=transfer)

    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper()))
    trio.run(main, args)
