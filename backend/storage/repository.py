"""
Watchtower Pricing — Storage Layer
Repository pattern: swap JSON ↔ SQLite ↔ PostgreSQL without changing tracker code.
"""

from __future__ import annotations
import json, csv, os
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict
from filelock import FileLock   # pip install filelock

from core.models import Product, PriceRecord, PriceChange


# ── Abstract Interface ────────────────────────────────────────────────────────

class PriceRepository(ABC):
    @abstractmethod
    def save_product(self, product: Product) -> None: ...
    @abstractmethod
    def get_product(self, product_id: str) -> Optional[Product]: ...
    @abstractmethod
    def list_products(self) -> List[Product]: ...
    @abstractmethod
    def update_product(self, product: Product) -> None: ...
    @abstractmethod
    def delete_product(self, product_id: str) -> None: ...
    @abstractmethod
    def save_price_record(self, record: PriceRecord) -> None: ...
    @abstractmethod
    def get_latest_price(self, product_id: str) -> Optional[PriceRecord]: ...
    @abstractmethod
    def get_price_history(self, product_id: str, limit: int = 30) -> List[PriceRecord]: ...


# ── JSON Implementation ───────────────────────────────────────────────────────

class JsonRepository(PriceRepository):
    """
    File-based storage using JSON for products and CSV for price history.
    Thread-safe via FileLock. Suitable for single-node up to ~10k records.
    Upgrade path: drop in SqliteRepository or PostgresRepository below.
    """

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._products_path = self.data_dir / "products.json"
        self._history_path = self.data_dir / "history.csv"
        self._lock = FileLock(str(self.data_dir / ".watchtower.lock"))
        self._ensure_files()

    # ── Products ──────────────────────────────────────────────────────────────

    def save_product(self, product: Product) -> None:
        products = self._load_products()
        products[product.id] = product.model_dump(mode="json")
        self._write_products(products)

    def get_product(self, product_id: str) -> Optional[Product]:
        products = self._load_products()
        data = products.get(product_id)
        return Product(**data) if data else None

    def list_products(self) -> List[Product]:
        return [Product(**v) for v in self._load_products().values()]

    def update_product(self, product: Product) -> None:
        self.save_product(product)

    def delete_product(self, product_id: str) -> None:
        products = self._load_products()
        products.pop(product_id, None)
        self._write_products(products)

    # ── Price Records ─────────────────────────────────────────────────────────

    def save_price_record(self, record: PriceRecord) -> None:
        with self._lock:
            with open(self._history_path, "a", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=self._csv_fields())
                row = record.model_dump(mode="json")
                # Flatten to CSV-safe types
                row["timestamp"] = row["timestamp"]
                writer.writerow({k: row.get(k, "") for k in self._csv_fields()})

    def get_latest_price(self, product_id: str) -> Optional[PriceRecord]:
        history = self.get_price_history(product_id, limit=1)
        return history[0] if history else None

    def get_price_history(self, product_id: str, limit: int = 30) -> List[PriceRecord]:
        records = []
        if not self._history_path.exists():
            return records
        with open(self._history_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("product_id") == product_id and row.get("scrape_success") != "False":
                    try:
                        records.append(PriceRecord(
                            id=row["id"],
                            product_id=row["product_id"],
                            price=float(row["price"]),
                            timestamp=datetime.fromisoformat(row["timestamp"]),
                            title=row.get("title") or None,
                            availability=row.get("availability") or None,
                        ))
                    except Exception:
                        pass
        # Return last `limit` records (most recent)
        return records[-limit:]

    # ── Stats helper ─────────────────────────────────────────────────────────

    def get_summary_stats(self) -> Dict:
        products = self.list_products()
        total_records = 0
        drops = 0
        rises = 0
        if self._history_path.exists():
            with open(self._history_path, newline="") as f:
                total_records = sum(1 for _ in f) - 1  # subtract header
        return {
            "products_tracked": len(products),
            "price_records": max(0, total_records),
            "active_products": sum(1 for p in products if p.is_active),
        }

    # ── Internal ─────────────────────────────────────────────────────────────

    def _ensure_files(self):
        if not self._products_path.exists():
            self._products_path.write_text("{}")
        if not self._history_path.exists():
            with open(self._history_path, "w", newline="") as f:
                csv.DictWriter(f, fieldnames=self._csv_fields()).writeheader()

    def _load_products(self) -> Dict:
        with self._lock:
            return json.loads(self._products_path.read_text())

    def _write_products(self, data: Dict) -> None:
        with self._lock:
            self._products_path.write_text(json.dumps(data, indent=2, default=str))

    @staticmethod
    def _csv_fields() -> List[str]:
        return [
            "id", "product_id", "price", "currency", "timestamp",
            "title", "availability", "scrape_success", "error_message",
            "response_time_ms",
        ]
