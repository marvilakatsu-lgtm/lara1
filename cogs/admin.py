"""Painel /adm: configuração por servidor, auditoria, diagnóstico e organização segura."""
from __future__ import annotations

import hashlib
import json
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
    LEGACY_CATEGORY_NAMES,
    ORGANIZATION,
    ROLE_DEFINITIONS,
    ROLE_SETTING_KEYS,
    STAFF_ROLE_ORDER,
    category_access_mode,
    count_channels,
    managed_role_hierarchy_keys,
    legacy_channel_names,
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
            "A aplicação vai criar/renomear categorias e canais para a estrutura comunitária simplificada, combinar destinos de feeds relacionados e preservar os IDs operacionais. "
            f"Vai criar/ajustar {len(ROLE_DEFINITIONS)} cargos com cores distintas e manter a progressão de XP existente. "
            "Canais redundantes e categorias antigas serão movidos/ocultados em 🗄️・ARQUIVO ANTIGO privado para preservar mensagens; nada será excluído nesta etapa. "
            "As permissões da equipe e o bloqueio de acesso até a verificação serão normalizados. "
            "Importante: o Discord exige que os cargos da equipe fiquem manualmente acima do cargo real do bot; o bot organizará os cargos funcionais abaixo dele. Confirma?"), embed=None,
            view=ConfirmOrganizationView(self.cog, self.guild_id))

    @discord.ui.button(label="Prévia de limpeza total", style=discord.ButtonStyle.danger, emoji="🧹", row=1)
    async def preview_cleanup(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Exclusão em massa afeta o histórico e os cargos de todos os membros; somente o dono
        # do servidor pode iniciar esse fluxo irreversível.
        if interaction.guild is None or interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message(
                "Por segurança, somente o dono do servidor pode iniciar a limpeza destrutiva.", ephemeral=True,
            )
        plan = await self.cog.build_cleanup_plan(interaction.guild)
        embed = self.cog.cleanup_preview_embed(interaction.guild, plan)
        view = None
        if not plan["blockers"]:
            view = CleanupPreviewView(self.cog, self.guild_id, plan["signature"], bool(
                plan["channels"] or plan["categories"] or plan["roles"]
            ))
        else:
            # Mantém o caminho de volta à aplicação normal se o plano ainda não estiver pronto.
            view = OrganizationPreviewView(self.cog, self.guild_id)
        await interaction.response.edit_message(content=None, embed=embed, view=view)


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


class CleanupPreviewView(AdminBaseView):
    """Second-stage cleanup: generate a backup before offering the irreversible action."""
    def __init__(self, cog, guild_id, plan_signature: str, has_candidates: bool = True):
        super().__init__(cog, guild_id, timeout=300)
        self.plan_signature = plan_signature
        self.has_candidates = bool(has_candidates)
        self.prepare_backup.disabled = not self.has_candidates

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.guild_id != self.guild_id or interaction.guild is None or interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                "Somente o dono do servidor pode preparar uma limpeza destrutiva.", ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="Gerar backup e preparar exclusão", style=discord.ButtonStyle.danger, emoji="💾", row=0)
    async def prepare_backup(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        backup_path = None
        try:
            current_plan = await self.cog.build_cleanup_plan(interaction.guild)
            if current_plan["blockers"]:
                return await interaction.followup.send(
                    "A limpeza foi bloqueada porque a estrutura não está pronta ou ainda há referências ativas.\n" +
                    "\n".join(f"• {item}" for item in current_plan["blockers"][:10]), ephemeral=True,
                )
            if current_plan["signature"] != self.plan_signature:
                return await interaction.followup.send(
                    "O servidor mudou desde a prévia. Nenhum item foi excluído. Gere uma nova prévia e revise a lista atualizada.",
                    ephemeral=True,
                )
            backup_path = await self.cog.create_cleanup_backup(interaction.guild, current_plan)
            await interaction.followup.send(
                "**Backup preparado.** Baixe e guarde o arquivo anexado antes de continuar. "
                "Ele contém os bancos de dados e um inventário dos canais/cargos, mas não contém o histórico das mensagens do Discord. "
                "A exclusão só ocorrerá após clicar em Confirmar e digitar exatamente `APAGAR RESTO`.",
                file=discord.File(backup_path, filename=os.path.basename(backup_path)),
                view=CleanupFinalConfirmationView(self.cog, self.guild_id, self.plan_signature, interaction.user.id),
                ephemeral=True,
            )
        except Exception as exc:
            log.exception("Falha preparando backup de limpeza destrutiva no servidor %s", self.guild_id)
            try:
                await interaction.followup.send(
                    f"Não foi possível preparar/entregar o backup ({type(exc).__name__}). Nenhum canal, categoria ou cargo foi excluído.",
                    ephemeral=True,
                )
            except discord.HTTPException:
                pass
        finally:
            if backup_path:
                try:
                    os.remove(backup_path)
                except OSError:
                    pass

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary, row=0)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Limpeza cancelada. Nada foi excluído.", embed=None, view=None)


class CleanupFinalConfirmationView(AdminBaseView):
    def __init__(self, cog, guild_id: int, plan_signature: str, owner_id: int):
        super().__init__(cog, guild_id, timeout=300)
        self.plan_signature = plan_signature
        self.owner_id = int(owner_id)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if (interaction.guild_id != self.guild_id or interaction.guild is None
                or interaction.user.id != interaction.guild.owner_id or interaction.user.id != self.owner_id):
            await interaction.response.send_message(
                "Somente o dono que preparou esta operação pode confirmá-la.", ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="Confirmar apagamento", style=discord.ButtonStyle.danger, emoji="🗑️", row=0)
    async def confirm_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CleanupConfirmationModal(
            self.cog, self.guild_id, self.plan_signature, self.owner_id,
        ))

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary, row=0)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Limpeza cancelada. Nenhum item foi excluído.", view=None)


