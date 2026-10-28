"""Estrutura compacta e funcional do servidor Quase Pro.

A organização é orientada ao uso diário: menos categorias, canais combinados quando
compartilham a mesma finalidade e destinos de bot associados ao mesmo canal quando
isso facilita a navegação. Canais e mensagens antigos nunca são excluídos; os canais
obsoletos conhecidos são movidos para um arquivo privado durante a aplicação confirmada.
"""
from __future__ import annotations

from levels import PATENTES, SIMBOLOS_PATENTES, nome_patente_exibicao

# Cada canal é (nome, tipo, chave(s) de configuração, aliases antigos, acesso especial).
# A chave pode ser uma string ou uma tupla: feeds que servem ao mesmo propósito podem
# compartilhar um canal sem quebrar as configurações legadas dos respectivos módulos.
ORGANIZATION = [
    (
        "👋・INÍCIO", "category_start_id", ("COMECE AQUI", "🔥 PORTÕES DO SANTUÁRIO", "PORTÕES DO SANTUÁRIO"),
        [
            ("👋・boas-vindas", "text", None, ("boas-vindas", "bem-vindos", "welcome", "guia-do-servidor"), None),
            ("📜・regras", "text", None, ("regras", "regras-do-reino", "regras-do-servidor"), None),
            ("✅・verificação", "text", None, ("verificacao", "verificação", "verificacao-do-servidor"), None),
        ],
    ),
    (
        "📣・QUASE PRO", "category_quasepro_id", ("QUASE PRO", "🎬 QUASE PRO"),
        [
            ("📣・avisos-e-vídeos", "text", ("announcements_channel_id", "creator_video_channel_id"),
             ("avisos-do-canal", "anuncios-importantes", "anúncios-importantes", "novos-videos", "novos-vídeos", "videos", "vídeos"), None),
            ("🔴・lives", "text", "creator_live_channel_id", ("lives", "lives-ao-vivo", "avisos-de-lives"), None),
            ("💡・conteúdo-e-votações", "text", None,
             ("sugestoes-de-videos", "sugestões-de-vídeos", "votacoes-da-comunidade", "votações-da-comunidade", "bastidores-do-quase-pro"), None),
        ],
    ),
    (
        "💬・COMUNIDADE", "category_community_id", ("COMUNIDADE", "🏰 PRAÇA DOS MACULADOS", "PRAÇA DOS MACULADOS"),
        [
            ("💬・chat-geral", "text", None, ("chat-geral", "bate-papo", "conversa-geral", "apresente-se", "apresentacoes", "apresentações"), None),
            ("😂・memes-e-clipes", "text", None, ("memes", "memes-do-reino", "prints-e-clipes", "clipes", "prints"), None),
            ("🤝・procurando-jogadores", "text", None, ("procurando-jogadores", "procurando-coop"), None),
            ("🎮・outros-jogos", "text", None, ("outros-jogos", "conversas-sobre-jogos"), None),
            ("💭・ajuda-e-sugestões", "text", "support_channel_id",
             ("sugestoes-do-servidor", "sugestões-do-servidor", "sugestoes", "sugestões", "central-de-ajuda", "pergunte-a-ia", "pergunte-à-ia", "abrir-suporte"), None),
            ("🎭・cargos-de-interesse", "text", None, ("escolha-seus-cargos", "selecao-de-cargos", "escolha-cargos"), None),
        ],
    ),
    (
        "🎮・SOULSLIKE", "category_soulslike_id", ("UNIVERSO SOULSLIKE", "TERRAS SOULSLIKE", "⚔️ TERRAS SOULSLIKE"),
        [
            ("🌳・elden-ring", "text", None, ("elden-ring",), None),
            ("🔥・dark-souls", "text", None, ("dark-souls", "dark-souls-ii", "dark-souls-iii", "dark-souls-2", "dark-souls-3"), None),
            ("🌑・outros-soulslikes", "text", None,
             ("bloodborne", "sekiro", "demon-souls", "lies-of-p", "nightreign", "outros-soulslikes", "outros-soulslike"), None),
            ("🗡️・builds-e-chefes", "text", None,
             ("builds-e-armas", "builds-e-estrategias", "builds-e-estratégias", "chefes-e-estrategias", "chefes-e-estratégias", "lore-e-teorias"), None),
            ("🏆・runs-e-desafios", "text", "soulslike_channel_id", ("runs-e-desafios", "runs-registradas", "runs"), None),
        ],
    ),
    (
        "📚・CATÁLOGO", "category_catalog_id", ("CATÁLOGO E OFERTAS", "ARQUIVO DO VIAJANTE", "📚 ARQUIVO DO VIAJANTE"),
        [
            ("📚・jogos-e-mods", "text", ("catalog_channel_id", "mods_channel_id"),
             ("catalogo-de-jogos", "catálogo-de-jogos", "catalogo-de-mods", "catálogo-de-mods", "envio-de-mods"), None),
            ("🎁・ofertas-e-notícias", "text", ("games_channel_id", "promos_channel_id", "news_channel_id"),
             ("jogos-gratis", "jogos-grátis", "promocoes", "promocoes-gamer", "promoções-gamer", "noticias-gamer", "notícias-gamer"), None),
        ],
    ),
    (
        "🏆・PROGRESSÃO E CLÃS", "category_systems_id",
        ("SISTEMAS SOULSBOT", "COLISEU DAS CINZAS", "CLÃS", "SALÃO DOS JURAMENTOS", "🛡️ SALÃO DOS JURAMENTOS"),
        [
            ("🏅・perfis-e-conquistas", "text", ("perfis_channel_id", "platinas_channel_id", "zerados_channel_id"),
             ("perfis", "perfis-e-patentes", "hall-das-platinas", "platinas", "ranking-de-zerados", "conquistas-da-comunidade", "santuarios", "santuários"), None),
            ("⚔️・coliseu-e-desafios", "text", "colizeu_channel_id",
             ("coliseu", "hall-do-coliseu", "runs-registradas", "atividades-soulslike"), None),
            ("🛡️・clãs", "text", ("clan_hall_channel_id", "clan_recruitment_channel_id", "clan_ranking_channel_id", "clan_events_channel_id"),
             ("painel-de-clas", "painel-de-clãs", "recrutamento-de-clas", "recrutamento-de-clãs", "ranking-de-clas", "ranking-de-clãs", "atividades-coletivas", "eventos-de-clas", "eventos-de-clãs"), None),
        ],
    ),
    (
        "🔊・VOZ", "category_voice_id", ("VOZ", "FOGUEIRAS DA COMUNIDADE", "🔊 FOGUEIRAS DA COMUNIDADE"),
        [
            ("🔊・papo-livre", "voice", None, ("sala-geral", "papo-livre"), None),
            ("🎮・coop-e-jogos", "voice", None, ("sala-de-jogos", "coop-souls", "coop-e-jogos", "voz-outros-jogos"), None),
            ("🎙️・eventos", "voice", None, ("sala-de-eventos", "eventos"), None),
        ],
    ),
    (
        "🔒・EQUIPE", "category_team_id", ("EQUIPE", "BASTIDORES DA ORDEM", "🔒 BASTIDORES DA ORDEM"),
        [
            ("💬・chat-da-equipe", "text", None, ("chat-da-equipe",), None),
            ("📋・logs-e-auditoria", "text", ("mod_channel_id", "bot_logs_channel_id", "clan_audit_channel_id"),
             ("moderacao", "moderação", "logs", "logs-de-moderacao", "logs-de-moderação", "logs-dos-bots", "auditoria-de-clas", "auditoria-de-clãs"), None),
            ("🎫・suporte-e-aprovações", "text", "support_reports_channel_id",
             ("relatorios-de-suporte", "relatórios-de-suporte", "suporte-e-aprovacoes", "suporte-e-aprovações"), "support"),
        ],
    ),
]

