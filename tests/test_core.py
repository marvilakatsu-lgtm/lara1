import asyncio
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
try:
    import aiosqlite  # noqa: F401
except ImportError:
    from tests import fake_aiosqlite
    fake_aiosqlite.instalar()

import conquistas as conq  # noqa: E402
import ui  # noqa: E402
from database import Database  # noqa: E402
from levels import PATENTES, nivel_por_xp, xp_para_nivel  # noqa: E402


def rodar(coro):
    return asyncio.run(coro)


class BancoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.tmp.name, "t.db"))
        rodar(self.db.connect())

    def tearDown(self):
        if getattr(self.db, "conn", None):
            rodar(self.db.conn.close())
        self.tmp.cleanup()

    def test_xp_nunca_fica_negativo(self):
        async def c():
            await self.db.add_reward(1, 50, 10)
            _, _, total = await self.db.add_reward(1, -200, -999)
            u = await self.db.get_user(1)
            return total, u["xp"], u["denarios"]
        total, xp, den = rodar(c())
        self.assertEqual((total, xp, den), (0, 0, 0))

    def test_recompensa_normal_continua_igual(self):
        async def c():
            ant, novo, total = await self.db.add_reward(1, 450, 5)
            return ant, novo, total
        ant, novo, total = rodar(c())
        self.assertEqual((ant, novo, total), (1, nivel_por_xp(450), 450))

    def test_decisao_de_platina_so_passa_uma_vez(self):
        async def c():
            pid = await self.db.criar_platina(1, "Elden Ring", "PC", "2025-01-01", "http://x", 1)
            a = await self.db.decidir_platina(pid, "approved", 9)
            b = await self.db.decidir_platina(pid, "approved", 8)
            c_ = await self.db.decidir_platina(pid, "rejected", 7)
            p = await self.db.get_platina(pid)
            return a, b, c_, p["status"], p["reviewer_id"]
        self.assertEqual(rodar(c()), (True, False, False, "approved", 9))

    def _run(self, user, jogo, desafio, seg, status="approved"):
        async def c():
            await self.db.conn.execute("INSERT OR IGNORE INTO sl_games(name) VALUES (?)", (jogo,))
            await self.db.conn.execute("INSERT OR IGNORE INTO sl_challenges(name) VALUES (?)", (desafio,))
            g = await self.db._one("SELECT id FROM sl_games WHERE name=?", (jogo,))
            ch = await self.db._one("SELECT id FROM sl_challenges WHERE name=?", (desafio,))
            await self.db.conn.execute(
                "INSERT INTO sl_runs(user_id, game_id, challenge_id, seconds, status) VALUES (?,?,?,?,?)",
                (user, g["id"], ch["id"], seg, status))
            await self.db.conn.commit()
        rodar(c())

    def test_stats_de_runs_e_recordes(self):
        self._run(1, "Elden Ring", "Any%", 3600)
        self._run(2, "Elden Ring", "Any%", 3000)            # recorde de 2
        self._run(1, "Elden Ring", "Nível 1", 5000)         # recorde de 1 (única)
        self._run(1, "Sekiro", "Any%", 100, status="pending")   # pendente não conta
        self._run(2, "Sekiro", "Any%", 90, status="rejected")   # rejeitada não conta
        s1 = rodar(self.db.stats_runs(1))
        s2 = rodar(self.db.stats_runs(2))
        s3 = rodar(self.db.stats_runs(3))
        self.assertEqual((s1["runs"], s1["recordes"]), (2, 1))
        self.assertEqual((s2["runs"], s2["recordes"]), (1, 1))
        self.assertEqual((s3["runs"], s3["recordes"]), (0, 0))

    def test_recordes_recentes_um_por_categoria(self):
        self._run(1, "Elden Ring", "Any%", 3600)
        self._run(2, "Elden Ring", "Any%", 3000)
        self._run(3, "Sekiro", "Any%", 4000)
        rows = rodar(self.db.recordes_recentes(6))
        achado = {(r["jogo"], r["desafio"]): (r["user_id"], r["seconds"]) for r in rows}
        self.assertEqual(achado, {("Elden Ring", "Any%"): (2, 3000), ("Sekiro", "Any%"): (3, 4000)})
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rodar(self.db.recordes_recentes(1))), 1)


class MigracaoSchemaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "legado.db")

    def tearDown(self):
        self.tmp.cleanup()

    def test_migracao_e_versionada_e_faz_backup_previo(self):
        import glob
        import sqlite3

        conn = sqlite3.connect(self.path)
        conn.execute("""CREATE TABLE platinas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, game TEXT NOT NULL,
            platform TEXT NOT NULL, earned_at TEXT NOT NULL, proof_url TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending', reviewer_id INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.execute("INSERT INTO platinas(user_id,game,platform,earned_at,proof_url) VALUES(1,'Jogo','PC','2025-01-01','https://exemplo.invalid')")
        conn.commit()
        conn.close()

        db = Database(self.path)
        rodar(db.connect())
        colunas = [row["name"] for row in rodar(db._all("PRAGMA table_info(platinas)"))]
        versoes = rodar(db._all("SELECT version FROM schema_migrations ORDER BY version"))
        rodar(db.conn.close())

        self.assertIn("proof_msg_id", colunas)
        self.assertEqual([row["version"] for row in versoes], [1, 2])
        backups = glob.glob(self.path + ".pre-migration-*.bak")
        self.assertEqual(len(backups), 1)
        backup = sqlite3.connect(backups[0])
        try:
            antigas = {row[1] for row in backup.execute("PRAGMA table_info(platinas)")}
        finally:
            backup.close()
        self.assertNotIn("proof_msg_id", antigas)


class ConfiguracaoClansTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.tmp.name, "integracao.db"))
        rodar(self.db.connect())

    def tearDown(self):
        if getattr(self.db, "conn", None):
            rodar(self.db.conn.close())
        self.tmp.cleanup()

    def test_configuracao_e_isolada_por_servidor(self):
        from types import SimpleNamespace
        from settings_store import get_setting, set_setting
        bot = SimpleNamespace(db=self.db)

        async def c():
            await set_setting(bot, 100, 9, "games_channel_id", 1111)
            await set_setting(bot, 200, 9, "games_channel_id", 2222)
            return (
                await get_setting(bot, 100, "games_channel_id", 0),
                await get_setting(bot, 200, "games_channel_id", 0),
                await get_setting(bot, 300, "games_channel_id", 0),
            )

        self.assertEqual(rodar(c()), (1111, 2222, 0))

    def test_banco_bloqueia_11o_integrante_e_mantem_exclusividade(self):
        import sqlite3

        async def c():
            async with self.db.conn.execute(
                "INSERT INTO clans(guild_id,name,tag,slug,main_game,play_style,creator_id,leader_id,status) "
                "VALUES(700,'Guardiões','GRD','guardioes','Elden Ring','cooperacao',900,900,'active')"
            ) as cur:
                clan_id = cur.lastrowid
            await self.db.conn.execute("INSERT INTO clan_members(guild_id,clan_id,user_id,role) VALUES(700,?,?,?)", (clan_id, 900, "leader"))
            for user_id in range(901, 910):
                await self.db.conn.execute("INSERT INTO clan_members(guild_id,clan_id,user_id,role) VALUES(700,?,?,?)", (clan_id, user_id, "member"))
            await self.db.conn.commit()
            with self.assertRaises(sqlite3.IntegrityError):
                await self.db.conn.execute("INSERT INTO clan_members(guild_id,clan_id,user_id,role) VALUES(700,?,?,?)", (clan_id, 910, "member"))
            await self.db.conn.rollback()
            with self.assertRaises(sqlite3.IntegrityError):
                await self.db.conn.execute("INSERT INTO clan_members(guild_id,clan_id,user_id,role) VALUES(700,?,?,?)", (clan_id, 900, "member"))
            await self.db.conn.rollback()
            row = await self.db._one("SELECT COUNT(*) AS n FROM clan_members WHERE guild_id=700 AND clan_id=?", (clan_id,))
            return row["n"]

        self.assertEqual(rodar(c()), 10)


class LojaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.tmp.name, "t.db"))
        rodar(self.db.connect())

    def tearDown(self):
        if getattr(self.db, "conn", None):
            rodar(self.db.conn.close())
        self.tmp.cleanup()

    def saldo(self, uid=1):
        return rodar(self.db.get_user(uid))["denarios"]

    def test_compra_debita_e_registra(self):
        rodar(self.db.add_reward(1, 0, 250))
        self.assertEqual(rodar(self.db.comprar_item(1, "cor_brasa", "cor", 100)), "ok")
        self.assertEqual(self.saldo(), 150)
        self.assertEqual([(r["item"], r["equipado"]) for r in rodar(self.db.inventario_do_usuario(1))], [("cor_brasa", 0)])

    def test_sem_saldo_nao_debita_nem_entrega(self):
        rodar(self.db.add_reward(1, 0, 99))
        self.assertEqual(rodar(self.db.comprar_item(1, "cor_brasa", "cor", 100)), "sem_saldo")
        self.assertEqual(self.saldo(), 99)
        self.assertEqual(rodar(self.db.inventario_do_usuario(1)), [])

    def test_nao_compra_duas_vezes(self):
        rodar(self.db.add_reward(1, 0, 300))
        self.assertEqual(rodar(self.db.comprar_item(1, "cor_brasa", "cor", 100)), "ok")
        self.assertEqual(rodar(self.db.comprar_item(1, "cor_brasa", "cor", 100)), "ja_tem")
        self.assertEqual(self.saldo(), 200)

    def test_equipar_so_um_por_tipo_e_so_o_que_possui(self):
        rodar(self.db.add_reward(1, 0, 500))
        self.assertFalse(rodar(self.db.equipar_item(1, "cor_brasa", "cor")))  # não possui
        rodar(self.db.comprar_item(1, "cor_brasa", "cor", 100))
        rodar(self.db.comprar_item(1, "cor_hera", "cor", 100))
        rodar(self.db.comprar_item(1, "tit_cacador", "titulo", 150))
        self.assertTrue(rodar(self.db.equipar_item(1, "cor_brasa", "cor")))
        self.assertTrue(rodar(self.db.equipar_item(1, "tit_cacador", "titulo")))
        self.assertTrue(rodar(self.db.equipar_item(1, "cor_hera", "cor")))
        eq = {r["item"] for r in rodar(self.db.inventario_do_usuario(1)) if r["equipado"]}
        self.assertEqual(eq, {"cor_hera", "tit_cacador"})
        rodar(self.db.desequipar_tipo(1, "cor"))
        eq = {r["item"] for r in rodar(self.db.inventario_do_usuario(1)) if r["equipado"]}
        self.assertEqual(eq, {"tit_cacador"})

    def test_inventarios_sao_independentes(self):
        rodar(self.db.add_reward(1, 0, 100))
        rodar(self.db.add_reward(2, 0, 100))
        rodar(self.db.comprar_item(1, "cor_brasa", "cor", 100))
        self.assertEqual(rodar(self.db.inventario_do_usuario(2)), [])
        self.assertEqual(rodar(self.db.comprar_item(2, "cor_brasa", "cor", 100)), "ok")

    def test_catalogo_consistente(self):
        import loja
        ids = [i.id for i in loja.ITENS]
        self.assertEqual(len(ids), len(set(ids)))
        for i in loja.ITENS:
            self.assertGreater(i.preco, 0)
            self.assertIn(i.tipo, loja.ROTULO_TIPO)
            self.assertLessEqual(len(i.nome), 100)
            if i.tipo == "cor":
                self.assertTrue(0 <= i.valor <= 0xFFFFFF)
        self.assertLessEqual(len(ids), 25)  # cabe em um menu do Discord

    def test_linha_item_estados(self):
        import loja
        it = loja.POR_ID["tit_renascido"]
        self.assertIn("🔒 nível 20", loja.linha_item(it, False, False, 5))
        self.assertIn("🪙 300", loja.linha_item(it, False, False, 20))
        self.assertIn("equipado", loja.linha_item(it, True, True, 20))


class ConquistasTests(unittest.TestCase):
    def nomes(self, **kw):
        return [c.nome for c in conq.calcular(conq.Stats(**kw))]

    def test_sem_dados_sem_conquistas(self):
        self.assertEqual(self.nomes(), [])
        self.assertIn("Nenhuma", conq.linha_resumo([]))

    def test_so_o_maior_marco_aparece(self):
        n = self.nomes(platinas=12)
        self.assertIn("10 platinas", n)
        self.assertNotIn("5 platinas", n)
        self.assertNotIn("Primeira platina", n)

    def test_primeiro_marco_tem_nome_proprio(self):
        self.assertIn("Primeira platina", self.nomes(platinas=1))
        self.assertIn("Primeiro zerado", self.nomes(zerados=1))
        self.assertIn("Primeira run", self.nomes(runs=1))

    def test_podio_exige_ter_pontuado(self):
        self.assertNotIn("Pódio de XP", self.nomes(xp=0, pos_xp=1))
        self.assertIn("Pódio de XP", self.nomes(xp=10, pos_xp=3))
        self.assertNotIn("Pódio de XP", self.nomes(xp=10, pos_xp=4))
        self.assertNotIn("Pódio de platinas", self.nomes(platinas=0, pos_platinas=1))

    def test_ordenadas_da_mais_rara_para_a_mais_comum(self):
        lista = conq.calcular(conq.Stats(platinas=50, zerados=1, recordes=3, nivel=50, dias_no_servidor=400))
        ordem = {"lendaria": 0, "epica": 1, "rara": 2, "comum": 3}
        pesos = [ordem[c.raridade] for c in lista]
        self.assertEqual(pesos, sorted(pesos))
        self.assertEqual(lista[-1].raridade, "comum")

    def test_resumo_limita_e_conta_o_resto(self):
        lista = conq.calcular(conq.Stats(platinas=50, zerados=100, runs=20, recordes=3, nivel=50, dias_no_servidor=400,
                                         xp=5, pos_xp=1, pos_platinas=1))
        self.assertGreater(len(lista), 6)
        self.assertRegex(conq.linha_resumo(lista, 6), r"\*\*\+\d+\*\*$")


class UiTests(unittest.TestCase):
    def test_toda_patente_tem_cor(self):
        for minimo, nome in PATENTES:
            self.assertIn(nome, ui.COR_PATENTE, nome)
            self.assertEqual(ui.cor_da_patente(minimo), ui.COR_PATENTE[nome])

    def test_progresso_e_proxima_patente(self):
        nivel, no_nivel, necessario, frac = ui.progresso_nivel(xp_para_nivel(5) + 10)
        self.assertEqual(nivel, 5)
        self.assertEqual(no_nivel, 10)
        self.assertTrue(0 < frac < 1)
        self.assertEqual(ui.proxima_patente(1), (5, "Guerreiro Caído"))
        self.assertIsNone(ui.proxima_patente(100))

    def test_barra_limites(self):
        self.assertEqual(ui.barra(0, 4), "▱▱▱▱")
        self.assertEqual(ui.barra(1, 4), "▰▰▰▰")
        self.assertEqual(ui.barra(7, 4), "▰▰▰▰")
        self.assertEqual(ui.barra(-3, 4), "▱▱▱▱")

    def test_formatos(self):
        self.assertEqual(ui.fmt_tempo(3725), "1:02:05")
        self.assertEqual(ui.fmt_data("2025-03-09"), "09/03/2025")
        self.assertEqual(ui.fmt_data("lixo"), "lixo")


class CartaoTests(unittest.TestCase):
    BASE = dict(nome="Teste", patente="Cinzas Novatas", nivel=1, xp_nivel=0, xp_necessario=100, fracao=0.0,
                cor=0x7A736B, tagline="", platinas=0, zerados=0, runs=0, denarios=0, pos_xp=None,
                pos_platinas=None, conquistas=[], desde=None, proxima=None)

    def render(self, **kw):
        from perfil_card import render_cartao
        dados = {**self.BASE, **kw}
        return render_cartao(dados, kw.get("avatar_bytes"))

    def test_gera_png_valido_com_tamanho_fixo(self):
        from io import BytesIO
        from PIL import Image
        img = Image.open(BytesIO(self.render()))
        self.assertEqual(img.format, "PNG")
        self.assertEqual(img.size, (920, 440))

    def test_nomes_hostis_nao_quebram(self):
        for nome in ("", "🔥🔥🔥", "A" * 300, "ｆｕｌｌｗｉｄｔｈ" * 20, "Ñandú — çãõ"):
            self.assertTrue(self.render(nome=nome).startswith(b"\x89PNG"))

    def test_muitas_conquistas_e_valores_grandes(self):
        conqs = [(f"Conquista longa número {i}", "epica") for i in range(30)]
        self.assertTrue(self.render(conquistas=conqs, denarios=10**9, platinas=99999, fracao=5).startswith(b"\x89PNG"))

    def test_avatar_invalido_cai_para_inicial(self):
        self.assertTrue(self.render(avatar_bytes=b"isso nao e uma imagem").startswith(b"\x89PNG"))

    def test_avatar_valido(self):
        from io import BytesIO
        from PIL import Image
        buf = BytesIO()
        Image.new("RGB", (64, 64), (200, 30, 30)).save(buf, "PNG")
        self.assertTrue(self.render(avatar_bytes=buf.getvalue()).startswith(b"\x89PNG"))

    def test_com_titulo(self):
        self.assertTrue(self.render(titulo="Caçador de Chefes").startswith(b"\x89PNG"))
        self.assertTrue(self.render(titulo="T" * 200).startswith(b"\x89PNG"))

    def test_limpar_texto(self):
        from perfil_card import limpar_texto
        self.assertEqual(limpar_texto("Ana 🔥  Souza"), "Ana Souza")


if __name__ == "__main__":
    unittest.main()
