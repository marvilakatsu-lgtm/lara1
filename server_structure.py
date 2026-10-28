"""Estrutura e identidade visual oficiais do servidor Quase Pro.

Este módulo contém apenas dados e utilitários puros para permitir validação sem
conectar à API do Discord. Nenhuma operação destrutiva é definida aqui.
"""
from __future__ import annotations

from levels import PATENTES, SIMBOLOS_PATENTES, nome_patente_exibicao

# (nome da categoria, chave persistida, aliases de categorias antigas, canais)
# Canais: (nome final, tipo, configuração opcional, alias de canal antigo, acesso especial)
ORGANIZATION = [
    (
        "🔥・PORTÕES DO SANTUÁRIO", "category_start_id", ("COMECE AQUI", "PORTÕES DO SANTUÁRIO"),
        [
            ("📜・boas-vindas", "text", None, ("boas-vindas", "bem-vindos"), None),
            ("📕・regras-do-reino", "text", None, ("regras", "regras-do-servidor"), None),
            ("📢・anúncios-importantes", "text", "announcements_channel_id", ("anuncios", "anuncios-importantes"), None),
            ("🎭・escolha-seus-cargos", "text", None, ("selecao-de-cargos", "escolha-seus-cargos"), None),
            ("🧭・guia-do-servidor", "text", None, ("guia-do-servidor",), None),
        ],
    ),
    (
        "🎬・QUASE PRO", "category_quasepro_id", ("QUASE PRO",),
        [
            ("📣・avisos-do-canal", "text", None, ("avisos-do-canal",), None),
            ("🎥・novos-vídeos", "text", "creator_video_channel_id", ("videos", "novos-videos"), None),
            ("🔴・lives-ao-vivo", "text", "creator_live_channel_id", ("lives", "lives-ao-vivo"), None),
            ("💡・sugestões-de-vídeos", "text", None, ("sugestoes", "sugestoes-de-videos"), None),
            ("🗳️・votações-da-comunidade", "text", None, ("votacoes-da-comunidade",), None),
            ("🎬・bastidores-do-quase-pro", "text", None, ("bastidores-do-quase-pro",), None),
        ],
    ),
    (
        "🏰・PRAÇA DOS MACULADOS", "category_community_id", ("COMUNIDADE", "PRAÇA DOS MACULADOS"),
        [
            ("💬・bate-papo", "text", None, ("chat-geral", "bate-papo"), None),
            ("👋・apresente-se", "text", None, ("apresentacoes", "apresente-se"), None),
            ("😂・memes-do-reino", "text", None, ("memes", "memes-do-reino"), None),
            ("📸・prints-e-clipes", "text", None, ("prints-e-clipes",), None),
            ("🤝・procurando-jogadores", "text", None, ("procurando-jogadores",), None),
            ("🎮・outros-jogos", "text", None, ("outros-jogos",), None),
            ("💭・sugestões-do-servidor", "text", None, ("sugestoes-do-servidor",), None),
        ],
    ),
    (
        "⚔️・TERRAS SOULSLIKE", "category_soulslike_id", ("UNIVERSO SOULSLIKE", "TERRAS SOULSLIKE"),
        [
            ("🌳・elden-ring", "text", None, ("elden-ring",), None),
            ("🔥・dark-souls", "text", None, ("dark-souls",), None),
            ("🛡️・dark-souls-ii", "text", None, ("dark-souls-ii",), None),
            ("⚔️・dark-souls-iii", "text", None, ("dark-souls-iii",), None),
            ("🩸・bloodborne", "text", None, ("bloodborne",), None),
            ("🥷・sekiro", "text", None, ("sekiro",), None),
            ("👑・demon-souls", "text", None, ("demon-souls",), None),
            ("🦾・lies-of-p", "text", None, ("lies-of-p",), None),
            ("🌑・nightreign", "text", None, ("nightreign",), None),
            ("🗡️・builds-e-armas", "text", None, ("builds-e-estrategias", "builds-e-armas"), None),
            ("💀・chefes-e-estratégias", "text", None, ("chefes-e-estrategias",), None),
            ("🏆・runs-e-desafios", "text", "soulslike_channel_id", ("runs-e-desafios",), None),
            ("📖・lore-e-teorias", "text", None, ("lore-e-teorias",), None),
        ],
    ),
    (
        "🏆・COLISEU DAS CINZAS", "category_systems_id", ("SISTEMAS SOULSBOT", "COLISEU DAS CINZAS"),
        [
            ("🏟️・hall-do-coliseu", "text", "colizeu_channel_id", ("coliseu", "hall-do-coliseu"), None),
            ("📊・ranking-de-zerados", "text", "zerados_channel_id", ("ranking", "ranking-de-zerados"), None),
            ("💎・hall-das-platinas", "text", "platinas_channel_id", ("platinas", "hall-das-platinas"), None),
            ("🎖️・perfis-e-patentes", "text", "perfis_channel_id", ("perfis", "perfis-e-patentes"), None),
            ("🔥・santuários", "text", None, ("santuarios", "santuários"), None),
            ("📜・runs-registradas", "text", None, ("runs-registradas",), None),
            ("🥇・conquistas-da-comunidade", "text", None, ("conquistas-da-comunidade",), None),
        ],
    ),
    (
        "📚・ARQUIVO DO VIAJANTE", "category_catalog_id", ("CATÁLOGO E OFERTAS", "ARQUIVO DO VIAJANTE"),
        [
            ("🎮・catálogo-de-jogos", "text", "catalog_channel_id", ("catalogo-de-jogos", "catálogo-de-jogos"), None),
            ("🧩・catálogo-de-mods", "text", "mods_channel_id", ("catalogo-de-mods", "catálogo-de-mods"), None),
            ("📥・envio-de-mods", "text", None, ("envio-de-mods",), None),
            ("📰・notícias-gamer", "text", "news_channel_id", ("noticias-gamer", "notícias-gamer"), None),
            ("🎁・jogos-grátis", "text", "games_channel_id", ("jogos-gratis", "jogos-grátis"), None),
            ("💰・promoções-gamer", "text", "promos_channel_id", ("promocoes", "promocoes-gamer", "promoções-gamer"), None),
        ],
    ),
    (
        "🤖・ORÁCULO DO SANTUÁRIO", "category_oracle_id", ("ORÁCULO DO SANTUÁRIO",),
        [
            ("🧠・pergunte-à-ia", "text", None, ("pergunte-a-ia", "pergunte-à-ia"), None),
            ("📘・central-de-ajuda", "text", None, ("central-de-ajuda",), None),
            ("🎫・abrir-suporte", "text", "support_channel_id", ("abrir-suporte",), None),
        ],
    ),
    (
        "🛡️・SALÃO DOS JURAMENTOS", "category_clans_id", ("CLÃS", "SALÃO DOS JURAMENTOS"),
        [
            ("⚔️・painel-de-clãs", "text", "clan_hall_channel_id", ("painel-de-clas", "painel-de-clãs"), None),
            ("📜・recrutamento-de-clãs", "text", "clan_recruitment_channel_id", ("recrutamento-de-clas", "recrutamento-de-clãs"), None),
            ("🏅・ranking-de-clãs", "text", "clan_ranking_channel_id", ("ranking-de-clas", "ranking-de-clãs"), None),
            ("📅・eventos-de-clãs", "text", "clan_events_channel_id", ("atividades-coletivas", "eventos-de-clas", "eventos-de-clãs"), None),
        ],
    ),
    (
        "🔊・FOGUEIRAS DA COMUNIDADE", "category_voice_id", ("VOZ", "FOGUEIRAS DA COMUNIDADE"),
        [
            ("🔥・papo-livre", "voice", None, ("Sala Geral", "papo-livre"), None),
            ("🤝・coop-souls", "voice", None, ("Sala de Jogos", "coop-souls"), None),
            ("⚔️・arena-pvp", "voice", None, ("arena-pvp",), None),
            ("🎮・outros-jogos", "voice", None, ("voz-outros-jogos",), None),
            ("🎙️・sala-de-eventos", "voice", None, ("sala-de-eventos",), None),
        ],
    ),
    (
        "🔒・BASTIDORES DA ORDEM", "category_team_id", ("EQUIPE", "BASTIDORES DA ORDEM"),
        [
            ("💬・chat-da-equipe", "text", None, ("chat-da-equipe",), None),
            ("🛡️・logs-de-moderação", "text", "mod_channel_id", ("moderacao", "logs-de-moderacao", "logs-de-moderação"), None),
            ("🤖・logs-dos-bots", "text", "bot_logs_channel_id", ("logs", "logs-dos-bots"), "developer"),
            ("⚙️・comandos-adm", "text", None, ("comandos-adm",), "developer"),
            ("🎫・relatórios-de-suporte", "text", "support_reports_channel_id", ("relatorios-de-suporte", "relatórios-de-suporte"), "support"),
            ("📋・auditoria-de-clãs", "text", "clan_audit_channel_id", ("auditoria-de-clas", "auditoria-de-clãs"), None),
        ],
    ),
]

