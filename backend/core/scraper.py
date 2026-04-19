"""
Watchtower Pricing — Scraper Engine
BaseScraper + site-specific registry with anti-detection techniques.
"""

from __future__ import annotations
import time, random, re, logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Type
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from core.models import ScrapeResult, Currency, SupportedStore

logger = logging.getLogger(__name__)

# ── User-agent pool (rotate to reduce fingerprinting) ───────────────────────
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

_BASE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def _random_delay(min_s: float = 1.5, max_s: float = 4.0) -> None:
    """Polite random delay between requests."""
    time.sleep(random.uniform(min_s, max_s))


# ── Base Scraper ─────────────────────────────────────────────────────────────

class BaseScraper(ABC):
    """Abstract base class every site-specific scraper must implement."""

    store: SupportedStore = SupportedStore.GENERIC
    currency: Currency = Currency.KES
    timeout: int = 15
    max_retries: int = 3

    def __init__(self, proxy: Optional[str] = None):
        self.proxy = proxy
        client_kwargs = {
            "timeout": self.timeout,
            "follow_redirects": True,
            "headers": self._build_headers(),
        }
        if proxy:
            client_kwargs["proxies"] = {"http://": proxy, "https://": proxy}
        self._client = httpx.Client(**client_kwargs)

    def _build_headers(self) -> dict:
        return {**_BASE_HEADERS, "User-Agent": random.choice(_USER_AGENTS)}

    def _get(self, url: str) -> httpx.Response:
        """GET with retry + exponential back-off."""
        for attempt in range(1, self.max_retries + 1):
            try:
                _random_delay()
                resp = self._client.get(url, headers=self._build_headers())
                resp.raise_for_status()
                return resp
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    wait = 2 ** attempt + random.random() * 2
                    logger.warning(f"Rate limited, waiting {wait:.1f}s (attempt {attempt})")
                    time.sleep(wait)
                else:
                    raise
            except httpx.RequestError as e:
                if attempt == self.max_retries:
                    raise
                time.sleep(2 ** attempt)
        raise RuntimeError("Max retries exceeded")

    def scrape(self, url: str, product_id: str) -> ScrapeResult:
        t0 = time.monotonic()
        try:
            resp = self._get(url)
            soup = BeautifulSoup(resp.text, "html.parser")
            price = self.extract_price(soup)
            title = self.extract_title(soup)
            availability = self.extract_availability(soup)
            return ScrapeResult(
                success=True,
                product_id=product_id,
                price=price,
                title=title,
                availability=availability,
                currency=self.currency,
                duration_ms=(time.monotonic() - t0) * 1000,
            )
        except Exception as exc:
            logger.error(f"Scrape failed for {url}: {exc}")
            return ScrapeResult(
                success=False,
                product_id=product_id,
                error=str(exc),
                duration_ms=(time.monotonic() - t0) * 1000,
            )

    @abstractmethod
    def extract_price(self, soup: BeautifulSoup) -> float:
        """Parse the price from the page. Must be implemented per site."""
        ...

    def extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        tag = soup.find("title")
        return tag.get_text(strip=True) if tag else None

    def extract_availability(self, soup: BeautifulSoup) -> Optional[str]:
        return None

    @staticmethod
    def _parse_price(raw: str) -> float:
        """Strip currency symbols and commas → float."""
        cleaned = re.sub(r"[^\d.,]", "", raw).replace(",", "")
        return float(cleaned)

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


# ── Site-Specific Scrapers ───────────────────────────────────────────────────

class AmazonScraper(BaseScraper):
    store = SupportedStore.AMAZON
    currency = Currency.USD

    def extract_price(self, soup: BeautifulSoup) -> float:
        # Try the main price widget first, then fallbacks
        selectors = [
            ("span", {"id": "priceblock_ourprice"}),
            ("span", {"class": "a-price-whole"}),
            ("span", {"id": "price_inside_buybox"}),
            ("span", {"class": "a-offscreen"}),
        ]
        for tag, attrs in selectors:
            el = soup.find(tag, attrs)
            if el and el.get_text(strip=True):
                try:
                    return self._parse_price(el.get_text())
                except ValueError:
                    continue
        raise ValueError("Price not found on Amazon page")

    def extract_availability(self, soup: BeautifulSoup) -> Optional[str]:
        el = soup.find("div", {"id": "availability"})
        return el.get_text(strip=True) if el else None


