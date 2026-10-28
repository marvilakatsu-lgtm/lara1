import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import server_structure
from levels import PATENTES, eh_cargo_patente, nome_patente_exibicao
from server_structure import role_hierarchy_keys, managed_role_hierarchy_keys, STAFF_ROLE_ORDER


class EstruturaServidorTests(unittest.TestCase):
    def test_estrutura_enxuta_com_oito_categorias_e_vinte_e_oito_canais(self):
        self.assertEqual(len(server_structure.ORGANIZATION), 8)
        self.assertEqual(server_structure.count_channels(), 28)

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
                if setting_key is not None:
                    keys = (setting_key,) if isinstance(setting_key, str) else setting_key
                    self.assertTrue(all(isinstance(key, str) and key.endswith("_id") for key in keys))

    def test_nomes_das_categorias_sao_os_do_plano(self):
        self.assertEqual(
            [row[0] for row in server_structure.ORGANIZATION],
            [
                "👋・INÍCIO",
                "📣・QUASE PRO",
                "💬・COMUNIDADE",
                "🎮・SOULSLIKE",
                "📚・CATÁLOGO",
                "🏆・PROGRESSÃO E CLÃS",
                "🔊・VOZ",
                "🔒・EQUIPE",
            ],
        )

    def test_todos_os_cargos_tem_nome_chave_e_cor_unicos(self):
        self.assertEqual(len(server_structure.ROLE_DEFINITIONS), 31)
        self.assertTrue(server_structure.validate_role_palette())
        self.assertEqual(len({r["color"] for r in server_structure.ROLE_DEFINITIONS}), 31)
        self.assertNotIn("bot_soulsbot", {r["key"] for r in server_structure.ROLE_DEFINITIONS})
        self.assertNotIn("bot_catalog", {r["key"] for r in server_structure.ROLE_DEFINITIONS})
        self.assertNotIn("bot_organizer", {r["key"] for r in server_structure.ROLE_DEFINITIONS})

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
        self.assertEqual(len(managed), 26)
        self.assertTrue(set(STAFF_ROLE_ORDER).isdisjoint(managed))
        self.assertEqual(managed[0], "rank_sentinela_imortal")
        self.assertEqual(managed[-1], "events_challenges")

    def test_patentes_antigas_e_novas_sao_reconhecidas(self):
        self.assertTrue(eh_cargo_patente("🔥・Executor Sombrio"))
        self.assertTrue(eh_cargo_patente("🔱・Arauto da Ruína"))
        self.assertTrue(eh_cargo_patente(nome_patente_exibicao("Guardião das Cinzas")))
        self.assertFalse(eh_cargo_patente("👑・Fundador"))

    def test_canais_de_interesse_têm_nove_opcoes_e_ids_persistentes(self):
        roles = [r for r in server_structure.ROLE_DEFINITIONS if r["group"] == "interest"]
        self.assertEqual(len(roles), 9)
        all_channels = [c[0] for cat in server_structure.ORGANIZATION for c in cat[3]]
        self.assertIn("🎭・cargos-de-interesse", all_channels)
        self.assertIn("✅・verificação", all_channels)
        combined = {key for _name, _kind, setting_key, _aliases, _access in (ch for cat in server_structure.ORGANIZATION for ch in cat[3])
                    for key in ((setting_key,) if isinstance(setting_key, str) else tuple(setting_key or ())) }
        self.assertTrue({"catalog_channel_id", "mods_channel_id", "games_channel_id", "promos_channel_id", "news_channel_id"}.issubset(combined))
        setting_keys = set(server_structure.ROLE_SETTING_KEYS.values())
        self.assertIn("video_notice_role_id", setting_keys)
        self.assertIn("live_notice_role_id", setting_keys)


    def test_destinos_duplicados_sao_unificados_sem_perder_chaves_legadas(self):
        mapping = {}
        for _category, _key, _aliases, channels in server_structure.ORGANIZATION:
            for channel_name, _kind, setting_key, _channel_aliases, _access in channels:
                keys = (setting_key,) if isinstance(setting_key, str) else tuple(setting_key or ())
                for key in keys:
                    mapping[key] = channel_name
        self.assertEqual(mapping["creator_video_channel_id"], "📣・avisos-e-vídeos")
        self.assertEqual(mapping["announcements_channel_id"], "📣・avisos-e-vídeos")
        self.assertEqual(mapping["catalog_channel_id"], "📚・jogos-e-mods")
        self.assertEqual(mapping["mods_channel_id"], "📚・jogos-e-mods")
        self.assertEqual(mapping["games_channel_id"], "🎁・ofertas-e-notícias")
        self.assertEqual(mapping["news_channel_id"], "🎁・ofertas-e-notícias")
        self.assertEqual(mapping["clan_hall_channel_id"], "🛡️・clãs")

    def test_categoria_de_entrada_e_visivel_sem_verificacao(self):
        self.assertEqual(server_structure.category_access_mode("category_start_id"), "entry")

    def test_membros_nao_verificados_nao_podem_escrever_na_categoria_de_entrada(self):
        admin_source = (Path(__file__).resolve().parents[1] / "cogs" / "admin.py").read_text(encoding="utf-8")
        self.assertIn("view_channel=True, send_messages=False, add_reactions=False", admin_source)
        self.assertIn("send_messages_in_threads=False", admin_source)

    def test_categorias_publicas_exigem_cargo_de_membro_verificado(self):
        gated_keys = {
            key for _name, key, _aliases, _channels in server_structure.ORGANIZATION
            if key not in {"category_start_id", "category_team_id"}
        }
        self.assertEqual(len(gated_keys), 6)
        for key in gated_keys:
            with self.subTest(category=key):
                self.assertEqual(server_structure.category_access_mode(key), "verified")

    def test_categoria_de_equipe_tem_politica_propria(self):
        self.assertEqual(server_structure.category_access_mode("category_team_id"), "staff")


if __name__ == "__main__":
    unittest.main()