# Alias explicitamente listados para migrar nomes antigos sem excluir mensagens.
CATEGORY_KEYS = {key: name for name, key, _aliases, _channels in ORGANIZATION}

# Hierarquia visual e operacional: staff > patentes > clãs > comunidade > interesses > etiquetas técnicas.
ROLE_GROUP_ORDER = ("staff", "rank", "clan", "community", "interest", "technical")

# Role definitions use distinct hex colors across all managed roles. The three
# permission profiles are applied only after an administrator confirms /adm.
ROLE_DEFINITIONS = [
    {"key": "founder", "name": "👑・Fundador", "color": 0xF1C40F, "group": "staff", "aliases": ("Fundador", "👑 Fundador"), "permissions": "founder"},
    {"key": "administrator", "name": "⚙️・Administrador", "color": 0xE74C3C, "group": "staff", "aliases": ("Administrador", "⚙️ Administrador"), "permissions": "administrator"},
    {"key": "moderator", "name": "🛡️・Moderador", "color": 0x3498DB, "group": "staff", "aliases": ("Moderador", "🛡️ Moderador"), "permissions": "moderator"},
    {"key": "support", "name": "🎫・Equipe de Suporte", "color": 0x9B59B6, "group": "staff", "aliases": ("Equipe de Suporte", "🎫 Equipe de Suporte"), "permissions": "none"},
    {"key": "developer", "name": "🔧・Desenvolvedor", "color": 0x1ABC9C, "group": "staff", "aliases": ("Desenvolvedor", "🔧 Desenvolvedor"), "permissions": "none"},
]