class JumiaScraper(BaseScraper):
    store = SupportedStore.JUMIA
    currency = Currency.KES

    def extract_price(self, soup: BeautifulSoup) -> float:
        el = soup.find("span", {"class": "-b -ltr -tal -fs24"})
        if not el:
            el = soup.find("span", {"data-price": True})
            if el:
                return float(el["data-price"])
        if el:
            return self._parse_price(el.get_text())
        raise ValueError("Price not found on Jumia page")


class KilimallScraper(BaseScraper):
    store = SupportedStore.KILIMALL
    currency = Currency.KES

    def extract_price(self, soup: BeautifulSoup) -> float:
        el = soup.find("div", {"class": "price"}) or soup.find("span", {"class": "now-price"})
        if el:
            return self._parse_price(el.get_text())
        raise ValueError("Price not found on Kilimall page")


class AliExpressScraper(BaseScraper):
    store = SupportedStore.ALIEXPRESS
    currency = Currency.USD

    def extract_price(self, soup: BeautifulSoup) -> float:
        # AliExpress is JS-heavy; we grab the og:price meta tag as a reliable fallback
        meta = soup.find("meta", {"property": "og:price:amount"})
        if meta and meta.get("content"):
            return float(meta["content"])
        el = soup.find("span", {"class": "product-price-value"})
        if el:
            return self._parse_price(el.get_text())
        raise ValueError("Price not found on AliExpress page (JS-heavy site — use Playwright for full support)")


class EbayScraper(BaseScraper):
    store = SupportedStore.EBAY
    currency = Currency.USD

    def extract_price(self, soup: BeautifulSoup) -> float:
        el = soup.find("span", {"itemprop": "price"})
        if el and el.get("content"):
            return float(el["content"])
        el = soup.find("div", {"class": "x-price-primary"})
        if el:
            return self._parse_price(el.get_text())
        raise ValueError("Price not found on eBay page")


class GenericScraper(BaseScraper):
    """Best-effort scraper for unsupported stores."""
    store = SupportedStore.GENERIC

    _PRICE_PATTERNS = [
        r"\$[\d,]+\.?\d*",
        r"KES\s?[\d,]+",
        r"USD\s?[\d,]+",
        r"[\d,]+\.\d{2}",
    ]

    def extract_price(self, soup: BeautifulSoup) -> float:
        # Look for JSON-LD structured data first (most reliable)
        import json
        for script in soup.find_all("script", {"type": "application/ld+json"}):
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and "price" in data.get("offers", {}):
                    return float(data["offers"]["price"])
            except Exception:
                pass

        # Try common price element patterns
        for cls in ["price", "product-price", "sale-price", "offer-price", "current-price"]:
            el = soup.find(class_=re.compile(cls, re.I))
            if el:
                try:
                    return self._parse_price(el.get_text())
                except ValueError:
                    pass

        # Regex scan of page text as last resort
        text = soup.get_text()
        for pattern in self._PRICE_PATTERNS:
            match = re.search(pattern, text)
            if match:
                try:
                    return self._parse_price(match.group())
                except ValueError:
                    pass

        raise ValueError("Could not extract price — site may require Playwright")


# ── Scraper Registry ─────────────────────────────────────────────────────────

_REGISTRY: Dict[SupportedStore, Type[BaseScraper]] = {
    SupportedStore.AMAZON:     AmazonScraper,
    SupportedStore.JUMIA:      JumiaScraper,
    SupportedStore.KILIMALL:   KilimallScraper,
    SupportedStore.ALIEXPRESS: AliExpressScraper,
    SupportedStore.EBAY:       EbayScraper,
    SupportedStore.GENERIC:    GenericScraper,
}


def get_scraper(store: SupportedStore, proxy: Optional[str] = None) -> BaseScraper:
    """Factory: return the right scraper for a given store."""
    cls = _REGISTRY.get(store, GenericScraper)
    return cls(proxy=proxy)


def register_scraper(store: SupportedStore, cls: Type[BaseScraper]) -> None:
    """Plugin hook: register a custom scraper at runtime."""
    _REGISTRY[store] = cls
