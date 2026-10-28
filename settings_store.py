"""Configuração persistente por servidor e auditoria administrativa."""
from __future__ import annotations

import json
from typing import Any


async def get_setting(bot, guild_id: int, key: str, default: Any = None) -> Any:
    """Lê configuração por guild; nunca usa um valor de outro servidor."""
    if not guild_id or not getattr(bot, "db", None) or not bot.db.conn:
        return default
    row = await bot.db._one(
        "SELECT value FROM guild_settings WHERE guild_id=? AND key=?",
        (int(guild_id), str(key)),
    )
    if row is None:
        return default
    value = row["value"]
    if isinstance(default, bool):
        return str(value).lower() in {"1", "true", "yes", "on"}
    if isinstance(default, int) or key.endswith("_id"):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
    return value


async def set_setting(bot, guild_id: int, actor_id: int, key: str, value: Any) -> None:
    if not guild_id:
        raise ValueError("Configurações precisam pertencer a um servidor Discord.")
    serialised = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list, tuple)) else str(value)
    before = await get_setting(bot, guild_id, key, None)
    await bot.db.conn.execute(
        "INSERT INTO guild_settings(guild_id,key,value,updated_by,updated_at) VALUES(?,?,?,?,CURRENT_TIMESTAMP) "
        "ON CONFLICT(guild_id,key) DO UPDATE SET value=excluded.value, updated_by=excluded.updated_by, updated_at=CURRENT_TIMESTAMP",
        (int(guild_id), str(key), serialised, int(actor_id)),
    )
    await bot.db.conn.execute(
        "INSERT INTO admin_audit(guild_id,actor_id,action,entity,before_val,after_val,result) VALUES(?,?,?,?,?,?,?)",
        (int(guild_id), int(actor_id), "setting_updated", str(key),
         None if before is None else str(before), serialised, "success"),
    )
    await bot.db.conn.commit()


async def module_enabled(bot, guild_id: int, key: str, default: bool = True) -> bool:
    if not guild_id or not getattr(bot, "db", None) or not bot.db.conn:
        return default
    row = await bot.db._one(
        "SELECT enabled FROM module_settings WHERE guild_id=? AND module_key=?",
        (int(guild_id), str(key)),
    )
    return default if row is None else bool(row["enabled"])


async def set_module_enabled(bot, guild_id: int, actor_id: int, key: str, enabled: bool) -> None:
    previous = await module_enabled(bot, guild_id, key, True)
    await bot.db.conn.execute(
        "INSERT INTO module_settings(guild_id,module_key,enabled,updated_by,updated_at) VALUES(?,?,?,?,CURRENT_TIMESTAMP) "
        "ON CONFLICT(guild_id,module_key) DO UPDATE SET enabled=excluded.enabled,updated_by=excluded.updated_by,updated_at=CURRENT_TIMESTAMP",
        (int(guild_id), str(key), int(bool(enabled)), int(actor_id)),
    )
    await bot.db.conn.execute(
        "INSERT INTO admin_audit(guild_id,actor_id,action,entity,before_val,after_val,result) VALUES(?,?,?,?,?,?,?)",
        (int(guild_id), int(actor_id), "module_toggled", key, str(previous), str(bool(enabled)), "success"),
    )
    await bot.db.conn.commit()


async def audit(bot, guild_id: int, actor_id: int, action: str, entity: str = "", before=None, after=None, result="success") -> None:
    await bot.db.conn.execute(
        "INSERT INTO admin_audit(guild_id,actor_id,action,entity,before_val,after_val,result) VALUES(?,?,?,?,?,?,?)",
        (int(guild_id), int(actor_id), str(action), str(entity),
         None if before is None else str(before), None if after is None else str(after), str(result)),
    )
    await bot.db.conn.commit()


async def migrate_legacy_env(bot, guild) -> list[str]:
    """Importa IDs antigos explícitos do ambiente sem sobrescrever valores do painel."""
    import os

    legacy = {
        "mod_channel_id": ("MOD_CHANNEL_ID", "channel"),
        "platinas_channel_id": ("PLATINAS_CHANNEL_ID", "channel"),
        "colizeu_channel_id": ("COLIZEU_CHANNEL_ID", "channel"),
        "perfis_channel_id": ("PERFIS_CHANNEL_ID", "channel"),
        "soulslike_channel_id": ("SOULSLIKE_CHANNEL_ID", "channel"),
        "zerados_channel_id": ("ZERADOS_CHANNEL_ID", "channel"),
        "creator_video_channel_id": ("CREATOR_VIDEO_CHANNEL_ID", "channel"),
        "creator_live_channel_id": ("CREATOR_LIVE_CHANNEL_ID", "channel"),
        "games_channel_id": ("GAMES_CHANNEL_ID", "channel"),
        "promos_channel_id": ("PROMOS_CHANNEL_ID", "channel"),
        "moderation_role_id": ("MOD_ROLE_ID", "role"),
    }
    imported = []
    for key, (env_name, kind) in legacy.items():
        raw = os.getenv(env_name, "").strip()
        if not raw:
            continue
        try:
            resource_id = int(raw)
        except ValueError:
            continue
        if resource_id <= 0:
            continue
        existing = await bot.db._one("SELECT 1 FROM guild_settings WHERE guild_id=? AND key=?", (guild.id, key))
        if existing:
            continue
        resource = guild.get_channel(resource_id) if kind == "channel" else guild.get_role(resource_id)
        if resource is None:
            await bot.db.conn.execute(
                "INSERT INTO admin_audit(guild_id,actor_id,action,entity,before_val,after_val,result) VALUES(?,?,?,?,?,?,?)",
                (guild.id, 0, "legacy_config_migration", key, None, str(resource_id), "invalid_resource"),
            )
            continue
        await bot.db.conn.execute(
            "INSERT INTO guild_settings(guild_id,key,value,updated_by,updated_at) VALUES(?,?,?,?,CURRENT_TIMESTAMP)",
            (guild.id, key, str(resource_id), 0),
        )
        await bot.db.conn.execute(
            "INSERT INTO admin_audit(guild_id,actor_id,action,entity,before_val,after_val,result) VALUES(?,?,?,?,?,?,?)",
            (guild.id, 0, "legacy_config_migration", key, None, str(resource_id), "success"),
        )
        imported.append(key)
    await bot.db.conn.commit()
    return imported