RANK_ROLE_COLORS = {
    "Cinzas Novatas": 0x7F8C8D,
    "Guerreiro Caído": 0x8E6E53,
    "Caçador de Almas": 0x7B241C,
    "Cavaleiro do Abismo": 0x2E4053,
    "Guardião das Cinzas": 0x566573,
    "Arauto da Ruína": 0x6C3483,
    "Executor Sombrio": 0x17202A,
    "Senhor das Almas": 0xD35400,
    "Lenda do Coliseu": 0xBA4A00,
    "Sentinela Imortal": 0xF4D03F,
}
_OLD_RANK_SYMBOLS = {
    "Cinzas Novatas": "🔥", "Guerreiro Caído": "⚔️", "Caçador de Almas": "☠️",
    "Cavaleiro do Abismo": "🛡️", "Guardião das Cinzas": "🌑", "Arauto da Ruína": "🔱",
    "Executor Sombrio": "💀", "Senhor das Almas": "👑", "Lenda do Coliseu": "🏆",
    "Sentinela Imortal": "🌟",
}
for _minimum, _base_name in PATENTES:
    ROLE_DEFINITIONS.append({
        "key": "rank_" + "_".join(_base_name.lower().replace("í", "i").replace("á", "a").replace("ã", "a").replace("ê", "e").replace("ó", "o").split()),
        "name": nome_patente_exibicao(_base_name),
        "color": RANK_ROLE_COLORS[_base_name],
        "group": "rank",
        "rank_name": _base_name,
        "level_min": _minimum,
        "aliases": (_base_name, f"{_OLD_RANK_SYMBOLS[_base_name]}・{_base_name}", f"{_OLD_RANK_SYMBOLS[_base_name]} { _base_name}"),
        "permissions": "none",
    })

