"""Arquitetura unificada de fontes de ofertas para o Quase Pro.

Cada fonte implementa um conector assíncrono que retorna uma lista de dicionários
padronizados. A falha de uma fonte nunca interrompe as demais. As chaves de oferta
são estáveis por loja+jogo para evitar duplicações quando o preço muda.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

import aiohttp

log = logging.getLogger("quasepro.ofertas")


@dataclass(frozen=True)
class Offer:
    """Representação imutável de uma oferta normalizada."""

    key: str
    title: str
    url: str
    source: str
    kind: str  # "free" | "promo" | "f2p"
    price: str
    original_price: str | None = None
    discount: int = 0
    currency: str = "BRL"
    platform: str = ""
    image: str | None = None
    description: str = ""
    end_date: str | None = None
    region: str = "BR"
    activation_platform: str = ""
    last_checked: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "kind": self.kind,
            "price": self.price,
            "original_price": self.original_price,
            "discount": self.discount,
            "currency": self.currency,
            "platform": self.platform or self.activation_platform,
            "image": self.image,
            "description": self.description,
            "end_date": self.end_date,
            "region": self.region,
            "activation_platform": self.activation_platform,
            "last_checked": self.last_checked,
        }


class SourceConnector(Protocol):
    """Contrato que todo conector de fonte deve implementar."""

    name: str
    enabled_by_default: bool

    async def fetch(self, session: aiohttp.ClientSession) -> list[Offer]: ...


# ---------------------------------------------------------------------------
# Utilitários compartilhados
# ---------------------------------------------------------------------------

def _money_brl(cents: Any) -> str | None:
    try:
        value = int(cents) / 100
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


async def _get_json(session: aiohttp.ClientSession, url: str, *, params: dict | None = None, timeout: float = 20.0) -> Any:
    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
            if resp.status == 429:
                log.warning("Rate limit em %s", url)
                return None
            resp.raise_for_status()
            return await resp.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
        log.exception("Falha consultando %s", url)
        return None


# ---------------------------------------------------------------------------
# Steam Store (API pública regional)
# ---------------------------------------------------------------------------

class SteamSource:
    name = "Steam"
    enabled_by_default = True

    async def fetch(self, session: aiohttp.ClientSession) -> list[Offer]:
        data = await _get_json(
            session,
            "https://store.steampowered.com/api/featuredcategories/",
            params={"cc": "br", "l": "brazilian"},
        )
        if not isinstance(data, dict):
            return []

        offers: list[Offer] = []
        for section_name in ("freegames", "specials"):
            section = data.get(section_name) or {}
            items = section.get("items", []) if isinstance(section, dict) else []
            for game in items:
                app_id = game.get("id")
                title = game.get("name")
                if not app_id or not title:
                    continue

                discount = _safe_int(game.get("discount_percent"))
                final_cents = game.get("final_price")
                initial_cents = game.get("original_price")
                actually_free = bool(game.get("is_free")) or final_cents == 0

                if not actually_free and (final_cents is None or discount <= 0):
                    continue

                final_price = "Grátis" if actually_free else _money_brl(final_cents)
                original_price = None if actually_free else _money_brl(initial_cents)
                if not final_price:
                    continue

                kind = "free" if actually_free else "promo"
                key = f"steam:{app_id}"  # chave estável; preço/disconto não fazem parte
                category = "JOGO GRÁTIS NA STEAM" if actually_free else f"PROMOÇÃO STEAM • {discount}% OFF"

                offers.append(Offer(
                    key=key,
                    title=title,
                    url=f"https://store.steampowered.com/app/{app_id}/?cc=br",
                    source="Steam Store Brasil",
                    kind=kind,
                    price=final_price,
                    original_price=original_price,
                    discount=discount,
                    platform="Steam",
                    image=game.get("header_image"),
                    description="Oferta regional da Steam. Confira a página da loja para condições e validade.",
                    end_date="Consulte a página da loja",
                    activation_platform="Steam",
                ))
        return offers


# ---------------------------------------------------------------------------
# GamerPower (API pública de giveaways)
# ---------------------------------------------------------------------------

class GamerPowerSource:
    name = "GamerPower"
    enabled_by_default = True

    async def fetch(self, session: aiohttp.ClientSession) -> list[Offer]:
        data = await _get_json(
            session,
            "https://www.gamerpower.com/api/giveaways",
            params={"type": "game"},
        )
        if not isinstance(data, list):
            return []

        offers: list[Offer] = []
        for g in data:
            title = g.get("title")
            url = g.get("open_giveaway_url") or g.get("gamerpower_url")
            if not title or not url:
                continue

            end_date = str(g.get("end_date") or "").strip()
            if not end_date or end_date.upper() == "N/A":
                end_date = None

            offers.append(Offer(
                key=f"gamerpower:{g.get('id') or title}",
                title=title,
                url=url,
                source="GamerPower",
                kind="free",
                price="Grátis",
                platform=g.get("platforms", "Plataforma não informada"),
                image=g.get("thumbnail"),
                description=(g.get("description") or "Jogo gratuito por tempo limitado.").strip(),
                end_date=end_date,
                activation_platform=g.get("platforms", ""),
            ))
        return offers


# ---------------------------------------------------------------------------
# Epic Games Store (GraphQL público)
# ---------------------------------------------------------------------------

class EpicGamesSource:
    name = "Epic Games Store"
    enabled_by_default = True

    _QUERY = """
    query searchStoreQuery($category: String, $locale: String) {
      Catalog {
        searchStore(category: $category, locale: $locale, count: 40) {
          elements {
            title
            id
            urlSlug
            productSlug
            promotions {
              promotionalOffers {
                promotionalOffers {
                  startDate
                  endDate
                  discountSetting {
                    discountType
                    discountPercentage
                  }
                }
              }
            }
            price {
              totalPrice {
                fmtPrice(locale: $locale) {
                  originalPrice
                  discountPrice
                }
              }
            }
            keyImages { type url }
          }
        }
      }
    }
    """

    async def fetch(self, session: aiohttp.ClientSession) -> list[Offer]:
        payload = {
            "query": self._QUERY,
            "variables": {"category": "freegames|on-sale", "locale": "pt-BR"},
        }
        try:
            async with session.post(
                "https://graphql.epicgames.com/graphql",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=25),
            ) as resp:
                if resp.status != 200:
                    log.warning("Epic Games GraphQL retornou status %s", resp.status)
                    return []
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            log.exception("Falha consultando Epic Games Store")
            return []

        elements = (
            data.get("data", {})
            .get("Catalog", {})
            .get("searchStore", {})
            .get("elements", [])
        )
        if not isinstance(elements, list):
            return []

        offers: list[Offer] = []
        now = datetime.now(timezone.utc)
        for item in elements:
            title = item.get("title")
            slug = item.get("productSlug") or item.get("urlSlug")
            if not title or not slug:
                continue

            # Preço formatado pela própria API
            fmt = (
                item.get("price", {})
                .get("totalPrice", {})
                .get("fmtPrice", {})
            )
            original_price_str = fmt.get("originalPrice") if isinstance(fmt, dict) else None
            discount_price_str = fmt.get("discountPrice") if isinstance(fmt, dict) else None

            # Detectar promoção ativa
            promos = item.get("promotions", {}).get("promotionalOffers", []) if isinstance(item.get("promotions"), dict) else []
            active_promo = False
            discount_pct = 0
            end_date = None
            for promo_group in (promos or []):
                for p in promo_group.get("promotionalOffers", []) if isinstance(promo_group, dict) else []:
                    ds = p.get("discountSetting", {}) if isinstance(p, dict) else {}
                    if ds.get("discountType") == "PERCENTAGE":
                        discount_pct = _safe_int(ds.get("discountPercentage"))
                    start = p.get("startDate")
                    end = p.get("endDate")
                    if start and end:
                        try:
                            s = datetime.fromisoformat(start.replace("Z", "+00:00"))
                            e = datetime.fromisoformat(end.replace("Z", "+00:00"))
                            if s <= now <= e:
                                active_promo = True
                                end_date = e.strftime("%d/%m/%Y %H:%M UTC")
                        except (ValueError, TypeError):
                            pass

            is_free = discount_price_str in (None, "", "R$ 0,00", "0") or discount_pct >= 100
            if not is_free and not active_promo:
                continue

            kind = "free" if is_free else "promo"
            price_display = "Grátis" if is_free else (discount_price_str or "Consulte a loja")
            original_display = original_price_str if not is_free else None

            image = None
            for img in item.get("keyImages", []) or []:
                if isinstance(img, dict) and img.get("url"):
                    image = img["url"]
                    break

            offers.append(Offer(
                key=f"epic:{item.get('id') or slug}",
                title=title,
                url=f"https://store.epicgames.com/p/{slug}",
                source="Epic Games Store",
                kind=kind,
                price=price_display,
                original_price=original_display,
                discount=discount_pct if not is_free else 100,
                platform="Epic Games Store",
                image=image,
                description="Oferta da Epic Games Store. Resgate diretamente na loja.",
                end_date=end_date,
                activation_platform="Epic Games Launcher",
            ))
        return offers


# ---------------------------------------------------------------------------
# GOG.com (API pública de catálogo)
# ---------------------------------------------------------------------------

class GogSource:
    name = "GOG"
    enabled_by_default = True

    async def fetch(self, session: aiohttp.ClientSession) -> list[Offer]:
        data = await _get_json(
            session,
            "https://catalog.gog.com/v1/catalog",
            params={
                "order": "desc:score",
                "productType": "in:game",
                "price": "in:0,0",  # jogos gratuitos ou em promoção
                "countryCode": "BR",
                "currencyCode": "BRL",
                "limit": "30",
            },
            timeout=20.0,
        )
        if not isinstance(data, dict):
            return []

        products = data.get("products", [])
        if not isinstance(products, list):
            return []

        offers: list[Offer] = []
        for p in products:
            pid = p.get("id")
            title = p.get("title")
            if not pid or not title:
                continue

            price_info = p.get("price", {}) if isinstance(p.get("price"), dict) else {}
            base = price_info.get("basePrice")
            final = price_info.get("finalPrice")
            discount_pct = _safe_int(price_info.get("discountPercentage"))

            if final is None:
                continue

            is_free = final == 0
            if not is_free and discount_pct <= 0:
                continue

            price_display = "Grátis" if is_free else _money_brl(final)
            original_display = None if is_free else _money_brl(base)
            if not price_display:
                continue

            cover = None
            images = p.get("images", []) if isinstance(p.get("images"), list) else []
            for img in images:
                if isinstance(img, dict) and img.get("url"):
                    cover = img["url"]
                    break

            offers.append(Offer(
                key=f"gog:{pid}",
                title=title,
                url=f"https://www.gog.com/game/{p.get('slug', pid)}",
                source="GOG.com",
                kind="free" if is_free else "promo",
                price=price_display,
                original_price=original_display,
                discount=discount_pct,
                platform="GOG",
                image=cover,
                description="Oferta do GOG.com. Jogo sem DRM.",
                end_date=None,
                activation_platform="GOG Galaxy / Standalone",
            ))
        return offers


# ---------------------------------------------------------------------------
# Nuuvem (scraping leve da página de busca/catalogo)
# ---------------------------------------------------------------------------

class NuuvemSource:
    """Conector para Nuuvem baseado em scraping da página de catálogo.

    A Nuuvem não oferece API pública documentada; este conector consulta a
    página de busca e extrai títulos, preços e links. É mais frágil que uma
    API oficial, mas é a única forma viável de integração automática.
    """

    name = "Nuuvem"
    enabled_by_default = True

    _SEARCH_URL = "https://www.nuuvem.com/catalog/search/{query}"
    _CATALOG_URL = "https://www.nuuvem.com/catalog"

    async def fetch(self, session: aiohttp.ClientSession) -> list[Offer]:
        # Busca por termos genéricos para capturar promoções ativas.
        queries = ["oferta", "gratis", "free"]
        all_offers: list[Offer] = []
        seen_keys: set[str] = set()

        for query in queries:
            url = self._SEARCH_URL.format(query=query)
            html = await self._fetch_html(session, url)
            if not html:
                continue
            items = self._parse_search_results(html, query)
            for item in items:
                if item.key not in seen_keys:
                    seen_keys.add(item.key)
                    all_offers.append(item)

        return all_offers

    async def _fetch_html(self, session: aiohttp.ClientSession, url: str) -> str | None:
        try:
            headers = {
                "User-Agent": "QuaseProBot/2.0 (compatible; offers-monitor)",
                "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
                "Accept": "text/html,application/xhtml+xml",
            }
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status != 200:
                    log.warning("Nuuvem retornou status %s para %s", resp.status, url)
                    return None
                return await resp.text()
        except (aiohttp.ClientError, asyncio.TimeoutError):
            log.exception("Falha consultando Nuuvem: %s", url)
            return None

    def _parse_search_results(self, html: str, query: str) -> list[Offer]:
        """Extrai produtos da página de busca usando regex simples.

        Evita dependência de BeautifulSoup no núcleo do bot; se o layout
        mudar significativamente, este parser precisará ser atualizado.
        """
        import re

        offers: list[Offer] = []
        # Padrão para cards de produto na Nuuvem (sujeito a mudanças de layout)
        # Busca blocos com título, preço e link
        card_pattern = re.compile(
            r'<a[^>]+href="(/[^"]+)"[^>]*class="[^"]*product-card[^"]*"[^>]*>.*?'
            r'class="[^"]*product-title[^"]*"[^>]*>([^<]+)</.*?'
            r'class="[^"]*product-price[^"]*"[^>]*>([^<]+)<',
            re.DOTALL | re.IGNORECASE,
        )

        for match in card_pattern.finditer(html):
            path, title_raw, price_raw = match.groups()
            title = title_raw.strip()
            price_text = price_raw.strip()

            if not title or not price_text:
                continue

            url = f"https://www.nuuvem.com{path}" if path.startswith("/") else path
            price_value = self._parse_price(price_text)
            is_free = price_value is not None and price_value <= 0

            if not is_free and price_value is None:
                continue

            price_display = "Grátis" if is_free else price_text
            key = f"nuuvem:{re.sub(r'[^a-z0-9]', '', title.lower())}"

            offers.append(Offer(
                key=key,
                title=title,
                url=url,
                source="Nuuvem",
                kind="free" if is_free else "promo",
                price=price_display,
                platform="PC",
                description="Oferta da Nuuvem. Confira a página da loja para condições.",
                activation_platform="PC",
            ))

        return offers

    @staticmethod
    def _parse_price(text: str) -> float | None:
        """Extrai valor numérico de texto de preço brasileiro."""
        import re
        cleaned = re.sub(r'[^\d,\.]', '', text.replace('.', '').replace(',', '.'))
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None


# ---------------------------------------------------------------------------
# Instant Gaming (scraping da página de busca)
# ---------------------------------------------------------------------------

class InstantGamingSource:
    """Conector para Instant Gaming baseado em scraping da página de busca.

    A Instant Gaming não oferece API pública gratuita; este conector consulta
    a página de pesquisa em português e extrai resultados com preços.
    """

    name = "Instant Gaming"
    enabled_by_default = True

    _SEARCH_URL = "https://www.instant-gaming.com/pt/pesquisar/?query={query}"

    async def fetch(self, session: aiohttp.ClientSession) -> list[Offer]:
        queries = ["oferta", "gratis", "free", "promo"]
        all_offers: list[Offer] = []
        seen_keys: set[str] = set()

        for query in queries:
            url = self._SEARCH_URL.format(query=query)
            html = await self._fetch_html(session, url)
            if not html:
                continue
            items = self._parse_search_results(html)
            for item in items:
                if item.key not in seen_keys:
                    seen_keys.add(item.key)
                    all_offers.append(item)

        return all_offers

    async def _fetch_html(self, session: aiohttp.ClientSession, url: str) -> str | None:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8",
                "Accept": "text/html,application/xhtml+xml",
                "Referer": "https://www.instant-gaming.com/en/",
            }
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status != 200:
                    log.warning("Instant Gaming retornou status %s para %s", resp.status, url)
                    return None
                return await resp.text()
        except (aiohttp.ClientError, asyncio.TimeoutError):
            log.exception("Falha consultando Instant Gaming: %s", url)
            return None

    def _parse_search_results(self, html: str) -> list[Offer]:
        """Extrai produtos da página de busca da Instant Gaming."""
        import re

        offers: list[Offer] = []
        # Padrão para artigos de produto na Instant Gaming
        article_pattern = re.compile(
            r'<article[^>]+class="[^"]*item[^"]*"[^>]*>.*?'
            r'<span[^>]+class="[^"]*title[^"]*"[^>]*>([^<]+)</span>.*?'
            r'<a[^>]+href="([^"]+)"[^>]*class="[^"]*cover[^"]*".*?>.*?'
            r'<div[^>]+class="[^"]*price[^"]*"[^>]*>([^<]*)</div>',
            re.DOTALL | re.IGNORECASE,
        )

        for match in article_pattern.finditer(html):
            title_raw, href, price_raw = match.groups()
            title = title_raw.strip()
            price_text = price_raw.strip() if price_raw else ""

            if not title:
                continue

            full_url = href if href.startswith("http") else f"https://www.instant-gaming.com{href}"
            price_value = self._parse_price(price_text)
            is_free = price_value is not None and price_value <= 0

            if not price_text and not is_free:
                continue

            price_display = "Grátis" if is_free else (price_text or "Consulte a loja")
            key = f"instantgaming:{re.sub(r'[^a-z0-9]', '', title.lower())}"

            offers.append(Offer(
                key=key,
                title=title,
                url=full_url,
                source="Instant Gaming",
                kind="free" if is_free else "promo",
                price=price_display,
                platform="PC",
                description="Oferta da Instant Gaming. Verifique a região e condições na loja.",
                activation_platform="PC",
            ))

        return offers

    @staticmethod
    def _parse_price(text: str) -> float | None:
        """Extrai valor numérico de texto de preço."""
        import re
        if not text:
            return None
        # Remove símbolos de moeda e normaliza separadores
        cleaned = re.sub(r'[^\d,\.]', '', text.replace('.', '').replace(',', '.'))
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None


# ---------------------------------------------------------------------------
# Registro central de fontes
# ---------------------------------------------------------------------------

ALL_SOURCES: list[SourceConnector] = [
    SteamSource(),
    GamerPowerSource(),
    EpicGamesSource(),
    GogSource(),
    NuuvemSource(),
    InstantGamingSource(),
]

SOURCE_NAMES = {s.name: s for s in ALL_SOURCES}


async def fetch_all_offers(
    session: aiohttp.ClientSession,
    *,
    enabled_sources: set[str] | None = None,
) -> tuple[list[Offer], dict[str, str]]:
    """Consulta todas as fontes habilitadas concorrentemente.

    Retorna (lista de ofertas, dicionário de erros por fonte).
    Uma fonte sem erro mas sem ofertas é considerada saudável.
    """
    sources = [s for s in ALL_SOURCES if enabled_sources is None or s.name in enabled_sources]
    errors: dict[str, str] = {}
    results = await asyncio.gather(
        *[s.fetch(session) for s in sources],
        return_exceptions=True,
    )

    all_offers: list[Offer] = []
    for source, result in zip(sources, results):
        if isinstance(result, Exception):
            errors[source.name] = f"{type(result).__name__}: {result}"
            log.error("Fonte %s falhou: %s", source.name, result)
        elif isinstance(result, list):
            all_offers.extend(result)
        else:
            errors[source.name] = "Retorno inesperado"

    return all_offers, errors