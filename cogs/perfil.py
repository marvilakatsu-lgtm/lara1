import asyncio
import datetime as dt
import io
import logging

import discord
from discord import app_commands
from discord.ext import commands

import config
import conquistas as conq
import loja
import ui
from levels import nivel_por_xp, patente_por_nivel, barra_progresso
from perfil_card import render_cartao

log = logging.getLogger("colizeu")


class Perfil(commands.Cog):
    """Perfil dos membros: embeds, cartão e comando /perfil (veja mais abaixo)."""

    def __init__(self, bot):
        self.bot = bot

    # ------------------------------------------------------------ dados do perfil
    async def coletar(self, membro) -> dict:
        """Reúne tudo que o perfil mostra (embed e cartão usam a MESMA fonte de números)."""
        db = self.bot.db
        user = await db.get_user(membro.id)
        xp = int(user["xp"])
        nivel = nivel_por_xp(xp)
        plat = await db.contar_platinas(membro.id)
        zer = await db.contar_zerados(membro.id)
        runs = await db.stats_runs(membro.id)
        desde = getattr(membro, "joined_at", None)
        dias = (discord.utils.utcnow() - desde).days if desde else None
        stats = conq.Stats(
            nivel=nivel, xp=xp, platinas=plat, zerados=zer,
            runs=int(runs["runs"] or 0), recordes=int(runs["recordes"] or 0),
            # posição só faz sentido para quem já pontuou (antes, quem tinha 0 aparecia como "#N")
            pos_xp=await db.posicao_xp(xp) if xp > 0 else None,
            pos_platinas=await db.posicao_platinas(plat) if plat > 0 else None,
            dias_no_servidor=dias,
        )
        equipados = {}
        for r in await db.inventario_do_usuario(membro.id):
            if r["equipado"] and r["item"] in loja.POR_ID:
                equipados[r["tipo"]] = loja.POR_ID[r["item"]]
        return {
            "user": user, "stats": stats, "conquistas": conq.calcular(stats), "desde": desde,
            "santuario": await db.get_perfil(membro.id), "equipados": equipados,
        }

    def _cor(self, info: dict) -> int:
        """Cor comprada na loja > cor escolhida no santuário > cor da patente."""
        cor_loja = info.get("equipados", {}).get("cor")
        if cor_loja is not None and cor_loja.valor is not None:
            return cor_loja.valor
        sant = info["santuario"]
        if sant is not None and sant["theme"] and sant["theme"] != "Ouro":
            try:
                from cogs.santuario import TEMAS
                return TEMAS.get(sant["theme"], ui.cor_da_patente(info["stats"].nivel))
            except ImportError:
                pass
        return ui.cor_da_patente(info["stats"].nivel)

    @staticmethod
    def _pos(valor) -> str:
        return f"#{valor}" if valor else "—"

    async def embed_perfil(self, membro: discord.Member) -> discord.Embed:
        info = await self.coletar(membro)
        s, user, sant = info["stats"], info["user"], info["santuario"]
        nivel, xp_nv, xp_nec, frac = ui.progresso_nivel(s.xp)

        embed = discord.Embed(title=f"🏛️ {membro.display_name}", color=self._cor(info))
        if sant is not None and sant["tagline"]:
            embed.description = f"*“{sant['tagline']}”*"
        embed.set_thumbnail(url=membro.display_avatar.url)

        # 1) identidade: patente e nível
        embed.add_field(name="🎖️ Patente", value=ui.patente_com_simbolo(nivel), inline=True)
        embed.add_field(name="⭐ Nível", value=str(nivel), inline=True)
        embed.add_field(name="🪙 Denários", value=f"{user['denarios']:,}".replace(",", "."), inline=True)

        # 2) progresso, com o que falta para a próxima patente
        prox = ui.proxima_patente(nivel)
        legenda = f"{ui.barra(frac)} **{xp_nv}/{xp_nec} XP**"
        if prox:
            legenda += f"\n_Próxima patente: {prox[1]} (nível {prox[0]})_"
        embed.add_field(name="✨ Experiência", value=legenda, inline=False)

        # 3) o que a pessoa fez
        embed.add_field(name="🏆 Platinas", value=str(s.platinas), inline=True)
        embed.add_field(name="✅ Zerados", value=str(s.zerados), inline=True)
        embed.add_field(name="⚔️ Runs", value=str(s.runs), inline=True)

        # 4) onde ela está
        embed.add_field(name="📈 Rank XP", value=self._pos(s.pos_xp), inline=True)
        embed.add_field(name="🥇 Rank Platinas", value=self._pos(s.pos_platinas), inline=True)
        if s.recordes:
            embed.add_field(name="👑 Recordes", value=str(s.recordes), inline=True)

        titulo = info["equipados"].get("titulo")
        if titulo is not None:
            embed.add_field(name="🏷️ Título", value=f"{titulo.emoji} {titulo.nome}", inline=False)
        embed.add_field(name="🎖️ Conquistas", value=conq.linha_resumo(info["conquistas"]), inline=False)
        rodape = ui.rodape("Perfil")
        if info["desde"]:
            rodape += f" · No servidor desde {info['desde']:%d/%m/%Y}"
        embed.set_footer(text=rodape)
        return embed

    # ------------------------------------------------------------ cartão em imagem
    async def _avatar_bytes(self, membro) -> bytes | None:
        try:
            return await membro.display_avatar.replace(size=256, format="png").read()
        except (discord.HTTPException, ValueError):
            return None

    async def arquivo_cartao(self, membro, info: dict) -> discord.File:
        s, user, sant = info["stats"], info["user"], info["santuario"]
        nivel, xp_nv, xp_nec, frac = ui.progresso_nivel(s.xp)
        prox = ui.proxima_patente(nivel)
        dados = {
            "nome": membro.display_name, "patente": patente_por_nivel(nivel), "nivel": nivel,
            "xp_nivel": xp_nv, "xp_necessario": xp_nec, "fracao": frac, "cor": self._cor(info),
            "tagline": sant["tagline"] if sant is not None else "",
            "titulo": info["equipados"]["titulo"].nome if "titulo" in info["equipados"] else "",
            "platinas": s.platinas, "zerados": s.zerados, "runs": s.runs, "denarios": int(user["denarios"]),
            "pos_xp": s.pos_xp, "pos_platinas": s.pos_platinas,
            "conquistas": [(c.nome, c.raridade) for c in info["conquistas"]],
            "desde": info["desde"].strftime("%d/%m/%Y") if info["desde"] else None,
            "proxima": f"{prox[1]} no nível {prox[0]}" if prox else "Patente máxima",
        }
        avatar = await self._avatar_bytes(membro)
        png = await asyncio.to_thread(render_cartao, dados, avatar)  # Pillow fora do loop do bot
        return discord.File(io.BytesIO(png), filename="perfil.png")

    @app_commands.command(name="perfil", description="Mostra o cartão de perfil de um membro.")
    @app_commands.describe(membro="Quem você quer ver (padrão: você)", publico="Mostrar para todos no canal")
    @app_commands.guild_only()
    async def perfil(self, interaction: discord.Interaction, membro: discord.Member = None, publico: bool = False):
        alvo = membro or interaction.user
        if alvo.bot:
            return await interaction.response.send_message("Bots não têm perfil.", ephemeral=True)
        await interaction.response.defer(ephemeral=not publico)
        try:
            info = await self.coletar(alvo)
            arquivo = await self.arquivo_cartao(alvo, info)
        except Exception:
            # o cartão é um extra visual: se falhar, o perfil em embed continua disponível
            log.exception("Falha ao gerar o cartão de perfil de %s", alvo.id)
            return await interaction.followup.send(embed=await self.embed_perfil(alvo), ephemeral=not publico)
        embed = discord.Embed(
            description=f"**{alvo.display_name}** · {ui.patente_com_simbolo(info['stats'].nivel)} · Nível {info['stats'].nivel}",
            color=self._cor(info),
        )
        embed.set_image(url=f"attachment://{arquivo.filename}")
        embed.set_footer(text=ui.rodape("Perfil"))
        await interaction.followup.send(
            embed=embed, file=arquivo, view=PerfilView(self, interaction.user, alvo, info), ephemeral=not publico,
        )

    async def embed_platinas(self, membro: discord.Member) -> discord.Embed | None:
        rows = await self.bot.db.platinas_do_usuario(membro.id)
        if not rows:
            return None
        linhas = [f"🏆 **{r['game']}** — {r['platform']} ({r['earned_at']})" for r in rows[:25]]
        embed = discord.Embed(
            title=f"Platinas de {membro.display_name}",
            description="\n".join(linhas),
            color=config.COR_PRATA,
        )
        if len(rows) > 25:
            embed.set_footer(text=f"Mostrando 25 de {len(rows)}")
        return embed

    async def texto_platinas(self, membro: discord.Member) -> str | None:
        rows = await self.bot.db.platinas_do_usuario(membro.id)
        if not rows:
            return None
        def data_legivel(valor):
            try:
                return dt.date.fromisoformat(str(valor)).strftime("%d/%m/%Y")
            except (ValueError, TypeError):
                return str(valor)
        cabecalho = f"## 📜 Platinas de {membro.display_name}\n\n"
        linhas = []
        for r in rows[:25]:
            linha = f"🏆 **{r['game']}** · `{r['platform']}` · {data_legivel(r['earned_at'])}"
            candidato = cabecalho + "\n".join(linhas + [linha])
            if len(candidato) > 1850:
                break
            linhas.append(linha)
        texto = cabecalho + ("\n".join(linhas) or "Nenhuma conquista cabe na lista atual.")
        if len(rows) > len(linhas):
            texto += f"\n\n_Mostrando {len(linhas)} de {len(rows)} conquistas. O perfil continua com a coleção completa._"
        return texto[:1990]

    def texto_ajuda(self) -> str:
        return (
            "## ⚔️ Colizeu — Guia rápido\n\n"
            "**`/coliseu`** abre o painel de conquistas e jornadas.\n\n"
            "🏆 **Registrar platina** — informe o jogo, a plataforma, a data e os comprovantes; "
            "a moderação revisará o registro.\n"
            "👤 **Perfil** — consulta patente, nível, XP e posições no ranking.\n"
            "📜 **Platinas** — lista suas conquistas aprovadas.\n"
            "🏛️ **Santuário** — personalize sua apresentação, galeria e plataformas.\n"
            "✅ **Zerados** — registre os jogos que você finalizou, sem precisar platinar.\n"
            "⚔️ **Runs e desafios** — registre tempos e acompanhe recordes.\n\n"
            "_Use os botões de voltar para navegar sem criar mensagens adicionais._"
        )

    def embed_ajuda(self) -> discord.Embed:
        embed = discord.Embed(title="⚔️ Colizeu Bot — Como usar", color=config.COR_OURO)
        embed.description = (
            "Use **`/coliseu`** e escolha **Platinas** para abrir o painel. Nele você pode:\n\n"
            "📤 **Registrar platina** — informe jogo, plataforma, data e anexe o print. "
            "A moderação aprova ou rejeita.\n"
            "👤 **Perfil** — patente, nível, XP e ranking.\n"
            "📜 **Platinas** — lista de jogos platinados.\n"
            "🏆 **Ranking** — platinas, XP e platinas do mês.\n"
            "🔎 O menu de membros deixa você consultar o perfil de outra pessoa.\n"
            "🏛️ **Meu santuário** — seu espaço pessoal com platinas, prints e redes.\n"
            "🚪 **Visitar santuário** — entre no santuário do membro escolhido no menu. "
            "Para sair, use *Sair do tópico* e ele some da sua lista."
        )
        return embed


