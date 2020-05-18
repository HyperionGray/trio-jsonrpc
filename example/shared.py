from trio_jsonrpc import JsonRpcApplicationError


class AuthorizationError(JsonRpcApplicationError):
    ERROR_CODE = 1000
    ERROR_MESSAGE = "Not authorized"


class InsufficientFundsError(JsonRpcApplicationError):
    ERROR_CODE = 1001
    ERROR_MESSAGE = "Not authorized"
