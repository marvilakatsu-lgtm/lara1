import math

# (nível mínimo, patente)
PATENTES = [
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


def xp_para_nivel(nivel: int) -> int:
    """XP total necessário para ALCANÇAR o nível."""
    return 100 * (nivel - 1) ** 2


def nivel_por_xp(xp: int) -> int:
    return int(math.sqrt(max(xp, 0) / 100)) + 1


def patente_por_nivel(nivel: int) -> str:
    atual = PATENTES[0][1]
    for minimo, nome in PATENTES:
        if nivel >= minimo:
            atual = nome
    return atual


def barra_progresso(xp: int, tamanho: int = 10) -> str:
    nivel = nivel_por_xp(xp)
    base, topo = xp_para_nivel(nivel), xp_para_nivel(nivel + 1)
    frac = (xp - base) / (topo - base)
    cheio = int(frac * tamanho)
    return "▰" * cheio + "▱" * (tamanho - cheio) + f" {xp - base}/{topo - base} XP"


# Símbolos visuais das patentes.
SIMBOLOS_PATENTES = {
    # Os nomes e critérios de nível são preservados; os símbolos seguem a nova identidade do servidor.
    "Cinzas Novatas": "🪨",
    "Guerreiro Caído": "🩸",
    "Caçador de Almas": "💀",
    "Cavaleiro do Abismo": "⚔️",
    "Guardião das Cinzas": "🪶",
    "Arauto da Ruína": "🌑",
    "Executor Sombrio": "🔥",
    "Senhor das Almas": "🌌",
    "Lenda do Coliseu": "🏆",
    "Sentinela Imortal": "🌟",
}

def nome_patente_exibicao(nome: str) -> str:
    """Retorna a patente com símbolo sem duplicar o prefixo."""
    for nome_base, simbolo in SIMBOLOS_PATENTES.items():
        if nome == nome_base or nome == f"{simbolo}・{nome_base}":
            return f"{simbolo}・{nome_base}"
    return nome

def eh_cargo_patente(nome: str) -> bool:
    """Reconhece cargos de patente antigos e novos, inclusive símbolos legados."""
    nome = str(nome or "").strip()
    for base in SIMBOLOS_PATENTES:
        if nome == base or nome == nome_patente_exibicao(base):
            return True
        # Os cargos históricos tinham emojis diferentes antes da reformulação.
        if nome.endswith(f"・{base}") or nome.endswith(f" {base}"):
            return True
    return False
