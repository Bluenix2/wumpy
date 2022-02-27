from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union

from . import option as __option
from .base import *
from .context import *
from .option import _MISSING_DEFAULT, CommandType
from .registrar import *
from .slash import *

T = TypeVar('T', bound=Union[SlashCommand, Subcommand])


# The reason for this function is because we need the "return type" to be Any.
# If we'd use the class directly then the following would break type checking
# def command(number: int = Option(description='A number'))
# 'int' and 'Option' is incompatible. This function avoids that
def Option(
    default: Any = _MISSING_DEFAULT,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    required: Optional[bool] = None,
    choices: Union[List[Union[str, int, float]], Dict[str, Union[str, int, float]], None] = None,
    min: Optional[int] = None,
    max: Optional[int] = None,
    type: Optional[Any] = None,
    cls: Type[Any] = __option.OptionClass
) -> Any:
    """Interaction option, should be set as a default to a parameter.

    The `cls` parameter can be used if you want to use a custom Option
    class, you can use `functools.partial()` as to not repeat the kwarg.

    Parameters:
        default:
            Default value when the option is not passed, makes the option
            optional so that it can be omitted.
        name:
            Name of the option in the Discord client. By default it uses
            the name of the parameter.
        description: Description of the option.
        required:
            Whether the option can be omitted. If a default is passed this is
            automatically set implicitly.
        choices: Set choices that the user can pick from in the Discord client.
        min: Smallest number that can be entered for number types.
        max: Biggest number that can be entered for number types.
        type:
            The type of the option, overriding the annotation. This can be
            a `ApplicationCommandOption` value or any type.
        cls: The class to use, defaults to `OptionClass`.

    Returns:
        The `cls` parameter (`OptionClass` by default) disguised as
        `typing.Any`. This way this function can be used as a default without
        violating static type checkers.
    """
    return cls(
        default, name=name, description=description,
        required=required, choices=choices,
        min=min, max=max, type=type
    )


# This is different from the above function as this is a decorator meant
# to be used on command instances.
def option(
    param: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    required: Optional[bool] = None,
    choices: Union[List[Union[str, int, float]], Dict[str, Union[str, int, float]], None] = None,
    min: Optional[int] = None,
    max: Optional[int] = None,
    type: Optional[Any] = None
) -> Callable[[T], T]:
    """Option decorator for updating an option.

    This decorator needs to be placed outside of the command decorator.

    Parameters:
        param: The name of the parameter for this option.
        name: The new name of the option.
        description: The new description of the option.
        required: Whether the option should be able to be omitted.
        choices: Set choices that the user needs to pick from.
        min: Smallest number that can be entered for number types.
        max: Biggest number that can be entered for number types.
        type: New type of the option, overriding the annotation.

    Exceptions:
        ValueError: This decorator was not used on a command.
    """
    # Because of the fact that we delete the type variable below, it won't be
    # available when this function is created.
    def decorator(command: 'T') -> 'T':
        if not isinstance(command, Subcommand):
            raise TypeError(
                "The 'option' decorator can only be used on commands."
            )

        command.update_option(
            param, name=name, description=description,
            required=required, choices=choices, min=min, max=max, type=type
        )

        # Return the command again for chaining.
        return command
    return decorator


# Clean up as we don't want users importing these from here
del Any, Callable, Dict, List, Optional, T, Type, Union
del _MISSING_DEFAULT, __option
