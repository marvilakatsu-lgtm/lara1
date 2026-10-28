import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import server_structure
from levels import PATENTES, eh_cargo_patente, nome_patente_exibicao


class EstruturaServidorTests(unittest.TestCase):
    def test_dez_categorias_e_sessenta_e_dois_canais(self):
        self.assertEqual(len(server_structure.ORGANIZATION), 10)
        self.assertEqual(server_structure.count_channels(), 62)

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

    def test_patentes_antigas_e_novas_sao_reconhecidas(self):
        self.assertTrue(eh_cargo_patente("🔥・Executor Sombrio"))
        self.assertTrue(eh_cargo_patente("🔱・Arauto da Ruína"))
        self.assertTrue(eh_cargo_patente(nome_patente_exibicao("Guardião das Cinzas")))
        self.assertFalse(eh_cargo_patente("👑・Fundador"))

    def test_canais_de_interesse_têm_nove_opcoes_e_ids_persistentes(self):
        roles = [r for r in server_structure.ROLE_DEFINITIONS if r["group"] == "interest"]
        self.assertEqual(len(roles), 9)
        self.assertIn("🎭・escolha-seus-cargos", [c[0] for cat in server_structure.ORGANIZATION for c in cat[3]])
        setting_keys = set(server_structure.ROLE_SETTING_KEYS.values())
        self.assertIn("video_notice_role_id", setting_keys)
        self.assertIn("live_notice_role_id", setting_keys)


if __name__ == "__main__":
    unittest.main()