ENTRY_CATEGORY_KEY = "category_start_id"
STAFF_CATEGORY_KEY = "category_team_id"
VERIFICATION_CHANNEL_NAME = "✅・verificação"
ROLE_GROUP_ORDER = ("staff", "rank", "community", "clan", "interest")
STAFF_ROLE_ORDER = ("founder", "administrator", "moderator", "support", "developer")
CLAN_ROLE_ORDER = ("clan_leader", "clan_officer", "clan_member")
COMMUNITY_ROLE_ORDER = ("creator", "ally", "member", "newcomer")

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
    {"key": "creator", "name": "📺・Criador de Conteúdo", "color": 0x5DADE2, "group": "community", "aliases": ("Criador de Conteúdo", "Criador de Conteudo"), "permissions": "none"},
    {"key": "ally", "name": "🤝・Aliado", "color": 0xB7950B, "group": "community", "aliases": ("Aliado",), "permissions": "none"},
    {"key": "member", "name": "🟢・Membro", "color": 0x27AE60, "group": "community", "aliases": ("Membro",), "permissions": "none"},
    {"key": "newcomer", "name": "🌱・Recém-chegado", "color": 0x82E0AA, "group": "community", "aliases": ("Recém-chegado", "Recem-chegado"), "permissions": "none"},
    {"key": "interest_elden_ring", "name": "🎮・Elden Ring", "color": 0x1F618D, "group": "interest", "aliases": ("Elden Ring",), "permissions": "none"},
    {"key": "interest_dark_souls", "name": "🔥・Dark Souls", "color": 0x884EA0, "group": "interest", "aliases": ("Dark Souls",), "permissions": "none"},
    {"key": "interest_bloodborne", "name": "🩸・Bloodborne", "color": 0x117864, "group": "interest", "aliases": ("Bloodborne",), "permissions": "none"},
    {"key": "interest_sekiro", "name": "🥷・Sekiro", "color": 0xCD6155, "group": "interest", "aliases": ("Sekiro",), "permissions": "none"},
    {"key": "interest_lies_of_p", "name": "🦾・Lies of P", "color": 0xA93226, "group": "interest", "aliases": ("Lies of P",), "permissions": "none"},
    {"key": "interest_nightreign", "name": "🌑・Nightreign", "color": 0x2874A6, "group": "interest", "aliases": ("Nightreign",), "permissions": "none"},
    {"key": "notice_videos", "name": "📹・Avisos de vídeos", "color": 0x239B56, "group": "interest", "aliases": ("Avisos de vídeos", "Avisos de videos"), "permissions": "none"},
    {"key": "notice_lives", "name": "🔴・Avisos de lives", "color": 0xCA6F1E, "group": "interest", "aliases": ("Avisos de lives",), "permissions": "none"},
    {"key": "events_challenges", "name": "🏆・Eventos e desafios", "color": 0x616A6B, "group": "interest", "aliases": ("Eventos e desafios",), "permissions": "none"},
])


