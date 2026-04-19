"""
Watchtower Pricing — Core Data Models
Production-grade Pydantic v2 models for type-safe data throughout the system.
"""

from __future__ import annotations
from pydantic import BaseModel, Field, field_validator, model_validator, HttpUrl
from datetime import datetime
from typing import Optional, List
from enum import Enum
import uuid


class SupportedStore(str, Enum):
    AMAZON = "amazon"
    JUMIA = "jumia"
    KILIMALL = "kilimall"
    ALIEXPRESS = "aliexpress"
    EBAY = "ebay"
    GENERIC = "generic"


class AlertChannel(str, Enum):
    EMAIL = "email"
    TELEGRAM = "telegram"
    WEBHOOK = "webhook"


class ChangeDirection(str, Enum):
    DROP = "drop"
    RISE = "rise"
    STABLE = "stable"
    UNAVAILABLE = "unavailable"


class Currency(str, Enum):
    KES = "KES"
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"


# ── Product ──────────────────────────────────────────────────────────────────

class Product(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    url: str
    name: Optional[str] = None
    store: SupportedStore = SupportedStore.GENERIC
    product_id: Optional[str] = None          # ASIN, SKU, etc.
    image_url: Optional[str] = None
    currency: Currency = Currency.KES
    target_price: Optional[float] = None       # Alert threshold
    notify_channels: List[AlertChannel] = Field(default_factory=list)
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    tags: List[str] = Field(default_factory=list)

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v.strip()

    @field_validator("target_price")
    @classmethod
    def target_must_be_positive(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Target price must be positive")
        return v

    def detect_store(self) -> SupportedStore:
        url_lower = self.url.lower()
        for store in SupportedStore:
            if store.value in url_lower:
                return store
        return SupportedStore.GENERIC


# ── Price Record ─────────────────────────────────────────────────────────────

class PriceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    product_id: str
    price: float
    currency: Currency = Currency.KES
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    title: Optional[str] = None
    availability: Optional[str] = None
    scrape_success: bool = True
    error_message: Optional[str] = None
    response_time_ms: Optional[float] = None

    @field_validator("price")
    @classmethod
    def price_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Price must be positive")
        return round(v, 2)


# ── Price Change ─────────────────────────────────────────────────────────────

class PriceChange(BaseModel):
    product_id: str
    product_name: Optional[str]
    product_url: str
    old_price: float
    new_price: float
    currency: Currency
    change_amount: float
    change_percent: float
    direction: ChangeDirection
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    target_price: Optional[float] = None

    @model_validator(mode="after")
    def compute_direction(self) -> "PriceChange":
        if self.change_amount < -0.01:
            object.__setattr__(self, "direction", ChangeDirection.DROP)
        elif self.change_amount > 0.01:
            object.__setattr__(self, "direction", ChangeDirection.RISE)
        else:
            object.__setattr__(self, "direction", ChangeDirection.STABLE)
        return self

    @property
    def below_target(self) -> bool:
        return (
            self.target_price is not None
            and self.new_price <= self.target_price
        )

    @property
    def summary(self) -> str:
        arrow = "▼" if self.direction == ChangeDirection.DROP else "▲"
        return (
            f"{arrow} {self.product_name or 'Product'}: "
            f"{self.currency} {self.old_price:,.0f} → {self.new_price:,.0f} "
            f"({self.change_percent:+.1f}%)"
        )


# ── Alert Settings ────────────────────────────────────────────────────────────

class AlertConfig(BaseModel):
    email_to: Optional[str] = None
    email_from: Optional[str] = None
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_password: Optional[str] = None
    telegram_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    webhook_url: Optional[str] = None
    min_change_percent: float = 1.0       # Only alert on ≥1% change
    cooldown_minutes: int = 60             # Don't repeat same alert within 1h


# ── Scrape Result ─────────────────────────────────────────────────────────────

class ScrapeResult(BaseModel):
    success: bool
    product_id: str
    price: Optional[float] = None
    title: Optional[str] = None
    availability: Optional[str] = None
    currency: Currency = Currency.KES
    error: Optional[str] = None
    duration_ms: float = 0.0
