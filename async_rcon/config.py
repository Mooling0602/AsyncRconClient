import asyncio
import io
import os
from asyncio import AbstractEventLoop
from typing import Any

import aiofiles
from mcdreforged.api.all import PluginServerInterface
from pydantic import BaseModel
from ruamel.yaml import YAML

yaml: YAML = YAML()


class CustomServerConnectInfo(BaseModel):
    host: str = "localhost"
    port: int = 25575
    password: str = "password"


class PluginConfig(BaseModel):
    custom_server: CustomServerConnectInfo = CustomServerConnectInfo()
    use_mcdr_config: bool = True


async def load_dict_from_yml(file_path: str) -> dict:
    async with aiofiles.open(file_path, mode="r") as f:
        content: str = await f.read()
        loop: AbstractEventLoop = asyncio.get_event_loop()
        result: dict = await loop.run_in_executor(None, yaml.load, content)
        return result


async def save_dict_to_yml(file_path: str, data: dict) -> None:
    stream = io.StringIO()
    yaml.dump(data, stream)
    async with aiofiles.open(file_path, mode="w") as f:
        await f.write(stream.getvalue())


def find_conflict_dict_keys(
    default: dict, actual: dict, prefix: str = ""
) -> tuple[set[Any], set[Any]]:
    missing = set()
    extra = set()
    if not (isinstance(default, dict) and isinstance(actual, dict)):
        return missing, extra
    for key in default:
        if key not in actual:
            missing.add(f"{prefix}{key}")
        else:
            m, e = find_conflict_dict_keys(
                default[key], actual[key], prefix=f"{prefix}{key}."
            )
            missing |= m
            extra |= e
    for key in actual:
        if key not in default:
            extra.add(f"{prefix}{key}")
    return missing, extra


def merge_dict(default: dict, actual: dict) -> dict:
    if not isinstance(default, dict) or not isinstance(actual, dict):
        return actual if actual is not None else default
    merged: dict = dict(default)
    for k, v in actual.items():
        if k in merged:
            merged[k] = merge_dict(merged[k], v)
        else:
            merged[k] = v
    return merged


async def load_config(server: PluginServerInterface) -> PluginConfig:
    config_path: str = os.path.join(server.get_data_folder(), "config.yml")
    default_config_dict = PluginConfig().model_dump()
    if not os.path.exists(config_path):
        server.logger.warning("Config file not found, creating a new one...")
        await save_dict_to_yml(config_path, default_config_dict)
        return PluginConfig()
    server.logger.info("Loading config file...")
    config_dict: dict = await load_dict_from_yml(config_path)
    if not config_dict and os.path.exists(config_path):
        server.logger.error(f"Saved wrong config data: {config_dict}")
    missing_keys, extra_keys = find_conflict_dict_keys(
        PluginConfig().model_dump(), config_dict
    )
    config_format_fine: bool = missing_keys == extra_keys == set()
    if missing_keys:
        config_format_fine = False
        server.logger.warning(
            f"Missing keys in config options: {missing_keys} (will use default values instead.)"
        )
    if extra_keys:
        config_format_fine = False
        server.logger.warning(
            f"Extra keys in config options: {extra_keys} (will be ignored, but you shouldn't keep them.)"
        )
    if config_format_fine:
        return PluginConfig(**config_dict)
    merged_config_dict: dict = merge_dict(default_config_dict, config_dict)
    try:
        server.logger.warning("Merging old config with default one in plugin...")
        await save_dict_to_yml(config_path, merged_config_dict)
        return PluginConfig.model_validate(merged_config_dict, strict=False)
    except Exception as e:
        server.logger.error(f"Loading config error: {e}")
        server.logger.warning(
            "Fallback to default config, actual config file is keeping."
        )
        return PluginConfig()
