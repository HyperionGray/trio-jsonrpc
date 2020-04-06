from contextlib import contextmanager
from functools import wraps
import json

import logging
import pytest
import trio


@contextmanager
def assert_min_elapsed(seconds):
    """
    Fail the test if the execution of a block takes less than ``seconds``.
    """
    start = trio.current_time()
    yield
    elapsed = trio.current_time() - start
    assert (
        elapsed >= seconds
    ), "Completed in less than {} seconds (elapsed={:0.3f}s)".format(seconds, elapsed)


class AsyncMock:
    """ A mock that acts like an async def function. """

    def __init__(
        self, return_value=None, return_values=None, raises=None, side_effect=None
    ):
        self._raises = None
        self._side_effect = None
        self._return_value = None
        self._index = None
        self._call_count = 0
        self._call_args = None
        self._call_kwargs = None

        if raises:
            self._raises = raises
        elif return_values:
            self._return_value = return_values
            self._index = 0
        elif side_effect:
            self._side_effect = side_effect
        else:
            self._return_value = return_value

    @property
    def call_args(self):
        return self._call_args

    @property
    def call_kwargs(self):
        return self._call_kwargs

    @property
    def called(self):
        return self._call_count > 0

    @property
    def call_count(self):
        return self._call_count

    async def __call__(self, *args, **kwargs):
        self._call_args = args
        self._call_kwargs = kwargs
        self._call_count += 1
        if self._raises:
            raise (self._raises)
        elif self._side_effect:
            return await self._side_effect(*args, **kwargs)
        elif self._index is not None:
            return_index = self._index
            self._index += 1
            return self._return_value[return_index]
        else:
            return self._return_value


def parse_bytes(b):
    """ A helper to convert a network byte string to a JSON object. """
    return json.loads(b.decode("ascii"))


class fail_after:
    """ This decorator fails if the runtime of the decorated function (as
    measured by the Trio clock) exceeds the specified value. """

    def __init__(self, seconds):
        self._seconds = seconds

    def __call__(self, fn):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            with trio.move_on_after(self._seconds) as cancel_scope:
                await fn(*args, **kwargs)
            if cancel_scope.cancelled_caught:
                pytest.fail(
                    "Test runtime exceeded the maximum {} seconds".format(self._seconds)
                )

        return wrapper