def role_hierarchy_keys(include_staff: bool = True) -> list[str]:
    """Cargo keys em ordem visual de cima para baixo (maior para menor hierarquia)."""
    by_key = {item["key"]: item for item in ROLE_DEFINITIONS}
    keys: list[str] = []
    if include_staff:
        keys.extend(key for key in STAFF_ROLE_ORDER if key in by_key)
    ranks = sorted(
        (item for item in ROLE_DEFINITIONS if item.get("group") == "rank"),
        key=lambda item: int(item.get("level_min", 0)), reverse=True,
    )
    keys.extend(item["key"] for item in ranks)
    keys.extend(key for key in CLAN_ROLE_ORDER if key in by_key)
    keys.extend(key for key in COMMUNITY_ROLE_ORDER if key in by_key)
    keys.extend(item["key"] for item in ROLE_DEFINITIONS if item.get("group") == "interest")
    keys.extend(item["key"] for item in ROLE_DEFINITIONS if item["key"] not in keys and (include_staff or item.get("group") != "staff"))
    return keys


def managed_role_hierarchy_keys() -> list[str]:
    """Cargos que o bot pode organizar abaixo de si; exclui cargos de equipe."""
    return role_hierarchy_keys(include_staff=False)


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

CHANNEL_SETTINGS_LABELS = {
    "mod_channel_id": ("Logs e moderação", 0, "text"),
    "platinas_channel_id": ("Perfis e conquistas — platinas", 0, "text"),
    "colizeu_channel_id": ("Coliseu e desafios", 0, "text"),
    "perfis_channel_id": ("Perfis e conquistas — perfis", 0, "text"),
    "soulslike_channel_id": ("Runs e desafios Soulslike", 0, "text"),
    "zerados_channel_id": ("Perfis e conquistas — jogos concluídos", 0, "text"),
    "creator_video_channel_id": ("Avisos e vídeos do canal", 0, "text"),
    "creator_live_channel_id": ("Lives do canal", 0, "text"),
    "games_channel_id": ("Ofertas e notícias — jogos grátis", 0, "text"),
    "promos_channel_id": ("Ofertas e notícias — promoções", 0, "text"),
    "clan_hall_channel_id": ("Painel de clãs", 0, "text"),
    "announcements_channel_id": ("Avisos do Quase Pro", 0, "text"),
    "catalog_channel_id": ("Catálogo de jogos e mods — jogos", 0, "text"),
    "mods_channel_id": ("Catálogo de jogos e mods — mods", 0, "text"),
    "news_channel_id": ("Ofertas e notícias — notícias", 0, "text"),
    "support_channel_id": ("Ajuda e sugestões", 0, "text"),
    "support_reports_channel_id": ("Suporte e aprovações", 0, "text"),
    "clan_recruitment_channel_id": ("Painel de clãs — recrutamento", 0, "text"),
    "clan_ranking_channel_id": ("Painel de clãs — ranking", 0, "text"),
    "clan_events_channel_id": ("Painel de clãs — eventos", 0, "text"),
    "bot_logs_channel_id": ("Logs e auditoria — bots", 0, "text"),
    "clan_audit_channel_id": ("Logs e auditoria — clãs", 0, "text"),
}

