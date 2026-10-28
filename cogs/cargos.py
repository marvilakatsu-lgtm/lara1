import json
import discord
from discord import app_commands
from discord.ext import commands
from utils import upsert_panel, erro_comando

DEFAULT_ROLES = [
    ("interest_elden_ring", "Elden Ring", "🎮"),
    ("interest_dark_souls", "Dark Souls", "🔥"),
    ("interest_bloodborne", "Bloodborne", "🩸"),
    ("interest_sekiro", "Sekiro", "🥷"),
    ("interest_lies_of_p", "Lies of P", "🦾"),
    ("interest_nightreign", "Nightreign", "🌑"),
    ("notice_videos", "Avisos de vídeos", "📹"),
    ("notice_lives", "Avisos de lives", "🔴"),
    ("events_challenges", "Eventos e desafios", "🏆"),
]
MAX_ROLES = 25


class Verificacao(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Verificar-me", emoji="✅", style=discord.ButtonStyle.success,
                       custom_id="verificar_membro")
    async def verificar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Use este botão dentro do servidor.", ephemeral=True)
            return
        from settings_store import get_setting
        from server_structure import normalize_name
        role_id = await get_setting(interaction.client, interaction.guild.id, "member_role_id", 0)
        cargo = interaction.guild.get_role(int(role_id)) if role_id else None
        if cargo is None:
            cargo = next((r for r in interaction.guild.roles if normalize_name(r.name) == "membro"), None)
        newcomer_id = await get_setting(interaction.client, interaction.guild.id, "role_newcomer_id", 0)
        newcomer = interaction.guild.get_role(int(newcomer_id)) if newcomer_id else None
        if newcomer is None:
            newcomer = next((r for r in interaction.guild.roles if normalize_name(r.name) == "recem-chegado"), None)
        if cargo is None:
            await interaction.response.send_message("Cargo 🟢・Membro não encontrado. Peça à equipe para executar /adm → Organização do servidor.", ephemeral=True)
            return
        try:
            if cargo not in interaction.user.roles:
                await interaction.user.add_roles(cargo, reason="Verificação pelo painel de boas-vindas")
            if newcomer and newcomer in interaction.user.roles:
                await interaction.user.remove_roles(newcomer, reason="Membro concluiu a verificação do servidor")
            await interaction.response.send_message("Acesso de membro confirmado. Bem-vindo(a) ao Quase Pro!", ephemeral=True)
        except (discord.Forbidden, discord.HTTPException):
            await interaction.response.send_message(
                "Não consigo atualizar seus cargos. A equipe deve conferir Gerenciar Cargos e a hierarquia do bot.",
                ephemeral=True)


