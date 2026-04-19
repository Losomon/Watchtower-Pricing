"""
Watchtower Pricing — Test Suite
Run: pytest tests/ -v
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

# Adjust path for test discovery
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.models import (
    Product, PriceRecord, PriceChange, AlertConfig,
    SupportedStore, Currency, ChangeDirection
)
from core.scraper import GenericScraper, get_scraper, _REGISTRY
from core.tracker import PriceTracker, build_summary_report
from storage.repository import JsonRepository
from alerts.notifier import AlertNotifier


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_repo(tmp_path):
    return JsonRepository(data_dir=str(tmp_path))


@pytest.fixture
def sample_product():
    return Product(
        url="https://jumia.co.ke/sony-wh1000xm5/",
        name="Sony WH-1000XM5",
        store=SupportedStore.JUMIA,
        currency=Currency.KES,
        target_price=25000.0,
    )


@pytest.fixture
def sample_record(sample_product):
    return PriceRecord(
        product_id=sample_product.id,
        price=28500.0,
        currency=Currency.KES,
    )


# ── Model Tests ───────────────────────────────────────────────────────────────

class TestProduct:
    def test_valid_product(self, sample_product):
        assert sample_product.store == SupportedStore.JUMIA
        assert sample_product.currency == Currency.KES

    def test_invalid_url_raises(self):
        with pytest.raises(Exception):
            Product(url="not-a-url")

    def test_negative_target_raises(self):
        with pytest.raises(Exception):
            Product(url="https://example.com", target_price=-100)

    def test_detect_store_from_url(self):
        p = Product(url="https://amazon.com/dp/B09XS7JWHH")
        assert p.detect_store() == SupportedStore.AMAZON

    def test_generic_store_fallback(self):
        p = Product(url="https://somerandombrand.co.ke/product/1")
        assert p.detect_store() == SupportedStore.GENERIC


class TestPriceRecord:
    def test_valid_record(self, sample_record):
        assert sample_record.price == 28500.0

    def test_zero_price_raises(self, sample_product):
        with pytest.raises(Exception):
            PriceRecord(product_id=sample_product.id, price=0)

    def test_price_rounded(self, sample_product):
        r = PriceRecord(product_id=sample_product.id, price=28500.999)
        assert r.price == 28501.0


class TestPriceChange:
    def test_drop_direction(self, sample_product):
        c = PriceChange(
            product_id=sample_product.id, product_name="Test",
            product_url="https://example.com",
            old_price=30000, new_price=28000,
            currency=Currency.KES,
            change_amount=-2000, change_percent=-6.67,
            direction=ChangeDirection.DROP,
        )
        assert c.direction == ChangeDirection.DROP
        assert "▼" in c.summary

    def test_below_target_flag(self, sample_product):
        c = PriceChange(
            product_id=sample_product.id, product_name="Test",
            product_url="https://example.com",
            old_price=30000, new_price=24000,
            currency=Currency.KES,
            change_amount=-6000, change_percent=-20.0,
            direction=ChangeDirection.DROP,
            target_price=25000,
        )
        assert c.below_target is True


# ── Storage Tests ─────────────────────────────────────────────────────────────

class TestJsonRepository:
    def test_save_and_get_product(self, tmp_repo, sample_product):
        tmp_repo.save_product(sample_product)
        retrieved = tmp_repo.get_product(sample_product.id)
        assert retrieved is not None
        assert retrieved.name == sample_product.name

    def test_list_products(self, tmp_repo, sample_product):
        tmp_repo.save_product(sample_product)
        products = tmp_repo.list_products()
        assert len(products) == 1

    def test_delete_product(self, tmp_repo, sample_product):
        tmp_repo.save_product(sample_product)
        tmp_repo.delete_product(sample_product.id)
        assert tmp_repo.get_product(sample_product.id) is None

    def test_save_price_record(self, tmp_repo, sample_product, sample_record):
        tmp_repo.save_product(sample_product)
        tmp_repo.save_price_record(sample_record)
        latest = tmp_repo.get_latest_price(sample_product.id)
        assert latest is not None
        assert latest.price == 28500.0

    def test_price_history_ordering(self, tmp_repo, sample_product):
        tmp_repo.save_product(sample_product)
        prices = [28500, 27000, 29000, 26000]
        for p in prices:
            tmp_repo.save_price_record(PriceRecord(product_id=sample_product.id, price=p))
        history = tmp_repo.get_price_history(sample_product.id)
        assert [r.price for r in history] == prices

    def test_get_latest_returns_last(self, tmp_repo, sample_product):
        tmp_repo.save_product(sample_product)
        for p in [30000, 29000, 28000]:
            tmp_repo.save_price_record(PriceRecord(product_id=sample_product.id, price=p))
        latest = tmp_repo.get_latest_price(sample_product.id)
        assert latest.price == 28000

    def test_get_latest_when_empty(self, tmp_repo, sample_product):
        assert tmp_repo.get_latest_price(sample_product.id) is None


# ── Tracker Tests ─────────────────────────────────────────────────────────────

class TestPriceTracker:
    def _make_tracker(self, repo):
        notifier = MagicMock()
        config = AlertConfig(min_change_percent=1.0)
        return PriceTracker(repo, notifier, config)

    def test_first_scrape_no_change(self, tmp_repo, sample_product):
        tmp_repo.save_product(sample_product)
        tracker = self._make_tracker(tmp_repo)
        mock_result = MagicMock(success=True, price=28500.0, title="Sony Headphones",
                                 availability="In Stock", currency=Currency.KES, duration_ms=200.0, error=None)
        with patch("core.tracker.get_scraper") as mock_gs:
            mock_scraper = MagicMock()
            mock_scraper.__enter__ = MagicMock(return_value=mock_scraper)
            mock_scraper.__exit__ = MagicMock(return_value=False)
            mock_scraper.scrape.return_value = mock_result
            mock_gs.return_value = mock_scraper
            change = tracker.run_single(sample_product)
        assert change is None  # First scrape → no previous to compare

    def test_price_drop_detected(self, tmp_repo, sample_product):
        tmp_repo.save_product(sample_product)
        tmp_repo.save_price_record(PriceRecord(product_id=sample_product.id, price=30000.0))
        tracker = self._make_tracker(tmp_repo)
        mock_result = MagicMock(success=True, price=27000.0, title="Sony",
                                 availability=None, currency=Currency.KES, duration_ms=100.0, error=None)
        with patch("core.tracker.get_scraper") as mock_gs:
            mock_scraper = MagicMock()
            mock_scraper.__enter__ = MagicMock(return_value=mock_scraper)
            mock_scraper.__exit__ = MagicMock(return_value=False)
            mock_scraper.scrape.return_value = mock_result
            mock_gs.return_value = mock_scraper
            change = tracker.run_single(sample_product)
        assert change is not None
        assert change.direction == ChangeDirection.DROP
        assert change.change_percent < 0

    def test_small_change_below_threshold_ignored(self, tmp_repo, sample_product):
        tmp_repo.save_product(sample_product)
        tmp_repo.save_price_record(PriceRecord(product_id=sample_product.id, price=28500.0))
        tracker = self._make_tracker(tmp_repo)
        mock_result = MagicMock(success=True, price=28490.0, title=None,
                                 availability=None, currency=Currency.KES, duration_ms=100.0, error=None)
        with patch("core.tracker.get_scraper") as mock_gs:
            mock_scraper = MagicMock()
            mock_scraper.__enter__ = MagicMock(return_value=mock_scraper)
            mock_scraper.__exit__ = MagicMock(return_value=False)
            mock_scraper.scrape.return_value = mock_result
            mock_gs.return_value = mock_scraper
            change = tracker.run_single(sample_product)
        assert change is None  # 0.04% change → below 1% threshold

    def test_failed_scrape_returns_none(self, tmp_repo, sample_product):
        tmp_repo.save_product(sample_product)
        tracker = self._make_tracker(tmp_repo)
        mock_result = MagicMock(success=False, price=None, error="Timeout", duration_ms=5000.0)
        with patch("core.tracker.get_scraper") as mock_gs:
            mock_scraper = MagicMock()
            mock_scraper.__enter__ = MagicMock(return_value=mock_scraper)
            mock_scraper.__exit__ = MagicMock(return_value=False)
            mock_scraper.scrape.return_value = mock_result
            mock_gs.return_value = mock_scraper
            change = tracker.run_single(sample_product)
        assert change is None


# ── Scraper Registry Tests ─────────────────────────────────────────────────────

class TestScraperRegistry:
    def test_get_scraper_amazon(self):
        from core.scraper import AmazonScraper
        scraper = get_scraper(SupportedStore.AMAZON)
        assert isinstance(scraper, AmazonScraper)
        scraper.close()

    def test_get_scraper_generic_fallback(self):
        scraper = get_scraper(SupportedStore.GENERIC)
        assert isinstance(scraper, GenericScraper)
        scraper.close()


# ── Report Tests ──────────────────────────────────────────────────────────────

class TestReport:
    def test_empty_changes(self):
        assert "No significant" in build_summary_report([])

    def test_report_includes_drops(self):
        c = PriceChange(
            product_id="x", product_name="Widget", product_url="https://example.com",
            old_price=100, new_price=80, currency=Currency.KES,
            change_amount=-20, change_percent=-20.0, direction=ChangeDirection.DROP,
        )
        report = build_summary_report([c])
        assert "Drop" in report
        assert "Widget" in report
