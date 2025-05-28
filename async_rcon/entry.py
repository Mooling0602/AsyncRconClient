import asyncio
from asyncio import Task

from mcdreforged.api.all import (
    CommandContext,
    CommandSource,
    PluginServerInterface,
    QuotableText,
    SimpleCommandBuilder,
)

from . import AsyncRconConnection

builder = SimpleCommandBuilder()
client = AsyncRconConnection("example.com", 25575, "password")
rcon_task: Task | None = None
rcon_lock: bool = False


async def on_load(server: PluginServerInterface, _prev_module):
    global rcon_task
    builder.arg("command", QuotableText)
    builder.register(server)
    init_rcon: bool = await start_client()
    if init_rcon:
        server.logger.info("Rcon client started!")
    else:
        server.logger.warning(
            "Failed to start rcon client, maybe it's already running?"
        )


async def start_client() -> bool:
    global rcon_task
    if not rcon_task:
        rcon_task = asyncio.create_task(client.connect())
        return True
    else:
        return False


async def close_client():
    global rcon_task
    if rcon_task:
        await client.disconnect()
        rcon_task.cancel()
        await rcon_task
        rcon_task = None


async def on_unload(server: PluginServerInterface):
    global rcon_task
    await close_client()
    if rcon_task:
        rcon_task.cancel()
        await rcon_task
        rcon_task = None


@builder.command("@rcon <command>")
async def on_command_node_rcon_command(src: CommandSource, ctx: CommandContext):
    rcon_status: bool | None = None
    response: str | None = None
    if not rcon_task:
        if rcon_lock:
            src.reply("Rcon client need restart manually! Use @rcon connect")
            return
        src.reply(
            "Rcon client is not running, will restart it and reconnecting rcon server automatically."
        )
        rcon_status = await start_client()
        if not rcon_status:
            raise RuntimeError("Rcon connection status is inconsistent.")
    response = await client.send_command(ctx["command"])
    src.reply(f"[Response] \n{response}\n")


@builder.command("@rcon disconnect")
async def on_command_node_rcon_disconnect(src: CommandSource, ctx: CommandContext):
    global rcon_lock
    await close_client()
    rcon_lock = True
    src.reply("Rcon client closed.")


@builder.command("@rcon connect")
async def on_command_node_rcon_connect(src: CommandSource, ctx: CommandContext):
    rcon_status = await start_client()
    if rcon_status:
        src.reply("Rcon client started!")
    else:
        src.reply("Rcon client is already running!")
