from trio_jsonrpc import JsonRpcApplicationError


class AuthorizationError(JsonRpcApplicationError):
    """ The user is not authorized to execute this method. """

    ERROR_CODE = 1000
    ERROR_MESSAGE = "Not authorized"


class InsufficientFundsError(JsonRpcApplicationError):
    """ The user has insufficient funds in their account. """

    ERROR_CODE = 1001
    ERROR_MESSAGE = "Insufficient funds"
