import os
from dotenv import load_dotenv

load_dotenv()


def _env_int(nome: str, padrao: int = 0) -> int:
    """IDs mal preenchidos no .env não devem impedir o bot de iniciar."""
    raw = os.getenv(nome, "").strip()
    if not raw:
        return padrao
    try:
        return int(raw)
    except ValueError:
        return padrao


TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = _env_int("GUILD_ID", 0) or None
MOD_CHANNEL_ID = _env_int("MOD_CHANNEL_ID")
SOULSLIKE_CHANNEL_ID = _env_int("SOULSLIKE_CHANNEL_ID")
COLIZEU_CHANNEL_ID = _env_int("COLIZEU_CHANNEL_ID")
PLATINAS_CHANNEL_ID = _env_int("PLATINAS_CHANNEL_ID")
MOD_ROLE_ID = _env_int("MOD_ROLE_ID")
PERFIS_CHANNEL_ID = _env_int("PERFIS_CHANNEL_ID")
# ID opcional do proprietário para personalização do santuário. Sem valor, não há ID embutido no código.
DONO_ID = _env_int("DONO_ID", 0)
DB_PATH = os.getenv("DB_PATH", "/data/colizeu.db" if os.path.isdir("/data") else "data/colizeu.db")

# Recompensas por platina aprovada
XP_PLATINA = 200
DENARIOS_PLATINA = 50

# Jogos zerados (versão leve das platinas, sem comprovante obrigatório)
ZERADOS_CHANNEL_ID = _env_int("ZERADOS_CHANNEL_ID")  # canal de anúncios (0 = não anuncia)
XP_ZERADO = int(os.getenv("XP_ZERADO", "50"))
DENARIOS_ZERADO = int(os.getenv("DENARIOS_ZERADO", "10"))
# Quantos zerados por 24h rendem XP/Denários (evita farm). 0 = sem limite.
ZERADOS_XP_LIMITE_DIARIO = int(os.getenv("ZERADOS_XP_LIMITE_DIARIO", "3"))

# Identidade visual (preto, dourado, prata)
COR_OURO = 0xD4AF37
COR_PRATA = 0xC0C0C0
COR_PRETO = 0x0D0D0D


# =====================================================================
# Configurações trazidas do bot antigo (YouTube, ofertas, cargos)
# Os nomes das variáveis de ambiente são os mesmos de antes.
# =====================================================================
import asyncio  # noqa: E402,F401
from datetime import timedelta, timezone  # noqa: E402
from pathlib import Path  # noqa: E402
from urllib.parse import quote  # noqa: E402
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError  # noqa: E402

def _env_bool(nome: str, padrao: bool) -> bool:
    return os.getenv(nome, str(padrao)).strip().lower() in ("1", "true", "sim", "yes")


TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "").strip()
YOUTUBE_CHANNEL_ID = os.getenv(
    "YOUTUBE_CHANNEL_ID", "UCBuR1KPa9g9yYilBiy_7iqw"
).strip()

# Canais do Discord
VIDEO_CHANNEL_ID = _env_int("CREATOR_VIDEO_CHANNEL_ID")
LIVE_CHANNEL_ID = _env_int("CREATOR_LIVE_CHANNEL_ID")
GAMES_CHANNEL_ID = _env_int("GAMES_CHANNEL_ID")
PROMOS_CHANNEL_ID = _env_int("PROMOS_CHANNEL_ID")

# Cargos mencionados nos avisos (criados pelo script do servidor)
ROLE_VIDEO = os.getenv("ROLE_VIDEO_NAME", "🔔 Avisos de Vídeo")
ROLE_LIVE = os.getenv("ROLE_LIVE_NAME", "🔴 Avisos de Live")

# Vídeos novos: RSS (leve, sem custo de cota).
# Lives: search.list da YouTube Data API (100 unidades por consulta).
# A cota padrão é 10.000/dia: a cada 10 min por 5 h = 30 consultas = 3.000 unidades.
YOUTUBE_VIDEO_CHECK_SECONDS = max(60, int(os.getenv("YOUTUBE_VIDEO_CHECK_SECONDS", "120")))
YOUTUBE_LIVE_CHECK_MINUTES = max(5, int(os.getenv("YOUTUBE_LIVE_CHECK_MINUTES", "10")))
LIVE_START_HOUR = int(os.getenv("LIVE_START_HOUR", "19"))
LIVE_END_HOUR = int(os.getenv("LIVE_END_HOUR", "24"))  # exclusivo: 19:00 até 23:59

OFFERS_CHECK_MINUTES = max(10, int(os.getenv("OFFERS_CHECK_MINUTES", "30")))
MAX_OFFERS_PER_CHECK = max(1, int(os.getenv("MAX_OFFERS_PER_CHECK", "8")))
# Só avisa promoções da Steam com pelo menos esse desconto (0 = todas)
MIN_PROMO_DISCOUNT = max(0, int(os.getenv("MIN_PROMO_DISCOUNT", "50")))
# Na primeira execução, registra as ofertas que já existem sem postar (evita inundar o canal)
SEED_OFFERS_ON_FIRST_RUN = _env_bool("SEED_OFFERS_ON_FIRST_RUN", True)

DATA_DIR = Path(os.getenv("DATA_DIR", "/data" if Path("/data").is_dir() else "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
SENT_DB_PATH = DATA_DIR / "sent_offers.sqlite3"

try:
    BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")
except ZoneInfoNotFoundError:
    BRAZIL_TZ = timezone(timedelta(hours=-3))  # Brasília não tem horário de verão atualmente

ATOM = "{http://www.w3.org/2005/Atom}"
YT = "{http://www.youtube.com/xml/schemas/2015}"
YOUTUBE_FEED_URL = (
    "https://www.youtube.com/feeds/videos.xml?channel_id="
    + quote(YOUTUBE_CHANNEL_ID)
)

