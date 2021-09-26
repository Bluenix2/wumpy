import inspect
from functools import partial
from typing import Any, Callable, Coroutine, Dict, Optional

import anyio.abc

from ...errors import CommandSetupError
from ...models import InteractionUser
from ...utils import MISSING
from ..base import CommandInteraction
from .base import CommandCallback
from .option import CommandType


class ContextMenuCommand(CommandCallback):
    """Discord context menu command that gets a user or message."""

    def __init__(self, callback: Callable[..., Coroutine], *, name: str = MISSING) -> None:
        super().__init__(callback, name=name)

        self.argument = MISSING

    def _set_callback(self, function) -> None:
        super()._set_callback(function)

        signature = inspect.signature(function)

        for param in signature.parameters.values():
            if isinstance(param.annotation, CommandInteraction):
                continue

            # This should be the second argument
            self.argument = param.annotation
            break

    def resolve_value(self, interaction: CommandInteraction) -> Optional[Any]:
        """Resolve the value to pass to the menu from the interaction.

        This gets overriden by subclasses to return the message or user.
        """
        raise NotImplementedError()

    def handle_interaction(self, interaction: CommandInteraction, *, tg: anyio.abc.TaskGroup) -> None:
        value = self.resolve_value(interaction)
        if value is None or self.callback is None:
            return

        tg.start_soon(partial(self.callback, interaction, value))


class MessageCommand(ContextMenuCommand):
    """Message context menu command."""

    def resolve_value(self, interaction: CommandInteraction) -> Any:
        """Resolve the message to pass to the callback."""
        if not interaction.target_id:
            raise CommandSetupError('Message command did not receive target ID.')

        message = interaction.resolved.messages.get(interaction.target_id)

        assert message is not None, 'Discord did not send message data'

        return message


class UserCommand(ContextMenuCommand):
    """User or member context menu command."""

    def resolve_value(self, interaction: CommandInteraction) -> Optional[Any]:
        """Resolve the user or member to pass to the callback."""
        if not interaction.target_id:
            raise CommandSetupError('User command did not receive target ID.')

        # ContextMenuCommand saves the argument in preperation for real support
        # of differentiating between InteractionUser and InteractionMember
        if isinstance(self.argument, InteractionUser):
            target = interaction.resolved.users.get(interaction.target_id)
        else:
            raise CommandSetupError("User command's second argument incorrectly annotated")

        return target