class CargosView(discord.ui.View):
    """View persistente: cada botão aponta para a posição salva na configuração do servidor."""
    def __init__(self, itens=None):
        super().__init__(timeout=None)
        # Sem configuração: registra todos os IDs possíveis para views antigas persistirem.
        # Com configuração: exibe apenas os botões realmente configurados.
        if itens is None:
            itens = [{"label": "Cargo", "emoji": None} for _ in range(MAX_ROLES)]
            disabled = True
        else:
            disabled = False
        for i, item in enumerate(itens[:MAX_ROLES]):
            button = discord.ui.Button(
                label=item.get("label", "Cargo")[:80],
                emoji=item.get("emoji") or None,
                style=discord.ButtonStyle.secondary,
                custom_id=f"cargo_escolha_{i}",
                disabled=disabled,
            )
            button.callback = self._callback(i)
            self.add_item(button)

    @staticmethod
    def _callback(index):
        async def callback(interaction: discord.Interaction):
            if interaction.guild is None or not isinstance(interaction.user, discord.Member):
                await interaction.response.send_message("Use este botão dentro do servidor.", ephemeral=True)
                return
            raw = await interaction.client.db.get_kv(f"roles_config:{interaction.guild_id}")
            config_data = json.loads(raw) if raw else {}
            itens = config_data.get("roles", [])
            if index >= len(itens):
                await interaction.response.send_message("Este botão não está configurado. Avise a moderação.", ephemeral=True)
                return
            item = itens[index]
            role_id = item.get("role_id")
            role = interaction.guild.get_role(int(role_id)) if role_id else None
            if role is None:
                await interaction.response.send_message(
                    f"O cargo configurado para **{item.get('label', 'este botão')}** não existe mais. Avise a moderação.",
                    ephemeral=True)
                return
            try:
                if role in interaction.user.roles:
                    await interaction.user.remove_roles(role, reason="Cargo removido pelo painel de cargos")
                    await interaction.response.send_message(f"Cargo **{role.name}** removido.", ephemeral=True)
                else:
                    await interaction.user.add_roles(role, reason="Cargo escolhido pelo painel")
                    await interaction.response.send_message(f"Cargo **{role.name}** adicionado.", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message(
                    "Não consigo alterar esse cargo. Confira Gerenciar Cargos e a hierarquia do bot.",
                    ephemeral=True)
        return callback


class Cargos(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(Verificacao())
        # Registra os custom_ids persistentes para os painéis existentes após reinicialização.
        self.bot.add_view(CargosView())

    async def _get_config(self, guild: discord.Guild):
        key = f"roles_config:{guild.id}"
        raw = await self.bot.db.get_kv(key)
        if raw:
            try:
                data = json.loads(raw)
                data.setdefault("title", "🎭 Escolha seus cargos")
                data.setdefault("description", "Escolha os jogos que você acompanha e os avisos que deseja receber. Clique novamente para remover um cargo. As patentes Soulslike são atribuídas automaticamente pelo XP e nível.")
                data.setdefault("roles", [])
                return data
            except (ValueError, TypeError):
                pass
        from settings_store import get_setting
        from server_structure import normalize_name
        roles = []
        for role_key, name, emoji in DEFAULT_ROLES:
            role_id = await get_setting(self.bot, guild.id, f"role_{role_key}_id", 0)
            role = guild.get_role(int(role_id)) if role_id else None
            if role is None:
                wanted = normalize_name(name)
                role = next((r for r in guild.roles if normalize_name(r.name) == wanted), None)
            if role:
                roles.append({"role_id": role.id, "label": name, "emoji": emoji})
        data = {
            "title": "🎭 Escolha seus cargos",
            "description": ("Escolha os jogos que você acompanha e quais notificações deseja receber. "
                            "Clique novamente no mesmo botão para remover o cargo. "
                            "As patentes de Soulslike são atribuídas automaticamente pelo XP e nível."),
            "roles": roles,
        }
        await self._save_config(guild.id, data)
        return data

    async def _save_config(self, guild_id, data):
        await self.bot.db.set_kv(f"roles_config:{guild_id}", json.dumps(data, ensure_ascii=False))

    async def _update_panel(self, interaction, data):
        if interaction.guild is None or interaction.channel is None:
            raise ValueError("Use este comando dentro de um servidor e canal de texto.")
        content = f"# {data['title']}\n\n{data['description']}"
        await upsert_panel(
            self.bot, interaction.channel,
            f"panel:roles:{interaction.guild_id}:{interaction.channel_id}",
            marker="cargo_escolha_*", content=content, embeds=[],
            view=CargosView(data.get("roles", [])),
        )

    async def publish_welcome_panel(self, guild: discord.Guild, channel: discord.TextChannel):
        """Publica/atualiza o painel de boas-vindas e sincroniza o cargo Membro."""
        content = (
            "# ✅ Verificação do Quase Pro\n\n"
            "1. Leia `📕・regras-do-reino`.\n"
            "2. Clique em **Verificar-me** para confirmar sua entrada.\n"
            "3. Você receberá o cargo **🟢 Membro**, que libera o acesso às categorias da comunidade.\n\n"
            "Os canais de entrada permanecem visíveis para que todos possam ler as regras e concluir a verificação. "
            "As demais categorias ficam ocultas até a atribuição do cargo de membro verificado."
        )
        return await upsert_panel(
            self.bot, channel, f"panel:verification:{guild.id}:{channel.id}",
            marker="verificar_membro", content=content, embeds=[], view=Verificacao(),
        )

    async def publish_organization_panel(self, guild: discord.Guild, channel: discord.TextChannel):
        """Salva e publica a lista de cargos de interesse definida pelo projeto."""
        roles = []
        for role_key, name, emoji in DEFAULT_ROLES:
            # A fonte de verdade fica na configuração central por servidor.
            from settings_store import get_setting
            configured_id = await get_setting(self.bot, guild.id, f"role_{role_key}_id", 0)
            role = guild.get_role(int(configured_id)) if configured_id else None
            if role is None:
                from server_structure import normalize_name
                role = next((r for r in guild.roles if normalize_name(r.name) == normalize_name(name)), None)
            if role is not None:
                roles.append({"role_id": role.id, "label": name, "emoji": emoji})
        data = {
            "title": "🎭 Escolha seus cargos",
            "description": (
                "Selecione os jogos que você acompanha e os avisos que deseja receber. "
                "Clique novamente para remover um cargo.\n\n"
                "**As patentes Soulslike são automáticas:** o Soulsbot atribui a patente correspondente ao seu XP e nível."
            ),
            "roles": roles,
        }
        await self._save_config(guild.id, data)
        content = f"# {data['title']}\n\n{data['description']}"
        return await upsert_panel(
            self.bot, channel, f"panel:roles:{guild.id}:{channel.id}",
            marker="cargo_escolha_*", content=content, embeds=[],
            view=CargosView(data["roles"]),
        )

    @app_commands.command(name="painel_verificacao", description="[MOD] Publica ou atualiza o painel de verificação.")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def painel_verificacao(self, interaction: discord.Interaction):
        texto = "# ✅ Verificação do servidor\n\nPara liberar o acesso aos canais, clique em **Verificar-me** abaixo.\n\n_Se o botão não funcionar, avise a moderação._"
        await upsert_panel(self.bot, interaction.channel,
            f"panel:verification:{interaction.guild_id}:{interaction.channel_id}",
            marker="verificar_membro", content=texto, embeds=[], view=Verificacao())
        await interaction.response.send_message("Painel de verificação atualizado neste canal.", ephemeral=True)

    @app_commands.command(name="painel_cargos", description="[MOD] Publica ou atualiza o painel configurado de cargos.")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def painel_cargos(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("Use este comando dentro de um servidor.", ephemeral=True)
            return
        data = await self._get_config(interaction.guild)
        await self._update_panel(interaction, data)
        await interaction.response.send_message("Painel de cargos publicado/atualizado neste canal.", ephemeral=True)

    @app_commands.command(name="editar_painel_cargos", description="[MOD] Edita o título e a mensagem do painel de cargos.")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(titulo="Título exibido no painel", mensagem="Texto abaixo do título")
    async def editar_painel_cargos(self, interaction: discord.Interaction, titulo: str, mensagem: str):
        if interaction.guild is None:
            await interaction.response.send_message("Use este comando dentro de um servidor.", ephemeral=True)
            return
        data = await self._get_config(interaction.guild)
        data["title"] = titulo[:250]
        data["description"] = mensagem[:3500]
        await self._save_config(interaction.guild_id, data)
        await self._update_panel(interaction, data)
        await interaction.response.send_message("Texto salvo e painel atualizado neste canal.", ephemeral=True)

    @app_commands.command(name="cargo_painel", description="[MOD] Adiciona, edita ou remove uma opção do painel de cargos.")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(acao="O que deseja fazer", cargo="Cargo do servidor", nome="Texto do botão (sem emoji)", emoji="Emoji do botão")
    @app_commands.choices(acao=[
        app_commands.Choice(name="Adicionar", value="adicionar"),
        app_commands.Choice(name="Editar", value="editar"),
        app_commands.Choice(name="Remover", value="remover"),
    ])
    async def cargo_painel(self, interaction: discord.Interaction, acao: app_commands.Choice[str],
                           cargo: discord.Role, nome: str = None, emoji: str = None):
        if interaction.guild is None:
            await interaction.response.send_message("Use este comando dentro de um servidor.", ephemeral=True)
            return
        data = await self._get_config(interaction.guild)
        itens = data["roles"]
        found = next((i for i, item in enumerate(itens) if int(item.get("role_id", 0)) == cargo.id), None)
        if acao.value == "adicionar":
            if found is not None:
                await interaction.response.send_message("Esse cargo já está no painel. Use **Editar** para alterar o botão.", ephemeral=True)
                return
            if len(itens) >= MAX_ROLES:
                await interaction.response.send_message("O Discord permite no máximo 25 botões nesta view.", ephemeral=True)
                return
            itens.append({"role_id": cargo.id, "label": (nome or cargo.name)[:80], "emoji": emoji or None})
        elif acao.value == "editar":
            if found is None:
                await interaction.response.send_message("Esse cargo não está no painel. Use **Adicionar** primeiro.", ephemeral=True)
                return
            if nome is not None:
                itens[found]["label"] = nome[:80]
            if emoji is not None:
                itens[found]["emoji"] = emoji or None
        else:
            if found is None:
                await interaction.response.send_message("Esse cargo não está no painel.", ephemeral=True)
                return
            itens.pop(found)
        await self._save_config(interaction.guild_id, data)
        await self._update_panel(interaction, data)
        await interaction.response.send_message(f"Configuração de cargos atualizada: **{acao.name}**.", ephemeral=True)

    async def cog_app_command_error(self, interaction, error):
        await erro_comando(interaction, error)


async def setup(bot):
    await bot.add_cog(Cargos(bot))
