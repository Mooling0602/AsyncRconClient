from asyncio import AbstractEventLoop, Task

from mcdreforged.api.all import (
    CommandContext,
    CommandSource,
    PluginServerInterface,
    QuotableText,
    SimpleCommandBuilder,
)

from async_rcon import AsyncRconConnection
from async_rcon.commands import get_command_root_node
from async_rcon.config import PluginConfig, load_config
from async_rcon.lock import CustomLock
from async_rcon.utils import with_lock

builder = SimpleCommandBuilder()
get_node = get_command_root_node
client: AsyncRconConnection | None = None
rcon_task: Task | None = None
rcon_lock: bool = False
rcon_offline: bool = False
config: PluginConfig | None = None
lock: CustomLock | None = None
loop: AbstractEventLoop | None = None


async def on_load(server: PluginServerInterface, _prev_module):
    global rcon_task, config, client, loop
    builder.arg("command", QuotableText)
    root_command_node = get_node(server, "arcon")
    server.logger.info(f"Registering command root node: {root_command_node}")
    builder.command(f"{root_command_node} <command>", on_command_node_rcon_command)
    builder.command(f"{root_command_node} connect", on_command_node_rcon_connect)
    builder.command(f"{root_command_node} disconnect", on_command_node_rcon_disconnect)
    builder.command(
        f"{root_command_node} debug lock status",
        on_command_node_rcon_debug_lock_status,
    )
    builder.register(server)
    config = await load_config(server)
    mcdr_config = server.get_mcdr_config()
    assert config is not None
    loop = server.get_event_loop()
    client = AsyncRconConnection(
        address=config.custom_server.host,
        port=config.custom_server.port,
        password=config.custom_server.password,
        logger=server.logger,
    )
    if config.use_mcdr_config:
        server.logger.warning(
            "Using MCDR config to connect to the server, custom server connection info will be ignored."
        )
        client = AsyncRconConnection(
            address=mcdr_config["rcon"]["address"],
            port=mcdr_config["rcon"]["port"],
            password=mcdr_config["rcon"]["password"],
            logger=server.logger,
        )
    if client:
        init_rcon: bool = await start_client()
        if init_rcon:
            server.logger.info("Rcon client started!")
        else:
            server.logger.error(
                "Failed to start rcon client, maybe it's already running?"
            )
    if rcon_offline:
        server.logger.error(
            "Cannot connect to rcon server, please check your config file."
        )


async def start_client() -> bool:
    global rcon_offline, loop
    if not client or not loop:
        return False
    global rcon_task
    if not rcon_task:
        rcon_online: bool = await client.connect()
        if not rcon_online:
            rcon_offline = True
            return False
        else:
            rcon_offline = False
            await client.disconnect()
        rcon_task = loop.create_task(client.connect())
        return True
    else:
        return False


async def close_client():
    global loop
    if not client or not loop:
        return
    global rcon_task
    if rcon_task:
        loop.create_task(client.disconnect())
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


async def on_command_node_rcon_command(src: CommandSource, ctx: CommandContext):
    if not client:
        src.reply("Rcon error: client is not initialized!")
        return
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
            src.reply("Try restart rcon client failed, exit rcon command query.")
            src.reply(
                "You can restart rcon client manually by @rcon connect. Then retry query commands."
            )
            return
    response = await client.send_command(ctx["command"])
    src.reply(f"[Response] \n{response}\n")


@with_lock(lock, "client_option.disconnect")
async def on_command_node_rcon_disconnect(src: CommandSource, ctx: CommandContext):
    global rcon_lock
    await close_client()
    rcon_lock = True
    src.reply("Rcon client closed.")


@with_lock(lock, "client_option.connect")
async def on_command_node_rcon_connect(src: CommandSource, ctx: CommandContext):
    rcon_status = await start_client()
    if rcon_status:
        src.reply("Rcon client started!")
    else:
        if not rcon_offline:
            src.reply("Rcon client is maybe already running!")
        else:
            src.reply("Rcon server is offline, please check your config!")


async def on_command_node_rcon_debug_lock_status(
    src: CommandSource, ctx: CommandContext
):
    if lock:
        if lock.block:
            src.reply(f"Locking: {lock.id}")
            return
    src.reply("Not locking.")
