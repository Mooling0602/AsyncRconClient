from mcdreforged.api.command import SimpleCommandBuilder
from mcdreforged.api.types import PluginServerInterface

builder = SimpleCommandBuilder()


def get_command_root_node(server: PluginServerInterface, node: str, pfx: str = "!!"):
    existing_nodes = server._mcdr_server.command_manager.root_nodes
    if f"{pfx}{node}" not in existing_nodes:
        return f"{pfx}{node}"
    id_prefixed_node = f"{pfx}{server.get_self_metadata().id}:{node}"
    if id_prefixed_node not in existing_nodes:
        return id_prefixed_node
    else:
        return node


# def register_command(server: PluginServerInterface):
#     get_node = get_command_root_node
#     builder.arg('command', QuotableText)
#     builder.command(get_node(server, '!!rcon <command>'), on_command_node_rcon_command)
#     builder.command(get_node(server, '!!rcon connect'), on_command_node_rcon_connect)
#     builder.command(get_node(server, '!!rcon disconnect'), on_command_node_rcon_disconnect)
#     builder.command(get_node(server, '!!rcon debug lock status'), on_command_node_rcon_debug_lock_status)
