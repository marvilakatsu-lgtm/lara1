"""Painel /adm: configuração por servidor, auditoria, diagnóstico e organização segura."""
from __future__ import annotations

import os
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

import config
from settings_store import audit, get_setting, module_enabled, set_module_enabled, set_setting

CHANNELS = {
    "mod_channel_id": ("Canal de moderação/aprovações", getattr(config, "MOD_CHANNEL_ID", 0), "text"),
    "platinas_channel_id": ("Anúncios de platinas", getattr(config, "PLATINAS_CHANNEL_ID", 0), "text"),
    "colizeu_channel_id": ("Painel do Coliseu", getattr(config, "COLIZEU_CHANNEL_ID", 0), "text"),
    "perfis_channel_id": ("Santuários e perfis", getattr(config, "PERFIS_CHANNEL_ID", 0), "text"),
    "soulslike_channel_id": ("Runs e desafios Soulslike", getattr(config, "SOULSLIKE_CHANNEL_ID", 0), "text"),
    "zerados_channel_id": ("Anúncios de jogos zerados", getattr(config, "ZERADOS_CHANNEL_ID", 0), "text"),
    "creator_video_channel_id": ("Avisos de vídeos do YouTube", getattr(config, "VIDEO_CHANNEL_ID", 0), "text"),
    "creator_live_channel_id": ("Avisos de lives do YouTube", getattr(config, "LIVE_CHANNEL_ID", 0), "text"),
    "games_channel_id": ("Jogos gratuitos", getattr(config, "GAMES_CHANNEL_ID", 0), "text"),
    "promos_channel_id": ("Promoções", getattr(config, "PROMOS_CHANNEL_ID", 0), "text"),
    "clan_hall_channel_id": ("Salão dos Juramentos", 0, "text"),
}
ROLES = {
    "admin_role_id": ("Cargo administrativo autorizado", 0),
    "moderation_role_id": ("Cargo de moderação", getattr(config, "MOD_ROLE_ID", 0)),
    "video_notice_role_id": ("Cargo que recebe avisos de vídeos", 0),
    "live_notice_role_id": ("Cargo que recebe avisos de lives", 0),
    "member_role_id": ("Cargo padrão de membro", 0),
}
CATEGORIES = {
    "category_start_id": "COMECE AQUI",
    "category_quasepro_id": "QUASE PRO",
    "category_community_id": "COMUNIDADE",
    "category_soulslike_id": "UNIVERSO SOULSLIKE",
    "category_systems_id": "SISTEMAS SOULSBOT",
    "category_catalog_id": "CATÁLOGO E OFERTAS",
    "category_voice_id": "VOZ",
    "category_team_id": "EQUIPE",
    "category_clans_id": "CLÃS",
}
SECTIONS = [
    ("overview", "Visão geral", "Visão geral do bot e do servidor"),
    ("channels", "Canais", "Escolher canais de cada sistema"),
    ("categories", "Categorias", "Associar categorias e organizar a estrutura"),
    ("roles", "Cargos", "Configurar cargos administrativos e funcionais"),
    ("organization", "Organização do servidor", "Pré-visualizar e aplicar estrutura não destrutiva"),
    ("soulsbot", "Sistemas do Soulsbot", "Perfis, Coliseu, progressão, runs e conquistas"),
    ("catalog", "Catálogo de jogos e mods", "Catálogo, submissões, aprovações e notícias"),
    ("youtube", "YouTube", "Vídeos, lives, credenciais e destinos"),
    ("offers", "Jogos gratuitos e promoções", "Destinos e frequência das ofertas"),
    ("progression", "Perfis e progressão", "XP, patentes e dados individuais"),
    ("clans", "Sistema de Clãs", "Salão dos Juramentos, recrutamento e integridade"),
    ("moderation", "Moderação e permissões", "Cargos, validação e permissões do bot"),
    ("appearance", "Aparência", "Identidade visual e padrões dos painéis"),
    ("database", "Banco de dados", "Integridade e persistência"),
    ("diagnostics", "Diagnóstico", "Canais, cargos, permissões e clãs degradados"),
    ("history", "Histórico administrativo", "Registro de alterações e operações"),
    ("backup", "Backup e restauração", "Criar um backup antes de migrações"),
    ("help", "Ajuda", "Referência de comandos e dependências"),
]


def _member_has_role(member: discord.Member, role_id: int) -> bool:
    return bool(role_id and any(r.id == int(role_id) for r in member.roles))


async def is_admin(bot, interaction: discord.Interaction) -> bool:
    if interaction.guild is None or not isinstance(interaction.user, discord.Member):
        return False
    member = interaction.user
    if member.guild_permissions.administrator or member.guild_permissions.manage_guild:
        return True
    admin_role = await get_setting(bot, interaction.guild.id, "admin_role_id", 0)
    return _member_has_role(member, int(admin_role or 0))


async def _setting_value(bot, guild_id: int, key: str, default=0):
    return await get_setting(bot, guild_id, key, default)


