import asyncio
import time
from typing import Optional


class CustomLock:
    def __init__(self, block: bool, id: Optional[str | list[str]] = None) -> None:
        self.block: bool = block
        self.id: list[str] = []
        if not id:
            return
        match id:
            case id if isinstance(id, str):
                self.id.append(id)
            case id if isinstance(id, list):
                for i in id:
                    if i not in self.id:
                        self.id.append(i)
        self._condition = asyncio.Condition()
        self._last_add_time: float | None = None

    def add(self, id: str | list[str], rate_limit: float = 0.01) -> bool:
        _current_time = time.monotonic()
        if self._last_add_time:
            if _current_time - self._last_add_time < rate_limit:
                return False
        self._last_add_time = _current_time
        match id:
            case id if isinstance(id, list):
                if self.id != []:
                    for i in id:
                        if i not in self.id:
                            self.id.append(i)
                else:
                    self.id = id
            case id if isinstance(id, str):
                if id not in self.id:
                    self.id.append(id)
        return True

    async def add_async(
        self, id: str | list[str], rate_limit: float = 0.1, retry: bool = True
    ) -> bool:
        result: bool = self.add(id, rate_limit)
        if not result:
            await asyncio.sleep(rate_limit)
            result: bool = self.add(id, rate_limit)
        return result

    def remove(self, id: str | list[str]):
        if self.id == []:
            return
        match id:
            case id if isinstance(id, list):
                for i in id:
                    if i in self.id:
                        self.id.remove(i)
            case id if isinstance(id, str):
                if id in self.id:
                    self.id.remove(id)

    def unlock(self):
        self.block = False
        asyncio.create_task(self._notify_all())

    def lock(self):
        self.block = True

    async def _notify_all(self):
        async with self._condition:
            self._condition.notify_all()

    async def wait_for_lock_release_async(
        self, option_id: str, timeout: float = 5.0
    ) -> bool:
        try:
            async with asyncio.timeout(timeout):
                async with self._condition:
                    await self._condition.wait_for(
                        lambda: not self.block
                        or not (
                            option_id in self.id
                            or any(i.startswith(f"{option_id}.") for i in self.id)
                        )
                    )
                return True
        except TimeoutError:
            return False

    def wait_for_lock_release(self, option_id: str, timeout: float = 5.0) -> bool:
        condition: bool = not self.block or not (
            option_id in self.id or any(i.startswith(f"{option_id}.") for i in self.id)
        )
        if condition:
            return True
        else:
            time.sleep(timeout)
            if condition:
                return True
        return False
