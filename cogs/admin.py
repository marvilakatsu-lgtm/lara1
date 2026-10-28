"""Painel /adm: configuração por servidor, auditoria, diagnóstico e organização segura."""
from __future__ import annotations

import logging
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

log = logging.getLogger("quasepro.admin")

from server_structure import (
    CATEGORY_KEYS,
    CHANNEL_SETTINGS_LABELS,
    ORGANIZATION,
    ROLE_DEFINITIONS,
    ROLE_GROUP_ORDER,
    ROLE_SETTING_KEYS,
    normalize_name,
    validate_role_palette,
)

CHANNELS = CHANNEL_SETTINGS_LABELS
ROLES = {
    "founder_role_id": ("Cargo Fundador", 0),
    "admin_role_id": ("Cargo administrativo autorizado", 0),
    "moderation_role_id": ("Cargo de moderação", getattr(config, "MOD_ROLE_ID", 0)),
    "support_role_id": ("Cargo de suporte", 0),
    "developer_role_id": ("Cargo de desenvolvedor", 0),
    "member_role_id": ("Cargo padrão de membro", 0),
    "video_notice_role_id": ("Cargo que recebe avisos de vídeos", 0),
    "live_notice_role_id": ("Cargo que recebe avisos de lives", 0),
}
CATEGORIES = CATEGORY_KEYS
SECTIONS = [
    ("overview", "Visão geral", "Visão geral do bot e do servidor"),
    ("channels", "Canais", "Escolher canais de cada sistema"),
    ("categories", "Categorias", "Associar categorias e organizar a estrutura"),
    ("roles", "Cargos", "Configurar cargos administrativos e funcionais"),
    ("organization", "Organização do servidor", "Pré-visualizar e aplicar a estrutura Quase Pro e os cargos"),
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
    @discord.ui.button(label="Aplicar estrutura e cargos", style=discord.ButtonStyle.success, emoji="🧰", row=0)
    async def apply_plan(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content=(
            "A aplicação vai criar/renomear categorias e canais para a estrutura Quase Pro, mover canais existentes preservando o histórico, "
            "criar/ajustar os 34 cargos com cores distintas e vincular patentes aos níveis já existentes. Nenhum canal, mensagem ou dado será excluído. "
            "As permissões da categoria privada da equipe serão normalizadas. Confirma?"), embed=None,
            view=ConfirmOrganizationView(self.cog, self.guild_id))


class ConfirmOrganizationView(AdminBaseView):
    @discord.ui.button(label="Confirmar aplicação", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            results = await self.cog.apply_organization(interaction.guild, interaction.user.id)
        except Exception:
            log.exception(
                "Falha inesperada ao aplicar organização no servidor %s (usuário %s).",
                self.guild_id,
                interaction.user.id,
            )
            results = (
                "Ocorreu uma falha inesperada durante a aplicação. A operação pode ter sido parcial; "
                "nenhum recurso existente foi excluído. Consulte os logs da aplicação antes de tentar novamente."
            )
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
            embed = discord.Embed(
                title="Organização Quase Pro · Pré-visualização",
                description=(
                    "Estrutura definida conforme o plano do servidor: 10 categorias e 62 canais. "
                    "A aplicação reaproveita canais equivalentes e preserva mensagens, renomeando/movendo quando necessário. "
                    "Não exclui canais, mensagens, cargos nem dados."
                ),
                color=0xD4AF37,
            )
            for cat, _key, _aliases, channels in self.organization_plan():
                channel_names = [entry[0] for entry in channels]
                value = "\n".join(f"• {name}" for name in channel_names)
                embed.add_field(name=cat, value=value[:1024] or "Sem canais", inline=True)
            embed.add_field(
                name="Cargos e progressão",
                value=(f"{len(ROLE_DEFINITIONS)} cargos padronizados com cores únicas. "
                       "As 10 patentes preservam os requisitos atuais do Soulsbot: níveis "
                       + ", ".join(str(minimo) for minimo, _nome in __import__('levels').PATENTES)
                       + ". Nenhum XP, nível ou recompensa será recalculado."),
                inline=False,
            )
            embed.add_field(
                name="Permissões",
                value="Portões, comunidade, Soulslike, catálogo e canais públicos ficam acessíveis conforme permissões gerais. "
                      "BASTIDORES DA ORDEM permanece privado; suporte e desenvolvedor recebem apenas acessos próprios quando necessário.",
                inline=False,
            )
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
            embed.add_field(name="Operação", value="`/catalogo` publica/atualiza o painel no canal configurado em `/adm` → Canais. A aplicação da estrutura publica automaticamente os painéis de jogos e mods e evita duplicatas.", inline=False)
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
        """Plano oficial; nomes, aliases, tipos e destinos vêm de server_structure.py."""
        return ORGANIZATION

    @staticmethod
    def _role_permissions(profile: str) -> discord.Permissions:
        permissions = discord.Permissions.none()
        profiles = {
            "founder": {"administrator": True},
            "administrator": {
                "manage_guild": True, "manage_channels": True, "manage_roles": True,
                "manage_messages": True, "view_audit_log": True, "manage_events": True,
                "manage_webhooks": True, "kick_members": True, "ban_members": True,
                "moderate_members": True, "manage_threads": True,
            },
            "moderator": {
                "manage_messages": True, "moderate_members": True, "kick_members": True,
                "view_audit_log": True, "manage_threads": True,
            },
        }
        for name, enabled in profiles.get(profile, {}).items():
            setattr(permissions, name, enabled)
        return permissions

    async def _ensure_organization_roles(self, guild: discord.Guild, actor_id: int):
        me = guild.me or guild.get_member(self.bot.user.id if self.bot.user else 0)
        if not me or not me.guild_permissions.manage_roles:
            return {}, 0, 0, ["O bot não possui **Gerenciar Cargos**; nenhum cargo foi criado ou ajustado."]
        if not validate_role_palette():
            return {}, 0, 0, ["A paleta de cores do projeto contém duplicatas; criação de cargos interrompida."]

        role_objects = {}
        created = updated = 0
        errors = []
        for definition in ROLE_DEFINITIONS:
            target_name = definition["name"]
            aliases = {normalize_name(target_name)} | {normalize_name(x) for x in definition.get("aliases", ())}
            role = next((r for r in guild.roles if normalize_name(r.name) in aliases), None)
            permissions = self._role_permissions(definition.get("permissions", "none"))
            color = discord.Colour(int(definition["color"]))
            hoist = definition.get("group") in {"staff", "rank"}
            if role is None:
                try:
                    role = await guild.create_role(
                        name=target_name, colour=color, permissions=permissions,
                        hoist=hoist, mentionable=False,
                        reason="Quase Pro /adm: identidade visual e cargos oficiais",
                    )
                    created += 1
                except (discord.Forbidden, discord.HTTPException) as exc:
                    errors.append(f"Cargo {target_name}: {type(exc).__name__}")
                    continue
            else:
                if role.managed:
                    errors.append(f"Cargo {target_name}: cargo gerenciado pelo Discord, não editável pelo bot.")
                    role_objects[definition["key"]] = role
                    continue
                if role >= me.top_role:
                    errors.append(f"Cargo {target_name}: está acima/na hierarquia do bot; mova o cargo do bot para cima.")
                    role_objects[definition["key"]] = role
                    continue
                needs_update = (
                    role.name != target_name or role.colour.value != color.value
                    or role.permissions != permissions or role.hoist != hoist or role.mentionable
                )
                if needs_update:
                    try:
                        await role.edit(
                            name=target_name, colour=color, permissions=permissions,
                            hoist=hoist, mentionable=False,
                            reason="Quase Pro /adm: padronização de cargo e cor",
                        )
                        updated += 1
                    except (discord.Forbidden, discord.HTTPException) as exc:
                        errors.append(f"Cargo {target_name}: {type(exc).__name__}")
                        role_objects[definition["key"]] = role
                        continue

            role_objects[definition["key"]] = role
            # Persistência técnica de todos os IDs de cargo, isolada por servidor.
            generic_key = f"role_{definition['key']}_id"
            current_generic = await get_setting(self.bot, guild.id, generic_key, 0)
            if int(current_generic or 0) != role.id:
                await set_setting(self.bot, guild.id, actor_id, generic_key, role.id)
            # Preserva apenas os cargos admin/moderação que já estejam válidos: trocá-los
            # silenciosamente poderia bloquear a equipe atual. Os demais vínculos passam
            # para os cargos oficiais recém-padronizados.
            mapped_key = ROLE_SETTING_KEYS.get(definition["key"])
            if mapped_key:
                current_id = await get_setting(self.bot, guild.id, mapped_key, 0)
                current_role = guild.get_role(int(current_id)) if current_id else None
                preserve_existing = mapped_key in {"admin_role_id", "moderation_role_id"} and current_role is not None
                if not preserve_existing and int(current_id or 0) != role.id:
                    await set_setting(self.bot, guild.id, actor_id, mapped_key, role.id)

        # Ordena os cargos administrados para que patentes fiquem acima dos cargos
        # opcionais de interesse, preservando a capacidade de moderação. Nunca tenta
        # mover cargos gerenciados ou que estejam acima do cargo mais alto do bot.
        try:
            ordered_roles = []

            def add_position_role(role):
                if role and not role.managed and role < me.top_role and role not in ordered_roles:
                    ordered_roles.append(role)

            # Primeiro os cargos oficiais de maior autoridade; depois, cargos
            # administrativos legados ainda associados; em seguida a moderação,
            # o restante da equipe e por fim as patentes e cargos sem privilégios.
            for key in ("founder", "administrator"):
                add_position_role(role_objects.get(key))
            admin_id = await get_setting(self.bot, guild.id, "admin_role_id", 0)
            add_position_role(guild.get_role(int(admin_id)) if admin_id else None)
            add_position_role(role_objects.get("moderator"))
            moderation_id = await get_setting(self.bot, guild.id, "moderation_role_id", 0)
            add_position_role(guild.get_role(int(moderation_id)) if moderation_id else None)
            for key in ("support", "developer"):
                add_position_role(role_objects.get(key))
            for group in ROLE_GROUP_ORDER:
                if group == "staff":
                    continue
                for definition in ROLE_DEFINITIONS:
                    if definition["group"] == group:
                        add_position_role(role_objects.get(definition["key"]))
            top_position = int(me.top_role.position)
            if ordered_roles and top_position > len(ordered_roles):
                positions = {role: top_position - index - 1 for index, role in enumerate(ordered_roles)}
                await guild.edit_role_positions(
                    positions=positions,
                    reason="Quase Pro /adm: hierarquia oficial de cargos",
                )
            elif ordered_roles:
                errors.append("Hierarquia visual não reorganizada: mova o cargo mais alto do bot acima dos 34 cargos oficiais e tente novamente.")
        except (discord.Forbidden, discord.HTTPException) as exc:
            errors.append(f"Não foi possível ordenar a hierarquia de cargos: {type(exc).__name__}.")
        return role_objects, created, updated, errors

    def _find_existing_channel(self, guild, category, target_name, kind, aliases, used_ids):
        wanted = {normalize_name(target_name)} | {normalize_name(alias) for alias in aliases}
        candidates = []
        for channel in guild.channels:
            if channel.id in used_ids:
                continue
            if kind == "voice":
                if not isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
                    continue
            elif not isinstance(channel, discord.TextChannel):
                continue
            normalized = normalize_name(channel.name)
            if normalized not in wanted:
                continue
            exact = channel.name == target_name
            same_category = getattr(channel, "category_id", None) == category.id
            score = (0 if exact and same_category else 1 if exact else 2 if same_category else 3)
            candidates.append((score, channel.id, channel))
        candidates.sort(key=lambda item: (item[0], item[1]))
        return candidates[0][2] if candidates else None

    async def apply_organization(self, guild: discord.Guild, actor_id: int) -> str:
        created_categories, renamed_categories, created_channels, changed_channels = [], [], [], []
        errors = []
        me = guild.me or guild.get_member(self.bot.user.id if self.bot.user else 0)
        if not me or not me.guild_permissions.manage_channels:
            return "Aplicação interrompida: o bot não possui **Gerenciar Canais**. Nenhum recurso foi criado."
        if not me.guild_permissions.manage_roles:
            return "Aplicação interrompida: o bot precisa de **Gerenciar Cargos** para aplicar a estrutura e as patentes. Nenhum recurso foi criado."

        roles, roles_created, roles_updated, role_errors = await self._ensure_organization_roles(guild, actor_id)
        errors.extend(role_errors)
        if any("nenhum cargo foi criado" in message for message in role_errors):
            return "\n".join(role_errors)

        admin_role_id = await get_setting(self.bot, guild.id, "admin_role_id", 0)
        mod_role_id = await get_setting(self.bot, guild.id, "moderation_role_id", 0)
        team_overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_channels=True),
        }
        core_role_ids = {
            int(admin_role_id or 0), int(mod_role_id or 0),
            roles.get("founder").id if roles.get("founder") else 0,
            roles.get("administrator").id if roles.get("administrator") else 0,
            roles.get("moderator").id if roles.get("moderator") else 0,
        }
        for rid in core_role_ids:
            role = guild.get_role(rid) if rid else None
            if role:
                team_overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, read_message_history=True,
                )

        used_channel_ids = set()
        for position, (category_name, category_key, aliases, channel_defs) in enumerate(self.organization_plan()):
            category = discord.utils.get(guild.categories, name=category_name)
            if category is None:
                alias_names = {normalize_name(x) for x in aliases}
                category = next((cat for cat in guild.categories if normalize_name(cat.name) in alias_names), None)
            is_private = category_key == "category_team_id"
            category_overwrites = dict(team_overwrites) if is_private else {
                guild.default_role: discord.PermissionOverwrite(view_channel=True)
            }
            if category is None:
                try:
                    category = await guild.create_category(
                        category_name, overwrites=category_overwrites, position=position,
                        reason="Quase Pro /adm: estrutura aprovada",
                    )
                    created_categories.append(category_name)
                except (discord.Forbidden, discord.HTTPException) as exc:
                    errors.append(f"Categoria {category_name}: {type(exc).__name__}")
                    continue
            else:
                old_category_name = category.name
                was_renamed = old_category_name != category_name
                try:
                    await category.edit(
                        name=category_name,
                        overwrites=category_overwrites,
                        position=position,
                        reason="Quase Pro /adm: reorganização preservando canais e mensagens",
                    )
                    if was_renamed:
                        renamed_categories.append(f"{old_category_name} → {category_name}")
                except (discord.Forbidden, discord.HTTPException) as exc:
                    errors.append(f"Categoria {category_name}: {type(exc).__name__}")
                    # Não cria uma segunda categoria se a existente não puder ser ajustada.
                    continue
            current_category_id = await get_setting(self.bot, guild.id, category_key, 0)
            if int(current_category_id or 0) != category.id:
                await set_setting(self.bot, guild.id, actor_id, category_key, category.id)

            for channel_name, kind, setting_key, channel_aliases, special_access in channel_defs:
                special_overwrites = None
                if is_private and special_access in {"support", "developer"}:
                    special_overwrites = dict(team_overwrites)
                    role = roles.get(special_access)
                    if role:
                        special_overwrites[role] = discord.PermissionOverwrite(
                            view_channel=True, send_messages=True, read_message_history=True,
                            attach_files=True, embed_links=True,
                        )
                else:
                    special_overwrites = dict(category_overwrites)

                channel = self._find_existing_channel(
                    guild, category, channel_name, kind, channel_aliases, used_channel_ids,
                )
                if channel is None:
                    try:
                        if kind == "voice":
                            channel = await category.create_voice_channel(
                                channel_name, overwrites=special_overwrites,
                                reason="Quase Pro /adm: estrutura aprovada",
                            )
                        else:
                            channel = await category.create_text_channel(
                                channel_name, overwrites=special_overwrites,
                                reason="Quase Pro /adm: estrutura aprovada",
                            )
                        created_channels.append(f"{category_name} / {channel_name}")
                    except (discord.Forbidden, discord.HTTPException) as exc:
                        errors.append(f"Canal {category_name}/{channel_name}: {type(exc).__name__}")
                        continue
                else:
                    used_channel_ids.add(channel.id)
                    needs_change = channel.name != channel_name or getattr(channel, "category_id", None) != category.id
                    try:
                        if special_overwrites is not None and is_private and special_access in {"support", "developer"}:
                            if needs_change or channel.overwrites != special_overwrites:
                                old_channel_name = channel.name
                                await channel.edit(
                                    name=channel_name, category=category, overwrites=special_overwrites,
                                    reason="Quase Pro /adm: migração de canal privado preservando mensagens",
                                )
                                changed_channels.append(f"{old_channel_name} → {channel_name}")
                        elif needs_change or not getattr(channel, "permissions_synced", False):
                            old_name = channel.name
                            await channel.edit(
                                name=channel_name, category=category, sync_permissions=True,
                                reason="Quase Pro /adm: reorganização preservando mensagens",
                            )
                            changed_channels.append(f"{old_name} → {channel_name}")
                    except (discord.Forbidden, discord.HTTPException) as exc:
                        errors.append(f"Canal {category_name}/{channel_name}: {type(exc).__name__}")
                        continue
                used_channel_ids.add(channel.id)
                if setting_key:
                    current = await get_setting(self.bot, guild.id, setting_key, 0)
                    if int(current or 0) != channel.id:
                        await set_setting(self.bot, guild.id, actor_id, setting_key, channel.id)

        # Confere e reconcilia patentes dos membros com XP existente. Os limiares vêm de levels.PATENTES.
        rank_updates = 0
        try:
            from levels import nivel_por_xp
            from cogs.platinas import sincronizar_patente
            xp_rows = await self.bot.db._all("SELECT user_id,xp FROM users")
            for row in xp_rows:
                member = guild.get_member(int(row["user_id"]))
                if member is None or member.bot:
                    continue
                level = nivel_por_xp(int(row["xp"]))
                expected = next((name for minimum, name in reversed(__import__('levels').PATENTES) if level >= minimum), None)
                if expected is None:
                    continue
                current_rank_roles = [r for r in member.roles if __import__('levels').eh_cargo_patente(r.name)]
                expected_names = {expected, __import__('levels').nome_patente_exibicao(expected)}
                if len(current_rank_roles) != 1 or current_rank_roles[0].name not in expected_names:
                    try:
                        await sincronizar_patente(guild, member, level)
                        rank_updates += 1
                    except Exception as exc:
                        errors.append(f"Sincronização de patente de {member.id}: {type(exc).__name__}")
        except Exception:
            log.exception("Falha ao reconciliar patentes após aplicar a estrutura do servidor %s", guild.id)
            errors.append("Falha ao reconciliar uma parte das patentes com o XP existente; consulte os logs.")

        # Publica/atualiza os dois painéis persistentes nas posições definidas pelo plano.
        panels_published = []
        panel_specs = (
            ("📜・boas-vindas", "Cargos", "publish_welcome_panel", "painel de boas-vindas"),
            ("🎭・escolha-seus-cargos", "Cargos", "publish_organization_panel", "painel de escolha de cargos"),
            ("⚔️・painel-de-clãs", "Clans", "publish_organization_panel", "painel Salão dos Juramentos"),
        )
        for channel_name, cog_name, method_name, description in panel_specs:
            channel = next((c for c in guild.text_channels if c.name == channel_name), None)
            cog = self.bot.get_cog(cog_name)
            method = getattr(cog, method_name, None) if cog is not None else None
            if channel is None:
                errors.append(f"Não foi possível publicar {description}: canal de destino ausente.")
                continue
            if method is None:
                errors.append(f"Não foi possível publicar {description}: módulo {cog_name} indisponível.")
                continue
            try:
                _message, created = await method(guild, channel)
                panels_published.append(f"{description} {'criado' if created else 'atualizado'}")
            except (discord.Forbidden, discord.HTTPException, ValueError) as exc:
                errors.append(f"Falha ao publicar {description}: {type(exc).__name__}")
            except Exception as exc:
                log.exception("Falha publicando %s no servidor %s", description, guild.id)
                errors.append(f"Falha ao publicar {description}: {type(exc).__name__}")

        try:
            from cogs.catalogo import publish_organization_panels
            published = await publish_organization_panels(guild)
            panels_published.extend(published)
        except (discord.Forbidden, discord.HTTPException, ValueError) as exc:
            errors.append(f"Painéis do catálogo: {type(exc).__name__} — {exc}")
        except Exception as exc:
            log.exception("Falha publicando painéis do catálogo no servidor %s", guild.id)
            errors.append(f"Painéis do catálogo: {type(exc).__name__}")

        await audit(
            self.bot, guild.id, actor_id, "organization_applied", "quasepro-v2",
            after=(f"categories_created={len(created_categories)};categories_renamed={len(renamed_categories)};"
                   f"channels_created={len(created_channels)};channels_changed={len(changed_channels)};"
                   f"roles_created={roles_created};roles_updated={roles_updated};rank_sync={rank_updates};"
                   f"panels={len(panels_published)};errors={len(errors)}"),
            result="partial" if errors else "success",
        )
        parts = [
            "**Estrutura Quase Pro processada.**",
            f"Categorias criadas: **{len(created_categories)}** · renomeadas: **{len(renamed_categories)}**.",
            f"Canais criados: **{len(created_channels)}** · renomeados/movidos: **{len(changed_channels)}**.",
            f"Cargos criados: **{roles_created}** · ajustados: **{roles_updated}** · cores únicas definidas: **{len(ROLE_DEFINITIONS)}**.",
            ("Painéis: " + "; ".join(panels_published) + ".") if panels_published else "Painéis persistentes: nenhum foi publicado.",
            f"Membros com patente sincronizada a partir do XP existente: **{rank_updates}**.",
            "Nenhum canal, mensagem ou banco de dados foi excluído.",
        ]
        if created_categories:
            parts.append("Categorias criadas: " + ", ".join(created_categories[:10]))
        if renamed_categories:
            parts.append("Categorias renomeadas: " + "; ".join(renamed_categories[:10]))
        if errors:
            parts.append("**Avisos/falhas parciais:**\n" + "\n".join(f"• {line}" for line in errors[:12]))
            parts.append("Verifique **/adm → Diagnóstico** e a hierarquia do cargo do bot antes de repetir a aplicação.")
        return "\n".join(parts)

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
