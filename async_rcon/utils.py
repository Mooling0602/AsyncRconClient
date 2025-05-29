from functools import wraps
from inspect import iscoroutinefunction as iscorofunc

from async_rcon.lock import CustomLock


def with_lock(lock: CustomLock | None, option_id: str):
    def decorator(func):
        @wraps(func)
        async def async_wrapper(_lock=lock, _option_id=option_id, *args, **kwargs):
            if _lock is None:
                _lock = CustomLock(True, _option_id)
            else:
                wait: bool = await _lock.wait_for_lock_release_async(_option_id)
                if not wait:
                    return
                start: bool = await _lock.add_async(_option_id, 0.1, True)
                if not start:
                    return
            result = await func(*args, **kwargs)
            _lock.remove(_option_id)
            return result

        @wraps(func)
        def wrapper(_lock=lock, _option_id=option_id, *args, **kwargs):
            if _lock is None:
                _lock = CustomLock(True, _option_id)
            else:
                wait: bool = _lock.wait_for_lock_release(_option_id)
                if not wait:
                    return
                start: bool = _lock.add(_option_id, 0.1)
                if not start:
                    return
            result = func(*args, **kwargs)
            _lock.remove(_option_id)
            return result

        return async_wrapper if iscorofunc(func) else wrapper

    return decorator