CATEGORY_ALIASES = {
    "COMECE AQUI": "👋・INÍCIO",
    "QUASE PRO": "📣・QUASE PRO",
    "COMUNIDADE": "💬・COMUNIDADE",
    "PRAÇA DOS MACULADOS": "💬・COMUNIDADE",
    "UNIVERSO SOULSLIKE": "🎮・SOULSLIKE",
    "TERRAS SOULSLIKE": "🎮・SOULSLIKE",
    "SISTEMAS SOULSBOT": "🏆・PROGRESSÃO E CLÃS",
    "COLISEU DAS CINZAS": "🏆・PROGRESSÃO E CLÃS",
    "CATÁLOGO E OFERTAS": "📚・CATÁLOGO",
    "ARQUIVO DO VIAJANTE": "📚・CATÁLOGO",
    "VOZ": "🔊・VOZ",
    "FOGUEIRAS DA COMUNIDADE": "🔊・VOZ",
    "EQUIPE": "🔒・EQUIPE",
    "BASTIDORES DA ORDEM": "🔒・EQUIPE",
    "CLÃS": "🏆・PROGRESSÃO E CLÃS",
    "SALÃO DOS JURAMENTOS": "🏆・PROGRESSÃO E CLÃS",
    "ORÁCULO DO SANTUÁRIO": "💬・COMUNIDADE",
}

# This set includes old category titles and canonical names so duplicate old categories
# can be archived privately after a confirmed reorganization. Nothing is deleted.
LEGACY_CATEGORY_NAMES = {
    "comece-aqui", "portoes-do-santuario", "quase-pro", "comunidade", "praca-dos-maculados",
    "universo-soulslike", "terras-soulslike", "sistemas-soulsbot", "coliseu-das-cinzas",
    "catalogo-e-ofertas", "arquivo-do-viajante", "oraculo-do-santuario", "clas", "salao-dos-juramentos",
    "voz", "fogueiras-da-comunidade", "equipe", "bastidores-da-ordem",
    "inicio", "soulslike", "catalogo", "progressao-e-clas",
}


def normalize_name(value: str) -> str:
    """Normaliza nomes para comparação de aliases sem depender de acentos ou emojis."""
    import unicodedata
    value = str(value or "").split("・", 1)[-1].strip().casefold()
    value = "".join(ch for ch in unicodedata.normalize("NFKD", value) if not unicodedata.combining(ch))
    return "-".join("".join(ch if ch.isalnum() else " " for ch in value).split())


def legacy_channel_names() -> set[str]:
    names = set()
    for _category, _key, _aliases, channels in ORGANIZATION:
        for channel_name, _kind, _setting, aliases, _access in channels:
            names.add(normalize_name(channel_name))
            names.update(normalize_name(alias) for alias in aliases)
    return names


def validate_role_palette() -> bool:
    colors = [entry["color"] for entry in ROLE_DEFINITIONS]
    names = [entry["name"] for entry in ROLE_DEFINITIONS]
    keys = [entry["key"] for entry in ROLE_DEFINITIONS]
    return len(colors) == len(set(colors)) and len(names) == len(set(names)) and len(keys) == len(set(keys))


def count_channels() -> int:
    return sum(len(channels) for _name, _key, _aliases, channels in ORGANIZATION)


def category_access_mode(category_key: str) -> str:
    """Retorna 'entry', 'staff' ou 'verified' conforme a política de acesso."""
    if category_key == ENTRY_CATEGORY_KEY:
        return "entry"
    if category_key == STAFF_CATEGORY_KEY:
        return "staff"
    return "verified"


CATEGORY_KEYS = {key: name for name, key, _aliases, _channels in ORGANIZATION}
