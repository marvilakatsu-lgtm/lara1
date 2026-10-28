import unittest
from pathlib import Path

ADMIN_SOURCE = (Path(__file__).resolve().parents[1] / "cogs" / "admin.py").read_text(encoding="utf-8")


class DestructiveCleanupSourceTests(unittest.TestCase):
    def test_limpeza_e_uma_acao_separada_da_aplicacao_normal(self):
        self.assertIn('label="Aplicar estrutura e cargos"', ADMIN_SOURCE)
        self.assertIn('label="Prévia de limpeza total"', ADMIN_SOURCE)
        self.assertIn("class CleanupPreviewView", ADMIN_SOURCE)
        self.assertIn("class CleanupFinalConfirmationView", ADMIN_SOURCE)

    def test_exclusao_exige_confirmacao_textual_explicita(self):
        self.assertIn('Digite APAGAR RESTO para confirmar', ADMIN_SOURCE)
        self.assertIn('!= "APAGAR RESTO"', ADMIN_SOURCE)
        self.assertIn("class CleanupConfirmationModal", ADMIN_SOURCE)

    def test_limpeza_desstrutiva_requer_dono_do_servidor(self):
        self.assertGreaterEqual(ADMIN_SOURCE.count("interaction.user.id != interaction.guild.owner_id"), 3)
        self.assertIn("int(actor_id) != int(guild.owner_id)", ADMIN_SOURCE)

    def test_backup_precede_confirmacao_e_inclui_inventario(self):
        self.assertIn("create_cleanup_backup(interaction.guild, current_plan)", ADMIN_SOURCE)
        self.assertIn("server-state-and-deletion-manifest.json", ADMIN_SOURCE)
        self.assertIn("database-backup.zip", ADMIN_SOURCE)
        self.assertIn("não contém o histórico das mensagens do Discord", ADMIN_SOURCE)

    def test_clas_ativos_sao_preservados_pelo_id_persistido(self):
        self.assertIn("status IN ('active','degraded')", ADMIN_SOURCE)
        self.assertIn("protected_clan_category_ids", ADMIN_SOURCE)
        self.assertIn("protected_clan_channel_ids", ADMIN_SOURCE)

    def test_preserva_cargos_de_sistema_e_cargos_necessarios_ao_bot(self):
        self.assertIn("role.is_default() or role.id in target_role_ids", ADMIN_SOURCE)
        self.assertIn("if role.managed", ADMIN_SOURCE)
        self.assertIn("role.id in me_role_ids", ADMIN_SOURCE)
        self.assertIn("role >= me.top_role", ADMIN_SOURCE)

    def test_falta_de_canais_canonicos_bloqueia_a_limpeza(self):
        self.assertIn("Aplique a organização antes da limpeza", ADMIN_SOURCE)
        self.assertIn("current_plan[\"blockers\"]", ADMIN_SOURCE)
        self.assertIn("ainda está associado à configuração", ADMIN_SOURCE)


    def test_cargos_em_overwrites_de_areas_preservadas_bloqueiam_a_exclusao(self):
        self.assertIn("preserved_channel_objects", ADMIN_SOURCE)
        self.assertIn("overwrite_role_ids", ADMIN_SOURCE)
        self.assertIn("ainda controla permissões de um recurso preservado", ADMIN_SOURCE)

    def test_referencias_legadas_dos_dois_bots_sao_migradas_na_limpeza(self):
        self.assertIn('obsolete_bot_role_keys = {"role_bot_catalog_id", "role_bot_soulsbot_id"}', ADMIN_SOURCE)
        self.assertIn('item.name in {"Bot Catálogo", "Soulsbot"}', ADMIN_SOURCE)
        self.assertIn('"legacy_settings_to_remove": legacy_settings_to_remove', ADMIN_SOURCE)
        self.assertIn('"legacy_settings_to_remove": sorted(', ADMIN_SOURCE)
        self.assertIn('"legacy_role_setting_removed_for_cleanup"', ADMIN_SOURCE)

    def test_referencias_legadas_so_sao_removidas_depois_da_revalidacao_e_backup(self):
        execute_start = ADMIN_SOURCE.index("async def execute_cleanup_plan(")
        execute_end = ADMIN_SOURCE.index("    async def ", execute_start + 20)
        execute = ADMIN_SOURCE[execute_start:execute_end]
        self.assertLess(execute.index('fresh = await self.build_cleanup_plan(guild)'), execute.index('legacy_settings_to_remove', execute.index('fresh["blockers"]')))
        self.assertLess(execute.index('legacy_settings_to_remove', execute.index('fresh["blockers"]')), execute.index('for item in sorted(plan["roles"]'))

    def test_categorias_so_sao_apagadas_depois_dos_canais_e_quando_vazias(self):
        self.assertIn("for item in sorted(plan[\"channels\"]", ADMIN_SOURCE)
        self.assertIn("if category.channels:", ADMIN_SOURCE)
        self.assertIn("await category.delete(", ADMIN_SOURCE)

    def test_previa_reconhece_interacao_antes_de_montar_plano_lento(self):
        callback_start = ADMIN_SOURCE.index("async def preview_cleanup(")
        callback_end = ADMIN_SOURCE.index("class ConfirmOrganizationView", callback_start)
        callback = ADMIN_SOURCE[callback_start:callback_end]
        self.assertLess(callback.index("await interaction.response.defer()"), callback.index("await self.cog.build_cleanup_plan(interaction.guild)"))
        self.assertIn("await interaction.edit_original_response(content=None, embed=embed, view=view)", callback)
        self.assertIn("Nenhum canal, categoria ou cargo foi excluído.", callback)

    def test_painel_de_organizacao_tem_timeout_estendido(self):
        class_start = ADMIN_SOURCE.index("class OrganizationPreviewView")
        class_end = ADMIN_SOURCE.index("class ConfirmOrganizationView", class_start)
        view_source = ADMIN_SOURCE[class_start:class_end]
        self.assertIn("super().__init__(cog, guild_id, timeout=900)", view_source)


if __name__ == "__main__":
    unittest.main()
