"""Ponto único de inicialização do Quase Pro (Soulsbot + catálogo + clãs)."""
import copy
import logging

import discord
from discord.ext import commands

import config
from database import Database

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("quasepro")

EXTENSOES = (
    "cogs.perfil", "cogs.platinas", "cogs.ranking", "cogs.colizeu",
    "cogs.cargos", "cogs.sentinela", "cogs.youtube", "cogs.ofertas",
    "cogs.zerados", "cogs.santuario", "cogs.soulslike", "cogs.loja",
    "cogs.nexus_ia", "cogs.clans", "cogs.admin", "cogs.catalogo",
)


class QuaseProBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.voice_states = True
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)
        self.db = Database(config.DB_PATH)
        self._slash_sync_done = False
        self._guild_command_templates = []
        self.catalog_db_path = None

    async def setup_hook(self):
        await self.db.connect()
        for extension in EXTENSOES:
            try:
                await self.load_extension(extension)
                log.info("Extensão carregada: %s", extension)
            except Exception:
                log.exception("Falha carregando extensão %s; inicialização interrompida para evitar estado parcial.", extension)
                raise
        # Preserve cópias dos comandos antes de limpar o registro global local.
        # Elas também permitem sincronizar servidores que entrarem mais tarde.
        self._guild_command_templates = [copy.copy(command) for command in self.tree.get_commands()]

    async def _sync_guild_commands(self, guild: discord.Guild):
        for command in self._guild_command_templates:
            try:
                self.tree.add_command(copy.copy(command), guild=guild, override=True)
            except Exception:
                log.exception("Falha preparando comando %s para o servidor %s", command.name, guild.id)
                raise
        synced = await self.tree.sync(guild=guild)
        log.info("[slash] %s comandos sincronizados em %s (%s)", len(synced), guild.name, guild.id)
        return synced

    async def on_ready(self):
        log.info("Quase Pro conectado como %s (%s)", self.user, self.user.id if self.user else "sem ID")
        if self._slash_sync_done:
            return
        self._slash_sync_done = True
        for guild in list(self.guilds):
            try:
                await self._sync_guild_commands(guild)
            except Exception:
                log.exception("[slash] Falha ao sincronizar comandos no servidor %s (%s)", guild.name, guild.id)
        # Elimina comandos globais remotos antigos para que a UI não mostre duplicatas.
        try:
            self.tree.clear_commands(guild=None)
            await self.tree.sync()
            log.info("[slash] Comandos globais limpos; os comandos ficam no escopo de cada servidor.")
        except Exception:
            log.exception("[slash] Não foi possível limpar comandos globais antigos.")

    async def on_guild_join(self, guild: discord.Guild):
        try:
            await self._sync_guild_commands(guild)
        except Exception:
            log.exception("[slash] Falha sincronizando o novo servidor %s (%s)", guild.name, guild.id)

    async def close(self):
        try:
            await super().close()
        finally:
            if self.db and self.db.conn:
                await self.db.conn.close()
                self.db.conn = None


if __name__ == "__main__":
    if not config.TOKEN:
        raise SystemExit("Defina DISCORD_TOKEN nas variáveis de ambiente.")
    QuaseProBot().run(config.TOKEN)
