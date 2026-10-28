"""Sistema de Clãs do Quase Pro: descoberta pública e espaços privados por clã."""
from __future__ import annotations

import re
import sqlite3
import aiosqlite
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from settings_store import audit, get_setting, module_enabled

MAX_MEMBERS = 10
INVITE_DAYS = 7
STYLES = ("Cooperação", "PvP", "Conquistas e platinas", "Exploração", "Misto")
RECRUITMENT = ("Somente por convite", "Candidaturas abertas", "Misto")
STYLE_TO_DB = {
    "Cooperação": "cooperacao",
    "PvP": "pvp",
    "Conquistas e platinas": "conquistas",
    "Exploração": "exploracao",
    "Misto": "misto",
}


def _slug(text: str) -> str:
    import unicodedata
    value = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:48] or "cla"


def _style_label(value: str) -> str:
    return {
        "cooperacao": "Cooperação", "pvp": "PvP", "conquistas": "Conquistas e platinas",
        "exploracao": "Exploração", "misto": "Misto",
    }.get(value, value)


def _recruit_label(value: str) -> str:
    return {"invite": "Somente por convite", "applications": "Candidaturas abertas", "mixed": "Misto"}.get(value, value)


class ClanCreateModal(discord.ui.Modal, title="Fundar um clã"):
    name = discord.ui.TextInput(label="Nome do clã", min_length=3, max_length=32, placeholder="Ex.: Vigília das Cinzas")
    tag = discord.ui.TextInput(label="Sigla", min_length=2, max_length=5, placeholder="Ex.: VDC")
    game = discord.ui.TextInput(label="Jogo principal", min_length=2, max_length=50, placeholder="Ex.: Elden Ring")
    style = discord.ui.TextInput(label="Estilo", min_length=3, max_length=32, placeholder="Cooperação, PvP, Conquistas e platinas, Exploração ou Misto")
    description = discord.ui.TextInput(label="Descrição", style=discord.TextStyle.paragraph, required=False, max_length=200, placeholder="Objetivo e perfil do clã")

    def __init__(self, cog: "Clans"):
        super().__init__(timeout=300)
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        style_raw = str(self.style.value).strip().casefold()
        style = next((label for label in STYLES if label.casefold() == style_raw), None)
        if not style:
            return await interaction.response.send_message(
                "Estilo inválido. Use um destes valores: " + ", ".join(STYLES) + ".", ephemeral=True
            )
        await interaction.response.defer(ephemeral=True, thinking=True)
        result = await self.cog.create_clan(
            interaction, str(self.name.value).strip(), str(self.tag.value).strip().upper(),
            str(self.game.value).strip(), style, str(self.description.value or "").strip(),
        )
        await interaction.followup.send(result, ephemeral=True)


class ApplyClanModal(discord.ui.Modal, title="Candidatura para clã"):
    message = discord.ui.TextInput(label="Apresente-se ao clã", style=discord.TextStyle.paragraph, required=False, max_length=300, placeholder="Jogos, horários e o que procura no grupo")

    def __init__(self, cog: "Clans", clan_id: int):
        super().__init__(timeout=300)
        self.cog = cog
        self.clan_id = int(clan_id)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        result = await self.cog.apply_to_clan(interaction, self.clan_id, str(self.message.value or "").strip())
        await interaction.followup.send(result, ephemeral=True)


class ActivityModal(discord.ui.Modal, title="Registrar atividade do clã"):
    title_text = discord.ui.TextInput(label="Nome da atividade", min_length=3, max_length=70, placeholder="Ex.: Run cooperativa em Elden Ring")
    activity_type = discord.ui.TextInput(label="Tipo", min_length=2, max_length=30, placeholder="Cooperação, PvP, platina, evento...")
    when = discord.ui.TextInput(label="Quando (opcional)", required=False, max_length=50, placeholder="Ex.: sábado às 20h")

    def __init__(self, cog: "Clans", clan_id: int):
        super().__init__(timeout=300)
        self.cog = cog
        self.clan_id = int(clan_id)

    async def on_submit(self, interaction: discord.Interaction):
        await self.cog.create_activity(interaction, self.clan_id, str(self.title_text.value).strip(),
                                       str(self.activity_type.value).strip(), str(self.when.value or "").strip())


class ClanScopedView(discord.ui.View):
    """Base para bloquear interações de clã quando o módulo é desativado."""
    def __init__(self, cog: "Clans", guild_id: int | None = None, timeout: float | None = 240):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.guild_id = int(guild_id) if guild_id else None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            await interaction.response.send_message("Use este painel dentro de um servidor.", ephemeral=True)
            return False
        if self.guild_id is not None and interaction.guild.id != self.guild_id:
            await interaction.response.send_message("Este painel pertence a outro servidor.", ephemeral=True)
            return False
        if not await module_enabled(self.cog.bot, interaction.guild.id, "clans", True):
            await interaction.response.send_message("O Sistema de Clãs está desativado neste servidor.", ephemeral=True)
            return False
        return True


