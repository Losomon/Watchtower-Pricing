"""
Watchtower Pricing — FastAPI Backend
Production REST API: product CRUD, price history, stats, manual triggers.
Run: uvicorn api.main:app --reload
"""

from __future__ import annotations
import os, logging
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from core.models import (
    Product, PriceRecord, PriceChange, AlertConfig,
    SupportedStore, AlertChannel, Currency
)
from core.tracker import PriceTracker, build_summary_report
from storage.repository import JsonRepository
from alerts.notifier import AlertNotifier

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Startup / shutdown ────────────────────────────────────────────────────────

repo = JsonRepository(data_dir=os.getenv("DATA_DIR", "data"))
notifier = AlertNotifier()
alert_cfg = AlertConfig(
    email_to=os.getenv("ALERT_EMAIL_TO"),
    email_from=os.getenv("ALERT_EMAIL_FROM"),
    smtp_password=os.getenv("SMTP_PASSWORD"),
    telegram_token=os.getenv("TELEGRAM_TOKEN"),
    telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),
    webhook_url=os.getenv("WEBHOOK_URL"),
)
tracker = PriceTracker(repo, notifier, alert_cfg)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Watchtower API starting up ✓")
    yield
    logger.info("Watchtower API shutting down")


app = FastAPI(
    title="Watchtower Pricing API",
    description="Automated price intelligence — track, alert, analyse.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response Schemas ────────────────────────────────────────────────

class AddProductRequest(BaseModel):
    url: str
    name: Optional[str] = None
    store: SupportedStore = SupportedStore.GENERIC
    target_price: Optional[float] = None
    currency: Currency = Currency.KES
    notify_channels: List[AlertChannel] = Field(
        default_factory=lambda: [AlertChannel.EMAIL, AlertChannel.TELEGRAM]
    )
    tags: List[str] = Field(default_factory=list)


class PriceHistoryPoint(BaseModel):
    timestamp: str
    price: float
    currency: str


class ProductWithHistory(BaseModel):
    product: dict
    current_price: Optional[float]
    history: List[PriceHistoryPoint]
    lowest_ever: Optional[float]
    highest_ever: Optional[float]
    change_7d: Optional[float]


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", tags=["Meta"])
def root():
    return {"service": "Watchtower Pricing API", "version": "2.0.0", "status": "operational"}


@app.get("/health", tags=["Meta"])
def health():
    stats = repo.get_summary_stats()
    return {"status": "ok", **stats}


# ── Products ──────────────────────────────────────────────────────────────────

@app.get("/products", response_model=List[dict], tags=["Products"])
def list_products(active_only: bool = Query(False)):
    products = repo.list_products()
    if active_only:
        products = [p for p in products if p.is_active]
    return [p.model_dump() for p in products]


@app.post("/products", response_model=dict, status_code=201, tags=["Products"])
def add_product(req: AddProductRequest, background: BackgroundTasks):
    product = Product(**req.model_dump())
    # Auto-detect store from URL
    product.store = product.detect_store()
    repo.save_product(product)
    # Kick off a first scrape in the background
    background.add_task(_scrape_product_bg, product)
    return product.model_dump()


@app.get("/products/{product_id}", response_model=ProductWithHistory, tags=["Products"])
def get_product(product_id: str):
    product = repo.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    history = repo.get_price_history(product_id, limit=90)
    prices = [r.price for r in history]
    latest = repo.get_latest_price(product_id)
    change_7d = None
    if len(history) >= 2:
        old = history[max(0, len(history)-7)].price
        change_7d = round(((latest.price - old) / old) * 100, 2) if latest else None
    return ProductWithHistory(
        product=product.model_dump(),
        current_price=latest.price if latest else None,
        history=[PriceHistoryPoint(
            timestamp=r.timestamp.isoformat(), price=r.price, currency=r.currency.value
        ) for r in history],
        lowest_ever=min(prices) if prices else None,
        highest_ever=max(prices) if prices else None,
        change_7d=change_7d,
    )


@app.delete("/products/{product_id}", status_code=204, tags=["Products"])
def delete_product(product_id: str):
    if not repo.get_product(product_id):
        raise HTTPException(status_code=404, detail="Product not found")
    repo.delete_product(product_id)


@app.patch("/products/{product_id}", response_model=dict, tags=["Products"])
def update_product(product_id: str, updates: dict):
    product = repo.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    for k, v in updates.items():
        if hasattr(product, k):
            setattr(product, k, v)
    repo.update_product(product)
    return product.model_dump()


# ── Tracking ──────────────────────────────────────────────────────────────────

@app.post("/track/all", tags=["Tracking"])
def run_all(background: BackgroundTasks):
    """Trigger a full tracking cycle for all active products (async)."""
    background.add_task(_run_all_bg)
    return {"status": "queued", "message": "Tracking cycle started in background"}


@app.post("/track/{product_id}", tags=["Tracking"])
def run_one(product_id: str):
    """Immediately track a single product (synchronous for quick testing)."""
    product = repo.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    change = tracker.run_single(product)
    return {
        "status": "done",
        "change_detected": change is not None,
        "change": change.model_dump() if change else None,
    }


# ── History / Stats ───────────────────────────────────────────────────────────

@app.get("/products/{product_id}/history", tags=["History"])
def price_history(product_id: str, limit: int = Query(30, ge=1, le=365)):
    history = repo.get_price_history(product_id, limit=limit)
    return [{"timestamp": r.timestamp.isoformat(), "price": r.price} for r in history]


@app.get("/stats", tags=["Stats"])
def global_stats():
    stats = repo.get_summary_stats()
    products = repo.list_products()
    # Compute per-product drop/rise counts
    drop_products = []
    for p in products:
        hist = repo.get_price_history(p.id, limit=2)
        if len(hist) == 2 and hist[-1].price < hist[-2].price:
            drop_products.append({"name": p.name, "url": p.url, "price": hist[-1].price})
    return {**stats, "recent_drops": drop_products[:5]}


# ── Background helpers ────────────────────────────────────────────────────────

def _scrape_product_bg(product: Product):
    try:
        tracker.run_single(product)
    except Exception as exc:
        logger.error(f"Background scrape failed: {exc}")


def _run_all_bg():
    products = repo.list_products()
    changes = tracker.run(products)
    report = build_summary_report(changes)
    logger.info(report)
