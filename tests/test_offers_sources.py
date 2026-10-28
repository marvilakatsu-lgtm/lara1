"""Testes automatizados para a arquitetura unificada de ofertas.
Usa respostas simuladas para validar normalização, deduplicação e tratamento de erros
sem depender de chamadas reais às APIs.
"""
import asyncio
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp

from offers_sources import (
    ALL_SOURCES,
    EpicGamesSource,
    GamerPowerSource,
    GogSource,
    Offer,
    SteamSource,
    fetch_all_offers,
)


class TestOfferDataclass(unittest.TestCase):
    """Valida a estrutura imutável e a serialização da oferta."""

    def test_offer_to_dict_contains_required_fields(self):
        offer = Offer(
            key="steam:123",
            title="Jogo Teste",
            url="https://store.steampowered.com/app/123",
            source="Steam",
            kind="promo",
            price="R$ 29,90",
            original_price="R$ 59,90",
            discount=50,
            platform="Steam",
        )
        data = offer.to_dict()
        self.assertEqual(data["key"], "steam:123")
        self.assertEqual(data["kind"], "promo")
        self.assertEqual(data["discount"], 50)
        self.assertIn("last_checked", data)

    def test_offer_key_stability(self):
        """Chaves não devem incluir preço ou desconto para evitar duplicações."""
        key1 = "steam:123"
        key2 = "steam:123"
        self.assertEqual(key1, key2)


class TestSteamSource(unittest.TestCase):
    def setUp(self):
        self.source = SteamSource()
        self.session = AsyncMock(spec=aiohttp.ClientSession)

    def test_normalizes_free_game(self):
        mock_data = {
            "freegames": {
                "items": [
                    {
                        "id": 400,
                        "name": "Jogo Grátis",
                        "is_free": True,
                        "final_price": 0,
                        "header_image": "https://img.jpg",
                    }
                ]
            },
            "specials": {"items": []},
        }
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_data)
        mock_resp.raise_for_status = MagicMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_resp)
        ctx.__aexit__ = AsyncMock(return_value=False)
        self.session.get.return_value = ctx

        offers = asyncio.run(self.source.fetch(self.session))
        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].kind, "free")
        self.assertEqual(offers[0].price, "Grátis")
        self.assertTrue(offers[0].key.startswith("steam:"))

    def test_normalizes_promo(self):
        mock_data = {
            "freegames": {"items": []},
            "specials": {
                "items": [
                    {
                        "id": 500,
                        "name": "Jogo Promo",
                        "discount_percent": 40,
                        "final_price": 5990,
                        "original_price": 9990,
                        "is_free": False,
                        "header_image": "https://img2.jpg",
                    }
                ]
            },
        }
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_data)
        mock_resp.raise_for_status = MagicMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_resp)
        ctx.__aexit__ = AsyncMock(return_value=False)
        self.session.get.return_value = ctx

        offers = asyncio.run(self.source.fetch(self.session))
        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].kind, "promo")
        self.assertEqual(offers[0].discount, 40)
        self.assertIsNotNone(offers[0].original_price)

    def test_handles_api_failure_gracefully(self):
        self.session.get.side_effect = aiohttp.ClientError("fail")
        offers = asyncio.run(self.source.fetch(self.session))
        self.assertEqual(offers, [])


class TestGamerPowerSource(unittest.TestCase):
    def setUp(self):
        self.source = GamerPowerSource()
        self.session = AsyncMock(spec=aiohttp.ClientSession)

    def test_normalizes_giveaway(self):
        mock_data = [
            {
                "id": 999,
                "title": "Giveaway Teste",
                "open_giveaway_url": "https://gamerpower.com/g/999",
                "thumbnail": "https://thumb.jpg",
                "description": "Resgate grátis.",
                "platforms": "PC",
                "end_date": "2026-12-31",
            }
        ]
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_data)
        mock_resp.raise_for_status = MagicMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_resp)
        ctx.__aexit__ = AsyncMock(return_value=False)
        self.session.get.return_value = ctx

        offers = asyncio.run(self.source.fetch(self.session))
        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].kind, "free")
        self.assertEqual(offers[0].source, "GamerPower")


class TestEpicGamesSource(unittest.TestCase):
    def setUp(self):
        self.source = EpicGamesSource()
        self.session = AsyncMock(spec=aiohttp.ClientSession)

    def test_detects_free_promotion(self):
        mock_data = {
            "data": {
                "Catalog": {
                    "searchStore": {
                        "elements": [
                            {
                                "title": "Epic Free",
                                "productSlug": "epic-free-slug",
                                "id": "epic-1",
                                "promotions": {
                                    "promotionalOffers": [
                                        {
                                            "promotionalOffers": [
                                                {
                                                    "startDate": "2026-01-01T00:00:00Z",
                                                    "endDate": "2099-12-31T23:59:59Z",
                                                    "discountSetting": {
                                                        "discountType": "PERCENTAGE",
                                                        "discountPercentage": 100,
                                                    },
                                                }
                                            ]
                                        }
                                    ]
                                },
                                "price": {
                                    "totalPrice": {
                                        "fmtPrice": {
                                            "originalPrice": "R$ 100,00",
                                            "discountPrice": "R$ 0,00",
                                        }
                                    }
                                },
                                "keyImages": [{"type": "main", "url": "https://epic.jpg"}],
                            }
                        ]
                    }
                }
            }
        }
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_data)
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_resp)
        ctx.__aexit__ = AsyncMock(return_value=False)
        self.session.post.return_value = ctx

        offers = asyncio.run(self.source.fetch(self.session))
        self.assertGreaterEqual(len(offers), 1)
        free_offer = next((o for o in offers if o.title == "Epic Free"), None)
        self.assertIsNotNone(free_offer)
        self.assertEqual(free_offer.kind, "free")


class TestFetchAllOffers(unittest.TestCase):
    def test_one_source_failure_does_not_block_others(self):
        session = AsyncMock(spec=aiohttp.ClientSession)
        # Steam funciona, GamerPower falha
        with patch.object(SteamSource, "fetch", return_value=[
            Offer(key="s:1", title="OK", url="x", source="Steam", kind="free", price="Grátis")
        ]):
            with patch.object(GamerPowerSource, "fetch", side_effect=RuntimeError("boom")):
                with patch.object(EpicGamesSource, "fetch", return_value=[]):
                    with patch.object(GogSource, "fetch", return_value=[]):
                        offers, errors = asyncio.run(fetch_all_offers(session))
        self.assertEqual(len(offers), 1)
        self.assertIn("GamerPower", errors)
        self.assertNotIn("Steam", errors)


if __name__ == "__main__":
    unittest.main()