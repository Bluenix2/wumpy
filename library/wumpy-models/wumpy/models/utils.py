from typing import Any, Mapping, Optional

from typing_extensions import Final, NoReturn, final
from wumpy.rest.utils import MISSING

from .base import Snowflake

# Reintroduce MISSING here so that it can be imported easier by models
__all__ = ('MISSING', 'STATELESS', '_get_as_snowflake')


def _get_as_snowflake(data: Optional[Mapping], key: str) -> Optional[Snowflake]:
    """Get a key as a snowflake.

    Returns None if `data` is None or does not have the key.
    """
    if data is None:
        return None

    value = data.get(key)
    return Snowflake(value) if value is not None else None


class SatelessException(RuntimeError):
    """Exception signaling that the model is sateless.

    This signals that no REST-API related methods can be used, as it is raised
    if that is attempted. Allowing models to be fully stateless without loosing
    static typing or complicating code with if-statements.

    The purpose of this is to allow models to be user-constructed with nothing
    but the payload from Discord,
    """
    def __init__(self) -> None:
        super().__init__('Cannot call make an API call on a stateless model')


@final
class StatelessType:
    """Class to raise exceptions when attributes are accessed."""
    def __getattribute__(self, _: str) -> NoReturn:
        raise SatelessException()


STATELESS: Final[Any] = StatelessType()