ROLE_DEFINITIONS.extend([
    {"key": "clan_leader", "name": "👑・Líder de Clã", "color": 0xAF7AC5, "group": "clan", "aliases": ("Líder de Clã", "Líder de Clan"), "permissions": "none"},
    {"key": "clan_officer", "name": "🗡️・Oficial de Clã", "color": 0x4A235A, "group": "clan", "aliases": ("Oficial de Clã", "Oficial de Clan"), "permissions": "none"},
    {"key": "clan_member", "name": "⚔️・Membro de Clã", "color": 0x0E6251, "group": "clan", "aliases": ("Membro de Clã", "Membro de Clan"), "permissions": "none"},
    {"key": "newcomer", "name": "🌱・Recém-chegado", "color": 0x82E0AA, "group": "community", "aliases": ("Recém-chegado", "Recem-chegado"), "permissions": "none"},
    {"key": "member", "name": "🟢・Membro", "color": 0x27AE60, "group": "community", "aliases": ("Membro",), "permissions": "none"},
    {"key": "creator", "name": "📺・Criador de Conteúdo", "color": 0x5DADE2, "group": "community", "aliases": ("Criador de Conteúdo", "Criador de Conteudo"), "permissions": "none"},
    {"key": "ally", "name": "🤝・Aliado", "color": 0xB7950B, "group": "community", "aliases": ("Aliado",), "permissions": "none"},
    {"key": "interest_elden_ring", "name": "🎮・Elden Ring", "color": 0x1F618D, "group": "interest", "aliases": ("Elden Ring",), "permissions": "none"},
    {"key": "interest_dark_souls", "name": "🔥・Dark Souls", "color": 0x884EA0, "group": "interest", "aliases": ("Dark Souls",), "permissions": "none"},
    {"key": "interest_bloodborne", "name": "🩸・Bloodborne", "color": 0x117864, "group": "interest", "aliases": ("Bloodborne",), "permissions": "none"},
    {"key": "interest_sekiro", "name": "🥷・Sekiro", "color": 0xCD6155, "group": "interest", "aliases": ("Sekiro",), "permissions": "none"},
    {"key": "interest_lies_of_p", "name": "🦾・Lies of P", "color": 0xA93226, "group": "interest", "aliases": ("Lies of P",), "permissions": "none"},
    {"key": "interest_nightreign", "name": "🌑・Nightreign", "color": 0x2874A6, "group": "interest", "aliases": ("Nightreign",), "permissions": "none"},
    {"key": "notice_videos", "name": "📹・Avisos de vídeos", "color": 0x239B56, "group": "interest", "aliases": ("Avisos de vídeos", "Avisos de videos"), "permissions": "none"},
    {"key": "notice_lives", "name": "🔴・Avisos de lives", "color": 0xCA6F1E, "group": "interest", "aliases": ("Avisos de lives",), "permissions": "none"},
    {"key": "events_challenges", "name": "🏆・Eventos e desafios", "color": 0x616A6B, "group": "interest", "aliases": ("Eventos e desafios",), "permissions": "none"},
    {"key": "bot_soulsbot", "name": "🤖・Soulsbot", "color": 0xA3E4D7, "group": "technical", "aliases": ("Soulsbot",), "permissions": "none"},
    {"key": "bot_catalog", "name": "📚・Bot Catálogo", "color": 0xF5B7B1, "group": "technical", "aliases": ("Bot Catálogo", "Bot Catalogo"), "permissions": "none"},
    {"key": "bot_organizer", "name": "⚙️・Bot Organizador", "color": 0xFAD7A0, "group": "technical", "aliases": ("Bot Organizador",), "permissions": "none"},
])

