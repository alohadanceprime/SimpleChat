from functools import wraps
from typing import Callable, Any


def command(command_name: str) -> Callable:
    def decorator(func: Callable) -> Callable:
        func.command_name = command_name
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)
        return wrapper
    return decorator
