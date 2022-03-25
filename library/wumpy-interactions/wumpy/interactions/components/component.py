import re
from typing import (
    Any, Callable, Coroutine, Dict, Generic, List, Optional, Tuple, TypeVar,
    Union
)

import anyio
from anyio.abc import TaskGroup
from wumpy.models import DISCORD_EPOCH

from ..models import ComponentInteraction

__all__ = ('Component', 'ComponentEmoji')


T = TypeVar('T')
Coro = Coroutine[Any, Any, T]


class Result(Generic[T]):
    """Synchronizing Event but modified to pass a result."""

    __slots__ = ('_event', 'value')

    def __init__(self) -> None:
        self._event = anyio.Event()

    def is_set(self) -> bool:
        return self._event.is_set()

    def set(self, value: T) -> None:
        self._event.set()
        self.value = value

    async def wait(self) -> T:
        await self._event.wait()
        if not hasattr(self, 'value'):
            raise RuntimeError('Result woken up without value')

        return self.value  # value should now be set


class Component:
    """Implementation for awaiting components until they are called.

    All components inherit from this base class.
    """

    _callback: Optional[Callable[[ComponentInteraction], Coro[object]]]

    _waiters: List[
        Tuple[
            Callable[[ComponentInteraction], bool],
            Result[ComponentInteraction]
        ]
    ]

    __slots__ = ('_callback', '_waiters')

    def __init__(
        self,
        callback: Optional[Callable[[ComponentInteraction], Coro[object]]] = None,
    ) -> None:
        self._callback = callback
        self._waiters = []

    async def __call__(
        self,
        check: Callable[[ComponentInteraction], bool] = lambda i: True,
        *,
        timeout: Optional[float] = None
    ) -> ComponentInteraction:
        event: Result[ComponentInteraction] = Result()
        self._waiters.append((check, event))

        with anyio.fail_after(timeout):
            return await event.wait()

    def set_callback(
        self,
        callback: Callable[[ComponentInteraction], Coro[object]],
        *,
        override: bool = False
    ) -> None:
        """Set the callback for this component.

        Parameters:
            callback: Asynchornous callback that takes an interaction.
            override: Whether to override the callback if it is already set.

        Raises:
            RuntimeError: There is already a callback but `override` is False.
        """
        if self._callback is not None and not override:
            raise RuntimeError("Callback is already set but 'override' is False")

        self._callback = callback

    def handle_interaction(self, interaction: ComponentInteraction, *, tg: TaskGroup) -> None:
        """Handle the interaction and wake up any waiters."""
        if self._callback is not None:
            tg.start_soon(self._callback, interaction)

        for index, (check, result) in enumerate(self._waiters):
            if check(interaction):
                result.set(interaction)
                self._waiters.pop(index)

    def to_dict(self) -> Union[List[Any], Dict[str, Any]]:
        """Method meant to be implemented by subclasses."""
        raise NotImplementedError()


class ComponentEmoji:
    """Emoji sent with components to Discord.

    Attributes:
        animated: Whether the emoji is animated
        name: The name of the emoji (may be an unicode character)
        id:
            The ID of the emoji, for default emojis in Discord this is set to
            a fake ID created from the Discord epoch timestamp.
    """

    REGEX = re.compile(r'<?(?P<animated>a)?:?(?P<name>[A-Za-z0-9\_]+):(?P<id>[0-9]{13,20})>?')

    __slots__ = ('animated', 'name', 'id')

    def __init__(
        self,
        *,
        name: str,
        animated: bool = False,
        # In the case of unicode Discord emojis these were created when Discord
        # was created.
        id: int = DISCORD_EPOCH << 22
    ) -> None:
        self.animated = animated
        self.name = name
        self.id = id

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, int):
            return self.id == other
        elif isinstance(other, str):
            return self.name == other
        elif isinstance(other, self.__class__):
            return self.id == other.id and \
                self.name == other.name and \
                self.animated == other.animated
        else:
            return NotImplemented

    @classmethod
    def from_string(cls, value: str) -> 'ComponentEmoji':
        """Create an instance from a string."""
        match = cls.REGEX.match(value)
        if match:
            return cls(
                name=match.group('name'),
                animated=bool(match.group('animated')),
                id=int(match.group('id'))
            )

        # The regex didn't match, we'll just have to assume the user passed unicode
        return cls(name=value)

    def to_dict(self) -> Dict[str, Any]:
        """Turn the emoji into data meant to be sent to Discord."""
        data = {
            'name': self.name,
            'id': self.id,
            'animated': self.animated
        }
        # We should clean it for None values
        return {k: v for k, v in data.items() if v is not None}
