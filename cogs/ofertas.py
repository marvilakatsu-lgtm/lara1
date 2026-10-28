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
    GAMES_CHANNEL_ID, PROMOS_CHANNEL_ID, OFFERS_CHECK_MINUTES, MAX_OFFERS_PER_CHECK,
    MIN_PROMO_DISCOUNT, SEED_OFFERS_ON_FIRST_RUN, SENT_DB_PATH,
)
from utils import get_text_channel, erro_comando

log = logging.getLogger("ofertas")


# ---------------------------------------------------------------- banco local

def init_offers_db() -> None:
    with sqlite3.connect(SENT_DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sent_items (
                item_key TEXT PRIMARY KEY,
                sent_at TEXT NOT NULL
            )
        """)
        # Nova tabela por servidor. sent_items é mantida para respeitar o histórico antigo.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sent_items_by_guild (
                guild_id INTEGER NOT NULL,
                item_key TEXT NOT NULL,
                sent_at TEXT NOT NULL,
                PRIMARY KEY (guild_id, item_key)
            )
        """)
        conn.commit()


def offer_already_sent(item_key: str, guild_id: int | None = None) -> bool:
    with sqlite3.connect(SENT_DB_PATH) as conn:
        # Chaves gravadas pela versão antiga indicam que a oferta já era conhecida antes da migração.
        legacy = conn.execute("SELECT 1 FROM sent_items WHERE item_key = ?", (item_key,)).fetchone()
        if legacy:
            return True
        if guild_id is None:
            return False
        return conn.execute("SELECT 1 FROM sent_items_by_guild WHERE guild_id=? AND item_key=?", (guild_id, item_key)).fetchone() is not None


def mark_offer_sent(item_key: str, guild_id: int | None = None) -> None:
    with sqlite3.connect(SENT_DB_PATH) as conn:
        stamp = datetime.now(timezone.utc).isoformat()
        if guild_id is None:
            conn.execute("INSERT OR IGNORE INTO sent_items(item_key, sent_at) VALUES (?, ?)", (item_key, stamp))
        else:
            conn.execute("INSERT OR IGNORE INTO sent_items_by_guild(guild_id,item_key,sent_at) VALUES(?,?,?)", (guild_id, item_key, stamp))
        conn.commit()


def count_sent_items() -> int:
    with sqlite3.connect(SENT_DB_PATH) as conn:
        row = conn.execute("SELECT (SELECT COUNT(*) FROM sent_items) + (SELECT COUNT(*) FROM sent_items_by_guild)").fetchone()
        return int(row[0] or 0)


# ------------------------------------------------------------------- ofertas

def money_brl(cents: Any) -> str | None:
    try:
        return f"R$ {int(cents) / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return None