class AdminBaseView(discord.ui.View):
    def __init__(self, cog: "Admin", guild_id: int, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.guild_id = int(guild_id)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.guild_id != self.guild_id or not await is_admin(self.cog.bot, interaction):
            await interaction.response.send_message("Você não tem autorização para operar este painel administrativo.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Voltar ao início", style=discord.ButtonStyle.secondary, emoji="↩️", row=4)
    async def go_home(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await self.cog.overview_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=AdminHomeView(self.cog, self.guild_id))


class AdminHomeView(AdminBaseView):
    def __init__(self, cog: "Admin", guild_id: int):
        super().__init__(cog, guild_id)
        select = discord.ui.Select(placeholder="Selecione uma área administrativa", min_values=1, max_values=1,
                                  options=[discord.SelectOption(label=label, description=description[:100], value=value) for value, label, description in SECTIONS])
        select.callback = self._choose
        self.add_item(select)

    async def _choose(self, interaction: discord.Interaction):
        section = interaction.data["values"][0]
        embed, view = await self.cog.render_section(interaction.guild, section)
        await interaction.response.edit_message(embed=embed, view=view or AdminHomeView(self.cog, self.guild_id))


class ChannelSettingSelect(discord.ui.Select):
    def __init__(self, cog, guild_id, keys=None):
        self.cog, self.guild_id = cog, guild_id
        keys = keys or list(CHANNELS)
        options = [discord.SelectOption(label=CHANNELS[k][0][:100], value=k, description="Selecionar canal de destino"[:100]) for k in keys]
        super().__init__(placeholder="Qual destino deseja configurar?", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        key = self.values[0]
        label = CHANNELS[key][0]
        await interaction.response.edit_message(content=f"**{label}**\nSelecione um canal existente. A alteração ainda não será salva.", embed=None,
                                                view=ChannelPickerView(self.cog, self.guild_id, key))


class ChannelConfigView(AdminBaseView):
    def __init__(self, cog, guild_id):
        super().__init__(cog, guild_id)
        self.add_item(ChannelSettingSelect(cog, guild_id))


class ChannelPickerView(AdminBaseView):
    def __init__(self, cog, guild_id, key):
        super().__init__(cog, guild_id)
        self.key = key
        label, _, kind = CHANNELS[key]
        channel_types = [discord.ChannelType.text, discord.ChannelType.news]
        self.picker = discord.ui.ChannelSelect(placeholder=f"Escolha: {label}"[:100], min_values=1, max_values=1, channel_types=channel_types)
        self.picker.callback = self._selected
        self.add_item(self.picker)

    async def _selected(self, interaction: discord.Interaction):
        channel = self.picker.values[0]
        await interaction.response.edit_message(content=(f"Confirme a associação:\n\n**{CHANNELS[self.key][0]}** → {channel.mention}\n"
                                                         "A configuração será salva para este servidor e registrada no histórico."),
                                                embed=None, view=ConfirmChannelView(self.cog, self.guild_id, self.key, channel.id))


class ConfirmChannelView(AdminBaseView):
    def __init__(self, cog, guild_id, key, channel_id):
        super().__init__(cog, guild_id, timeout=120)
        self.key, self.channel_id = key, int(channel_id)

    @discord.ui.button(label="Confirmar e salvar", style=discord.ButtonStyle.success, emoji="💾")
    async def save(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.guild.get_channel(self.channel_id)
        if not channel:
            return await interaction.response.edit_message(content="O canal foi excluído ou deixou de estar acessível. Escolha outro.", view=None)
        me = interaction.guild.me
        perms = channel.permissions_for(me) if me else None
        if perms and not (perms.view_channel and perms.send_messages):
            return await interaction.response.send_message("Aviso: o bot não possui Ver canal e Enviar mensagens neste destino. A associação não foi salva.", ephemeral=True)
        await set_setting(self.cog.bot, self.guild_id, interaction.user.id, self.key, self.channel_id)
        await interaction.response.edit_message(content=f"Configuração salva: **{CHANNELS[self.key][0]}** → {channel.mention}.", view=None)

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Alteração cancelada; nada foi salvo.", view=None)


class RoleSettingSelect(discord.ui.Select):
    def __init__(self, cog, guild_id):
        self.cog, self.guild_id = cog, guild_id
        options = [discord.SelectOption(label=label[:100], value=key, description="Associação por servidor") for key, (label, _) in ROLES.items()]
        super().__init__(placeholder="Qual função de cargo deseja configurar?", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        key = self.values[0]
        await interaction.response.edit_message(content=f"Selecione um cargo para **{ROLES[key][0]}**. A alteração não será salva até a confirmação.", embed=None,
                                                view=RolePickerView(self.cog, self.guild_id, key))


class RoleConfigView(AdminBaseView):
    def __init__(self, cog, guild_id):
        super().__init__(cog, guild_id)
        self.add_item(RoleSettingSelect(cog, guild_id))


class RolePickerView(AdminBaseView):
    def __init__(self, cog, guild_id, key):
        super().__init__(cog, guild_id)
        self.key = key
        self.picker = discord.ui.RoleSelect(placeholder=f"Escolha: {ROLES[key][0]}"[:100], min_values=1, max_values=1)
        self.picker.callback = self._selected
        self.add_item(self.picker)

    async def _selected(self, interaction: discord.Interaction):
        role = self.picker.values[0]
        bot_member = interaction.guild.me
        warning = ""
        if bot_member and role >= bot_member.top_role:
            warning = "\n⚠️ O cargo está no mesmo nível ou acima do cargo mais alto do bot; o bot não conseguirá gerenciá-lo."
        await interaction.response.edit_message(content=f"Confirme: **{ROLES[self.key][0]}** → {role.mention}{warning}", embed=None,
                                                view=ConfirmRoleView(self.cog, self.guild_id, self.key, role.id))


class ConfirmRoleView(AdminBaseView):
    def __init__(self, cog, guild_id, key, role_id):
        super().__init__(cog, guild_id, timeout=120)
        self.key, self.role_id = key, int(role_id)

    @discord.ui.button(label="Confirmar e salvar", style=discord.ButtonStyle.success, emoji="💾")
    async def save(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = interaction.guild.get_role(self.role_id)
        if not role:
            return await interaction.response.edit_message(content="O cargo foi excluído; escolha outro.", view=None)
        await set_setting(self.cog.bot, self.guild_id, interaction.user.id, self.key, self.role_id)
        await interaction.response.edit_message(content=f"Configuração salva: **{ROLES[self.key][0]}** → {role.mention}.", view=None)

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Alteração cancelada; nada foi salvo.", view=None)


class CategoryConfigView(AdminBaseView):
    def __init__(self, cog, guild_id):
        super().__init__(cog, guild_id)
        self.picker = discord.ui.ChannelSelect(placeholder="Selecione uma categoria para associar", channel_types=[discord.ChannelType.category], min_values=1, max_values=1)
        self.picker.callback = self._selected
        self.add_item(self.picker)
        sel = discord.ui.Select(placeholder="Função da categoria", options=[discord.SelectOption(label=v, value=k) for k, v in CATEGORIES.items()], min_values=1, max_values=1)
        sel.callback = self._choose_key
        self.add_item(sel)
        self.key = None
        self.selected_channel = None

    async def _choose_key(self, interaction: discord.Interaction):
        self.key = interaction.data["values"][0]
        if self.selected_channel:
            return await interaction.response.edit_message(content=f"Associar a categoria **{CATEGORIES[self.key]}** à categoria selecionada **{self.selected_channel.name}**?", view=ConfirmCategoryView(self.cog, self.guild_id, self.key, self.selected_channel.id))
        await interaction.response.send_message(f"Função selecionada: **{CATEGORIES[self.key]}**. Agora escolha a categoria no seletor.", ephemeral=True)

    async def _selected(self, interaction: discord.Interaction):
        self.selected_channel = self.picker.values[0]
        if self.key:
            return await interaction.response.edit_message(content=f"Associar a categoria **{CATEGORIES[self.key]}** à categoria **{self.selected_channel.name}**?", view=ConfirmCategoryView(self.cog, self.guild_id, self.key, self.selected_channel.id))
        await interaction.response.send_message(f"Categoria selecionada: **{self.selected_channel.name}**. Agora escolha sua função no segundo menu.", ephemeral=True)


class ConfirmCategoryView(AdminBaseView):
    def __init__(self, cog, guild_id, key, category_id):
        super().__init__(cog, guild_id, timeout=120)
        self.key, self.category_id = key, int(category_id)

    @discord.ui.button(label="Confirmar associação", style=discord.ButtonStyle.success)
    async def save(self, interaction: discord.Interaction, button: discord.ui.Button):
        category = interaction.guild.get_channel(self.category_id)
        if not isinstance(category, discord.CategoryChannel):
            return await interaction.response.edit_message(content="A categoria não existe mais.", view=None)
        await set_setting(self.cog.bot, self.guild_id, interaction.user.id, self.key, self.category_id)
        await interaction.response.edit_message(content=f"Categoria **{CATEGORIES[self.key]}** associada a **{category.name}**.", view=None)

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Associação cancelada.", view=None)


class ModuleConfigView(AdminBaseView):
    MODULES = {
        "clans": "Sistema de Clãs",
        "catalog": "Catálogo de jogos e mods (status informativo)",
        "youtube": "Notificações do YouTube (status informativo)",
        "offers": "Jogos gratuitos e promoções (status informativo)",
    }

    def __init__(self, cog, guild_id):
        super().__init__(cog, guild_id)
        select = discord.ui.Select(placeholder="Selecione um módulo", min_values=1, max_values=1,
                                  options=[discord.SelectOption(label=label[:100], value=key) for key, label in self.MODULES.items()])
        select.callback = self._select_module
        self.add_item(select)

    async def _select_module(self, interaction: discord.Interaction):
        key = interaction.data["values"][0]
        enabled = await module_enabled(self.cog.bot, self.guild_id, key, True)
        if key != "clans":
            embed = discord.Embed(title=self.MODULES[key], description=(f"Estado salvo: **{'Ativo' if enabled else 'Desativado'}**.\n\n"
                "Este módulo ainda não oferece desligamento integral por flag central; por segurança, não será alterado pelo painel. "
                "A tela informa o estado, mas a opção não está disponível até todas as rotas e tarefas do módulo respeitarem a flag."), color=0xC0C0C0)
            return await interaction.response.edit_message(embed=embed, view=self)
        embed = discord.Embed(title="Sistema de Clãs", description=f"Estado atual: **{'Ativo' if enabled else 'Desativado'}**.\n\nA alteração bloqueia ou libera o painel público e os componentes de clã ainda abertos neste servidor.", color=0xD4AF37)
        await interaction.response.edit_message(embed=embed, view=ClanModuleToggleView(self.cog, self.guild_id, enabled))


class ClanModuleToggleView(AdminBaseView):
    def __init__(self, cog, guild_id, enabled):
        super().__init__(cog, guild_id, timeout=120)
        self.enabled = enabled

    @discord.ui.button(label="Ativar", style=discord.ButtonStyle.success)
    async def enable(self, interaction: discord.Interaction, button: discord.ui.Button):
        await set_module_enabled(self.cog.bot, self.guild_id, interaction.user.id, "clans", True)
        await interaction.response.edit_message(content="Sistema de Clãs ativado neste servidor.", embed=None, view=None)

    @discord.ui.button(label="Desativar", style=discord.ButtonStyle.danger)
    async def disable(self, interaction: discord.Interaction, button: discord.ui.Button):
        await set_module_enabled(self.cog.bot, self.guild_id, interaction.user.id, "clans", False)
        await interaction.response.edit_message(content="Sistema de Clãs desativado para novas interações. Os dados e canais existentes não foram excluídos.", embed=None, view=None)


class OrganizationPreviewView(AdminBaseView):
    @discord.ui.button(label="Aplicar plano não destrutivo", style=discord.ButtonStyle.success, emoji="🧰", row=0)
    async def apply_plan(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="A aplicação criará apenas categorias/canais ausentes, sem renomear, mover ou excluir recursos. Confirma?", embed=None,
                                                view=ConfirmOrganizationView(self.cog, self.guild_id))


class ConfirmOrganizationView(AdminBaseView):
    @discord.ui.button(label="Confirmar aplicação", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        results = await self.cog.apply_organization(interaction.guild, interaction.user.id)
        await interaction.followup.send(results, ephemeral=True)
        try:
            await interaction.message.edit(content="Plano processado. Consulte a resposta privada para o resultado detalhado.", embed=None, view=None)
        except discord.HTTPException:
            pass

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Plano cancelado. Nenhum recurso foi alterado.", view=None)


class SimpleActionView(AdminBaseView):
    def __init__(self, cog, guild_id, section):
        super().__init__(cog, guild_id)
        self.section = section

    @discord.ui.button(label="Atualizar", style=discord.ButtonStyle.primary, emoji="🔄", row=0)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed, view = await self.cog.render_section(interaction.guild, self.section)
        await interaction.response.edit_message(embed=embed, view=view or AdminHomeView(self.cog, self.guild_id))


class ClansAdminView(AdminBaseView):
    def __init__(self, cog, guild_id):
        super().__init__(cog, guild_id)
        select = discord.ui.Select(
            placeholder="Modo padrão para novos clãs", min_values=1, max_values=1, row=1,
            options=[
                discord.SelectOption(label="Somente por convite", value="invite"),
                discord.SelectOption(label="Candidaturas abertas", value="applications"),
                discord.SelectOption(label="Misto", value="mixed"),
            ],
        )
        select.callback = self.set_default_recruitment
        self.add_item(select)

    async def set_default_recruitment(self, interaction: discord.Interaction):
        mode = interaction.data["values"][0]
        await set_setting(self.cog.bot, self.guild_id, interaction.user.id, "clans_default_recruitment", mode)
        names = {"invite": "Somente por convite", "applications": "Candidaturas abertas", "mixed": "Misto"}
        await interaction.response.send_message(f"Modo padrão para novos clãs salvo: **{names[mode]}**. Líderes podem alterar o modo individualmente no painel do próprio clã.", ephemeral=True)

    @discord.ui.button(label="Publicar/atualizar Salão dos Juramentos", style=discord.ButtonStyle.primary, emoji="⚔️", row=0)
    async def publish(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel_id = await get_setting(self.cog.bot, self.guild_id, "clan_hall_channel_id", 0)
        channel = interaction.guild.get_channel(int(channel_id)) if channel_id else None
        if not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message("Configure primeiro o canal **Salão dos Juramentos** na seção Canais.", ephemeral=True)
        clans = self.cog.bot.get_cog("Clans")
        if not clans:
            return await interaction.response.send_message("O módulo de clãs não foi carregado; confira os logs de inicialização.", ephemeral=True)
        await clans.post_public_panel(interaction, channel)

    @discord.ui.button(label="Validar recursos de clãs", style=discord.ButtonStyle.secondary, emoji="🩺", row=0)
    async def check_clans(self, interaction: discord.Interaction, button: discord.ui.Button):
        lines = await self.cog.clan_integrity(interaction.guild)
        await interaction.response.send_message("\n".join(lines) or "Nenhuma inconsistência detectada.", ephemeral=True)

    @discord.ui.button(label="Reparar recursos", style=discord.ButtonStyle.success, emoji="🛠️", row=2)
    async def repair_clans(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content=("O reparo tentará recriar categorias/canais ausentes e sincronizar permissões dos clãs não encerrados. "
                     "Registros históricos não serão excluídos. Confirma?"),
            embed=None,
            view=ConfirmRepairClansView(self.cog, self.guild_id),
        )


class ConfirmRepairClansView(AdminBaseView):
    @discord.ui.button(label="Confirmar reparo", style=discord.ButtonStyle.success, emoji="🛠️")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        clans = self.cog.bot.get_cog("Clans")
        if not clans:
            return await interaction.followup.send("O módulo de clãs não está carregado.", ephemeral=True)
        results = await clans.repair_guild_clans(interaction.guild, interaction.user.id)
        await interaction.followup.send("\n".join(results)[:1900], ephemeral=True)
        try:
            await interaction.message.edit(content="Verificação/reparo concluído. Consulte o resultado privado.", view=None)
        except discord.HTTPException:
            pass

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Reparo cancelado; nenhum recurso foi alterado.", view=None)


class BackupView(AdminBaseView):
    @discord.ui.button(label="Gerar backup dos bancos", style=discord.ButtonStyle.primary, emoji="💾")
    async def create_backup(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        path = await self.cog.create_backup()
        try:
            await interaction.followup.send("Backup concluído. Guarde o arquivo em local seguro; ele contém dados de usuários e do catálogo.", file=discord.File(path, filename=os.path.basename(path)), ephemeral=True)
        finally:
            try:
                os.remove(path)
            except OSError:
                pass


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        from settings_store import migrate_legacy_env
        for guild in list(self.bot.guilds):
            try:
                imported = await migrate_legacy_env(self.bot, guild)
                if imported:
                    print(f"[adm] Configurações antigas importadas em {guild.id}: {', '.join(imported)}")
            except Exception:
                print(f"[adm] Falha na migração das configurações antigas do servidor {guild.id}", flush=True)

    async def overview_embed(self, guild: discord.Guild) -> discord.Embed:
        settings_count = await self.bot.db._one("SELECT COUNT(*) AS n FROM guild_settings WHERE guild_id=?", (guild.id,))
        clan_count = await self.bot.db._one("SELECT COUNT(*) AS n FROM clans WHERE guild_id=? AND status='active'", (guild.id,))
        degraded = await self.bot.db._one("SELECT COUNT(*) AS n FROM clans WHERE guild_id=? AND status='degraded'", (guild.id,))
        embed = discord.Embed(title="Quase Pro · Painel Administrativo `/adm`", description="Configuração centralizada por servidor. Alterações são persistidas e registradas no histórico.", color=0x0D0D0D)
        embed.add_field(name="Servidor", value=f"{guild.name}\nID: `{guild.id}`", inline=True)
        embed.add_field(name="Configurações persistidas", value=str(settings_count["n"] if settings_count else 0), inline=True)
        embed.add_field(name="Clãs ativos/degradados", value=f"{clan_count['n'] if clan_count else 0} / {degraded['n'] if degraded else 0}", inline=True)
        embed.add_field(name="Arquitetura", value="Um cliente Discord · comandos do Soulsbot e catálogo na mesma árvore · bancos SQLite separados", inline=False)
        embed.add_field(name="Atenção", value="O `.env` continua necessário para tokens e APIs. IDs operacionais podem ser associados pelos seletores abaixo.", inline=False)
        embed.set_footer(text="Use os menus para configurar canais/cargos, revisar a estrutura e auditar mudanças.")
        return embed

    async def render_section(self, guild: discord.Guild, section: str):
        if section == "overview":
            return await self.overview_embed(guild), AdminHomeView(self, guild.id)
        if section == "channels":
            embed = discord.Embed(title="Configuração de canais", description="Escolha a associação lógica e depois selecione um canal. O salvamento exige confirmação.", color=0xC0C0C0)
            lines = []
            for key, (label, default, _) in CHANNELS.items():
                val = await get_setting(self.bot, guild.id, key, 0)
                ch = guild.get_channel(int(val)) if val else None
                lines.append(f"**{label}:** {ch.mention if ch else '`Não configurado/inválido`'}")
            embed.description += "\n\n" + "\n".join(lines)
            return embed, ChannelConfigView(self, guild.id)
        if section == "categories":
            embed = discord.Embed(title="Associações de categorias", description="Associe as funções de categoria às categorias existentes. Essa configuração não move canais automaticamente.", color=0xC0C0C0)
            lines = []
            for key, name in CATEGORIES.items():
                val = await get_setting(self.bot, guild.id, key, 0)
                category = guild.get_channel(int(val)) if val else None
                lines.append(f"**{name}:** {category.name if isinstance(category, discord.CategoryChannel) else 'Não associado'}")
            embed.description += "\n\n" + "\n".join(lines)
            return embed, CategoryConfigView(self, guild.id)
        if section == "roles":
            embed = discord.Embed(title="Configuração de cargos", description="Os IDs de cargos são resolvidos pelos seletores nativos do Discord. O bot não concede permissões administrativas automaticamente.", color=0xC0C0C0)
            lines = []
            for key, (label, default) in ROLES.items():
                val = await get_setting(self.bot, guild.id, key, 0)
                role = guild.get_role(int(val)) if val else None
                lines.append(f"**{label}:** {role.mention if role else 'Não configurado'}")
            embed.description += "\n\n" + "\n".join(lines)
            return embed, RoleConfigView(self, guild.id)
        if section == "organization":
            embed = discord.Embed(title="Organização do servidor · Pré-visualização", description=("O plano padrão cria apenas recursos ausentes. Ele não renomeia, move nem exclui canais/cargos. "
                "Canais existentes com o mesmo nome sob outra categoria não serão movidos. Recursos privados de equipe serão criados com acesso restrito, conforme os cargos configurados."), color=0xD4AF37)
            plan = self.organization_plan()
            embed.add_field(name="Categorias/canais", value="\n".join(f"**{cat}**: {', '.join(channels)}" for cat, channels, _ in plan)[:1024], inline=False)
            embed.add_field(name="Operações destrutivas", value="Nenhuma. Exclusões, renomeações e movimentações exigem plano separado e confirmação explícita.", inline=False)
            return embed, OrganizationPreviewView(self, guild.id)
        if section == "clans":
            enabled = await module_enabled(self.bot, guild.id, "clans", True)
            hall_id = await get_setting(self.bot, guild.id, "clan_hall_channel_id", 0)
            hall = guild.get_channel(int(hall_id)) if hall_id else None
            row = await self.bot.db._one("SELECT COUNT(*) AS n FROM clans WHERE guild_id=? AND status='active'", (guild.id,))
            embed = discord.Embed(title="Sistema de Clãs", description=f"Módulo: **{'Ativo' if enabled else 'Desativado'}**\nClãs ativos: **{row['n'] if row else 0}**\nSalão dos Juramentos: {hall.mention if hall else 'não configurado'}\n\nLimite estrutural: 10 integrantes por clã; o banco bloqueia a 11ª entrada.", color=0xD4AF37)
            embed.add_field(name="Progressão", value="XP competitivo não é concedido automaticamente. O ranking usa atividades concluídas e número de integrantes até que regras de pontuação sejam explicitamente definidas.", inline=False)
            return embed, ClansAdminView(self, guild.id)
        if section == "diagnostics":
            lines = await self.diagnostics(guild)
            embed = discord.Embed(title="Diagnóstico e integridade", description="\n".join(lines)[:4000] or "Nenhum problema detectado.", color=0xD4AF37)
            return embed, SimpleActionView(self, guild.id, section)
        if section == "history":
            rows = await self.bot.db._all("SELECT actor_id,action,entity,before_val,after_val,result,created_at FROM admin_audit WHERE guild_id=? ORDER BY id DESC LIMIT 10", (guild.id,))
            lines = [f"`{r['created_at']}` · <@{r['actor_id']}> · **{r['action']}** · `{r['entity']}` · {r['result']}" for r in rows]
            embed = discord.Embed(title="Histórico administrativo · 10 mais recentes", description="\n".join(lines) or "Ainda não há operações administrativas registradas.", color=0xC0C0C0)
            return embed, SimpleActionView(self, guild.id, section)
        if section == "backup":
            embed = discord.Embed(title="Backup e restauração", description="Gera snapshots consistentes dos bancos SQLite do Soulsbot e do catálogo. Faça backup antes de migrações, mudanças de estrutura ou limpeza de canais. O arquivo pode conter dados pessoais e deve ser guardado com acesso restrito.", color=0xC0C0C0)
            return embed, BackupView(self, guild.id)
        if section == "catalog":
            embed = discord.Embed(title="Catálogo de jogos e mods", description="O catálogo foi carregado como extensão do mesmo cliente Discord. Os comandos originais são preservados: `/catalogo`, `/mods`, `/painelmods`, `/enviarmod`, `/adicionarmod` e os comandos `/noticias_*`. O banco `jogos.db` continua separado do banco de progressão.", color=0xC0C0C0)
            embed.add_field(name="Operação", value="Execute `/catalogo` no canal desejado para publicar/atualizar o painel. O ID da mensagem é persistido no banco de catálogo.", inline=False)
            return embed, SimpleActionView(self, guild.id, section)
        if section == "youtube":
            yt_key = bool(getattr(config, "YOUTUBE_API_KEY", ""))
            embed = discord.Embed(title="YouTube", description=f"API key: **{'configurada no ambiente' if yt_key else 'não configurada'}**\nFeed RSS de vídeos não exige chave; consultas de lives usam a API. Configure destinos em Canais.", color=0xC0C0C0)
            return embed, ChannelConfigView(self, guild.id)
        if section == "offers":
            embed = discord.Embed(title="Jogos gratuitos e promoções", description="Configure os destinos de jogos gratuitos e promoções na seção Canais. A frequência, filtros de desconto e credenciais continuam sendo parâmetros de infraestrutura no `.env`; tokens não são armazenados no Discord.", color=0xC0C0C0)
            return embed, ChannelConfigView(self, guild.id)
        if section == "soulsbot":
            embed = discord.Embed(title="Sistemas do Soulsbot", description="Extensões carregadas: perfis, platinas, ranking, Coliseu, cargos, Sentinela, YouTube, ofertas, zerados, santuários, runs Soulslike, loja e Nexus AI. Os módulos continuam preservados, e os destinos operacionais mais comuns estão disponíveis em Canais.", color=0xC0C0C0)
            return embed, ChannelConfigView(self, guild.id)
        if section == "progression":
            embed = discord.Embed(title="Perfis e progressão", description=f"Recompensas atualmente definidas no código: platina = {config.XP_PLATINA} XP / {config.DENARIOS_PLATINA} Denários; jogo zerado = {config.XP_ZERADO} XP / {config.DENARIOS_ZERADO} Denários. Esta tela é informativa: alterar regras competitivas exige migração/configuração própria e não é feito implicitamente.", color=0xC0C0C0)
            return embed, SimpleActionView(self, guild.id, section)
        if section == "moderation":
            embed = discord.Embed(title="Moderação e permissões", description="O painel revalida permissões em cada interação e operações sensíveis são efêmeras. Configure cargo administrativo/moderação em Cargos e canal de aprovação em Canais. O cargo do bot precisa estar acima dos cargos que gerencia.", color=0xC0C0C0)
            return embed, RoleConfigView(self, guild.id)
        if section == "appearance":
            embed = discord.Embed(title="Identidade visual", description="Base visual atual: carvão `#0D0D0D`, ouro `#D4AF37` e prata `#C0C0C0`. O Discord limita a apresentação a embeds, componentes nativos e imagens; esta seção não altera regras de negócio.", color=0x0D0D0D)
            return embed, SimpleActionView(self, guild.id, section)
        if section == "database":
            embed = discord.Embed(title="Banco de dados e persistência", description=f"Soulsbot: `{self.bot.db.path}`\nCatálogo: `{getattr(self.bot, 'catalog_db_path', 'não configurado')}`\n\nOs bancos permanecem separados para evitar migração destrutiva. Configurações, clãs e auditoria ficam no banco principal. Use Backup antes de qualquer operação estrutural.", color=0xC0C0C0)
            return embed, BackupView(self, guild.id)
        embed = discord.Embed(title="Ajuda e documentação interna", description="Use `/adm` para configurar canais, cargos e associações de categorias. Comandos do catálogo e notícias são mantidos na mesma aplicação. A configuração de chaves e tokens externos permanece no ambiente da hospedagem.", color=0xC0C0C0)
        return embed, SimpleActionView(self, guild.id, section)

    def organization_plan(self):
        return [
            ("COMECE AQUI", ["boas-vindas", "regras", "selecao-de-cargos"], "category_start_id"),
            ("QUASE PRO", ["anuncios", "videos", "lives", "sugestoes"], "category_quasepro_id"),
            ("COMUNIDADE", ["chat-geral", "apresentacoes", "memes", "procurando-jogadores"], "category_community_id"),
            ("UNIVERSO SOULSLIKE", ["runs-e-desafios", "builds-e-estrategias"], "category_soulslike_id"),
            ("SISTEMAS SOULSBOT", ["coliseu", "ranking", "platinas", "perfis", "santuarios"], "category_systems_id"),
            ("CATÁLOGO E OFERTAS", ["catalogo-de-jogos", "catalogo-de-mods", "noticias-gamer", "jogos-gratis", "promocoes"], "category_catalog_id"),
            ("VOZ", ["Sala Geral", "Sala de Jogos"], "category_voice_id"),
            ("EQUIPE", ["moderacao", "logs", "aprovacoes"], "category_team_id"),
            ("CLÃS", ["recrutamento-de-clas", "ranking-de-clas", "atividades-coletivas"], "category_clans_id"),
        ]

    async def apply_organization(self, guild: discord.Guild, actor_id: int) -> str:
        created_categories, created_channels, errors = [], [], []
        me = guild.me or guild.get_member(self.bot.user.id)
        if not me or not me.guild_permissions.manage_channels:
            return "Aplicação interrompida: o bot não possui **Gerenciar Canais**. Nenhum recurso foi criado."
        admin_role_id = await get_setting(self.bot, guild.id, "admin_role_id", 0)
        mod_role_id = await get_setting(self.bot, guild.id, "moderation_role_id", 0)
        team_overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=False), me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_channels=True)}
        for rid in (admin_role_id, mod_role_id):
            role = guild.get_role(int(rid)) if rid else None
            if role:
                team_overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        key_channel_defaults = {
            "moderacao": "mod_channel_id", "aprovacoes": "mod_channel_id", "videos": "creator_video_channel_id",
            "lives": "creator_live_channel_id", "coliseu": "colizeu_channel_id", "platinas": "platinas_channel_id",
            "perfis": "perfis_channel_id", "runs-e-desafios": "soulslike_channel_id", "jogos-gratis": "games_channel_id",
            "promocoes": "promos_channel_id",
        }
        for category_name, channel_names, category_key in self.organization_plan():
            category = discord.utils.get(guild.categories, name=category_name)
            if not category:
                try:
                    overwrites = team_overwrites if category_key == "category_team_id" else None
                    category = await guild.create_category(category_name, overwrites=overwrites, reason="Quase Pro /adm: estrutura aprovada")
                    created_categories.append(category_name)
                except (discord.Forbidden, discord.HTTPException) as exc:
                    errors.append(f"Categoria {category_name}: {type(exc).__name__}")
                    continue
            await set_setting(self.bot, guild.id, actor_id, category_key, category.id)
            for channel_name in channel_names:
                channel = discord.utils.get(guild.channels, name=channel_name, category=category)
                if channel:
                    continue
                try:
                    if channel_name in ("Sala Geral", "Sala de Jogos"):
                        channel = await category.create_voice_channel(channel_name, reason="Quase Pro /adm: estrutura aprovada")
                    else:
                        channel = await category.create_text_channel(channel_name, reason="Quase Pro /adm: estrutura aprovada")
                    created_channels.append(f"{category_name}/#{channel_name}")
                    key = key_channel_defaults.get(channel_name)
                    if key:
                        old_value = await get_setting(self.bot, guild.id, key, 0)
                        if not old_value:
                            await set_setting(self.bot, guild.id, actor_id, key, channel.id)
                except (discord.Forbidden, discord.HTTPException) as exc:
                    errors.append(f"Canal {category_name}/{channel_name}: {type(exc).__name__}")
        await audit(self.bot, guild.id, actor_id, "organization_applied", "safe-create-only", after=f"categories={len(created_categories)};channels={len(created_channels)};errors={len(errors)}", result="partial" if errors else "success")
        result = f"Plano aplicado. Categorias criadas: {len(created_categories)}; canais criados: {len(created_channels)}. Nenhum canal foi movido, renomeado ou excluído."
        if created_categories:
            result += "\nCategorias: " + ", ".join(created_categories)
        if errors:
            result += "\nFalhas parciais: " + "; ".join(errors[:10])
        return result

    async def diagnostics(self, guild: discord.Guild) -> list[str]:
        lines = []
        me = guild.me or guild.get_member(self.bot.user.id)
        if not me:
            lines.append("🔴 Bot não encontrado como membro deste servidor.")
        else:
            missing = []
            if not me.guild_permissions.view_channel: missing.append("Ver canais")
            if not me.guild_permissions.send_messages: missing.append("Enviar mensagens")
            if not me.guild_permissions.manage_channels: missing.append("Gerenciar canais (necessário para estrutura/clãs)")
            lines.append("🟢 Permissões gerais do bot: conferidas." if not missing else "🟠 Permissões a revisar: " + ", ".join(missing))
        for key, (label, default, _) in CHANNELS.items():
            value = await get_setting(self.bot, guild.id, key, 0)
            channel = guild.get_channel(int(value)) if value else None
            if not value:
                lines.append(f"🟠 {label}: não configurado.")
            elif channel is None:
                lines.append(f"🔴 {label}: ID persistido `{value}` não existe neste servidor.")
            else:
                perms = channel.permissions_for(me) if me else None
                if perms and not (perms.view_channel and perms.send_messages):
                    lines.append(f"🟠 {label}: {channel.mention}, mas faltam Ver canal/Enviar mensagens.")
                else:
                    lines.append(f"🟢 {label}: {channel.mention}.")
        for key, (label, default) in ROLES.items():
            value = await get_setting(self.bot, guild.id, key, 0)
            role = guild.get_role(int(value)) if value else None
            if value and role is None:
                lines.append(f"🔴 {label}: cargo `{value}` não existe.")
        degraded = await self.bot.db._all("SELECT id,name,category_id,chat_channel_id,announcements_id,strategies_id,voice_channel_id FROM clans WHERE guild_id=? AND status IN ('degraded','active')", (guild.id,))
        for clan in degraded:
            missing_fields = [key for key in ("category_id", "chat_channel_id", "announcements_id", "strategies_id", "voice_channel_id") if not clan[key] or not guild.get_channel(int(clan[key]))]
            if missing_fields:
                lines.append(f"🔴 Clã [{clan['id']}] {clan['name']}: recurso ausente/inválido — {', '.join(missing_fields)}.")
        if not lines:
            lines.append("🟢 Nenhum problema detectado.")
        return lines

    async def clan_integrity(self, guild: discord.Guild) -> list[str]:
        return await self.diagnostics(guild)

    async def create_backup(self) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        fd, target_path = tempfile.mkstemp(prefix=f"quasepro-backup-{stamp}-", suffix=".zip")
        os.close(fd)
        db_paths = [
            ("soulsbot.db", self.bot.db.path),
            ("jogos.db", getattr(self.bot, "catalog_db_path", "")),
            ("sent_offers.sqlite3", str(getattr(config, "SENT_DB_PATH", ""))),
        ]
        with zipfile.ZipFile(target_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for archive_name, source_path in db_paths:
                if not source_path or not os.path.exists(source_path):
                    continue
                fd, snapshot = tempfile.mkstemp(prefix="quasepro-snapshot-", suffix=".db")
                os.close(fd)
                try:
                    src = sqlite3.connect(source_path, timeout=10)
                    dst = sqlite3.connect(snapshot)
                    try:
                        src.backup(dst)
                    finally:
                        dst.close()
                        src.close()
                    archive.write(snapshot, archive_name)
                finally:
                    try: os.remove(snapshot)
                    except OSError: pass
        return target_path

    @app_commands.command(name="adm", description="Abre o painel administrativo central do Quase Pro")
    @app_commands.guild_only()
    async def adm(self, interaction: discord.Interaction):
        if not await is_admin(self.bot, interaction):
            return await interaction.response.send_message("Acesso negado. É necessária a permissão Gerenciar Servidor/Administrador ou um cargo autorizado pelo painel.", ephemeral=True)
        embed = await self.overview_embed(interaction.guild)
        await interaction.response.send_message(embed=embed, view=AdminHomeView(self, interaction.guild.id), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Admin(bot))
