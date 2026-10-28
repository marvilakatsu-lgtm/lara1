"""Monitoramento unificado de ofertas para o Quase Pro.

Integra múltiplas fontes (Steam, GamerPower, Epic Games Store, GOG) através da
arquitetura definida em offers_sources.py. Mantém compatibilidade com o banco
SQLite legado (sent_items / sent_items_by_guild) e com as configurações por
servidor já existentes.
"""
from __future__ import annotations

import asyncio
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import (
    OFFERS_CHECK_MINUTES,
    MAX_OFFERS_PER_CHECK,
    MIN_PROMO_DISCOUNT,
    SEED_OFFERS_ON_FIRST_RUN,
    SENT_DB_PATH,
)
from offers_sources import ALL_SOURCES, SOURCE_NAMES, Offer, fetch_all_offers
from settings_store import get_setting
from utils import erro_comando, get_text_channel

log = logging.getLogger("quasepro.ofertas")


# ---------------------------------------------------------------------------
# Banco SQLite local (compatível com histórico legado)
# ---------------------------------------------------------------------------

def init_offers_db() -> None:
    with sqlite3.connect(SENT_DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sent_items (
                item_key TEXT PRIMARY KEY,
                sent_at  TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sent_items_by_guild (
                guild_id INTEGER NOT NULL,
                item_key TEXT NOT NULL,
                sent_at  TEXT NOT NULL,
                PRIMARY KEY (guild_id, item_key)
            )
        """)
        # Tabela de diagnóstico por fonte
        conn.execute("""
            CREATE TABLE IF NOT EXISTS offers_source_status (
                source_name TEXT PRIMARY KEY,
                last_check  TEXT,
                last_success TEXT,
                last_error  TEXT,
                offers_found INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.commit()


def offer_already_sent(item_key: str, guild_id: int | None = None) -> bool:
    with sqlite3.connect(SENT_DB_PATH) as conn:
        legacy = conn.execute(
            "SELECT 1 FROM sent_items WHERE item_key = ?", (item_key,)
        ).fetchone()
        if legacy:
            return True
        if guild_id is None:
            return False
        return conn.execute(
            "SELECT 1 FROM sent_items_by_guild WHERE guild_id=? AND item_key=?",
            (guild_id, item_key),
        ).fetchone() is not None


def mark_offer_sent(item_key: str, guild_id: int | None = None) -> None:
    with sqlite3.connect(SENT_DB_PATH) as conn:
        stamp = datetime.now(timezone.utc).isoformat()
        if guild_id is None:
            conn.execute(
                "INSERT OR IGNORE INTO sent_items(item_key, sent_at) VALUES (?, ?)",
                (item_key, stamp),
            )
        else:
            conn.execute(
                "INSERT OR IGNORE INTO sent_items_by_guild(guild_id,item_key,sent_at) VALUES(?,?,?)",
                (guild_id, item_key, stamp),
            )
        conn.commit()


def count_sent_items() -> int:
    with sqlite3.connect(SENT_DB_PATH) as conn:
        row = conn.execute(
            "SELECT (SELECT COUNT(*) FROM sent_items) + (SELECT COUNT(*) FROM sent_items_by_guild)"
        ).fetchone()
        return int(row[0] or 0)


def update_source_status(source_name: str, *, success: bool, offers_found: int = 0, error: str | None = None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(SENT_DB_PATH) as conn:
        if success:
            conn.execute(
                "INSERT INTO offers_source_status(source_name,last_check,last_success,last_error,offers_found) "
                "VALUES(?,?,?,?,?) ON CONFLICT(source_name) DO UPDATE SET "
                "last_check=excluded.last_check, last_success=excluded.last_success, "
                "last_error=NULL, offers_found=excluded.offers_found",
                (source_name, now, now, None, offers_found),
            )
        else:
            conn.execute(
                "INSERT INTO offers_source_status(source_name,last_check,last_error,offers_found) "
                "VALUES(?,?,?,?) ON CONFLICT(source_name) DO UPDATE SET "
                "last_check=excluded.last_check, last_error=excluded.last_error, "
                "offers_found=excluded.offers_found",
                (source_name, now, error or "Erro desconhecido", offers_found),
            )
        conn.commit()


def get_source_statuses() -> list[dict[str, Any]]:
    with sqlite3.connect(SENT_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT source_name, last_check, last_success, last_error, offers_found "
            "FROM offers_source_status ORDER BY source_name"
        ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Embeds
# ---------------------------------------------------------------------------

def make_offer_embed(offer: Offer) -> discord.Embed:
    """Monta embed profissional mantendo a identidade do Quase Pro."""
    titulo = str(offer.title)[:256]
    descricao = str(offer.description or "Confira os detalhes na página da oferta.")[:1024]

    is_free = offer.kind == "free"
    cor = discord.Color.green() if is_free else discord.Color.orange()

    embed = discord.Embed(title=titulo, url=offer.url or None, description=descricao, color=cor)

    # Preço
    preco = offer.price
    if offer.original_price and offer.original_price != preco:
        preco = f"~~{offer.original_price}~~ → **{preco}**"
    embed.add_field(name="Preço", value=preco or "Consulte a loja", inline=True)

    # Tipo
    tipo_label = "🎁 Jogo Grátis" if is_free else f"🏷️ Promoção ({offer.discount}% OFF)"
    embed.add_field(name="Tipo", value=tipo_label, inline=True)

    # Plataforma
    plataforma = offer.platform or offer.activation_platform or "Não informada"
    embed.add_field(name="Plataforma", value=str(plataforma)[:120], inline=True)

    # Validade
    validade = offer.end_date or "Consulte a loja"
    embed.add_field(name="Validade", value=str(validade)[:120], inline=False)

    # Loja
    embed.set_footer(text=f"Fonte: {offer.source}")

    # Imagem
    if offer.image and str(offer.image).startswith("https://"):
        embed.set_image(url=str(offer.image))

    return embed


# ---------------------------------------------------------------------------
# Cog principal
# ---------------------------------------------------------------------------

class Ofertas(commands.Cog):
    """Monitoramento unificado de jogos grátis e promoções multi-fonte."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.http_session: aiohttp.ClientSession | None = None
        self._first_run_done = False

    async def cog_load(self):
        self.http_session = aiohttp.ClientSession(headers={"User-Agent": "QuaseProBot/2.0"})
        init_offers_db()
        self.offers_loop.start()

    async def cog_unload(self):
        self.offers_loop.cancel()
        if self.http_session and not self.http_session.closed:
            await self.http_session.close()

    @tasks.loop(minutes=OFFERS_CHECK_MINUTES)
    async def offers_loop(self):
        if not self.http_session:
            return

        try:
            # Coleta habilitada por servidor pode ser expandida futuramente;
            # por ora usa o conjunto global de fontes padrão.
            enabled = {s.name for s in ALL_SOURCES if s.enabled_by_default}
            all_offers, errors = await fetch_all_offers(self.http_session, enabled_sources=enabled)

            # Atualiza diagnóstico por fonte
            source_counts: dict[str, int] = {}
            for offer in all_offers:
                source_counts[offer.source] = source_counts.get(offer.source, 0) + 1
            for name in enabled:
                update_source_status(
                    name,
                    success=name not in errors,
                    offers_found=source_counts.get(name, 0),
                    error=errors.get(name),
                )

            # Deduplicação por chave estável
            unique: dict[str, Offer] = {}
            for offer in all_offers:
                if offer.key not in unique:
                    unique[offer.key] = offer

            guilds = list(self.bot.guilds)

            # Seed inicial: registra estado atual sem inundar canais
            if SEED_OFFERS_ON_FIRST_RUN and not self._first_run_done and unique and count_sent_items() == 0:
                for guild in guilds:
                    for key in unique:
                        mark_offer_sent(key, guild.id)
                log.info(
                    "Primeira execução: %s ofertas registradas em %s servidor(es), sem postagem.",
                    len(unique), len(guilds),
                )
                self._first_run_done = True
                return

            self._first_run_done = True
            sent_by_guild: dict[int, int] = {g.id: 0 for g in guilds}

            for offer in unique.values():
                # Filtro de desconto mínimo para promoções
                if offer.kind == "promo" and offer.discount < MIN_PROMO_DISCOUNT:
                    continue

                for guild in guilds:
                    if sent_by_guild[guild.id] >= MAX_OFFERS_PER_CHECK:
                        continue
                    if offer_already_sent(offer.key, guild.id):
                        continue

                    setting_key = "games_channel_id" if offer.kind == "free" else "promos_channel_id"
                    target_id = await get_setting(self.bot, guild.id, setting_key, 0)
                    if not target_id:
                        continue

                    channel = await get_text_channel(self.bot, int(target_id))
                    if channel is None or getattr(channel, "guild", None) is None or channel.guild.id != guild.id:
                        continue

                    try:
                        await channel.send(embed=make_offer_embed(offer))
                        mark_offer_sent(offer.key, guild.id)
                        sent_by_guild[guild.id] += 1
                        await asyncio.sleep(1.2)
                    except discord.HTTPException:
                        log.exception("Falha publicando oferta %s em %s", offer.title, guild.id)

            sent_total = sum(sent_by_guild.values())
            log.info("Ofertas verificadas: %s; novas publicadas: %s", len(unique), sent_total)

        except Exception:
            log.exception("Erro na rotina de ofertas.")

    @offers_loop.before_loop
    async def before_offers_loop(self):
        await self.bot.wait_until_ready()

    # -------------------------------------------------------------------
    # Comando de diagnóstico
    # -------------------------------------------------------------------

    @app_commands.command(name="status_ofertas", description="Mostra o estado do monitoramento de ofertas e suas fontes.")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def status_ofertas(self, interaction: discord.Interaction):
        games_id = await get_setting(self.bot, interaction.guild.id, "games_channel_id", 0)
        promos_id = await get_setting(self.bot, interaction.guild.id, "promos_channel_id", 0)
        games = f"<#{games_id}>" if games_id else "❌ Não configurado"
        promos = f"<#{promos_id}>" if promos_id else "❌ Não configurado"

        statuses = get_source_statuses()
        enabled_names = {s.name for s in ALL_SOURCES if s.enabled_by_default}

        linhas_fontes: list[str] = []
        for name in sorted(enabled_names):
            info = next((s for s in statuses if s["source_name"] == name), None)
            if info:
                status_icon = "✅" if info.get("last_success") and not info.get("last_error") else "⚠️"
                ultima = info.get("last_check") or "Nunca"
                if isinstance(ultima, str) and "T" in ultima:
                    try:
                        dt = datetime.fromisoformat(ultima.replace("Z", "+00:00"))
                        ultima = dt.strftime("%d/%m %H:%M UTC")
                    except (ValueError, TypeError):
                        pass
                qtd = info.get("offers_found", 0)
                err = info.get("last_error")
                linha = f"{status_icon} **{name}** — {qtd} ofertas — última: {ultima}"
                if err:
                    linha += f"\n└ ⚠️ `{str(err)[:80]}`"
                linhas_fontes.append(linha)
            else:
                linhas_fontes.append(f"⏳ **{name}** — aguardando primeira verificação")

        fontes_text = "\n".join(linhas_fontes) if linhas_fontes else "Nenhuma fonte registrada ainda."

        embed = discord.Embed(
            title="📊 Status do Monitoramento de Ofertas",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Canal Jogos Grátis", value=games, inline=True)
        embed.add_field(name="Canal Promoções", value=promos, inline=True)
        embed.add_field(
            name="Configuração",
            value=(
                f"Intervalo: **{OFFERS_CHECK_MINUTES} min**\n"
                f"Desconto mín.: **{MIN_PROMO_DISCOUNT}%**\n"
                f"Máx./ciclo: **{MAX_OFFERS_PER_CHECK}**\n"
                f"Histórico: **{count_sent_items()}** registros"
            ),
            inline=False,
        )
        embed.add_field(name="Fontes", value=fontes_text, inline=False)
        embed.set_footer(text="Quase Pro • Monitoramento Unificado de Ofertas")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def cog_app_command_error(self, interaction: discord.Interaction, error):
        await erro_comando(interaction, error)


async def setup(bot: commands.Bot):
    await bot.add_cog(Ofertas(bot))