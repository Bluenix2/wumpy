import enum
import json
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

from wumpy.models import (
    AllowedMentions, InteractionChannel, InteractionMember, Model, User
)
from wumpy.models.member import Member
from wumpy.rest.utils import MISSING

from .components import ComponentList

__all__ = (
    'InteractionType', 'ComponentType', 'ApplicationCommandOption',
    'ResolvedInteractionData', 'CommandInteractionOption', 'Interaction',
    'CommandInteraction', 'ComponentInteraction', 'SelectInteractionValue',
)


class InteractionType(enum.Enum):
    ping = 1
    application_command = 2
    message_component = 3


class ComponentType(enum.Enum):
    action_row = 1
    button = 2
    select_menu = 3


class ApplicationCommandOption(enum.Enum):
    subcommand = 1
    subcommand_group = 2
    string = 3
    integer = 4
    boolean = 5
    user = 6
    channel = 7
    role = 8
    mentionable = 9
    number = 10  # Includes decimals


class ResolvedInteractionData:
    """Asynchronously resolved data from Discord."""

    users: Dict[int, User]
    members: Dict[int, InteractionMember]

    roles: Dict[int, Dict[str, Any]]
    channels: Dict[int, InteractionChannel]

    messages: Dict[int, Dict[str, Any]]

    __slots__ = ('users', 'members', 'roles', 'channels', 'messages')

    def __init__(self, data: Dict[str, Any]) -> None:
        self.users = {int(k): User.from_data(v) for k, v in data.get('users', {}).items()}

        self.members = {
            int(k): InteractionMember.from_data(data.get('users', {}).get(k), v)
            for k, v in data.get('members', {}).items()
            if data.get('users', {}).get(k)
        }

        self.roles = {int(k): v for k, v in data.get('roles', {}).items()}
        self.channels = {
            int(k): InteractionChannel.from_data(v)
            for k, v in data.get('channels', {}).items()
        }

        self.messages = {int(k): v for k, v in data.get('messages', {}).items()}


class CommandInteractionOption:
    """Application Command option received from Discord.

    `value` and `options` are mutually exclusive, the latter is only sent
    when `type` is a subcommand, or subcommand group.
    """

    name: str
    type: ApplicationCommandOption

    value: Optional[Any]
    options: List['CommandInteractionOption']

    __slots__ = ('name', 'type', 'value', 'options')

    def __init__(self, data: Dict[str, Any]) -> None:
        self.name = data['name']
        self.type = ApplicationCommandOption(data['type'])

        self.value = data.get('value')
        self.options = [CommandInteractionOption(option) for option in data.get('options', [])]


class SelectInteractionValue:
    """One of the values for a select option."""

    label: str
    value: str
    description: Optional[str]
    emoji: Optional[Dict[str, Any]]
    default: Optional[bool]

    __slots__ = ('label', 'value', 'description', 'emoji', 'default')

    def __init__(self, data: Dict[str, Any]) -> None:
        self.label = data['label']
        self.value = data['value']

        self.description = data.get('description')
        self.emoji = data.get('emoji')
        self.emoji = data.get('default')


class Interaction(Model):
    """Base for all interaction objects."""

    _send: Callable[[Dict[str, Any]], Awaitable[None]]

    application_id: int
    type: InteractionType

    guild_id: Optional[int]
    channel_id: Optional[int]

    user: User
    token: str

    __slots__ = (
        'app', '_send', '_rest', 'application_id', 'type', 'guild_id',
        'channel_id', 'member', 'user', 'token', 'version'
    )

    def __init__(
        self,
        app: Any,
        send: Callable[[Dict[str, Any]], Awaitable[None]],
        data: Dict[str, Any]
    ) -> None:
        super().__init__(int(data['id']))

        self.app = app

        self._send = send

        self.application_id = data['application_id']
        self.type = data['type']

        self.channel_id = data.get('channel_id')
        self.guild_id = data.get('guild_id')

        member = data.get('member')
        if member:
            self.user = Member.from_data(None, member)
        else:
            self.user = User.from_data(data['user'])

        self.token = data['token']
        self.version = data['version']

    async def respond(
        self,
        content: str = MISSING,
        *,
        tts: bool = MISSING,
        embeds: List[Dict[str, Any]] = MISSING,
        allowed_mentions: AllowedMentions = MISSING,
        ephemeral: bool = MISSING,
        components: Union[List, ComponentList] = MISSING,
    ) -> None:
        """Directly respond to the interaction with a message."""
        if isinstance(components, list):
            components = ComponentList(*components)

        data = {
            'content': content,
            'tts': tts,
            'embeds': embeds,
            'allowed_mentions': allowed_mentions.data() if allowed_mentions else allowed_mentions,
            'components': components.to_dict() if components else components
        }
        if ephemeral:
            data['flags'] = 1 << 6

        data = {k: v for k, v in data.items() if v is not MISSING}

        await self._send({
            'type': 'http.response.start', 'status': 200,
            'headers': [(b'content-type', b'application/json')]
        })
        # Respond with CHANNEL_MESSAGE_WITH_SOURCE
        await self._send({
            'type': 'http.response.body',
            'body': json.dumps({'type': 4, 'data': data}).encode()
        })

    async def defer(self) -> None:
        """Defer the interaction and respond later.

        The user will see a loading state and wait for a result.
        """
        await self._send({
            'type': 'http.response.start', 'status': 200,
            'headers': [(b'content-type', b'application/json')]
        })
        # Respond with DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE
        await self._send({'type': 'http.response.body', 'body': b'{"type": 5}'})


