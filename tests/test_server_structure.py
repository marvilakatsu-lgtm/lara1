import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import server_structure
from levels import PATENTES, eh_cargo_patente, nome_patente_exibicao
from server_structure import role_hierarchy_keys, managed_role_hierarchy_keys, STAFF_ROLE_ORDER


class EstruturaServidorTests(unittest.TestCase):
    def test_dez_categorias_e_sessenta_e_tres_canais(self):
        self.assertEqual(len(server_structure.ORGANIZATION), 10)
        self.assertEqual(server_structure.count_channels(), 63)

    def test_schema_de_categoria_tem_chave_aliases_e_canais_na_ordem_esperada(self):
        for category_name, category_key, aliases, channels in server_structure.ORGANIZATION:
            self.assertTrue(category_name)
            self.assertTrue(category_key.endswith("_id"))
            self.assertIsInstance(aliases, tuple)
            self.assertIsInstance(channels, list)
            for channel_name, kind, setting_key, channel_aliases, special_access in channels:
                self.assertTrue(channel_name)
                self.assertIn(kind, {"text", "voice"})
                self.assertIsInstance(channel_aliases, tuple)
                self.assertIn(special_access, {None, "support", "developer"})

    def test_nomes_das_categorias_sao_os_do_plano(self):
        self.assertEqual(
            [row[0] for row in server_structure.ORGANIZATION],
            [
                "🔥・PORTÕES DO SANTUÁRIO",
                "🎬・QUASE PRO",
                "🏰・PRAÇA DOS MACULADOS",
                "⚔️・TERRAS SOULSLIKE",
                "🏆・COLISEU DAS CINZAS",
                "📚・ARQUIVO DO VIAJANTE",
                "🤖・ORÁCULO DO SANTUÁRIO",
                "🛡️・SALÃO DOS JURAMENTOS",
                "🔊・FOGUEIRAS DA COMUNIDADE",
                "🔒・BASTIDORES DA ORDEM",
            ],
        )

    def test_todos_os_cargos_tem_nome_chave_e_cor_unicos(self):
        self.assertEqual(len(server_structure.ROLE_DEFINITIONS), 34)
        self.assertTrue(server_structure.validate_role_palette())
        self.assertEqual(len({r["color"] for r in server_structure.ROLE_DEFINITIONS}), 34)

    def test_patentes_preservam_niveis_e_nomes_da_logica_original(self):
        expected = [
            (1, "Cinzas Novatas"),
            (5, "Guerreiro Caído"),
            (10, "Caçador de Almas"),
            (15, "Cavaleiro do Abismo"),
            (20, "Guardião das Cinzas"),
            (30, "Arauto da Ruína"),
            (40, "Executor Sombrio"),
            (50, "Senhor das Almas"),
            (75, "Lenda do Coliseu"),
            (100, "Sentinela Imortal"),
        ]
        self.assertEqual(PATENTES, expected)
        ranks = [r for r in server_structure.ROLE_DEFINITIONS if r["group"] == "rank"]
        self.assertEqual([(r["level_min"], r["rank_name"]) for r in ranks], expected)

    def test_hierarquia_da_equipe_e_explicita_e_na_ordem_correta(self):
        hierarchy = role_hierarchy_keys()
        self.assertEqual(tuple(hierarchy[:5]), STAFF_ROLE_ORDER)
        self.assertEqual(STAFF_ROLE_ORDER, ("founder", "administrator", "moderator", "support", "developer"))

    def test_patentes_ordenadas_da_maior_para_a_menor_na_hierarquia(self):
        by_key = {item["key"]: item for item in server_structure.ROLE_DEFINITIONS}
        hierarchy = role_hierarchy_keys(include_staff=False)
        ranks = [by_key[key] for key in hierarchy if by_key[key].get("group") == "rank"]
        self.assertEqual(
            [item["level_min"] for item in ranks],
            sorted((minimum for minimum, _name in PATENTES), reverse=True),
        )
        self.assertEqual(ranks[0]["rank_name"], "Sentinela Imortal")
        self.assertEqual(ranks[-1]["rank_name"], "Cinzas Novatas")

    def test_hierarquia_de_cla_e_comunidade_respeita_funcao(self):
        hierarchy = role_hierarchy_keys(include_staff=False)
        self.assertLess(hierarchy.index("clan_leader"), hierarchy.index("clan_officer"))
        self.assertLess(hierarchy.index("clan_officer"), hierarchy.index("clan_member"))
        self.assertLess(hierarchy.index("creator"), hierarchy.index("member"))
        self.assertLess(hierarchy.index("ally"), hierarchy.index("member"))
        self.assertLess(hierarchy.index("member"), hierarchy.index("newcomer"))

    def test_ordenacao_automatica_nunca_tenta_mover_cargos_de_equipe(self):
        managed = managed_role_hierarchy_keys()
        self.assertEqual(len(managed), 29)
        self.assertTrue(set(STAFF_ROLE_ORDER).isdisjoint(managed))
        self.assertEqual(managed[0], "rank_sentinela_imortal")
        self.assertEqual(managed[-1], "bot_organizer")

    def test_patentes_antigas_e_novas_sao_reconhecidas(self):
        self.assertTrue(eh_cargo_patente("🔥・Executor Sombrio"))
        self.assertTrue(eh_cargo_patente("🔱・Arauto da Ruína"))
        self.assertTrue(eh_cargo_patente(nome_patente_exibicao("Guardião das Cinzas")))
        self.assertFalse(eh_cargo_patente("👑・Fundador"))

    def test_canais_de_interesse_têm_nove_opcoes_e_ids_persistentes(self):
        roles = [r for r in server_structure.ROLE_DEFINITIONS if r["group"] == "interest"]
        self.assertEqual(len(roles), 9)
        all_channels = [c[0] for cat in server_structure.ORGANIZATION for c in cat[3]]
        self.assertIn("🎭・escolha-seus-cargos", all_channels)
        self.assertIn("✅・verificação", all_channels)
        setting_keys = set(server_structure.ROLE_SETTING_KEYS.values())
        self.assertIn("video_notice_role_id", setting_keys)
        self.assertIn("live_notice_role_id", setting_keys)

    def test_categoria_de_entrada_e_visivel_sem_verificacao(self):
        self.assertEqual(server_structure.category_access_mode("category_start_id"), "entry")

    def test_categorias_publicas_exigem_cargo_de_membro_verificado(self):
        gated_keys = {
            key for _name, key, _aliases, _channels in server_structure.ORGANIZATION
            if key not in {"category_start_id", "category_team_id"}
        }
        self.assertEqual(len(gated_keys), 8)
        for key in gated_keys:
            with self.subTest(category=key):
                self.assertEqual(server_structure.category_access_mode(key), "verified")

    def test_categoria_de_equipe_tem_politica_propria(self):
        self.assertEqual(server_structure.category_access_mode("category_team_id"), "staff")


if __name__ == "__main__":
    unittest.main()
