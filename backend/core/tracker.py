"""
Watchtower Pricing — Price Tracker
Compares new prices against history, detects meaningful changes,
and orchestrates the full scrape → compare → alert pipeline.
"""

from __future__ import annotations
import logging
from typing import List, Optional, Tuple
from datetime import datetime

from core.models import (
    Product, PriceRecord, PriceChange, ScrapeResult,
    ChangeDirection, AlertConfig
)
from core.scraper import get_scraper
from storage.repository import PriceRepository
from alerts.notifier import AlertNotifier

logger = logging.getLogger(__name__)


class PriceTracker:
    """
    Main orchestrator. For each product:
      1. Scrape current price
      2. Load history from storage
      3. Detect change (if any)
      4. Persist new record
      5. Fire alerts if thresholds crossed
    """

    def __init__(
        self,
        repository: PriceRepository,
        notifier: AlertNotifier,
        alert_config: AlertConfig,
        proxy: Optional[str] = None,
    ):
        self.repo = repository
        self.notifier = notifier
        self.alert_config = alert_config
        self.proxy = proxy

    # ── Public API ──────────────────────────────────────────────────────────

    def run(self, products: List[Product]) -> List[PriceChange]:
        """Run a full tracking cycle for a list of products."""
        changes: List[PriceChange] = []
        for product in products:
            if not product.is_active:
                logger.info(f"Skipping inactive product: {product.name}")
                continue
            try:
                change = self._process_product(product)
                if change:
                    changes.append(change)
            except Exception as exc:
                logger.error(f"Error processing {product.url}: {exc}", exc_info=True)
        return changes

    def run_single(self, product: Product) -> Optional[PriceChange]:
        return self._process_product(product)

    # ── Internal ─────────────────────────────────────────────────────────────

    def _process_product(self, product: Product) -> Optional[PriceChange]:
        logger.info(f"Checking: {product.name or product.url}")

        # 1. Scrape
        store = product.detect_store()
        with get_scraper(store, proxy=self.proxy) as scraper:
            result: ScrapeResult = scraper.scrape(product.url, product.id)

        if not result.success or result.price is None:
            logger.warning(f"Scrape failed for {product.url}: {result.error}")
            self._save_failed_record(product, result)
            return None

        # 2. Auto-fill product name if missing
        if not product.name and result.title:
            product.name = result.title[:80]
            self.repo.update_product(product)

        # 3. Load last price from history
        last_record = self.repo.get_latest_price(product.id)

        # 4. Persist new price record
        new_record = PriceRecord(
            product_id=product.id,
            price=result.price,
            currency=result.currency,
            title=result.title,
            availability=result.availability,
            response_time_ms=result.duration_ms,
        )
        self.repo.save_price_record(new_record)

        # 5. Detect change
        if last_record is None:
            logger.info(f"First record for {product.name}: {result.currency} {result.price:,.2f}")
            return None

        change = self._compute_change(product, last_record, new_record)
        if change is None:
            return None

        logger.info(f"Change detected: {change.summary}")

        # 6. Alert
        if self._should_alert(change):
            self.notifier.notify(change, product, self.alert_config)

        return change

    def _compute_change(
        self,
        product: Product,
        old: PriceRecord,
        new: PriceRecord,
    ) -> Optional[PriceChange]:
        amount = new.price - old.price
        pct = (amount / old.price) * 100 if old.price else 0

        if abs(pct) < self.alert_config.min_change_percent:
            return None   # Below noise floor

        direction = (
            ChangeDirection.DROP if amount < 0
            else ChangeDirection.RISE if amount > 0
            else ChangeDirection.STABLE
        )

        return PriceChange(
            product_id=product.id,
            product_name=product.name,
            product_url=product.url,
            old_price=old.price,
            new_price=new.price,
            currency=new.currency,
            change_amount=amount,
            change_percent=pct,
            direction=direction,
            target_price=product.target_price,
        )

    def _should_alert(self, change: PriceChange) -> bool:
        """Alert on drops always; only alert on rises if significant."""
        if change.direction == ChangeDirection.DROP:
            return True
        if change.direction == ChangeDirection.RISE and abs(change.change_percent) >= 5:
            return True
        if change.below_target:
            return True
        return False

    def _save_failed_record(self, product: Product, result: ScrapeResult) -> None:
        record = PriceRecord(
            product_id=product.id,
            price=0.0,
            scrape_success=False,
            error_message=result.error,
            response_time_ms=result.duration_ms,
        )
        # Override validator for failed record (price = 0)
        self.repo.save_price_record(record)


# ── Standalone summary helper ─────────────────────────────────────────────────

def build_summary_report(changes: List[PriceChange]) -> str:
    if not changes:
        return "No significant price changes detected."
    drops = [c for c in changes if c.direction == ChangeDirection.DROP]
    rises = [c for c in changes if c.direction == ChangeDirection.RISE]
    lines = [f"📊 Watchtower Report — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC", ""]
    if drops:
        lines.append(f"📉 Price Drops ({len(drops)})")
        for c in drops:
            lines.append(f"  • {c.summary}")
            if c.below_target:
                lines.append(f"    🎯 BELOW YOUR TARGET of {c.currency} {c.target_price:,.0f}!")
    if rises:
        lines.append(f"\n📈 Price Rises ({len(rises)})")
        for c in rises:
            lines.append(f"  • {c.summary}")
    return "\n".join(lines)
