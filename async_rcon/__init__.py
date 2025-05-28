import dataclasses
import struct
import sys
import asyncio
from logging import Logger
from typing import Optional


class _RequestId:
    DEFAULT = 0
    LOGIN_FAIL = -1


class _PacketType:
    COMMAND_RESPONSE = 0
    COMMAND_REQUEST = 2
    LOGIN_REQUEST = 3
    ENDING_PACKET = 100


@dataclasses.dataclass(frozen=True)
class Packet:
    request_id: int
    packet_type: int
    payload: str

    def flush(self) -> bytes:
        data = struct.pack('<ii', self.request_id, self.packet_type) + (self.payload + '\x00\x00').encode('utf8')
        return struct.pack('<i', len(data)) + data


class AsyncRconConnection:
    BUFFER_SIZE = 2 ** 10

    def __init__(self, address: str, port: int, password: str, *, logger: Optional[Logger] = None):
        self.logger = logger
        self.address = address
        self.port = port
        self.password = password
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.lock = asyncio.Lock()

    async def connect(self) -> bool:
        if self.writer is not None:
            await self.disconnect()

        self.reader, self.writer = await asyncio.open_connection(self.address, self.port)
        await self.__send(Packet(_RequestId.DEFAULT, _PacketType.LOGIN_REQUEST, self.password))

        try:
            packet = await self.__receive_packet()
            success = packet.request_id != _RequestId.LOGIN_FAIL
        except Exception:
            success = False

        if not success:
            await self.disconnect()
        return success

    async def disconnect(self):
        if self.writer is not None:
            self.writer.close()
            await self.writer.wait_closed()
            self.writer = None
            self.reader = None

    async def __send(self, packet: Packet):
        assert self.writer is not None
        self.writer.write(packet.flush())
        await self.writer.drain()
        await asyncio.sleep(0.03)  # Avoid MC-72390

    async def __receive(self, length: int) -> bytes:
        assert self.reader is not None
        data = b''
        while len(data) < length:
            chunk = await self.reader.read(length - len(data))
            if not chunk:
                raise ConnectionError("Connection closed while receiving data")
            data += chunk
        return data

    async def __receive_packet(self) -> Packet:
        length_bytes = await self.__receive(4)
        length = struct.unpack('<i', length_bytes)[0]
        data = await self.__receive(length)

        request_id = struct.unpack('<i', data[0:4])[0]
        packet_type = struct.unpack('<i', data[4:8])[0]
        payload = data[8:-2].decode('utf8')

        return Packet(request_id, packet_type, payload)

    async def send_command(self, command: str, max_retry_time: int = 3) -> Optional[str]:
        async with self.lock:
            for _ in range(max_retry_time):
                try:
                    await self.__send(Packet(_RequestId.DEFAULT, _PacketType.COMMAND_REQUEST, command))
                    await self.__send(Packet(_RequestId.DEFAULT, _PacketType.ENDING_PACKET, 'lol'))
                    result = ''
                    while True:
                        packet = await self.__receive_packet()
                        if packet.payload == f"Unknown request {hex(_PacketType.ENDING_PACKET)[2:]}":
                            break
                        result += packet.payload
                    return result
                except Exception as e:
                    if self.logger:
                        self.logger.warning(f"Rcon packet receive failed: {e}")
                    try:
                        await self.disconnect()
                        if await self.connect():
                            continue
                    except Exception:
                        break
            return None


async def main():
    rcon = AsyncRconConnection('mod.staringplanet.top', 51003, 'password')
    print("Connecting RCON server...")
    ok = await rcon.connect()

    if ok:
        print("Connected!")
        try:
            while True:
                command = input("Server <- ")
                result = await rcon.send_command(command)
                print("Server ->", result)
        except EOFError:
            await rcon.disconnect()
        finally:
            await rcon.disconnect()
            print("Exited!")
    else:
        print("Failed to connect RCON server!")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit()