class ClansPublicView(ClanScopedView):
    """View persistente; callbacks consultam permissão e banco novamente."""
    def __init__(self, cog: "Clans"):
        super().__init__(cog, timeout=None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await super().interaction_check(interaction)

    @discord.ui.button(label="Criar clã", emoji="⚒️", style=discord.ButtonStyle.primary, custom_id="quasepro:clans:create", row=0)
    async def create(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ClanCreateModal(self.cog))

    @discord.ui.button(label="Explorar clãs", emoji="🔎", style=discord.ButtonStyle.secondary, custom_id="quasepro:clans:explore", row=0)
    async def explore(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed, view = await self.cog.explore_view(interaction.guild.id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Meu clã", emoji="🛡️", style=discord.ButtonStyle.secondary, custom_id="quasepro:clans:mine", row=0)
    async def mine(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.show_my_clan(interaction)

    @discord.ui.button(label="Meus convites", emoji="✉️", style=discord.ButtonStyle.secondary, custom_id="quasepro:clans:invites", row=1)
    async def invites(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed, view = await self.cog.invites_view(interaction.guild.id, interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Atividades", emoji="⚔️", style=discord.ButtonStyle.secondary, custom_id="quasepro:clans:activities", row=1)
    async def activities(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.show_activities(interaction)

    @discord.ui.button(label="Ranking", emoji="🏆", style=discord.ButtonStyle.secondary, custom_id="quasepro:clans:ranking", row=1)
    async def ranking(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.show_ranking(interaction)

    @discord.ui.button(label="Ajuda e regras", emoji="📜", style=discord.ButtonStyle.secondary, custom_id="quasepro:clans:help", row=1)
    async def help(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="Salão dos Juramentos — Regras",
            description=(
                f"• Cada membro pode pertencer a apenas um clã por servidor.\n"
                f"• Cada clã aceita no máximo {MAX_MEMBERS} integrantes, incluindo a liderança.\n"
                "• A criação por usuário é limitada a um clã por servidor, mesmo após encerrar o clã.\n"
                "• O acesso aos canais privados é controlado por permissões da categoria e atualizado na entrada/saída.\n"
                "• Administradores do servidor podem ter meios de acessar canais privados; não há privacidade absoluta contra a equipe com permissões elevadas.\n"
                "• XP e recompensas competitivas só serão ativados quando regras forem definidas e aprovadas em `/adm`."
            ), color=0xD4AF37,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ExploreClansView(ClanScopedView):
    def __init__(self, cog: "Clans", guild_id: int, clans: list, page: int = 0):
        super().__init__(cog, guild_id, timeout=240)
        self.clans = clans
        self.page = max(0, min(page, max(0, (len(clans) - 1) // 25)))
        self.selected_clan_id: int | None = None
        chunk = clans[self.page * 25:(self.page + 1) * 25]
        if chunk:
            options = []
            for row in chunk:
                vacancies = max(0, MAX_MEMBERS - int(row["member_count"]))
                options.append(discord.SelectOption(
                    label=f"[{row['tag']}] {row['name']}"[:100],
                    description=f"{row['main_game']} · {vacancies} vaga(s) · {_style_label(row['play_style'])}"[:100],
                    value=str(row["id"]),
                ))
            self.clan_select = discord.ui.Select(placeholder="Selecione um clã para ver detalhes", min_values=1, max_values=1, options=options)
            self.clan_select.callback = self._select_clan
            self.add_item(self.clan_select)
        if self.page > 0:
            self.add_item(discord.ui.Button(label="Anterior", style=discord.ButtonStyle.secondary, custom_id="clans:explore:prev"))
            self.children[-1].callback = self._prev
        if (self.page + 1) * 25 < len(clans):
            self.add_item(discord.ui.Button(label="Próxima", style=discord.ButtonStyle.secondary, custom_id="clans:explore:next"))
            self.children[-1].callback = self._next
        apply_button = discord.ui.Button(label="Candidatar-se", style=discord.ButtonStyle.success, custom_id="clans:explore:apply")
        apply_button.callback = self._apply
        self.add_item(apply_button)

    async def _select_clan(self, interaction: discord.Interaction):
        self.selected_clan_id = int(self.clan_select.values[0])
        row = await self.cog.get_clan(self.guild_id, self.selected_clan_id)
        if not row:
            return await interaction.response.send_message("Este clã não está mais disponível.", ephemeral=True)
        count = await self.cog.member_count(self.guild_id, self.selected_clan_id)
        embed = self.cog.clan_embed(row, count)
        await interaction.response.edit_message(embed=embed, view=self)

    async def _prev(self, interaction: discord.Interaction):
        embed, view = await self.cog.explore_view(self.guild_id, self.page - 1)
        await interaction.response.edit_message(embed=embed, view=view)

    async def _next(self, interaction: discord.Interaction):
        embed, view = await self.cog.explore_view(self.guild_id, self.page + 1)
        await interaction.response.edit_message(embed=embed, view=view)

    async def _apply(self, interaction: discord.Interaction):
        if self.selected_clan_id is None:
            return await interaction.response.send_message("Selecione um clã primeiro.", ephemeral=True)
        row = await self.cog.get_clan(self.guild_id, self.selected_clan_id)
        if not row or row["recruitment"] not in ("applications", "mixed"):
            return await interaction.response.send_message("Este clã não está aceitando candidaturas.", ephemeral=True)
        await interaction.response.send_modal(ApplyClanModal(self.cog, self.selected_clan_id))


class InviteMemberSelectView(ClanScopedView):
    def __init__(self, cog: "Clans", clan_id: int):
        super().__init__(cog, timeout=180)
        self.clan_id = int(clan_id)
        self.user_select = discord.ui.UserSelect(placeholder="Escolha uma pessoa para convidar", min_values=1, max_values=1)
        self.user_select.callback = self._selected
        self.add_item(self.user_select)

    async def _selected(self, interaction: discord.Interaction):
        member = self.user_select.values[0]
        if not isinstance(member, discord.Member) or member.guild.id != interaction.guild_id:
            return await interaction.response.send_message("Selecione um membro deste servidor.", ephemeral=True)
        result = await self.cog.issue_invite(interaction, self.clan_id, member)
        await interaction.response.edit_message(content=result, embed=None, view=None)


class InviteListView(ClanScopedView):
    def __init__(self, cog: "Clans", guild_id: int, user_id: int, rows: list):
        super().__init__(cog, guild_id, timeout=240)
        self.user_id = int(user_id)
        self.rows = rows
        self.selected_invite_id: int | None = None
        if rows:
            options = [discord.SelectOption(label=f"[{r['tag']}] {r['name']}"[:100], description=f"Convite de <@{r['inviter_id']}>"[:100], value=str(r["id"])) for r in rows[:25]]
            self.select = discord.ui.Select(placeholder="Selecione um convite", options=options, min_values=1, max_values=1)
            self.select.callback = self._choose
            self.add_item(self.select)
            for label, action, style in (("Aceitar", "accept", discord.ButtonStyle.success), ("Recusar", "reject", discord.ButtonStyle.danger)):
                btn = discord.ui.Button(label=label, style=style, custom_id=f"clans:invite:{action}")
                btn.callback = lambda i, a=action: self._resolve(i, a)
                self.add_item(btn)

    async def _choose(self, interaction: discord.Interaction):
        self.selected_invite_id = int(self.select.values[0])
        await interaction.response.edit_message(content=f"Convite selecionado: **{self.rows_by_id()[self.selected_invite_id]['name']}**. Aceite ou recuse.", embed=None, view=self)

    def rows_by_id(self):
        return {int(r["id"]): r for r in self.rows}

    async def _resolve(self, interaction: discord.Interaction, action: str):
        if self.selected_invite_id is None:
            return await interaction.response.send_message("Selecione um convite.", ephemeral=True)
        result = await self.cog.resolve_invite(interaction, self.selected_invite_id, action == "accept")
        await interaction.response.edit_message(content=result, embed=None, view=None)


class ApplicationQueueView(ClanScopedView):
    def __init__(self, cog: "Clans", clan_id: int, guild_id: int, rows: list):
        super().__init__(cog, guild_id, timeout=240)
        self.clan_id, self.rows = int(clan_id), rows
        self.selected_app_id: int | None = None
        if rows:
            options = [discord.SelectOption(label=f"Candidatura #{r['id']} · {r['user_id']}"[:100], description=(r["message"] or "Sem mensagem")[:100], value=str(r["id"])) for r in rows[:25]]
            self.select = discord.ui.Select(placeholder="Escolha uma candidatura", options=options)
            self.select.callback = self._choose
            self.add_item(self.select)
            for label, accept, style in (("Aprovar", True, discord.ButtonStyle.success), ("Rejeitar", False, discord.ButtonStyle.danger)):
                btn = discord.ui.Button(label=label, style=style, custom_id=f"clans:application:{'accept' if accept else 'reject'}")
                btn.callback = lambda i, a=accept: self._resolve(i, a)
                self.add_item(btn)

    async def _choose(self, interaction: discord.Interaction):
        self.selected_app_id = int(self.select.values[0])
        row = next((r for r in self.rows if int(r["id"]) == self.selected_app_id), None)
        await interaction.response.edit_message(content=f"Candidatura #{self.selected_app_id}\nMembro: <@{row['user_id']}>\nMensagem: {row['message'] or '—'}", embed=None, view=self)

    async def _resolve(self, interaction: discord.Interaction, accept: bool):
        if self.selected_app_id is None:
            return await interaction.response.send_message("Selecione uma candidatura primeiro.", ephemeral=True)
        result = await self.cog.resolve_application(interaction, self.clan_id, self.selected_app_id, accept)
        await interaction.response.edit_message(content=result, embed=None, view=None)


class ClanManageView(ClanScopedView):
    def __init__(self, cog: "Clans", clan_id: int):
        super().__init__(cog, timeout=240)
        self.clan_id = int(clan_id)
        recruitment = discord.ui.Select(
            placeholder="Modo de recrutamento (somente líder)", min_values=1, max_values=1, row=2,
            options=[
                discord.SelectOption(label="Somente por convite", value="invite"),
                discord.SelectOption(label="Candidaturas abertas", value="applications"),
                discord.SelectOption(label="Misto", value="mixed"),
            ],
        )
        recruitment.callback = self._set_recruitment
        self.add_item(recruitment)

    async def _set_recruitment(self, interaction: discord.Interaction):
        mode = interaction.data["values"][0]
        result = await self.cog.set_recruitment(interaction, self.clan_id, mode)
        await interaction.response.send_message(result, ephemeral=True)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not await super().interaction_check(interaction):
            return False
        row = await self.cog.member_role(interaction.guild.id, self.clan_id, interaction.user.id)
        if row is None:
            await interaction.response.send_message("Você não é integrante deste clã.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Convidar membro", style=discord.ButtonStyle.primary, emoji="✉️", row=0)
    async def invite(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = await self.cog.member_role(interaction.guild.id, self.clan_id, interaction.user.id)
        if role not in ("leader", "officer"):
            return await interaction.response.send_message("Somente liderança e oficiais podem convidar.", ephemeral=True)
        await interaction.response.edit_message(content="Escolha um membro para convidar:", embed=None, view=InviteMemberSelectView(self.cog, self.clan_id))

    @discord.ui.button(label="Candidaturas", style=discord.ButtonStyle.secondary, emoji="📨", row=0)
    async def applications(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = await self.cog.member_role(interaction.guild.id, self.clan_id, interaction.user.id)
        if role not in ("leader", "officer"):
            return await interaction.response.send_message("Somente liderança e oficiais podem avaliar candidaturas.", ephemeral=True)
        rows = await self.cog.pending_applications(interaction.guild.id, self.clan_id)
        if not rows:
            return await interaction.response.send_message("Não há candidaturas pendentes.", ephemeral=True)
        await interaction.response.edit_message(content="Selecione uma candidatura e aprove ou rejeite:", embed=None, view=ApplicationQueueView(self.cog, self.clan_id, interaction.guild.id, rows))

    @discord.ui.button(label="Criar atividade", style=discord.ButtonStyle.secondary, emoji="⚔️", row=0)
    async def activity(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ActivityModal(self.cog, self.clan_id))

    @discord.ui.button(label="Sair", style=discord.ButtonStyle.secondary, emoji="🚪", row=1)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = await self.cog.member_role(interaction.guild.id, self.clan_id, interaction.user.id)
        if role == "leader":
            return await interaction.response.send_message("Transfira a liderança ou encerre o clã antes de sair.", ephemeral=True)
        view = ConfirmClanActionView(self.cog, self.clan_id, "leave", interaction.user.id)
        await interaction.response.send_message("Confirme a saída. Seu acesso aos canais privados será removido.", view=view, ephemeral=True)

    @discord.ui.button(label="Transferir liderança", style=discord.ButtonStyle.secondary, emoji="👑", row=1)
    async def transfer(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = await self.cog.member_role(interaction.guild.id, self.clan_id, interaction.user.id)
        if role != "leader":
            return await interaction.response.send_message("Somente o líder atual pode transferir a liderança.", ephemeral=True)
        await interaction.response.edit_message(content="Escolha um integrante atual para receber a liderança:", embed=None, view=TransferLeaderView(self.cog, self.clan_id, interaction.user.id))

    @discord.ui.button(label="Encerrar clã", style=discord.ButtonStyle.danger, emoji="🗡️", row=1)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = await self.cog.member_role(interaction.guild.id, self.clan_id, interaction.user.id)
        if role != "leader":
            return await interaction.response.send_message("Somente o líder pode solicitar o encerramento.", ephemeral=True)
        row = await self.cog.get_clan(interaction.guild.id, self.clan_id)
        text = (f"Encerrar **{row['name']}**? O registro histórico e as estatísticas serão preservados; "
                "a categoria e os canais do clã serão removidos quando as permissões permitirem.")
        await interaction.response.send_message(text, view=ConfirmClanActionView(self.cog, self.clan_id, "close", interaction.user.id), ephemeral=True)

    @discord.ui.button(label="Nomear oficial", style=discord.ButtonStyle.secondary, emoji="🛡️", row=3)
    async def promote_officer(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self.cog.member_role(interaction.guild.id, self.clan_id, interaction.user.id) != "leader":
            return await interaction.response.send_message("Somente o líder pode nomear oficiais.", ephemeral=True)
        await interaction.response.send_message("Selecione um integrante para nomear oficial:", view=OfficerActionView(self.cog, self.clan_id, True, interaction.user.id), ephemeral=True)

    @discord.ui.button(label="Remover oficial", style=discord.ButtonStyle.secondary, emoji="↩️", row=3)
    async def demote_officer(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self.cog.member_role(interaction.guild.id, self.clan_id, interaction.user.id) != "leader":
            return await interaction.response.send_message("Somente o líder pode remover oficiais.", ephemeral=True)
        await interaction.response.send_message("Selecione o oficial que retornará a integrante:", view=OfficerActionView(self.cog, self.clan_id, False, interaction.user.id), ephemeral=True)


class TransferLeaderView(ClanScopedView):
    def __init__(self, cog: "Clans", clan_id: int, leader_id: int):
        super().__init__(cog, timeout=180)
        self.clan_id, self.leader_id = int(clan_id), int(leader_id)
        self.select = discord.ui.UserSelect(placeholder="Novo líder", min_values=1, max_values=1)
        self.select.callback = self._select
        self.add_item(self.select)

    async def _select(self, interaction: discord.Interaction):
        if interaction.user.id != self.leader_id:
            return await interaction.response.send_message("Somente o líder que iniciou a transferência pode continuar.", ephemeral=True)
        target = self.select.values[0]
        await interaction.response.edit_message(
            content=f"Confirma transferir a liderança do clã para <@{target.id}>? A operação não pode ser desfeita automaticamente.",
            view=ConfirmTransferLeaderView(self.cog, self.clan_id, self.leader_id, target.id),
        )


class ConfirmTransferLeaderView(ClanScopedView):
    def __init__(self, cog: "Clans", clan_id: int, leader_id: int, target_id: int):
        super().__init__(cog, timeout=120)
        self.clan_id = int(clan_id)
        self.leader_id, self.target_id = int(leader_id), int(target_id)

    @discord.ui.button(label="Confirmar transferência", style=discord.ButtonStyle.danger, emoji="👑")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.leader_id:
            return await interaction.response.send_message("Somente o líder que iniciou a operação pode confirmá-la.", ephemeral=True)
        result = await self.cog.transfer_leader(interaction, self.clan_id, self.target_id)
        await interaction.response.edit_message(content=result, view=None)

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.leader_id:
            return await interaction.response.send_message("Somente quem iniciou a operação pode cancelá-la.", ephemeral=True)
        await interaction.response.edit_message(content="Transferência cancelada.", view=None)


class OfficerActionView(ClanScopedView):
    def __init__(self, cog: "Clans", clan_id: int, promote: bool, leader_id: int):
        super().__init__(cog, timeout=120)
        self.clan_id = int(clan_id)
        self.promote, self.leader_id = bool(promote), int(leader_id)
        self.select = discord.ui.UserSelect(placeholder="Selecione um integrante", min_values=1, max_values=1)
        self.select.callback = self._select
        self.add_item(self.select)

    async def _select(self, interaction: discord.Interaction):
        if interaction.user.id != self.leader_id:
            return await interaction.response.send_message("Somente o líder que iniciou a operação pode continuar.", ephemeral=True)
        target = self.select.values[0]
        result = await self.cog.set_officer(interaction, self.clan_id, target.id, self.promote)
        await interaction.response.edit_message(content=result, view=None)


class ConfirmClanActionView(ClanScopedView):
    def __init__(self, cog: "Clans", clan_id: int, action: str, actor_id: int):
        super().__init__(cog, timeout=120)
        self.clan_id, self.action, self.actor_id = int(clan_id), action, int(actor_id)

    @discord.ui.button(label="Confirmar", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.actor_id:
            return await interaction.response.send_message("Somente quem iniciou a operação pode confirmá-la.", ephemeral=True)
        if self.action == "leave":
            result = await self.cog.leave_clan(interaction, self.clan_id, self.actor_id)
            await interaction.response.edit_message(content=result, view=None)
        else:
            await interaction.response.defer(ephemeral=True, thinking=True)
            result = await self.cog.close_clan(interaction, self.clan_id, self.actor_id)
            await interaction.followup.send(result, ephemeral=True)
            try:
                await interaction.message.edit(content="Encerramento processado. Consulte a resposta privada para o resultado.", view=None)
            except discord.HTTPException:
                pass

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.actor_id:
            return await interaction.response.send_message("Somente quem iniciou a operação pode cancelar.", ephemeral=True)
        await interaction.response.edit_message(content="Operação cancelada.", view=None)


class Clans(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _open_transaction(self):
        """Use a dedicated SQLite connection so unrelated cogs cannot commit a clan transaction."""
        conn = await aiosqlite.connect(self.bot.db.path, timeout=15)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA foreign_keys=ON")
        await conn.execute("BEGIN IMMEDIATE")
        return conn

    @staticmethod
    async def _tx_one(conn, sql, args=()):
        async with conn.execute(sql, args) as cur:
            return await cur.fetchone()

    async def cog_load(self):
        # O registro persistente reaplica os custom_ids após reinicializações.
        self.bot.add_view(ClansPublicView(self))

    async def get_clan(self, guild_id: int, clan_id: int):
        return await self.bot.db._one("SELECT * FROM clans WHERE guild_id=? AND id=?", (int(guild_id), int(clan_id)))

    async def member_count(self, guild_id: int, clan_id: int) -> int:
        row = await self.bot.db._one("SELECT COUNT(*) AS n FROM clan_members WHERE guild_id=? AND clan_id=?", (int(guild_id), int(clan_id)))
        return int(row["n"] if row else 0)

    async def member_role(self, guild_id: int, clan_id: int, user_id: int):
        row = await self.bot.db._one("SELECT role FROM clan_members WHERE guild_id=? AND clan_id=? AND user_id=?", (int(guild_id), int(clan_id), int(user_id)))
        return row["role"] if row else None

    def clan_embed(self, row, count: int) -> discord.Embed:
        vacancies = max(0, MAX_MEMBERS - count)
        embed = discord.Embed(title=f"[{row['tag']}] {row['name']}", description=row["description"] or "Sem descrição cadastrada.", color=0xD4AF37)
        embed.add_field(name="Jogo principal", value=row["main_game"], inline=True)
        embed.add_field(name="Estilo", value=_style_label(row["play_style"]), inline=True)
        embed.add_field(name="Integrantes", value=f"{count}/{MAX_MEMBERS}", inline=True)
        embed.add_field(name="Vagas", value=str(vacancies), inline=True)
        embed.add_field(name="Recrutamento", value=_recruit_label(row["recruitment"]), inline=True)
        embed.add_field(name="Líder", value=f"<@{row['leader_id']}>", inline=True)
        embed.set_footer(text=f"Clã #{row['id']} · canais privados não aparecem nesta ficha pública")
        return embed

    async def create_clan(self, interaction: discord.Interaction, name: str, tag: str, game: str, style: str, description: str) -> str:
        guild = interaction.guild
        user = interaction.user
        if guild is None or not isinstance(user, discord.Member):
            return "Criação de clã disponível somente dentro de um servidor."
        if not await module_enabled(self.bot, guild.id, "clans", True):
            return "O Sistema de Clãs está desativado neste servidor."
        if not re.fullmatch(r"[\w -]{3,32}", name, flags=re.UNICODE) or len(name.strip()) < 3:
            return "O nome precisa ter de 3 a 32 caracteres e não pode conter menções ou caracteres de controle."
        if not re.fullmatch(r"[A-Z0-9]{2,5}", tag):
            return "A sigla deve ter de 2 a 5 letras ou números."
        if not game or len(game) > 50 or len(description) > 200:
            return "Confira o tamanho do jogo principal e da descrição."
        if style not in STYLES:
            return "Estilo de jogo inválido."

        default_recruitment = await get_setting(self.bot, guild.id, "clans_default_recruitment", "applications")
        recruitment = default_recruitment if default_recruitment in ("invite", "applications", "mixed") else "applications"
        slug = _slug(name)
        conn = await self._open_transaction()
        try:
            if await self._tx_one(conn, "SELECT id FROM clans WHERE guild_id=? AND creator_id=?", (guild.id, user.id)):
                await conn.rollback()
                return "Você já criou um clã neste servidor. A política padrão não permite criar outro mesmo após sair ou encerrar."
            if await self._tx_one(conn, "SELECT clan_id FROM clan_members WHERE guild_id=? AND user_id=?", (guild.id, user.id)):
                await conn.rollback()
                return "Você já pertence a um clã. Saia dele antes de fundar outro."
            if await self._tx_one(conn, "SELECT id FROM clans WHERE guild_id=? AND slug=? AND status!='closed'", (guild.id, slug)):
                await conn.rollback()
                return "Já existe um clã com nome semelhante. Escolha outro nome."
            async with conn.execute(
                "INSERT INTO clans(guild_id,name,tag,slug,description,main_game,play_style,creator_id,leader_id,status,recruitment) "
                "VALUES(?,?,?,?,?,?,?,?,?,'provisioning',?)",
                (guild.id, name, tag, slug, description, game, STYLE_TO_DB[style], user.id, user.id, recruitment),
            ) as cur:
                clan_id = int(cur.lastrowid)
            await conn.execute("INSERT INTO clan_members(guild_id,clan_id,user_id,role) VALUES(?,?,?,'leader')", (guild.id, clan_id, user.id))
            await conn.commit()
        except sqlite3.IntegrityError as exc:
            await conn.rollback()
            if "clan_member_limit" in str(exc):
                return f"O clã atingiu o limite de {MAX_MEMBERS} integrantes."
            return "Não foi possível registrar o clã: nome, sigla ou limite exclusivo já utilizado."
        finally:
            await conn.close()

        channel_result = await self._create_private_space(guild, user, clan_id, name)
        status = "active" if channel_result else "degraded"
        await self.bot.db.conn.execute("UPDATE clans SET status=?, updated_at=CURRENT_TIMESTAMP WHERE guild_id=? AND id=?", (status, guild.id, clan_id))
        await self.bot.db.conn.commit()
        action = "clan_created" if channel_result else "clan_provision_failed"
        await audit(self.bot, guild.id, user.id, action, f"clan_id={clan_id}", after=name, result="success" if channel_result else "partial")
        if channel_result:
            return f"Clã **[{tag}] {name}** criado. A categoria privada e os canais foram provisionados. Recrutamento: **{_recruit_label(recruitment)}**."
        return (f"O clã **[{tag}] {name}** foi registrado, mas a criação de algum recurso do Discord falhou. "
                "O registro foi preservado como `degraded`; a equipe pode usar `/adm` → Sistema de Clãs → Reparar recursos para tentar corrigir. "
                "Verifique se o bot tem Gerenciar Canais e Gerenciar Permissões.")

    async def _create_private_space(self, guild: discord.Guild, leader: discord.Member | None, clan_id: int, name: str) -> bool:
        row = await self.get_clan(guild.id, clan_id)
        category = guild.get_channel(int(row["category_id"])) if row and row["category_id"] else None
        if not isinstance(category, discord.CategoryChannel):
            category = None
        try:
            bot_member = guild.me or (guild.get_member(self.bot.user.id) if self.bot.user else None)
            overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=False)}
            if bot_member:
                overwrites[bot_member] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, read_message_history=True,
                    manage_channels=True, manage_roles=True, connect=True, speak=True,
                )
            if leader is not None:
                overwrites[leader] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, read_message_history=True, connect=True, speak=True,
                )
            for setting_key in ("admin_role_id", "moderation_role_id"):
                role_id = await get_setting(self.bot, guild.id, setting_key, 0)
                role = guild.get_role(int(role_id)) if role_id else None
                if role:
                    overwrites[role] = discord.PermissionOverwrite(
                        view_channel=True, send_messages=True, read_message_history=True, connect=True, speak=True,
                    )

            # Reaplica a lista de membros persistida em uma única allowlist de overwrites.
            # Ao editar uma categoria existente, substituir o mapa remove permissões antigas
            # que poderiam conceder acesso a cargos externos ao clã.
            member_rows = await self.bot.db._all(
                "SELECT user_id FROM clan_members WHERE guild_id=? AND clan_id=?",
                (int(guild.id), int(clan_id)),
            )
            for member_row in member_rows:
                member_id = int(member_row["user_id"])
                member = leader if leader is not None and leader.id == member_id else guild.get_member(member_id)
                if member is None:
                    try:
                        member = await guild.fetch_member(member_id)
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                        member = None
                if member is not None:
                    overwrites[member] = discord.PermissionOverwrite(
                        view_channel=True, send_messages=True, read_message_history=True,
                        connect=True, speak=True,
                    )

            if category is None:
                safe_name = f"cla-{_slug(name)}"[:90]
                category = await guild.create_category(
                    safe_name, overwrites=overwrites,
                    reason=f"Quase Pro: provisionamento do clã #{clan_id}",
                )
                await self.bot.db.conn.execute(
                    "UPDATE clans SET category_id=? WHERE guild_id=? AND id=?",
                    (category.id, guild.id, clan_id),
                )
                await self.bot.db.conn.commit()
            else:
                await category.edit(
                    overwrites=overwrites,
                    reason=f"Quase Pro: reconciliar allowlist privada do clã #{clan_id}",
                )

            channel_defs = (
                ("chat_channel_id", "conversa", "text"),
                ("announcements_id", "anuncios-do-cla", "text"),
                ("strategies_id", "estrategias-e-builds", "text"),
                ("voice_channel_id", "sala-do-cla", "voice"),
            )
            for field, channel_name, kind in channel_defs:
                row = await self.get_clan(guild.id, clan_id)
                current_id = row[field] if row else None
                channel = guild.get_channel(int(current_id)) if current_id else None
                valid_type = isinstance(channel, discord.VoiceChannel) if kind == "voice" else isinstance(channel, discord.TextChannel)
                if not valid_type:
                    channel = None
                if channel is None:
                    if kind == "voice":
                        channel = await category.create_voice_channel(
                            channel_name, overwrites=category.overwrites,
                            reason=f"Quase Pro: canal do clã #{clan_id}",
                        )
                    else:
                        channel = await category.create_text_channel(
                            channel_name, overwrites=category.overwrites,
                            reason=f"Quase Pro: canal do clã #{clan_id}",
                        )
                    await self.bot.db.conn.execute(
                        f"UPDATE clans SET {field}=? WHERE guild_id=? AND id=?",
                        (channel.id, guild.id, clan_id),
                    )
                    await self.bot.db.conn.commit()
                elif channel.category_id != category.id:
                    await channel.edit(
                        category=category, sync_permissions=True,
                        reason=f"Quase Pro: reparar categoria do clã #{clan_id}",
                    )
                else:
                    await channel.edit(
                        sync_permissions=True,
                        reason=f"Quase Pro: sincronizar permissões do clã #{clan_id}",
                    )
            return True
        except Exception as exc:
            # Estado parcial permanece registrado para diagnóstico e reparo posterior.
            await self.bot.db.conn.execute(
                "UPDATE clans SET updated_at=CURRENT_TIMESTAMP WHERE guild_id=? AND id=?",
                (guild.id, clan_id),
            )
            await self.bot.db.conn.commit()
            print(f"[clans] Falha ao provisionar clã {clan_id} em {guild.id}: {exc!r}")
            return False

    async def repair_guild_clans(self, guild: discord.Guild, actor_id: int) -> list[str]:
        """Reconcilia recursos ausentes dos clãs sem excluir registros históricos."""
        rows = await self.bot.db._all(
            "SELECT id,name,leader_id,status FROM clans WHERE guild_id=? AND status IN ('active','degraded') ORDER BY id",
            (int(guild.id),),
        )
        if not rows:
            return ["Não há clãs ativos/degradados para verificar."]
        results = []
        for row in rows:
            leader = guild.get_member(int(row["leader_id"]))
            if leader is None:
                try:
                    leader = await guild.fetch_member(int(row["leader_id"]))
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    leader = None
            repaired = await self._create_private_space(guild, leader, int(row["id"]), row["name"])
            status = "active" if repaired and leader is not None else "degraded"
            await self.bot.db.conn.execute(
                "UPDATE clans SET status=?,updated_at=CURRENT_TIMESTAMP WHERE guild_id=? AND id=?",
                (status, int(guild.id), int(row["id"])),
            )
            await self.bot.db.conn.commit()
            await audit(
                self.bot, guild.id, actor_id,
                "clan_resources_repaired" if status == "active" else "clan_resources_repair_partial",
                f"clan_id={row['id']}", before=row["status"], after=status,
                result="success" if status == "active" else "partial",
            )
            if status == "active":
                results.append(f"Clã #{row['id']} **{row['name']}**: recursos e permissões reconciliados.")
            elif leader is None and repaired:
                results.append(f"Clã #{row['id']} **{row['name']}**: recursos criados, mas líder não está acessível no servidor; permanece degradado.")
            else:
                results.append(f"Clã #{row['id']} **{row['name']}**: reparo parcial/falhou; verifique Gerenciar Canais, permissões e hierarquia do bot.")
        return results

    async def explore_view(self, guild_id: int, page: int = 0):
        rows = await self.bot.db._all(
            "SELECT c.*, COUNT(m.user_id) AS member_count FROM clans c "
            "LEFT JOIN clan_members m ON m.guild_id=c.guild_id AND m.clan_id=c.id "
            "WHERE c.guild_id=? AND c.status='active' AND c.recruitment IN ('applications','mixed') "
            "GROUP BY c.id ORDER BY c.created_at DESC", (int(guild_id),),
        )
        embed = discord.Embed(title="Explorar clãs", description="Selecione um clã para ver a ficha ou enviar candidatura. Canais privados nunca são exibidos.", color=0xC0C0C0)
        if not rows:
            embed.description = "Ainda não há clãs ativos com candidaturas abertas. Você pode criar um pelo Salão dos Juramentos."
        else:
            lines = []
            for row in rows[page * 25:(page + 1) * 25]:
                lines.append(f"**[{row['tag']}] {row['name']}** — {row['main_game']} · {await self.member_count(guild_id, row['id'])}/{MAX_MEMBERS} integrantes")
            embed.description = "\n".join(lines) or "Nenhum clã nesta página."
            embed.set_footer(text=f"Página {page + 1} · {len(rows)} clã(s)")
        return embed, ExploreClansView(self, int(guild_id), list(rows), page)

    async def apply_to_clan(self, interaction: discord.Interaction, clan_id: int, message: str) -> str:
        if interaction.guild is None:
            return "Candidaturas só podem ser enviadas dentro do servidor."
        guild_id, user_id = interaction.guild.id, interaction.user.id
        if not await module_enabled(self.bot, guild_id, "clans", True):
            return "O Sistema de Clãs está desativado neste servidor."
        row = await self.get_clan(guild_id, clan_id)
        if not row or row["status"] != "active" or row["recruitment"] not in ("applications", "mixed"):
            return "Este clã não está aceitando candidaturas."
        membership = await self.bot.db._one("SELECT clan_id FROM clan_members WHERE guild_id=? AND user_id=?", (guild_id, user_id))
        if membership:
            return "Você já pertence a um clã neste servidor."
        count = await self.member_count(guild_id, clan_id)
        if count >= MAX_MEMBERS:
            return f"Este clã está cheio ({MAX_MEMBERS}/{MAX_MEMBERS})."
        duplicate = await self.bot.db._one("SELECT id FROM clan_applications WHERE guild_id=? AND clan_id=? AND user_id=? AND status='pending'", (guild_id, clan_id, user_id))
        if duplicate:
            return "Você já tem uma candidatura pendente para este clã."
        try:
            await self.bot.db.conn.execute("INSERT INTO clan_applications(guild_id,clan_id,user_id,message) VALUES(?,?,?,?)", (guild_id, clan_id, user_id, message))
            await self.bot.db.conn.commit()
        except sqlite3.IntegrityError:
            await self.bot.db.conn.rollback()
            return "Já existe uma candidatura pendente para esse clã."
        await audit(self.bot, guild_id, user_id, "clan_application_created", f"clan_id={clan_id}")
        return f"Candidatura enviada para **[{row['tag']}] {row['name']}**. A liderança receberá a solicitação na área de gerenciamento do clã."

    async def show_my_clan(self, interaction: discord.Interaction):
        row = await self.bot.db._one(
            "SELECT c.*, m.role AS my_role FROM clan_members m JOIN clans c ON c.id=m.clan_id AND c.guild_id=m.guild_id "
            "WHERE m.guild_id=? AND m.user_id=? AND c.status!='closed'",
            (interaction.guild.id, interaction.user.id),
        )
        if not row:
            return await interaction.response.send_message("Você não está em um clã ativo. Explore clãs ou crie o seu no Salão dos Juramentos.", ephemeral=True)
        count = await self.member_count(interaction.guild.id, row["id"])
        embed = self.clan_embed(row, count)
        embed.add_field(name="Sua função", value={"leader": "Líder", "officer": "Oficial", "member": "Integrante"}.get(row["my_role"], row["my_role"]), inline=True)
        member_rows = await self.bot.db._all("SELECT user_id,role FROM clan_members WHERE guild_id=? AND clan_id=? ORDER BY CASE role WHEN 'leader' THEN 0 WHEN 'officer' THEN 1 ELSE 2 END, joined_at", (interaction.guild.id, row["id"]))
        embed.add_field(name="Integrantes", value="\n".join(f"{'👑' if m['role']=='leader' else '🛡️' if m['role']=='officer' else '•'} <@{m['user_id']}>" for m in member_rows) or "—", inline=False)
        await interaction.response.send_message(embed=embed, view=ClanManageView(self, row["id"]), ephemeral=True)

    async def issue_invite(self, interaction: discord.Interaction, clan_id: int, target: discord.Member) -> str:
        guild_id = interaction.guild.id
        role = await self.member_role(guild_id, clan_id, interaction.user.id)
        if role not in ("leader", "officer"):
            return "Somente liderança e oficiais podem convidar integrantes."
        if target.bot or target.id == interaction.user.id:
            return "Não é possível convidar bots ou convidar a si mesmo."
        row = await self.get_clan(guild_id, clan_id)
        if not row or row["status"] != "active" or row["recruitment"] == "applications":
            return "Este clã não está aceitando convites."
        if await self.member_count(guild_id, clan_id) >= MAX_MEMBERS:
            return f"O clã está cheio ({MAX_MEMBERS}/{MAX_MEMBERS})."
        already = await self.bot.db._one("SELECT clan_id FROM clan_members WHERE guild_id=? AND user_id=?", (guild_id, target.id))
        if already:
            return "Esse membro já pertence a um clã neste servidor."
        pending = await self.bot.db._one("SELECT id FROM clan_invites WHERE guild_id=? AND clan_id=? AND invitee_id=? AND status='pending'", (guild_id, clan_id, target.id))
        if pending:
            return "Já existe um convite pendente para esse membro."
        exp = (datetime.now(timezone.utc) + timedelta(days=INVITE_DAYS)).isoformat()
        try:
            await self.bot.db.conn.execute("INSERT INTO clan_invites(guild_id,clan_id,inviter_id,invitee_id,expires_at) VALUES(?,?,?,?,?)", (guild_id, clan_id, interaction.user.id, target.id, exp))
            await self.bot.db.conn.commit()
        except sqlite3.IntegrityError:
            await self.bot.db.conn.rollback()
            return "Já existe um convite pendente para esse membro."
        await audit(self.bot, guild_id, interaction.user.id, "clan_invite_created", f"clan_id={clan_id};invitee={target.id}")
        try:
            await target.send(f"Você recebeu um convite para **[{row['tag']}] {row['name']}** no servidor **{interaction.guild.name}**. Abra o Salão dos Juramentos e clique em **Meus convites**. O convite expira em {INVITE_DAYS} dias.")
        except discord.Forbidden:
            pass
        return f"Convite registrado para {target.mention}. Ele aparece em Meus convites; expira em {INVITE_DAYS} dias."

    async def invites_view(self, guild_id: int, user_id: int):
        rows = await self.bot.db._all(
            "SELECT i.*,c.name,c.tag,c.main_game FROM clan_invites i JOIN clans c ON c.id=i.clan_id AND c.guild_id=i.guild_id "
            "WHERE i.guild_id=? AND i.invitee_id=? AND i.status='pending' ORDER BY i.created_at DESC LIMIT 25", (guild_id, user_id),
        )
        valid = []
        now = datetime.now(timezone.utc)
        for row in rows:
            try:
                expired = datetime.fromisoformat(row["expires_at"]) <= now
            except ValueError:
                expired = True
            if expired:
                await self.bot.db.conn.execute("UPDATE clan_invites SET status='expired' WHERE id=? AND status='pending'", (row["id"],))
            else:
                valid.append(row)
        await self.bot.db.conn.commit()
        embed = discord.Embed(title="Meus convites", description="Selecione um convite e aceite ou recuse.", color=0xC0C0C0)
        if not valid:
            embed.description = "Você não possui convites pendentes."
        else:
            embed.description = "\n".join(f"**[{r['tag']}] {r['name']}** — {r['main_game']} · convite de <@{r['inviter_id']}>" for r in valid)
        return embed, InviteListView(self, guild_id, user_id, valid)

    async def resolve_invite(self, interaction: discord.Interaction, invite_id: int, accept: bool) -> str:
        guild_id, user_id = interaction.guild.id, interaction.user.id
        if not accept:
            async with self.bot.db.conn.execute(
                "UPDATE clan_invites SET status='rejected' WHERE guild_id=? AND id=? AND invitee_id=? AND status='pending'",
                (guild_id, invite_id, user_id),
            ) as cur:
                changed = cur.rowcount
            await self.bot.db.conn.commit()
            if changed == 0:
                return "Este convite não está mais pendente."
            return "Convite recusado."

        conn = await self._open_transaction()
        try:
            row = await self._tx_one(conn,
                "SELECT * FROM clan_invites WHERE guild_id=? AND id=? AND invitee_id=? AND status='pending'",
                (guild_id, invite_id, user_id),
            )
            if not row:
                await conn.rollback()
                return "Este convite não está mais pendente."
            try:
                if datetime.fromisoformat(row["expires_at"]) <= datetime.now(timezone.utc):
                    await conn.execute("UPDATE clan_invites SET status='expired' WHERE id=? AND status='pending'", (invite_id,))
                    await conn.commit()
                    return "Este convite expirou."
            except ValueError:
                await conn.rollback()
                return "O prazo deste convite é inválido. Peça um novo convite."
            clan = await self._tx_one(conn, "SELECT * FROM clans WHERE guild_id=? AND id=?", (guild_id, row["clan_id"]))
            if not clan or clan["status"] != "active":
                await conn.rollback()
                return "Este clã não está ativo."
            count_row = await self._tx_one(conn, "SELECT COUNT(*) AS n FROM clan_members WHERE guild_id=? AND clan_id=?", (guild_id, row["clan_id"]))
            if int(count_row["n"]) >= MAX_MEMBERS:
                await conn.rollback()
                return f"O clã encheu antes de sua entrada. Limite: {MAX_MEMBERS} integrantes."
            existing = await self._tx_one(conn, "SELECT clan_id FROM clan_members WHERE guild_id=? AND user_id=?", (guild_id, user_id))
            if existing:
                await conn.rollback()
                return "Você já pertence a um clã neste servidor."
            await conn.execute("INSERT INTO clan_members(guild_id,clan_id,user_id,role) VALUES(?,?,?,'member')", (guild_id, row["clan_id"], user_id))
            async with conn.execute("UPDATE clan_invites SET status='accepted' WHERE id=? AND status='pending'", (invite_id,)) as cur:
                if cur.rowcount != 1:
                    await conn.rollback()
                    return "Este convite já foi processado."
            await conn.commit()
        except sqlite3.IntegrityError as exc:
            await conn.rollback()
            if "clan_member_limit" in str(exc):
                return f"O clã já atingiu o limite de {MAX_MEMBERS} integrantes."
            return "Não foi possível entrar no clã: você pode já ter entrado em outro clã."
        finally:
            await conn.close()

        member = interaction.guild.get_member(user_id)
        if member is None:
            try:
                member = await interaction.guild.fetch_member(user_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                member = None
        permissions_ok = await self._set_member_permission(interaction.guild, row["clan_id"], member, True)
        await audit(self.bot, guild_id, user_id, "clan_invite_accepted", f"clan_id={row['clan_id']}", result="success" if permissions_ok else "partial")
        if not permissions_ok:
            return "Convite aceito e vínculo registrado, mas as permissões do Discord não foram aplicadas. Avise a equipe para corrigir a integridade pelo `/adm`."
        return "Convite aceito. Seu acesso aos canais privados foi atualizado."

    async def pending_applications(self, guild_id: int, clan_id: int):
        return await self.bot.db._all("SELECT * FROM clan_applications WHERE guild_id=? AND clan_id=? AND status='pending' ORDER BY created_at", (guild_id, clan_id))

    async def resolve_application(self, interaction: discord.Interaction, clan_id: int, app_id: int, accept: bool) -> str:
        guild_id = interaction.guild.id
        role = await self.member_role(guild_id, clan_id, interaction.user.id)
        if role not in ("leader", "officer"):
            return "Somente liderança e oficiais podem decidir candidaturas."
        if not accept:
            async with self.bot.db.conn.execute(
                "UPDATE clan_applications SET status='rejected',decided_by=?,decided_at=CURRENT_TIMESTAMP WHERE guild_id=? AND clan_id=? AND id=? AND status='pending'",
                (interaction.user.id, guild_id, clan_id, app_id),
            ) as cur:
                changed = cur.rowcount
            await self.bot.db.conn.commit()
            if changed != 1:
                return "Esta candidatura já foi processada."
            await audit(self.bot, guild_id, interaction.user.id, "clan_application_rejected", f"application_id={app_id}")
            return "Candidatura rejeitada."

        conn = await self._open_transaction()
        try:
            app = await self._tx_one(conn,
                "SELECT * FROM clan_applications WHERE guild_id=? AND clan_id=? AND id=? AND status='pending'",
                (guild_id, clan_id, app_id),
            )
            if not app:
                await conn.rollback()
                return "Esta candidatura já foi processada."
            current_role = await self._tx_one(conn,
                "SELECT role FROM clan_members WHERE guild_id=? AND clan_id=? AND user_id=?",
                (guild_id, clan_id, interaction.user.id),
            )
            if not current_role or current_role["role"] not in ("leader", "officer"):
                await conn.rollback()
                return "Sua permissão de liderança mudou; a candidatura não foi alterada."
            clan = await self._tx_one(conn, "SELECT status FROM clans WHERE guild_id=? AND id=?", (guild_id, clan_id))
            if not clan or clan["status"] != "active":
                await conn.rollback()
                return "Este clã não está ativo."
            count = await self._tx_one(conn, "SELECT COUNT(*) AS n FROM clan_members WHERE guild_id=? AND clan_id=?", (guild_id, clan_id))
            if int(count["n"]) >= MAX_MEMBERS:
                await conn.rollback()
                return f"O clã está cheio ({MAX_MEMBERS}/{MAX_MEMBERS})."
            existing = await self._tx_one(conn, "SELECT clan_id FROM clan_members WHERE guild_id=? AND user_id=?", (guild_id, app["user_id"]))
            if existing:
                await conn.rollback()
                return "Esse membro já pertence a um clã e não pode aceitar a candidatura."
            await conn.execute("INSERT INTO clan_members(guild_id,clan_id,user_id,role) VALUES(?,?,?,'member')", (guild_id, clan_id, app["user_id"]))
            async with conn.execute("UPDATE clan_applications SET status='accepted',decided_by=?,decided_at=CURRENT_TIMESTAMP WHERE id=? AND status='pending'", (interaction.user.id, app_id)) as cur:
                if cur.rowcount != 1:
                    await conn.rollback()
                    return "Esta candidatura já foi processada."
            await conn.commit()
        except sqlite3.IntegrityError as exc:
            await conn.rollback()
            if "clan_member_limit" in str(exc):
                return f"O clã atingiu o limite de {MAX_MEMBERS} integrantes."
            return "Não foi possível aceitar a candidatura: o membro pode ter entrado em outro clã."
        finally:
            await conn.close()

        member = interaction.guild.get_member(app["user_id"])
        if member is None:
            try:
                member = await interaction.guild.fetch_member(app["user_id"])
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                member = None
        permissions_ok = await self._set_member_permission(interaction.guild, clan_id, member, True)
        await audit(self.bot, guild_id, interaction.user.id, "clan_application_accepted", f"application_id={app_id}", result="success" if permissions_ok else "partial")
        if not permissions_ok:
            return f"Candidatura de <@{app['user_id']}> aprovada e registro salvo, mas as permissões do Discord falharam. Avise a equipe para usar `/adm` → Sistema de Clãs → Reparar recursos."
        return f"Candidatura de <@{app['user_id']}> aprovada; permissões privadas atualizadas."

    async def _set_member_permission(self, guild: discord.Guild, clan_id: int, member: discord.Member | None, allow: bool) -> bool:
        if member is None:
            return False
        row = await self.get_clan(guild.id, clan_id)
        if not row or not row["category_id"]:
            return False
        category = guild.get_channel(int(row["category_id"]))
        if not isinstance(category, discord.CategoryChannel):
            return False
        try:
            if allow:
                await category.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True, connect=True, speak=True, reason=f"Clã #{clan_id}: entrada de integrante")
            else:
                await category.set_permissions(member, overwrite=None, reason=f"Clã #{clan_id}: remoção de integrante")
            for field in ("chat_channel_id", "announcements_id", "strategies_id", "voice_channel_id"):
                channel_id = row[field]
                channel = guild.get_channel(int(channel_id)) if channel_id else None
                if channel is None:
                    continue
                if allow:
                    await channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True, connect=True, speak=True, reason=f"Clã #{clan_id}: entrada de integrante")
                else:
                    await channel.set_permissions(member, overwrite=None, reason=f"Clã #{clan_id}: remoção de integrante")
            return True
        except (discord.Forbidden, discord.HTTPException) as exc:
            print(f"[clans] Falha atualizando permissões do membro {member.id}: {exc!r}")
            return False

    async def leave_clan(self, interaction: discord.Interaction, clan_id: int, user_id: int) -> str:
        role = await self.member_role(interaction.guild.id, clan_id, user_id)
        if role == "leader":
            return "O líder precisa transferir a liderança ou encerrar o clã antes de sair."
        record = await self.bot.db._one("SELECT role,joined_at FROM clan_members WHERE guild_id=? AND clan_id=? AND user_id=?", (interaction.guild.id, clan_id, user_id))
        if record:
            await self.bot.db.conn.execute("INSERT INTO clan_members_history(guild_id,clan_id,user_id,role,joined_at,exit_reason) VALUES(?,?,?,?,?,'left')", (interaction.guild.id, clan_id, user_id, record['role'], record['joined_at']))
        await self.bot.db.conn.execute("DELETE FROM clan_members WHERE guild_id=? AND clan_id=? AND user_id=?", (interaction.guild.id, clan_id, user_id))
        await self.bot.db.conn.commit()
        await self._set_member_permission(interaction.guild, clan_id, interaction.guild.get_member(user_id), False)
        await audit(self.bot, interaction.guild.id, user_id, "clan_member_left", f"clan_id={clan_id}")
        return "Você saiu do clã e o acesso à categoria privada foi removido."

    async def transfer_leader(self, interaction: discord.Interaction, clan_id: int, target_id: int) -> str:
        guild_id = interaction.guild.id
        conn = await self._open_transaction()
        try:
            leader = await self._tx_one(conn, "SELECT role FROM clan_members WHERE guild_id=? AND clan_id=? AND user_id=?", (guild_id, clan_id, interaction.user.id))
            target = await self._tx_one(conn, "SELECT role FROM clan_members WHERE guild_id=? AND clan_id=? AND user_id=?", (guild_id, clan_id, target_id))
            clan = await self._tx_one(conn, "SELECT status FROM clans WHERE guild_id=? AND id=?", (guild_id, clan_id))
            if not leader or leader["role"] != "leader":
                await conn.rollback()
                return "Somente o líder atual pode transferir a liderança."
            if not target:
                await conn.rollback()
                return "O destinatário precisa ser um integrante atual do clã."
            if not clan or clan["status"] != "active":
                await conn.rollback()
                return "Este clã não está ativo."
            await conn.execute("UPDATE clan_members SET role='member' WHERE guild_id=? AND clan_id=? AND user_id=?", (guild_id, clan_id, interaction.user.id))
            await conn.execute("UPDATE clan_members SET role='leader' WHERE guild_id=? AND clan_id=? AND user_id=?", (guild_id, clan_id, target_id))
            await conn.execute("UPDATE clans SET leader_id=?,updated_at=CURRENT_TIMESTAMP WHERE guild_id=? AND id=?", (target_id, guild_id, clan_id))
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise
        finally:
            await conn.close()
        await audit(self.bot, guild_id, interaction.user.id, "clan_leadership_transferred", f"clan_id={clan_id};new_leader={target_id}")
        return f"Liderança transferida para <@{target_id}>. O histórico do clã foi preservado."

    async def close_clan(self, interaction: discord.Interaction, clan_id: int, actor_id: int) -> str:
        guild_id = interaction.guild.id
        if actor_id != interaction.user.id or await self.member_role(guild_id, clan_id, actor_id) != "leader":
            return "Somente o líder atual pode confirmar o encerramento."
        row = await self.get_clan(guild_id, clan_id)
        if not row or row["status"] == "closed":
            return "Este clã já está encerrado ou não existe."
        await self.bot.db.conn.execute("UPDATE clans SET status='closed', closed_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE guild_id=? AND id=?", (guild_id, clan_id))
        await self.bot.db.conn.execute("UPDATE clan_invites SET status='revoked' WHERE guild_id=? AND clan_id=? AND status='pending'", (guild_id, clan_id))
        await self.bot.db.conn.execute("UPDATE clan_applications SET status='withdrawn', decided_at=CURRENT_TIMESTAMP WHERE guild_id=? AND clan_id=? AND status='pending'", (guild_id, clan_id))
        members = await self.bot.db._all("SELECT user_id,role,joined_at FROM clan_members WHERE guild_id=? AND clan_id=?", (guild_id, clan_id))
        for m in members:
            await self.bot.db.conn.execute("INSERT INTO clan_members_history(guild_id,clan_id,user_id,role,joined_at,exit_reason) VALUES(?,?,?,?,?,'clan_closed')", (guild_id, clan_id, m['user_id'], m['role'], m['joined_at']))
        await self.bot.db.conn.execute("DELETE FROM clan_members WHERE guild_id=? AND clan_id=?", (guild_id, clan_id))
        await self.bot.db.conn.commit()
        for m in members:
            await self._set_member_permission(interaction.guild, clan_id, interaction.guild.get_member(m["user_id"]), False)
        deleted, failed = 0, []
        for field in ("chat_channel_id", "announcements_id", "strategies_id", "voice_channel_id", "category_id"):
            value = row[field]
            channel = interaction.guild.get_channel(int(value)) if value else None
            if channel:
                try:
                    await channel.delete(reason=f"Quase Pro: encerramento do clã #{clan_id}")
                    deleted += 1
                except (discord.Forbidden, discord.HTTPException) as exc:
                    failed.append(f"{field}: {type(exc).__name__}")
        await audit(self.bot, guild_id, actor_id, "clan_closed", f"clan_id={clan_id};deleted={deleted};failed={','.join(failed)}", result="partial" if failed else "success")
        if failed:
            return f"Clã encerrado e registro preservado. Recursos removidos: {deleted}. Falhas: {', '.join(failed)}. A equipe pode concluir a limpeza pelo diagnóstico."
        return f"Clã **{row['name']}** encerrado. Recursos removidos: {deleted}. Histórico e estatísticas foram preservados."

    async def set_recruitment(self, interaction: discord.Interaction, clan_id: int, mode: str) -> str:
        if mode not in ("invite", "applications", "mixed"):
            return "Modo de recrutamento inválido."
        if await self.member_role(interaction.guild.id, clan_id, interaction.user.id) != "leader":
            return "Somente o líder pode alterar o recrutamento."
        async with self.bot.db.conn.execute(
            "UPDATE clans SET recruitment=?,updated_at=CURRENT_TIMESTAMP WHERE guild_id=? AND id=? AND leader_id=? AND status='active'",
            (mode, interaction.guild.id, clan_id, interaction.user.id),
        ) as cur:
            changed = cur.rowcount
        await self.bot.db.conn.commit()
        if changed != 1:
            return "O clã não está ativo ou a liderança mudou."
        await audit(self.bot, interaction.guild.id, interaction.user.id, "clan_recruitment_changed", f"clan_id={clan_id}", after=mode)
        return f"Recrutamento atualizado para **{_recruit_label(mode)}**."

    async def set_officer(self, interaction: discord.Interaction, clan_id: int, target_id: int, promote: bool) -> str:
        guild_id = interaction.guild.id
        conn = await self._open_transaction()
        try:
            leader = await self._tx_one(conn, "SELECT role FROM clan_members WHERE guild_id=? AND clan_id=? AND user_id=?", (guild_id, clan_id, interaction.user.id))
            target = await self._tx_one(conn, "SELECT role FROM clan_members WHERE guild_id=? AND clan_id=? AND user_id=?", (guild_id, clan_id, target_id))
            if not leader or leader["role"] != "leader":
                await conn.rollback()
                return "Somente o líder atual pode gerenciar oficiais."
            if not target or target["role"] == "leader":
                await conn.rollback()
                return "O alvo precisa ser integrante atual; a liderança não pode ser alterada por esta ação."
            if promote and target["role"] == "officer":
                await conn.rollback()
                return "Esse integrante já é oficial."
            if not promote and target["role"] != "officer":
                await conn.rollback()
                return "O membro selecionado não é oficial."
            new_role = "officer" if promote else "member"
            await conn.execute("UPDATE clan_members SET role=? WHERE guild_id=? AND clan_id=? AND user_id=?", (new_role, guild_id, clan_id, target_id))
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise
        finally:
            await conn.close()
        action = "clan_officer_appointed" if promote else "clan_officer_removed"
        await audit(self.bot, guild_id, interaction.user.id, action, f"clan_id={clan_id};member={target_id}")
        return f"<@{target_id}> {'foi nomeado oficial' if promote else 'deixou de ser oficial'}."

    async def create_activity(self, interaction: discord.Interaction, clan_id: int, title: str, kind: str, when: str):
        if interaction.guild is None:
            return await interaction.response.send_message("Atividades só podem ser criadas dentro do servidor.", ephemeral=True)
        if not await module_enabled(self.bot, interaction.guild.id, "clans", True):
            return await interaction.response.send_message("O Sistema de Clãs está desativado neste servidor.", ephemeral=True)
        role = await self.member_role(interaction.guild.id, clan_id, interaction.user.id)
        if role not in ("leader", "officer"):
            return await interaction.response.send_message("Somente liderança e oficiais podem organizar atividades.", ephemeral=True)
        await self.bot.db.conn.execute("INSERT INTO clan_activities(guild_id,clan_id,creator_id,title,activity_type,scheduled_at) VALUES(?,?,?,?,?,?)", (interaction.guild.id, clan_id, interaction.user.id, title, kind, when or None))
        await self.bot.db.conn.commit()
        await audit(self.bot, interaction.guild.id, interaction.user.id, "clan_activity_created", f"clan_id={clan_id};title={title}")
        row = await self.get_clan(interaction.guild.id, clan_id)
        category_id = row["category_id"] if row else None
        channel = interaction.guild.get_channel(int(row["announcements_id"])) if row and row["announcements_id"] else None
        if channel:
            try:
                await channel.send(f"⚔️ **Nova atividade do clã: {title}**\nTipo: {kind}\nQuando: {when or 'A combinar'}\nOrganizada por <@{interaction.user.id}>")
            except discord.HTTPException:
                pass
        await interaction.response.send_message(f"Atividade **{title}** registrada. Ela aparece no histórico do clã; nenhuma pontuação automática foi concedida.", ephemeral=True)

    async def show_activities(self, interaction: discord.Interaction):
        rows = await self.bot.db._all(
            "SELECT a.*,c.name,c.tag FROM clan_activities a JOIN clans c ON c.id=a.clan_id AND c.guild_id=a.guild_id "
            "WHERE a.guild_id=? AND c.status='active' ORDER BY a.created_at DESC LIMIT 12", (interaction.guild.id,),
        )
        embed = discord.Embed(title="Atividades coletivas", description="\n".join(f"**[{r['tag']}] {r['name']}** — {r['title']} · {r['activity_type']} · {r['status']}" for r in rows) or "Nenhuma atividade registrada.", color=0xD4AF37)
        embed.set_footer(text="Registro de atividades não concede XP automaticamente; as regras competitivas ainda precisam ser configuradas.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def show_ranking(self, interaction: discord.Interaction):
        rows = await self.bot.db._all(
            "SELECT c.id,c.name,c.tag,"
            "(SELECT COUNT(*) FROM clan_members m WHERE m.guild_id=c.guild_id AND m.clan_id=c.id) AS members,"
            "(SELECT COUNT(*) FROM clan_activities a WHERE a.guild_id=c.guild_id AND a.clan_id=c.id AND a.status='completed') AS completed "
            "FROM clans c WHERE c.guild_id=? AND c.status='active' "
            "ORDER BY completed DESC,members DESC,c.created_at ASC LIMIT 10", (interaction.guild.id,),
        )
        lines = [f"**{i}. [{r['tag']}] {r['name']}** — {r['members']}/{MAX_MEMBERS} membros · {r['completed'] or 0} atividades concluídas" for i, r in enumerate(rows, 1)]
        embed = discord.Embed(title="Ranking de clãs", description="\n".join(lines) or "Ainda não há clãs ativos.", color=0xD4AF37)
        embed.set_footer(text="Ordenação provisória por atividades concluídas e integrantes. XP competitivo não está ativo sem regras aprovadas.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def post_public_panel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        from cogs.admin import is_admin
        if not await is_admin(self.bot, interaction):
            return await interaction.response.send_message("Apenas a equipe administrativa autorizada pode publicar o painel.", ephemeral=True)
        embed = discord.Embed(
            title="⚔️ Salão dos Juramentos",
            description=("Encontre companheiros de jornada, reúna seu clã e organize desafios do Quase Pro.\n\n"
                         f"Cada clã tem até {MAX_MEMBERS} integrantes e uma categoria privada. Use os botões para criar, explorar e gerenciar sua jornada."),
            color=0x0D0D0D,
        )
        embed.add_field(name="Juramentos", value="Cooperação · PvP · Platinas · Exploração", inline=False)
        embed.set_footer(text="A privacidade dos canais não é absoluta contra administradores do servidor.")
        await interaction.response.defer(ephemeral=True, thinking=True)
        # Se já houver painel registrado para este servidor/canal, tenta editar em vez de duplicar.
        setting_key = "clan_hall_message_id"
        old_id = await get_setting(self.bot, interaction.guild.id, setting_key, 0)
        message = None
        if old_id and int(await get_setting(self.bot, interaction.guild.id, "clan_hall_channel_id", 0) or 0) == channel.id:
            try:
                message = await channel.fetch_message(int(old_id))
                if message.author.id != self.bot.user.id:
                    message = None
            except (discord.NotFound, discord.Forbidden, discord.HTTPException, ValueError):
                message = None
        view = ClansPublicView(self)
        if message:
            await message.edit(embed=embed, view=view)
        else:
            message = await channel.send(embed=embed, view=view)
        # Save both IDs, with audit, via the common configuration store.
        from settings_store import set_setting
        await set_setting(self.bot, interaction.guild.id, interaction.user.id, "clan_hall_channel_id", channel.id)
        await set_setting(self.bot, interaction.guild.id, interaction.user.id, "clan_hall_message_id", message.id)
        await interaction.edit_original_response(content=f"Salão dos Juramentos publicado/atualizado em {channel.mention}. Mensagem: `{message.id}`.")


async def setup(bot):
    await bot.add_cog(Clans(bot))
