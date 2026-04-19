"""
Watchtower Pricing — Alert Notifier
Unified interface dispatching to Email, Telegram, and Webhook channels.
"""

from __future__ import annotations
import smtplib, logging, json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional
from datetime import datetime

import httpx

from core.models import PriceChange, Product, AlertConfig, AlertChannel, ChangeDirection

logger = logging.getLogger(__name__)


# ── Message Builder ───────────────────────────────────────────────────────────

def _build_email_html(change: PriceChange) -> str:
    arrow = "📉" if change.direction == ChangeDirection.DROP else "📈"
    color = "#00c896" if change.direction == ChangeDirection.DROP else "#ff4757"
    target_block = ""
    if change.below_target:
        target_block = f"""
        <div style="background:#00c89620;border:1px solid #00c896;border-radius:8px;
                    padding:12px 16px;margin:16px 0;color:#00c896;font-weight:600;">
            🎯 BELOW YOUR TARGET PRICE of {change.currency} {change.target_price:,.0f}!
            Time to buy!
        </div>"""
    return f"""
    <html><body style="font-family:sans-serif;background:#0a0c0f;color:#e8eaf0;padding:24px">
    <div style="max-width:520px;margin:0 auto;background:#111317;border-radius:12px;
                border:1px solid #1f2329;overflow:hidden">
        <div style="background:#0a0c0f;padding:20px 24px;border-bottom:1px solid #1f2329">
            <span style="font-size:20px;font-weight:800;color:#00e5a0">Watchtower</span>
            <span style="font-size:13px;color:#6b7280;margin-left:12px">Price Alert</span>
        </div>
        <div style="padding:24px">
            <div style="font-size:24px;margin-bottom:8px">{arrow} Price {change.direction.value.title()}</div>
            <div style="font-size:18px;font-weight:700;margin-bottom:20px">
                {change.product_name or 'Product'}
            </div>
            <div style="display:flex;gap:16px;margin-bottom:20px">
                <div style="flex:1;background:#181b20;border-radius:8px;padding:16px;text-align:center">
                    <div style="font-size:12px;color:#6b7280;margin-bottom:4px">WAS</div>
                    <div style="font-size:22px;font-weight:700;text-decoration:line-through;color:#6b7280">
                        {change.currency} {change.old_price:,.0f}
                    </div>
                </div>
                <div style="flex:1;background:#181b20;border-radius:8px;padding:16px;text-align:center">
                    <div style="font-size:12px;color:#6b7280;margin-bottom:4px">NOW</div>
                    <div style="font-size:22px;font-weight:700;color:{color}">
                        {change.currency} {change.new_price:,.0f}
                    </div>
                </div>
                <div style="flex:1;background:{color}22;border-radius:8px;padding:16px;text-align:center;
                            border:1px solid {color}44">
                    <div style="font-size:12px;color:#6b7280;margin-bottom:4px">CHANGE</div>
                    <div style="font-size:22px;font-weight:700;color:{color}">
                        {change.change_percent:+.1f}%
                    </div>
                </div>
            </div>
            {target_block}
            <a href="{change.product_url}" style="display:block;text-align:center;
               background:#00e5a0;color:#000;padding:14px;border-radius:8px;
               text-decoration:none;font-weight:700;font-size:14px">
               View Product →
            </a>
        </div>
        <div style="padding:16px 24px;border-top:1px solid #1f2329;font-size:12px;color:#6b7280">
            Sent by Watchtower Pricing · {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC
        </div>
    </div></body></html>"""


def _build_telegram_message(change: PriceChange) -> str:
    arrow = "📉" if change.direction == ChangeDirection.DROP else "📈"
    target = ""
    if change.below_target:
        target = f"\n🎯 *BELOW TARGET* ({change.currency} {change.target_price:,.0f}\\!) — Time to buy\\!"
    name = (change.product_name or "Product").replace("-", "\\-").replace(".", "\\.")
    return (
        f"{arrow} *Price {change.direction.value.title()}* \\— Watchtower\n\n"
        f"*{name}*\n"
        f"~~{change.currency} {change.old_price:,.0f}~~ → *{change.currency} {change.new_price:,.0f}*\n"
        f"Change: `{change.change_percent:+.1f}%`"
        f"{target}\n\n"
        f"[View Product]({change.product_url})"
    )


# ── Channel Senders ────────────────────────────────────────────────────────────

def _send_email(change: PriceChange, config: AlertConfig) -> bool:
    if not all([config.email_to, config.email_from, config.smtp_password]):
        logger.warning("Email not configured — skipping")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[Watchtower] Price {change.direction.value.title()} — {change.product_name or 'Product'}"
        msg["From"] = config.email_from
        msg["To"] = config.email_to
        msg.attach(MIMEText(_build_email_html(change), "html"))
        with smtplib.SMTP(config.smtp_host, config.smtp_port) as smtp:
            smtp.starttls()
            smtp.login(config.email_from, config.smtp_password)
            smtp.sendmail(config.email_from, config.email_to, msg.as_string())
        logger.info(f"Email sent to {config.email_to}")
        return True
    except Exception as exc:
        logger.error(f"Email send failed: {exc}")
        return False


def _send_telegram(change: PriceChange, config: AlertConfig) -> bool:
    if not all([config.telegram_token, config.telegram_chat_id]):
        logger.warning("Telegram not configured — skipping")
        return False
    try:
        url = f"https://api.telegram.org/bot{config.telegram_token}/sendMessage"
        payload = {
            "chat_id": config.telegram_chat_id,
            "text": _build_telegram_message(change),
            "parse_mode": "MarkdownV2",
            "disable_web_page_preview": False,
        }
        resp = httpx.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info("Telegram message sent")
        return True
    except Exception as exc:
        logger.error(f"Telegram send failed: {exc}")
        return False


def _send_webhook(change: PriceChange, config: AlertConfig) -> bool:
    if not config.webhook_url:
        return False
    try:
        payload = {
            "event": "price_change",
            "direction": change.direction.value,
            "product": change.product_name,
            "url": change.product_url,
            "old_price": change.old_price,
            "new_price": change.new_price,
            "change_percent": round(change.change_percent, 2),
            "currency": change.currency,
            "below_target": change.below_target,
            "timestamp": change.detected_at.isoformat(),
        }
        resp = httpx.post(config.webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info(f"Webhook sent to {config.webhook_url}")
        return True
    except Exception as exc:
        logger.error(f"Webhook send failed: {exc}")
        return False


# ── Notifier Facade ───────────────────────────────────────────────────────────

class AlertNotifier:
    """
    Unified notifier. Call notify() and it dispatches to all configured channels.
    """

    def notify(self, change: PriceChange, product: Product, config: AlertConfig) -> None:
        channels = product.notify_channels or [AlertChannel.EMAIL, AlertChannel.TELEGRAM]
        for channel in channels:
            if channel == AlertChannel.EMAIL:
                _send_email(change, config)
            elif channel == AlertChannel.TELEGRAM:
                _send_telegram(change, config)
            elif channel == AlertChannel.WEBHOOK:
                _send_webhook(change, config)