class CommandInteraction(Interaction):
    """Interaction for a Discord command (slash)."""

    name: str
    invoked: int
    invoked_type: ApplicationCommandOption

    resolved: ResolvedInteractionData
    target_id: Optional[int]
    options: List[CommandInteractionOption]

    __slots__ = ('name', 'invoked', 'invoked_type', 'resolved', 'target_id', 'options')

    def __init__(
        self,
        app: Any,
        send: Callable[[Dict[str, Any]], Awaitable[None]],
        data: Dict[str, Any]
    ) -> None:
        super().__init__(app, send, data)

        self.name = data['data']['name']
        self.invoked = data['data']['id']
        self.invoked_type = ApplicationCommandOption(data['data']['type'])

        self.resolved = ResolvedInteractionData(data['data'].get('resolved', {}))

        target_id = data['data'].get('target_id')
        self.target_id = int(target_id) if target_id else None

        self.options = [CommandInteractionOption(option) for option in data['data'].get('options', [])]


class ComponentInteraction(Interaction):
    """Interaction for a message component."""

    message: Dict[str, Any]

    custom_id: str
    component_type: ComponentType

    values: List[SelectInteractionValue]

    __slots__ = ('message', 'custom_id', 'component_type', 'values')

    def __init__(
        self,
        app: Any,
        send: Callable[[Dict[str, Any]], Awaitable[None]],
        data: Dict[str, Any]
    ) -> None:
        super().__init__(app, send, data)

        self.message = data['message']

        self.custom_id = data['data']['custom_id']
        self.component_type = ComponentType(data['data']['component_type'])

        self.values = [SelectInteractionValue(value) for value in data['data'].get('values', [])]

    async def defer_update(self) -> None:
        """Defer the update/edit of the original response.

        This has the benefit of the user not seeing a loading state, it can
        therefor be used when not wanting to send any form of response.
        """
        await self._send({
            'type': 'http.response.start', 'status': 200,
            'headers': [(b'content-type', b'application/json')]
        })
        # Respond with DEFERRED_UPDATE_MESSAGE
        await self._send({
            'type': 'http.response.body', 'body': b'{"type": 6}'
        })

    async def update(
        self,
        content: str = MISSING,
        *,
        tts: bool = MISSING,
        embeds: List[Dict[str, Any]] = MISSING,
        allowed_mentions: AllowedMentions = MISSING,
        ephemeral: bool = MISSING,
        components: Union[List, ComponentList] = MISSING,
    ) -> None:
        """Update the original message this component is attached to."""
        if isinstance(components, list):
            components = ComponentList(*components)

        data = {
            'content': content,
            'tts': tts,
            'embeds': embeds,
            'allowed_mentions': allowed_mentions.data() if allowed_mentions else allowed_mentions,
            'components': components.to_dict() if components else components
        }
        if ephemeral:
            data['flags'] = 1 << 6

        data = {k: v for k, v in data.items() if v is not MISSING}

        await self._send({
            'type': 'http.response.start', 'status': 200,
            'headers': [(b'content-type', b'application/json')]
        })
        # Respond with UPDATE_MESSAGE
        await self._send({
            'type': 'http.response.body',
            'body': json.dumps({'type': 7, 'data': data}).encode()
        })
