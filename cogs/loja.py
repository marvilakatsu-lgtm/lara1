import discord
from discord import app_commands
from discord.ext import commands

import config
import loja
import ui
from levels import nivel_por_xp


class Loja(commands.Cog):
    """Loja de Denários: cores de perfil e títulos. Só cosmético."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="loja", description="Gaste seus Denários em cores de perfil e títulos.")
    @app_commands.guild_only()
    async def loja(self, interaction: discord.Interaction):
        view = LojaView(self, interaction.user)
        await view.carregar()
        await interaction.response.send_message(embed=view.embed(), view=view, ephemeral=True)


class LojaView(discord.ui.View):
    def __init__(self, cog: Loja, user):
        super().__init__(timeout=600)
        self.cog, self.user = cog, user
        self.saldo = 0
        self.nivel = 1
        self.inv: dict[str, bool] = {}   # item -> equipado
        self.sel: str | None = None
        self.aviso = ""

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Use `/loja` para abrir a sua.", ephemeral=True)
            return False
        return True

    async def carregar(self):
        db = self.cog.bot.db
        u = await db.get_user(self.user.id)
        self.saldo, self.nivel = int(u["denarios"]), nivel_por_xp(int(u["xp"]))
        self.inv = {r["item"]: bool(r["equipado"]) for r in await db.inventario_do_usuario(self.user.id)}
        self._montar()

    def embed(self) -> discord.Embed:
        e = discord.Embed(title="🪙 Loja do Colizeu", color=config.COR_OURO)
        partes = [f"**Seu saldo:** 🪙 {self.saldo}\n"]
        for tipo, rotulo in loja.ROTULO_TIPO.items():
            partes.append(f"**{rotulo}**")
            partes.extend(
                loja.linha_item(i, i.id in self.inv, self.inv.get(i.id, False), self.nivel)
                for i in loja.ITENS if i.tipo == tipo
            )
            partes.append("")
        partes.append("_Escolha um item no menu. Itens são só visuais e aparecem no `/perfil`._")
        e.description = "\n".join(partes)
        if self.aviso:
            e.add_field(name="Resultado", value=self.aviso, inline=False)
        e.set_footer(text=ui.rodape("Loja"))
        return e

    def _montar(self):
        self.clear_items()
        opcoes = []
        for i in loja.ITENS:
            if i.id in self.inv:
                desc = "Equipado" if self.inv[i.id] else "Você já tem"
            elif self.nivel < i.nivel_min:
                desc = f"Exige nível {i.nivel_min}"
            else:
                desc = f"{i.preco} Denários"
            opcoes.append(discord.SelectOption(
                label=i.nome, value=i.id, emoji=i.emoji, description=f"{loja.ROTULO_TIPO[i.tipo]} · {desc}"[:100],
                default=i.id == self.sel))
        seletor = discord.ui.Select(placeholder="Escolha um item", options=opcoes, row=0)
        seletor.callback = self._escolher
        self.add_item(seletor)

        botao = discord.ui.Button(row=1)
        item = loja.POR_ID.get(self.sel) if self.sel else None
        if item is None:
            botao.label, botao.style, botao.disabled = "Escolha um item", discord.ButtonStyle.secondary, True
        elif item.id in self.inv:
            if self.inv[item.id]:
                botao.label, botao.style, botao.emoji = "Desequipar", discord.ButtonStyle.secondary, "↩️"
            else:
                botao.label, botao.style, botao.emoji = "Equipar", discord.ButtonStyle.primary, "✨"
        else:
            botao.label, botao.style, botao.emoji = f"Comprar por {item.preco}", discord.ButtonStyle.success, "🪙"
            botao.disabled = self.nivel < item.nivel_min or self.saldo < item.preco
        botao.callback = self._acao
        self.add_item(botao)

    async def _escolher(self, interaction: discord.Interaction):
        self.sel = interaction.data["values"][0]
        self.aviso = ""
        self._montar()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    async def _acao(self, interaction: discord.Interaction):
        db = self.cog.bot.db
        item = loja.POR_ID.get(self.sel)
        if item is None:
            return await interaction.response.send_message("Escolha um item primeiro.", ephemeral=True)
        if item.id in self.inv:
            if self.inv[item.id]:
                await db.desequipar_tipo(self.user.id, item.tipo)
                self.aviso = f"↩️ **{item.nome}** desequipado."
            elif await db.equipar_item(self.user.id, item.id, item.tipo):
                self.aviso = f"✨ **{item.nome}** equipado. Veja em `/perfil`."
            else:
                self.aviso = "Não consegui equipar esse item."
        elif self.nivel < item.nivel_min:
            self.aviso = f"🔒 **{item.nome}** exige nível {item.nivel_min}."
        else:
            resultado = await db.comprar_item(self.user.id, item.id, item.tipo, item.preco)
            if resultado == "ok":
                await db.log(self.user.id, "loja_compra", f"{item.id} preco={item.preco}")
                self.aviso = f"✅ Você comprou **{item.nome}** por 🪙 {item.preco}."
            elif resultado == "ja_tem":
                self.aviso = f"Você já tem **{item.nome}**."
            else:
                self.aviso = f"Denários insuficientes para **{item.nome}**."
        await self.carregar()
        await interaction.response.edit_message(embed=self.embed(), view=self)


async def setup(bot):
    await bot.add_cog(Loja(bot))