class CleanupConfirmationModal(discord.ui.Modal, title="Confirmação de exclusão definitiva"):
    confirmation = discord.ui.TextInput(
        label="Digite APAGAR RESTO para confirmar",
        placeholder="APAGAR RESTO",
        min_length=12,
        max_length=20,
        required=True,
    )

    def __init__(self, cog, guild_id: int, plan_signature: str, owner_id: int):
        super().__init__(timeout=180)
        self.cog = cog
        self.guild_id = int(guild_id)
        self.plan_signature = plan_signature
        self.owner_id = int(owner_id)

    async def on_submit(self, interaction: discord.Interaction):
        if (interaction.guild is None or interaction.guild_id != self.guild_id
                or interaction.user.id != interaction.guild.owner_id or interaction.user.id != self.owner_id):
            return await interaction.response.send_message(
                "Confirmação recusada: somente o dono original deste servidor pode executar a limpeza.", ephemeral=True,
            )
        if str(self.confirmation.value).strip().upper() != "APAGAR RESTO":
            return await interaction.response.send_message(
                "Texto incorreto. Nada foi excluído. Volte à prévia e recomece a confirmação.", ephemeral=True,
            )
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            current_plan = await self.cog.build_cleanup_plan(interaction.guild)
            if current_plan["blockers"]:
                return await interaction.followup.send(
                    "A limpeza foi interrompida porque há impedimentos novos. Nada foi excluído.\n" +
                    "\n".join(f"• {item}" for item in current_plan["blockers"][:10]), ephemeral=True,
                )
            if current_plan["signature"] != self.plan_signature:
                return await interaction.followup.send(
                    "A lista de recursos mudou desde a prévia. Nada foi excluído. Gere outra prévia e um novo backup.",
                    ephemeral=True,
                )
            result = await self.cog.execute_cleanup_plan(interaction.guild, interaction.user.id, current_plan)
            await interaction.followup.send(result[:1900], ephemeral=True)
        except Exception as exc:
            log.exception("Falha executando limpeza destrutiva no servidor %s", self.guild_id)
            await interaction.followup.send(
                f"A limpeza encontrou uma falha ({type(exc).__name__}). A operação pode ter sido parcial; consulte a auditoria e os logs.",
                ephemeral=True,
            )


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
            embed = discord.Embed(title="Configuração de cargos", description=(
                "Os cargos são resolvidos pelos seletores nativos. A organização aplica perfis predefinidos aos cargos que consegue gerir; "
                "a atribuição dos cargos de equipe aos membros continua manual. O cargo Fundador tem Administrador e deve ser atribuído com cautela."
            ), color=0xC0C0C0)
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
                    f"Estrutura comunitária simplificada: {len(ORGANIZATION)} categorias e {count_channels()} canais. "
                    "A aplicação normal reaproveita canais equivalentes e preserva mensagens. Canais redundantes são movidos para 🗄️・ARQUIVO ANTIGO, visível apenas à equipe; para excluir excedentes existe uma etapa destrutiva separada, exclusiva do dono."
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
                       "A hierarquia das patentes vai da maior para a menor; os requisitos originais de XP do Soulsbot são preservados: níveis "
                       + ", ".join(str(minimo) for minimo, _nome in __import__('levels').PATENTES)
                       + ". Nenhum XP, nível ou recompensa será recalculado."),
                inline=False,
            )
            embed.add_field(
                name="Permissões",
                value="Portões, comunidade, Soulslike e catálogo seguem a política de verificação. BASTIDORES DA ORDEM permanece privado. "
                      "Para hierarquia segura, mantenha Fundador > Administrador > Moderador > Suporte > Desenvolvedor acima do cargo real do bot; patentes, clãs, comunidade e cargos de interesse ficam abaixo do bot.",
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
        """Create/update role metadata and order only roles below the bot.

        Discord explicitly prevents bots from editing or positioning roles at or above
        their highest role. Staff roles therefore require a one-time manual move above
        the bot role; all XP, clan, community and interest roles are ordered below it.
        """
        me = guild.me or guild.get_member(self.bot.user.id if self.bot.user else 0)
        if not me or not me.guild_permissions.manage_roles:
            return {}, 0, 0, ["O bot não possui **Gerenciar Cargos**; nenhum cargo foi criado ou ajustado."]
        if not validate_role_palette():
            return {}, 0, 0, ["A paleta de cores do projeto contém duplicatas; criação de cargos interrompida."]

        role_objects = {}
        created = updated = 0
        errors = []

        async def persist_role_links(definition, role):
            generic_key = f"role_{definition['key']}_id"
            current_generic = await get_setting(self.bot, guild.id, generic_key, 0)
            if int(current_generic or 0) != role.id:
                await set_setting(self.bot, guild.id, actor_id, generic_key, role.id)
            mapped_key = ROLE_SETTING_KEYS.get(definition["key"])
            if mapped_key:
                current_id = await get_setting(self.bot, guild.id, mapped_key, 0)
                if int(current_id or 0) != role.id:
                    await set_setting(self.bot, guild.id, actor_id, mapped_key, role.id)

        for definition in ROLE_DEFINITIONS:
            target_name = definition["name"]
            aliases = {normalize_name(target_name)} | {normalize_name(x) for x in definition.get("aliases", ())}
            mapped_key = ROLE_SETTING_KEYS.get(definition["key"])
            role = None
            created_this_run = False

            # For administrative roles, preserve the role already configured as the
            # source of truth before looking for a duplicate by display name.
            if mapped_key:
                configured_id = await get_setting(self.bot, guild.id, mapped_key, 0)
                configured_role = guild.get_role(int(configured_id)) if configured_id else None
                if configured_role and not configured_role.is_default():
                    role = configured_role
            if role is None:
                generic_id = await get_setting(self.bot, guild.id, f"role_{definition['key']}_id", 0)
                generic_role = guild.get_role(int(generic_id)) if generic_id else None
                if generic_role and not generic_role.is_default():
                    role = generic_role
            if role is None:
                role = next((r for r in guild.roles if not r.is_default() and normalize_name(r.name) in aliases), None)

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
                    created_this_run = True
                except (discord.Forbidden, discord.HTTPException) as exc:
                    errors.append(f"Cargo {target_name}: {type(exc).__name__}")
                    continue
            else:
                if role.managed:
                    # Bot/integration roles are owned by Discord. Never try to rename,
                    # recolor or reposition them; the integrated bot's own role remains
                    # the actual hierarchy boundary, not a decorative label at the bottom.
                    role_objects[definition["key"]] = role
                    await persist_role_links(definition, role)
                    if definition.get("group") != "technical":
                        errors.append(f"Cargo {target_name}: cargo gerenciado por integração; não pode ser editado pelo bot.")
                    continue

                effective_permissions = permissions
                if definition.get("group") == "staff" and not created_this_run and role.permissions != permissions:
                    # An existing staff role may already be assigned. Do not silently
                    # elevate/downgrade any existing role while the hierarchy is being repaired;
                    # preserve its current permission bitset and flag a manual review.
                    effective_permissions = role.permissions
                    errors.append(
                        f"Cargo de equipe preexistente {target_name}: as permissões atuais foram preservadas para evitar mudanças silenciosas. "
                        "Revise-as manualmente depois de corrigir a hierarquia."
                    )
                needs_update = (
                    role.name != target_name or role.colour.value != color.value
                    or role.permissions != effective_permissions or role.hoist != hoist or role.mentionable
                )
                if role >= me.top_role:
                    # This is a valid position for staff roles, but Discord does not let
                    # the bot edit roles above itself. For lower-tier roles, this is a
                    # hierarchy error and must be corrected manually before assignment.
                    role_objects[definition["key"]] = role
                    await persist_role_links(definition, role)
                    if definition.get("group") == "staff":
                        if needs_update:
                            errors.append(
                                f"Cargo de equipe {target_name} está acima do bot e não pode ser padronizado pela API. "
                                "Confira manualmente nome, cor e permissões."
                            )
                    else:
                        errors.append(
                            f"Cargo funcional {target_name} está no mesmo nível/acima do cargo do bot. "
                            "Mova o cargo do bot acima dele e execute /adm novamente."
                        )
                    continue

                if needs_update:
                    try:
                        await role.edit(
                            name=target_name, colour=color, permissions=effective_permissions,
                            hoist=hoist, mentionable=False,
                            reason="Quase Pro /adm: padronização de cargo e cor",
                        )
                        updated += 1
                    except (discord.Forbidden, discord.HTTPException) as exc:
                        errors.append(f"Cargo {target_name}: {type(exc).__name__}")
                        role_objects[definition["key"]] = role
                        await persist_role_links(definition, role)
                        continue

            role_objects[definition["key"]] = role
            await persist_role_links(definition, role)

        # Put the managed roles directly below the bot, ordered top-to-bottom. Staff
        # roles are deliberately excluded: Discord forbids moving them above the bot.
        try:
            ordered_roles = []
            for key in managed_role_hierarchy_keys():
                role = role_objects.get(key)
                if not role or role.managed:
                    continue
                if role >= me.top_role:
                    errors.append(
                        f"Cargo funcional {role.name} está no mesmo nível/acima do cargo do bot; "
                        "ele foi omitido da ordenação automática."
                    )
                    continue
                if role not in ordered_roles:
                    ordered_roles.append(role)

            top_position = int(me.top_role.position)
            if ordered_roles and top_position > len(ordered_roles):
                positions = {role: top_position - index - 1 for index, role in enumerate(ordered_roles)}
                await guild.edit_role_positions(
                    positions=positions,
                    reason="Quase Pro /adm: hierarquia oficial de cargos funcionais",
                )
            elif ordered_roles:
                errors.append(
                    f"Não há posições suficientes abaixo do cargo do bot para ordenar {len(ordered_roles)} cargos. "
                    "Mova o cargo do bot para cima dos cargos funcionais, mantendo-o abaixo da equipe."
                )
        except (discord.Forbidden, discord.HTTPException) as exc:
            errors.append(f"Não foi possível ordenar a hierarquia dos cargos funcionais: {type(exc).__name__}.")

        # Verify staff order. If missing/below the bot, the owner must drag those roles
        # above the bot's managed role in Server Settings > Roles. This cannot be done
        # through the bot API by design.
        staff_roles = [role_objects.get(key) for key in STAFF_ROLE_ORDER]
        missing_staff = [key for key, role in zip(STAFF_ROLE_ORDER, staff_roles) if role is None]
        staff_below_bot = [
            role for role in staff_roles
            if role is not None and role.position <= me.top_role.position
        ]
        if missing_staff:
            errors.append(
                "Cargos de equipe não localizados: " + ", ".join(missing_staff) + ". "
                "Crie/associe esses cargos e mantenha-os acima do cargo do bot."
            )
        if staff_below_bot:
            expected_names = [
                (role_objects[key].name if role_objects.get(key) else key)
                for key in STAFF_ROLE_ORDER
            ]
            errors.append(
                "Hierarquia da equipe exige uma etapa manual: mova os cargos para ACIMA do cargo real do bot "
                "e ordene de cima para baixo assim: " + " > ".join(expected_names) + ". "
                "A API do Discord não permite que o bot se coloque acima de si mesmo nem mova cargos para cima dele. "
                "Não atribua esses cargos privilegiados a novos membros até concluir essa etapa."
            )
        elif all(staff_roles) and any(
            staff_roles[index].position <= staff_roles[index + 1].position
            for index in range(len(staff_roles) - 1)
        ):
            errors.append(
                "Os cargos de equipe já estão acima do bot, mas sua ordem relativa está incorreta. "
                "Ordene manualmente de cima para baixo: "
                + " > ".join(role.name for role in staff_roles) + "."
            )

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
        archived_categories, archived_channels = [], []
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

        verified_member_role = roles.get("member")
        if verified_member_role is None:
            return "Aplicação interrompida: não foi possível localizar/criar o cargo **🟢・Membro**. Nenhuma categoria foi alterada; corrija o cargo e tente novamente."
        if verified_member_role >= me.top_role:
            return "Aplicação interrompida: o cargo **🟢・Membro** está acima ou no mesmo nível do cargo do bot. Mova o cargo do bot para cima na hierarquia antes de aplicar a verificação. Nenhuma categoria foi alterada."

        admin_role_id = await get_setting(self.bot, guild.id, "admin_role_id", 0)
        mod_role_id = await get_setting(self.bot, guild.id, "moderation_role_id", 0)
        team_overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_channels=True),
        }
        # Todo o grupo de equipe compartilha a área privada; permissões administrativas
        # continuam sendo definidas pelo perfil real de cada cargo, não pela categoria.
        core_role_ids = {
            int(admin_role_id or 0), int(mod_role_id or 0),
            roles.get("founder").id if roles.get("founder") else 0,
            roles.get("administrator").id if roles.get("administrator") else 0,
            roles.get("moderator").id if roles.get("moderator") else 0,
            roles.get("support").id if roles.get("support") else 0,
            roles.get("developer").id if roles.get("developer") else 0,
        }
        for rid in core_role_ids:
            role = guild.get_role(rid) if rid else None
            if role:
                team_overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, read_message_history=True,
                )

        # Além do cargo Membro verificado, a equipe autorizada deve conseguir
        # diagnosticar os canais. Os cargos técnicos não recebem permissões admin.
        public_staff_roles = {
            roles.get(key) for key in ("founder", "administrator", "moderator", "support", "developer")
            if roles.get(key) is not None
        }
        for rid in (int(admin_role_id or 0), int(mod_role_id or 0)):
            role = guild.get_role(rid) if rid else None
            if role is not None:
                public_staff_roles.add(role)

        verified_overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True, manage_channels=True,
            ),
            verified_member_role: discord.PermissionOverwrite(view_channel=True),
        }
        for role in public_staff_roles:
            verified_overwrites[role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True,
            )

        # A categoria de entrada é visível a novos membros, mas somente o bot publica
        # mensagens. O botão de verificação continua funcionando sem exigir que o membro
        # tenha permissão de escrever no canal.
        entry_overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=True, send_messages=False, add_reactions=False,
                create_public_threads=False, create_private_threads=False,
                send_messages_in_threads=False,
            ),
            me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True,
                embed_links=True, attach_files=True,
            ),
        }

        used_channel_ids = set()
        active_category_ids = set()
        for position, (category_name, category_key, aliases, channel_defs) in enumerate(self.organization_plan()):
            category = discord.utils.get(guild.categories, name=category_name)
            if category is None:
                alias_names = {normalize_name(x) for x in aliases}
                category = next((cat for cat in guild.categories if normalize_name(cat.name) in alias_names), None)
            access_mode = category_access_mode(category_key)
            is_private = access_mode == "staff"
            if access_mode == "staff":
                category_overwrites = dict(team_overwrites)
            elif access_mode == "entry":
                category_overwrites = dict(entry_overwrites)
            else:
                # Fail closed: @everyone não vê áreas comuns; só o cargo Membro
                # concedido pelo botão de verificação e a equipe autorizada podem ver.
                category_overwrites = dict(verified_overwrites)
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
            active_category_ids.add(category.id)
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
                setting_keys = (setting_key,) if isinstance(setting_key, str) else tuple(setting_key or ())
                for config_key in setting_keys:
                    current = await get_setting(self.bot, guild.id, config_key, 0)
                    if int(current or 0) != channel.id:
                        await set_setting(self.bot, guild.id, actor_id, config_key, channel.id)

        # Arquiva recursos conhecidos que foram consolidados no plano simplificado.
        # Nada é apagado: canais, mensagens e histórico permanecem disponíveis à equipe.
        try:
            old_channel_names = legacy_channel_names()
            candidates = []
            legacy_categories = [
                category for category in guild.categories
                if category.id not in active_category_ids
                and normalize_name(category.name) in LEGACY_CATEGORY_NAMES
            ]
            candidate_ids = set()
            for category in legacy_categories:
                for channel in list(category.channels):
                    if channel.id not in used_channel_ids and channel.id not in candidate_ids:
                        candidates.append(channel)
                        candidate_ids.add(channel.id)
            for channel in list(guild.channels):
                if channel.id in used_channel_ids or channel.id in candidate_ids:
                    continue
                if (getattr(channel, "category_id", None) in active_category_ids
                        and normalize_name(channel.name) in old_channel_names):
                    candidates.append(channel)
                    candidate_ids.add(channel.id)

            archive_overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_channels=True),
            }
            for role_id in core_role_ids:
                role = guild.get_role(role_id) if role_id else None
                if role is not None:
                    archive_overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

            archive = discord.utils.get(guild.categories, name="🗄️・ARQUIVO ANTIGO")
            if candidates:
                if archive is None:
                    archive = await guild.create_category(
                        "🗄️・ARQUIVO ANTIGO", overwrites=archive_overwrites,
                        reason="Quase Pro /adm: arquivamento não destrutivo de canais consolidados",
                    )
                else:
                    await archive.edit(overwrites=archive_overwrites, reason="Quase Pro /adm: proteger arquivo legado")
                for channel in candidates:
                    if getattr(channel, "category_id", None) == archive.id:
                        continue
                    try:
                        await channel.edit(
                            category=archive, overwrites=archive_overwrites,
                            reason="Quase Pro /adm: preservar histórico de canal consolidado",
                        )
                        archived_channels.append(channel.name)
                    except (discord.Forbidden, discord.HTTPException) as exc:
                        errors.append(f"Não foi possível arquivar {channel.name}: {type(exc).__name__}")

            # Mesmo quando uma categoria antiga já ficou vazia, esconda/renomeie-a para
            # que ela não continue poluindo a navegação pública.
            for category in legacy_categories:
                try:
                    new_legacy_name = f"🗄️・ANTIGA {category.name}"[:100]
                    await category.edit(name=new_legacy_name, overwrites=archive_overwrites,
                                        reason="Quase Pro /adm: ocultar categoria antiga sem excluir histórico")
                    archived_categories.append(new_legacy_name)
                except (discord.Forbidden, discord.HTTPException) as exc:
                    errors.append(f"Não foi possível proteger categoria antiga {category.name}: {type(exc).__name__}")
        except (discord.Forbidden, discord.HTTPException) as exc:
            errors.append(f"Falha ao arquivar canais consolidados: {type(exc).__name__}")
        except Exception as exc:
            log.exception("Falha ao arquivar recursos antigos do servidor %s", guild.id)
            errors.append(f"Falha ao arquivar recursos antigos: {type(exc).__name__}")

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
            ("✅・verificação", "Cargos", "publish_welcome_panel", "painel de verificação"),
            ("🎭・cargos-de-interesse", "Cargos", "publish_organization_panel", "painel de cargos de interesse"),
            ("🛡️・clãs", "Clans", "publish_organization_panel", "painel Salão dos Juramentos"),
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
            f"Canais antigos arquivados sem exclusão: **{len(archived_channels)}** · categorias antigas protegidas: **{len(archived_categories)}**.",
            f"Cargos criados: **{roles_created}** · ajustados: **{roles_updated}** · cargos funcionais padronizados: **{len(ROLE_DEFINITIONS)}**.",
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

    @staticmethod
    def _cleanup_signature(plan: dict) -> str:
        def channel_record(item, include_overwrites=True):
            overwrites = []
            if include_overwrites:
                try:
                    for target, overwrite in item.overwrites.items():
                        allow, deny = overwrite.pair()
                        overwrites.append((int(getattr(target, "id", 0) or 0), int(allow.value), int(deny.value)))
                except Exception:
                    pass
            return (
                int(item.id), str(getattr(item, "name", "")),
                int(getattr(item, "category_id", 0) or 0), str(getattr(item, "type", "unknown")),
                int(getattr(item, "position", 0) or 0),
                int(getattr(item, "last_message_id", 0) or 0), tuple(sorted(overwrites)),
            )

        def category_record(item):
            return channel_record(item, include_overwrites=True)

        def candidate_role_record(item):
            # A mudança na associação de um cargo candidato exige um novo backup.
            members = tuple(sorted(int(member.id) for member in getattr(item, "members", [])))
            return (int(item.id), str(item.name), int(item.position), int(item.permissions.value), members)

        def target_role_record(item):
            # Mudanças na associação de cargos-alvo (ex.: um novo membro verificado) não
            # invalidam a limpeza, pois esses cargos não serão apagados.
            return (int(item.id), str(item.name))

        payload = {
            "channels": sorted(channel_record(item) for item in plan["channels"]),
            "categories": sorted(category_record(item) for item in plan["categories"]),
            "roles": sorted(candidate_role_record(item) for item in plan["roles"]),
            "target_channels": sorted(channel_record(item, include_overwrites=False) for item in plan["target_channels"]),
            "target_categories": sorted(category_record(item) for item in plan["target_categories"]),
            "target_roles": sorted(target_role_record(item) for item in plan["target_roles"]),
            "protected_clan_categories": sorted(plan["protected_clan_category_ids"]),
            "protected_clan_channels": sorted(plan["protected_clan_channel_ids"]),
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    async def build_cleanup_plan(self, guild: discord.Guild) -> dict:
        """Build a non-destructive inventory; never infer that a failed lookup is safe to delete."""
        blockers: list[str] = []
        me = guild.me or guild.get_member(self.bot.user.id if self.bot.user else 0)
        if not me:
            blockers.append("O bot não foi localizado como membro do servidor.")
        elif not me.guild_permissions.manage_channels or not me.guild_permissions.manage_roles:
            blockers.append("O bot precisa de Gerenciar Canais e Gerenciar Cargos para fazer a limpeza completa.")

        target_categories = []
        target_channels = []
        target_category_ids: set[int] = set()
        expected_channels_by_category: dict[int, set[int]] = {}
        # Só permite exclusão quando todas as categorias e canais canônicos da nova estrutura
        # já existem. Isso evita apagar o servidor caso a organização inicial tenha falhado.
        for category_name, _category_key, _aliases, channel_defs in self.organization_plan():
            category = next((item for item in guild.categories if item.name == category_name), None)
            if category is None:
                blockers.append(f"Categoria-alvo ausente: {category_name}. Aplique a organização antes da limpeza.")
                continue
            target_categories.append(category)
            target_category_ids.add(category.id)
            expected_channels_by_category[category.id] = set()
            for channel_name, kind, _setting_key, _aliases2, _special_access in channel_defs:
                channel = next((item for item in category.channels if item.name == channel_name and (
                    isinstance(item, discord.VoiceChannel) if kind == "voice" else isinstance(item, discord.TextChannel)
                )), None)
                if channel is None:
                    blockers.append(f"Canal-alvo ausente ou de tipo incorreto: {category_name} / {channel_name}.")
                    continue
                target_channels.append(channel)
                expected_channels_by_category[category.id].add(channel.id)

        # Categorias/canais pertencentes a clãs ativos ou degradados fazem parte da nova
        # organização mesmo que sejam criados dinamicamente e não estejam em ORGANIZATION.
        protected_clan_category_ids: set[int] = set()
        protected_clan_channel_ids: set[int] = set()
        try:
            clan_rows = await self.bot.db._all(
                "SELECT id,category_id,chat_channel_id,announcements_id,strategies_id,voice_channel_id "
                "FROM clans WHERE guild_id=? AND status IN ('active','degraded')",
                (int(guild.id),),
            )
            for row in clan_rows:
                for field in ("category_id",):
                    if row[field]:
                        protected_clan_category_ids.add(int(row[field]))
                for field in ("chat_channel_id", "announcements_id", "strategies_id", "voice_channel_id"):
                    if row[field]:
                        protected_clan_channel_ids.add(int(row[field]))
        except Exception:
            log.exception("Não foi possível conferir os canais dos clãs antes da limpeza no servidor %s", guild.id)
            blockers.append("Não foi possível validar os recursos de clãs ativos; limpeza bloqueada por segurança.")

        # Resolve each target role using stored IDs first, then canonical/legacy aliases.
        target_roles = []
        target_role_ids: set[int] = set()
        setting_role_ids: set[int] = set()
        for definition in ROLE_DEFINITIONS:
            setting_keys = [f"role_{definition['key']}_id"]
            mapped_setting = ROLE_SETTING_KEYS.get(definition["key"])
            if mapped_setting:
                setting_keys.append(mapped_setting)
            local_configured_ids: list[int] = []
            for setting_key in setting_keys:
                value = await get_setting(self.bot, guild.id, setting_key, 0)
                try:
                    configured = guild.get_role(int(value)) if value else None
                except (TypeError, ValueError):
                    configured = None
                if configured:
                    setting_role_ids.add(configured.id)
                    local_configured_ids.append(configured.id)
            name_aliases = {normalize_name(definition["name"])}
            name_aliases.update(normalize_name(alias) for alias in definition.get("aliases", ()))
            configured_role = next((guild.get_role(role_id) for role_id in local_configured_ids if guild.get_role(role_id)), None)
            role = configured_role or next((item for item in guild.roles if normalize_name(item.name) in name_aliases), None)
            if role is None:
                blockers.append(f"Cargo-alvo ausente: {definition['name']}. Aplique a organização antes da limpeza.")
            else:
                if role.id not in target_role_ids:
                    target_roles.append(role)
                    target_role_ids.add(role.id)
        # Configurações legadas ainda válidas são preservadas. Se apontarem para recurso
        # não pertencente à organização, serão reportadas como impedimento abaixo.
        target_role_ids.update(setting_role_ids)
        target_roles = list({role.id: role for role in target_roles + [guild.get_role(rid) for rid in setting_role_ids if guild.get_role(rid)]}.values())

        candidate_categories = [
            category for category in guild.categories
            if category.id not in target_category_ids and category.id not in protected_clan_category_ids
        ]
        candidate_category_ids = {category.id for category in candidate_categories}
        candidate_channels = []
        for channel in guild.channels:
            if isinstance(channel, discord.CategoryChannel):
                continue
            if channel.id in protected_clan_channel_ids or getattr(channel, "category_id", None) in protected_clan_category_ids:
                continue
            parent_id = getattr(channel, "category_id", None)
            if parent_id in target_category_ids:
                if channel.id not in expected_channels_by_category.get(parent_id, set()):
                    candidate_channels.append(channel)
            else:
                # Todo canal fora das categorias canônicas ou dos espaços dos clãs ativos
                # será listado para exclusão, incluindo canais sem categoria e o arquivo antigo.
                candidate_channels.append(channel)

        # Um cargo extra que ainda aparece nos overwrites de recursos preservados não pode
        # ser removido sem antes reparar essas permissões, pois isso alteraria acesso a áreas
        # que permanecerão no servidor.
        preserved_channel_objects = list(target_categories) + list(target_channels)
        for channel_id in protected_clan_category_ids | protected_clan_channel_ids:
            channel_obj = guild.get_channel(channel_id)
            if channel_obj is not None:
                preserved_channel_objects.append(channel_obj)
        overwrite_role_ids: set[int] = set()
        for preserved_channel in preserved_channel_objects:
            try:
                for overwrite_target in preserved_channel.overwrites:
                    if isinstance(overwrite_target, discord.Role) and overwrite_target.id not in target_role_ids and not overwrite_target.is_default() and not overwrite_target.managed:
                        overwrite_role_ids.add(overwrite_target.id)
            except Exception:
                blockers.append(f"Não foi possível validar sobrescritas de permissões de {getattr(preserved_channel, 'name', preserved_channel.id)}; limpeza bloqueada.")

        me_role_ids = {role.id for role in me.roles} if me else set()
        candidate_roles = []
        skipped_roles = []
        for role in guild.roles:
            if role.is_default() or role.id in target_role_ids:
                continue
            if role.id in overwrite_role_ids:
                skipped_roles.append((role, "ainda aparece nas permissões de um canal/categoria preservado"))
                blockers.append(f"O cargo {role.name} ainda controla permissões de um recurso preservado; reaplique/corrija essas permissões antes de excluí-lo.")
            elif role.managed:
                skipped_roles.append((role, "cargo gerenciado pelo Discord/integração"))
            elif role.id in me_role_ids:
                skipped_roles.append((role, "atribuído ao próprio bot; necessário para operar"))
            elif me and role >= me.top_role:
                skipped_roles.append((role, "acima da hierarquia do bot; a API não permite apagar"))
            else:
                candidate_roles.append(role)

        # Não exclui canais/categorias/cargos ainda apontados por configurações persistentes.
        channel_ids = {item.id for item in candidate_channels}
        category_ids = {item.id for item in candidate_categories}
        role_ids = {item.id for item in candidate_roles}
        try:
            settings_rows = await self.bot.db._all(
                "SELECT key,value FROM guild_settings WHERE guild_id=?", (int(guild.id),),
            )
            for row in settings_rows:
                key = str(row["key"])
                try:
                    ref_id = int(row["value"])
                except (TypeError, ValueError):
                    continue
                if (key.endswith("_channel_id") or key.endswith("_category_id")) and ref_id in channel_ids | category_ids:
                    item = guild.get_channel(ref_id)
                    blockers.append(f"{getattr(item, 'name', ref_id)} ainda está associado à configuração `{key}`; reaplique/corrija as associações antes de excluir.")
                if (key.endswith("_role_id") or (key.startswith("role_") and key.endswith("_id"))) and ref_id in role_ids:
                    item = guild.get_role(ref_id)
                    blockers.append(f"O cargo {getattr(item, 'name', ref_id)} ainda está associado à configuração `{key}`; corrija a associação antes de excluir.")
        except Exception:
            log.exception("Não foi possível validar referências de configuração antes da limpeza no servidor %s", guild.id)
            blockers.append("Não foi possível verificar todas as referências persistentes; limpeza bloqueada por segurança.")

        plan = {
            "blockers": list(dict.fromkeys(blockers)),
            "categories": candidate_categories,
            "channels": candidate_channels,
            "roles": candidate_roles,
            "skipped_roles": skipped_roles,
            "target_categories": target_categories,
            "target_channels": target_channels,
            "target_roles": target_roles,
            "protected_clan_category_ids": protected_clan_category_ids,
            "protected_clan_channel_ids": protected_clan_channel_ids,
        }
        plan["signature"] = self._cleanup_signature(plan)
        return plan

    def cleanup_preview_embed(self, guild: discord.Guild, plan: dict) -> discord.Embed:
        """Describe exact candidates; long inventories are included in the downloadable backup manifest."""
        embed = discord.Embed(
            title="Quase Pro · Prévia de limpeza destrutiva",
            description=(
                "**Esta ação apagará permanentemente os recursos listados.** Canais excluídos perdem o histórico de mensagens; "
                "o backup não consegue restaurar mensagens, threads ou anexos hospedados pelo Discord. "
                "A execução exige backup entregue ao dono do servidor e confirmação digitando `APAGAR RESTO`."
            ), color=0xC0392B,
        )
        embed.add_field(name="Canais a excluir", value=str(len(plan["channels"])), inline=True)
        embed.add_field(name="Categorias a excluir", value=str(len(plan["categories"])), inline=True)
        embed.add_field(name="Cargos a excluir", value=str(len(plan["roles"])), inline=True)
        embed.add_field(name="Espaços de clãs preservados", value=(
            f"{len(plan['protected_clan_category_ids'])} categorias · {len(plan['protected_clan_channel_ids'])} canais"), inline=True)
        embed.add_field(name="Cargos que serão preservados fora da lista-alvo", value=str(len(plan["skipped_roles"])), inline=True)

        def format_lines(items, name_fn, max_lines=10):
            if not items:
                return "Nenhum."
            lines = [name_fn(item) for item in items[:max_lines]]
            if len(items) > max_lines:
                lines.append(f"… e mais {len(items) - max_lines}; o inventário completo ficará no backup.")
            return "\n".join(lines)[:1024]

        embed.add_field(name="Canais excedentes (amostra)", value=format_lines(
            plan["channels"], lambda item: f"• {item.name} (`{item.id}`)"), inline=False)
        embed.add_field(name="Categorias excedentes (amostra)", value=format_lines(
            plan["categories"], lambda item: f"• {item.name} (`{item.id}`)"), inline=False)
        embed.add_field(name="Cargos excedentes (amostra)", value=format_lines(
            plan["roles"], lambda item: f"• {item.name} (`{item.id}`; {len(getattr(item, 'members', []))} membros)"), inline=False)
        if plan["skipped_roles"]:
            embed.add_field(name="Cargos preservados/limitação do Discord", value=format_lines(
                plan["skipped_roles"], lambda pair: f"• {pair[0].name}: {pair[1]}"), inline=False)
        if plan["blockers"]:
            embed.add_field(name="IMPEDIMENTOS — nada pode ser apagado", value="\n".join(
                f"• {item}" for item in plan["blockers"][:8])[:1024], inline=False)
            embed.set_footer(text="Corrija os impedimentos e aplique a estrutura completa antes de gerar outra prévia.")
        else:
            embed.set_footer(text="Apenas o dono do servidor pode continuar. O inventário completo será anexado ao backup antes da confirmação final.")
        return embed

    async def create_cleanup_backup(self, guild: discord.Guild, plan: dict) -> str:
        """Bundle database snapshots and a metadata manifest before any deletion is allowed."""
        db_backup = await self.create_backup()
        try:
            with zipfile.ZipFile(db_backup, "r") as database_archive:
                database_names = database_archive.namelist()
                if not database_names or "soulsbot.db" not in database_names:
                    raise RuntimeError("O backup não contém o banco principal soulsbot.db; a limpeza foi bloqueada.")
        except Exception:
            try:
                os.remove(db_backup)
            except OSError:
                pass
            raise
        manifest_fd, manifest_path = tempfile.mkstemp(prefix="quasepro-server-state-", suffix=".json")
        os.close(manifest_fd)
        target_fd, target_path = tempfile.mkstemp(prefix="quasepro-cleanup-backup-", suffix=".zip")
        os.close(target_fd)
        completed = False
        try:
            def overwrite_records(channel):
                result = []
                try:
                    for target, overwrite in channel.overwrites.items():
                        allow, deny = overwrite.pair()
                        result.append({
                            "target_id": getattr(target, "id", None),
                            "target_name": getattr(target, "name", None),
                            "target_type": "role" if isinstance(target, discord.Role) else "member",
                            "allow_bits": int(allow.value), "deny_bits": int(deny.value),
                        })
                except Exception:
                    return result
                return result

            channels_manifest = []
            for channel in guild.channels:
                channels_manifest.append({
                    "id": channel.id, "name": channel.name, "type": str(getattr(channel, "type", "unknown")),
                    "category_id": getattr(channel, "category_id", None),
                    "category_name": getattr(getattr(channel, "category", None), "name", None),
                    "position": getattr(channel, "position", None),
                    "last_message_id": getattr(channel, "last_message_id", None),
                    "topic": getattr(channel, "topic", None),
                    "nsfw": getattr(channel, "nsfw", None),
                    "slowmode_delay": getattr(channel, "slowmode_delay", None),
                    "bitrate": getattr(channel, "bitrate", None),
                    "user_limit": getattr(channel, "user_limit", None),
                    "overwrites": overwrite_records(channel),
                })
            roles_manifest = []
            for role in guild.roles:
                roles_manifest.append({
                    "id": role.id, "name": role.name, "color": getattr(getattr(role, "colour", None), "value", 0),
                    "position": role.position, "permissions_bits": role.permissions.value,
                    "hoist": role.hoist, "mentionable": role.mentionable, "managed": role.managed,
                    "member_ids_cached": [member.id for member in getattr(role, "members", [])],
                })
            manifest = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "guild_id": guild.id, "guild_name": guild.name,
                "warning": "Metadata-only Discord snapshot. It cannot restore deleted Discord messages, threads, or attachments.",
                "planned_deletion": {
                    "channels": [{"id": item.id, "name": item.name, "category_id": getattr(item, "category_id", None)} for item in plan["channels"]],
                    "categories": [{"id": item.id, "name": item.name} for item in plan["categories"]],
                    "roles": [{"id": item.id, "name": item.name, "position": item.position, "permissions_bits": item.permissions.value,
                               "member_ids_cached": [member.id for member in getattr(item, "members", [])]} for item in plan["roles"]],
                },
                "channels": channels_manifest,
                "roles": roles_manifest,
                "preserved_clan_category_ids": sorted(plan["protected_clan_category_ids"]),
                "preserved_clan_channel_ids": sorted(plan["protected_clan_channel_ids"]),
                "preserved_role_ids": [item.id for item in plan["target_roles"]],
            }
            with open(manifest_path, "w", encoding="utf-8") as stream:
                json.dump(manifest, stream, ensure_ascii=False, indent=2)
            with zipfile.ZipFile(target_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.write(db_backup, "database-backup.zip")
                archive.write(manifest_path, "server-state-and-deletion-manifest.json")
            completed = True
            return target_path
        finally:
            for path in (db_backup, manifest_path):
                try:
                    os.remove(path)
                except OSError:
                    pass
            if not completed:
                try:
                    os.remove(target_path)
                except OSError:
                    pass

    async def execute_cleanup_plan(self, guild: discord.Guild, actor_id: int, plan: dict) -> str:
        """Execute only the reviewed plan; recheck ownership, permissions and signature first."""
        if int(actor_id) != int(guild.owner_id):
            raise PermissionError("Only the guild owner may run destructive cleanup")
        me = guild.me or guild.get_member(self.bot.user.id if self.bot.user else 0)
        if not me or not me.guild_permissions.manage_channels or not me.guild_permissions.manage_roles:
            raise PermissionError("Bot requires Manage Channels and Manage Roles")
        fresh = await self.build_cleanup_plan(guild)
        if fresh["blockers"] or fresh["signature"] != plan["signature"]:
            raise RuntimeError("Cleanup plan became stale or blocked before execution")

        channel_deleted = category_deleted = role_deleted = 0
        failures: list[str] = []
        await audit(
            self.bot, guild.id, actor_id, "destructive_cleanup_started", "server-resources",
            before=(f"channels={len(plan['channels'])};categories={len(plan['categories'])};roles={len(plan['roles'])}"),
            result="started",
        )
        # Delete non-category channels first. Deleting parent channels also deletes their
        # Discord-hosted message history and threads, which the backup cannot restore.
        for item in sorted(plan["channels"], key=lambda channel: (getattr(channel, "category_id", 0) or 0, channel.id)):
            channel = guild.get_channel(item.id)
            if channel is None:
                continue
            try:
                await channel.delete(reason="Quase Pro: dono confirmou limpeza dos recursos fora da organização atual")
                channel_deleted += 1
            except (discord.Forbidden, discord.HTTPException) as exc:
                failures.append(f"Canal {item.name} (`{item.id}`): {type(exc).__name__}")

        for item in plan["categories"]:
            category = guild.get_channel(item.id)
            if not isinstance(category, discord.CategoryChannel):
                continue
            if category.channels:
                failures.append(f"Categoria {category.name} mantida porque ainda contém canais após falhas parciais.")
                continue
            try:
                await category.delete(reason="Quase Pro: dono confirmou limpeza dos recursos fora da organização atual")
                category_deleted += 1
            except (discord.Forbidden, discord.HTTPException) as exc:
                failures.append(f"Categoria {item.name} (`{item.id}`): {type(exc).__name__}")

        live_me = guild.me or guild.get_member(self.bot.user.id if self.bot.user else 0)
        bot_role_ids = {role.id for role in live_me.roles} if live_me else set()
        for item in sorted(plan["roles"], key=lambda role: role.position):
            role = guild.get_role(item.id)
            if role is None:
                continue
            if role.is_default() or role.managed or role.id in bot_role_ids or (live_me and role >= live_me.top_role):
                failures.append(f"Cargo {role.name} preservado porque é gerenciado, necessário ao bot ou está fora da hierarquia.")
                continue
            try:
                await role.delete(reason="Quase Pro: dono confirmou limpeza dos cargos fora da organização atual")
                role_deleted += 1
            except (discord.Forbidden, discord.HTTPException) as exc:
                failures.append(f"Cargo {role.name} (`{role.id}`): {type(exc).__name__}")

        await audit(
            self.bot, guild.id, actor_id, "destructive_cleanup_completed", "server-resources",
            after=(f"channels_deleted={channel_deleted};categories_deleted={category_deleted};roles_deleted={role_deleted};failures={len(failures)}"),
            result="partial" if failures else "success",
        )
        parts = [
            "**Limpeza destrutiva concluída.**",
            f"Canais excluídos: **{channel_deleted}** · categorias vazias excluídas: **{category_deleted}** · cargos excluídos: **{role_deleted}**.",
            "Foram preservados: as categorias/canais definidos na nova organização, espaços registrados de clãs ativos/degradados, cargos-alvo, cargos gerenciados e cargos necessários ao bot.",
            f"Cargos excedentes preservados por limitação da hierarquia/integração: **{len(plan['skipped_roles'])}**.",
            "O backup de bancos e metadados foi enviado antes da confirmação; ele não restaura mensagens, threads ou anexos do Discord.",
        ]
        if plan["skipped_roles"]:
            parts.append("**Cargos preservados:** " + "; ".join(f"{role.name} — {reason}" for role, reason in plan["skipped_roles"][:8]))
        if failures:
            parts.append("**Itens não excluídos / falhas parciais:**\n" + "\n".join(f"• {line}" for line in failures[:12]))
            parts.append("Revise o diagnóstico e o registro de auditoria; não repita sem analisar as falhas parciais.")
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
        # Verify the role hierarchy against Discord's hard boundary: the bot can only
        # manage roles strictly below its own highest role.
        if me:
            staff_roles = []
            for role_key in STAFF_ROLE_ORDER:
                role_id = await get_setting(self.bot, guild.id, f"role_{role_key}_id", 0)
                role = guild.get_role(int(role_id)) if role_id else None
                if role is None:
                    mapped_key = ROLE_SETTING_KEYS.get(role_key)
                    mapped_id = await get_setting(self.bot, guild.id, mapped_key, 0) if mapped_key else 0
                    role = guild.get_role(int(mapped_id)) if mapped_id else None
                staff_roles.append(role)
            missing_staff = [key for key, role in zip(STAFF_ROLE_ORDER, staff_roles) if role is None]
            if missing_staff:
                lines.append("🟠 Hierarquia: cargos de equipe não configurados — " + ", ".join(missing_staff) + ".")
            elif any(role.position <= me.top_role.position for role in staff_roles):
                lines.append(
                    "🟠 Hierarquia: mova Fundador, Administrador, Moderador, Equipe de Suporte e Desenvolvedor "
                    "para acima do cargo do bot; não atribua cargos privilegiados antes disso."
                )
            elif any(staff_roles[i].position <= staff_roles[i + 1].position for i in range(len(staff_roles) - 1)):
                lines.append("🟠 Hierarquia: os cargos de equipe estão acima do bot, mas fora da ordem recomendada.")

            mispositioned = []
            managed_positions = []
            for role_key in managed_role_hierarchy_keys():
                role_id = await get_setting(self.bot, guild.id, f"role_{role_key}_id", 0)
                role = guild.get_role(int(role_id)) if role_id else None
                if role and not role.managed:
                    if role.position >= me.top_role.position:
                        mispositioned.append(role.name)
                    else:
                        managed_positions.append(role)
            if mispositioned:
                lines.append(
                    "🔴 Hierarquia: cargos funcionais precisam ficar abaixo do cargo do bot — "
                    + ", ".join(mispositioned[:8]) + ("…" if len(mispositioned) > 8 else "") + "."
                )
            elif any(
                managed_positions[index].position <= managed_positions[index + 1].position
                for index in range(len(managed_positions) - 1)
            ):
                lines.append(
                    "🟠 Hierarquia: os cargos funcionais estão abaixo do bot, mas fora da ordem esperada. "
                    "Execute /adm → Organização do servidor para reorganizar patentes, cargos de clã, comunidade e interesses."
                )

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