async def fetch_gamerpower(session: aiohttp.ClientSession) -> list[dict[str, Any]]:
    try:
        async with session.get(
            "https://www.gamerpower.com/api/giveaways",
            params={"type": "game"},
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            if resp.status == 429:
                log.warning("GamerPower limitou requisições.")
                return []
            resp.raise_for_status()
            data = await resp.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
        log.exception("Falha consultando GamerPower.")
        return []
    if not isinstance(data, list):
        return []
    items = []
    for g in data:
        title = g.get("title")
        url = g.get("open_giveaway_url") or g.get("gamerpower_url")
        if not title or not url:
            continue
        end_date = str(g.get("end_date") or "").strip()
        if not end_date or end_date.upper() == "N/A":
            end_date = "Sem data informada"
        items.append({
            "key": f"gamerpower:{g.get('id') or title}",
            "title": title,
            "url": url,
            "image": g.get("thumbnail"),
            "description": (g.get("description") or "Jogo gratuito por tempo limitado.").strip(),
            "category": "JOGO GRÁTIS",
            "platform": g.get("platforms", "Plataforma não informada"),
            "price": "Grátis",
            "source": "GamerPower",
            "end_date": end_date,
            "kind": "game",
        })
    return items


async def fetch_steam_offers(session: aiohttp.ClientSession) -> list[dict[str, Any]]:
    try:
        async with session.get(
            "https://store.steampowered.com/api/featuredcategories/",
            params={"cc": "br", "l": "brazilian"},
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            if resp.status == 429:
                log.warning("Steam Store limitou requisições.")
                return []
            resp.raise_for_status()
            data = await resp.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
        log.exception("Falha consultando Steam Store.")
        return []
    if not isinstance(data, dict):
        return []
    items = []
    for section_name in ("freegames", "specials"):
        section = data.get(section_name) or {}
        for game in section.get("items", []) if isinstance(section, dict) else []:
            app_id = game.get("id")
            title = game.get("name")
            if not app_id or not title:
                continue
            discount = int(game.get("discount_percent") or 0)
            final_cents = game.get("final_price")
            initial_cents = game.get("original_price")
            actually_free = bool(game.get("is_free")) or final_cents == 0
            if not actually_free and (final_cents is None or discount <= 0):
                continue
            final_price = "Grátis" if actually_free else money_brl(final_cents)
            original_price = None if actually_free else money_brl(initial_cents)
            if not final_price:
                continue
            items.append({
                "key": f"steam:{app_id}:{discount}:{final_cents}",
                "title": title,
                "url": f"https://store.steampowered.com/app/{app_id}/?cc=br",
                "image": game.get("header_image"),
                "description": "Oferta regional da Steam. Confira a página da loja para condições e validade.",
                "category": "JOGO GRÁTIS NA STEAM" if actually_free else f"PROMOÇÃO STEAM • {discount}% OFF",
                "platform": "Steam",
                "price": final_price,
                "original_price": original_price,
                "discount": discount,
                "source": "Steam Store Brasil",
                "end_date": "Consulte a página da loja",
                "kind": "game" if actually_free else "promo",
            })
    return items


def make_offer_embed(item: dict[str, Any]) -> discord.Embed:
    """Monta um único embed por oferta (evita previews duplicados de link/imagem)."""
    titulo = str(item["title"])[:250]
    descricao = str(item.get("description") or "Confira os detalhes na página da oferta.")[:950]
    tipo = str(item.get("category", "Oferta"))[:120]
    plataforma = str(item.get("platform", "Não informada"))[:120]
    preco = str(item.get("price", "Consulte a loja"))
    original = item.get("original_price")
    if original and original != preco:
        preco = f"~~{original}~~ → **{preco}**"
    validade = str(item.get("end_date") or "Consulte a loja")[:120]
    fonte = str(item.get("source", "Fonte não informada"))[:100]
    url = str(item.get("url", ""))
    imagem = item.get("image")

    cor = discord.Color.green() if item.get("kind") == "game" else discord.Color.orange()
    embed = discord.Embed(title=titulo, url=url or None, description=descricao, color=cor)
    embed.add_field(name="Tipo", value=tipo, inline=True)
    embed.add_field(name="Plataforma", value=plataforma, inline=True)
    embed.add_field(name="Preço", value=preco, inline=True)
    embed.add_field(name="Validade", value=validade, inline=False)
    embed.set_footer(text=f"Fonte: {fonte}")
    if imagem and str(imagem).startswith("https://"):
        embed.set_image(url=str(imagem))
    return embed


class Ofertas(commands.Cog):
    """Jogos grátis (GamerPower/Steam) e promoções da Steam."""

    def __init__(self, bot):
        self.bot = bot
        self.http_session: aiohttp.ClientSession | None = None

    async def cog_load(self):
        self.http_session = aiohttp.ClientSession(headers={"User-Agent": "ColizeuBot/1.0"})
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
            offers = await asyncio.gather(
                fetch_gamerpower(self.http_session),
                fetch_steam_offers(self.http_session),
                return_exceptions=True,
            )
            items = []
            for result in offers:
                if isinstance(result, list):
                    items.extend(result)
                elif isinstance(result, Exception):
                    log.error("Erro consultando uma fonte de ofertas: %r", result)

            unique = {item["key"]: item for item in items}

            guilds = list(self.bot.guilds)
            # Primeira execução: registra o estado existente por servidor sem inundar os canais.
            if SEED_OFFERS_ON_FIRST_RUN and unique and count_sent_items() == 0:
                for guild in guilds:
                    for item in unique.values():
                        mark_offer_sent(item["key"], guild.id)
                log.info("Primeira execução: %s ofertas registradas em %s servidor(es), sem postagem.", len(unique), len(guilds))
                return

            from settings_store import get_setting
            sent_by_guild = {guild.id: 0 for guild in guilds}
            for item in unique.values():
                if offer_already_sent(item["key"]):
                    continue
                if item["kind"] == "promo" and item.get("discount", 0) < MIN_PROMO_DISCOUNT:
                    continue
                for guild in guilds:
                    if sent_by_guild[guild.id] >= MAX_OFFERS_PER_CHECK:
                        continue
                    if offer_already_sent(item["key"], guild.id):
                        continue
                    setting_key = "games_channel_id" if item["kind"] == "game" else "promos_channel_id"
                    target_id = await get_setting(self.bot, guild.id, setting_key, 0)
                    if not target_id:
                        continue
                    channel = await get_text_channel(self.bot, int(target_id))
                    if channel is None or getattr(channel, "guild", None) is None or channel.guild.id != guild.id:
                        continue
                    try:
                        await channel.send(embed=make_offer_embed(item))
                        mark_offer_sent(item["key"], guild.id)
                        sent_by_guild[guild.id] += 1
                        await asyncio.sleep(1.2)
                    except discord.HTTPException:
                        log.exception("Falha publicando oferta %s em %s", item.get("title"), guild.id)
            sent_this_cycle = sum(sent_by_guild.values())
            log.info("Ofertas verificadas: %s; novas publicadas: %s", len(unique), sent_this_cycle)
        except Exception:
            log.exception("Erro na rotina de ofertas.")

    @offers_loop.before_loop
    async def before_offers_loop(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="status_ofertas", description="Mostra se o monitoramento de ofertas está configurado e funcionando.")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def status_ofertas(self, interaction: discord.Interaction):
        from settings_store import get_setting
        games_id = await get_setting(self.bot, interaction.guild.id, "games_channel_id", 0)
        promos_id = await get_setting(self.bot, interaction.guild.id, "promos_channel_id", 0)
        games = f"<#{games_id}>" if games_id else "Não configurado"
        promos = f"<#{promos_id}>" if promos_id else "Não configurado"
        await interaction.response.send_message(
            f"**Jogos grátis:** {games}\n**Promoções:** {promos}\n"
            f"**Verificação:** a cada {OFFERS_CHECK_MINUTES} minutos.\n"
            f"**Desconto mínimo para promoções:** {MIN_PROMO_DISCOUNT}%",
            ephemeral=True,
        )

    async def cog_app_command_error(self, interaction, error):
        await erro_comando(interaction, error)


async def setup(bot):
    await bot.add_cog(Ofertas(bot))