# Settings whose logical names are consumed by existing bot modules.
ROLE_SETTING_KEYS = {
    "founder": "founder_role_id",
    "administrator": "admin_role_id",
    "moderator": "moderation_role_id",
    "support": "support_role_id",
    "developer": "developer_role_id",
    "member": "member_role_id",
    "notice_videos": "video_notice_role_id",
    "notice_lives": "live_notice_role_id",
}

# Old category names map to the official category, while preserving channel IDs.
CHANNEL_SETTINGS_LABELS = {
    "mod_channel_id": ("Logs de moderação e aprovações", 0, "text"),
    "platinas_channel_id": ("Hall das platinas", 0, "text"),
    "colizeu_channel_id": ("Hall do Coliseu", 0, "text"),
    "perfis_channel_id": ("Perfis e patentes", 0, "text"),
    "soulslike_channel_id": ("Runs e desafios Soulslike", 0, "text"),
    "zerados_channel_id": ("Ranking de zerados", 0, "text"),
    "creator_video_channel_id": ("Novos vídeos do canal", 0, "text"),
    "creator_live_channel_id": ("Lives ao vivo", 0, "text"),
    "games_channel_id": ("Jogos grátis", 0, "text"),
    "promos_channel_id": ("Promoções gamer", 0, "text"),
    "clan_hall_channel_id": ("Painel de clãs / Salão dos Juramentos", 0, "text"),
    "announcements_channel_id": ("Anúncios importantes", 0, "text"),
    "catalog_channel_id": ("Catálogo de jogos", 0, "text"),
    "mods_channel_id": ("Catálogo de mods", 0, "text"),
    "news_channel_id": ("Notícias gamer", 0, "text"),
    "support_channel_id": ("Abrir suporte", 0, "text"),
    "support_reports_channel_id": ("Relatórios de suporte", 0, "text"),
    "clan_recruitment_channel_id": ("Recrutamento de clãs", 0, "text"),
    "clan_ranking_channel_id": ("Ranking de clãs", 0, "text"),
    "clan_events_channel_id": ("Eventos de clãs", 0, "text"),
    "bot_logs_channel_id": ("Logs dos bots", 0, "text"),
    "clan_audit_channel_id": ("Auditoria de clãs", 0, "text"),
}

CATEGORY_ALIASES = {
    "COMECE AQUI": "🔥・PORTÕES DO SANTUÁRIO",
    "QUASE PRO": "🎬・QUASE PRO",
    "COMUNIDADE": "🏰・PRAÇA DOS MACULADOS",
    "UNIVERSO SOULSLIKE": "⚔️・TERRAS SOULSLIKE",
    "SISTEMAS SOULSBOT": "🏆・COLISEU DAS CINZAS",
    "CATÁLOGO E OFERTAS": "📚・ARQUIVO DO VIAJANTE",
    "VOZ": "🔊・FOGUEIRAS DA COMUNIDADE",
    "EQUIPE": "🔒・BASTIDORES DA ORDEM",
    "CLÃS": "🛡️・SALÃO DOS JURAMENTOS",
}


def normalize_name(value: str) -> str:
    """Normaliza nomes para comparação de aliases sem depender de acentos."""
    import unicodedata
    value = str(value or "").split("・", 1)[-1].strip().casefold()
    value = "".join(ch for ch in unicodedata.normalize("NFKD", value) if not unicodedata.combining(ch))
    return "-".join("".join(ch if ch.isalnum() else " " for ch in value).split())


def validate_role_palette() -> bool:
    colors = [entry["color"] for entry in ROLE_DEFINITIONS]
    names = [entry["name"] for entry in ROLE_DEFINITIONS]
    keys = [entry["key"] for entry in ROLE_DEFINITIONS]
    return len(colors) == len(set(colors)) and len(names) == len(set(names)) and len(keys) == len(set(keys))


def count_channels() -> int:
    return sum(len(channels) for _name, _key, _aliases, channels in ORGANIZATION)