class PerfilView(discord.ui.View):
    """Botões do cartão. Cada um abre uma resposta privada, sem substituir o cartão."""

    def __init__(self, cog: Perfil, quem_abriu, alvo, info: dict):
        super().__init__(timeout=600)
        self.cog, self.quem_abriu_id, self.alvo, self.info = cog, quem_abriu.id, alvo, info

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.quem_abriu_id:
            await interaction.response.send_message("Use `/perfil` para abrir o seu próprio cartão.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Conquistas", style=discord.ButtonStyle.primary, emoji="🎖️")
    async def conquistas(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title=f"🎖️ Conquistas de {self.alvo.display_name}",
            description=conq.texto_detalhado(self.info["conquistas"])[:4000],
            color=self.cog._cor(self.info),
        )
        embed.set_footer(text=ui.rodape("Conquistas"))
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Platinas", style=discord.ButtonStyle.secondary, emoji="📜")
    async def platinas(self, interaction: discord.Interaction, button: discord.ui.Button):
        texto = await self.cog.texto_platinas(self.alvo)
        if texto is None:
            texto = f"## 📜 Coleção de {self.alvo.display_name}\n\nAinda não há platinas aprovadas para exibir."
        await interaction.response.send_message(texto, ephemeral=True)

    @discord.ui.button(label="Santuário", style=discord.ButtonStyle.success, emoji="🏛️")
    async def santuario(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("Santuario")
        if cog is None:
            return await interaction.response.send_message("Os santuários estão indisponíveis no momento.", ephemeral=True)
        await cog.visitar(interaction, self.alvo.id, nova_resposta=True)


async def setup(bot):
    await bot.add_cog(Perfil(bot))
