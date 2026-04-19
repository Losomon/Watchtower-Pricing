"""
Watchtower Pricing — CLI & Scheduler
Usage:
  python -m automation.run track          # Run one cycle
  python -m automation.run schedule       # Run on cron
  python -m automation.run add <url>      # Add a product
  python -m automation.run list           # List all products
"""

from __future__ import annotations
import sys, os, logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from core.models import Product, AlertConfig, AlertChannel, Currency, SupportedStore
from core.tracker import PriceTracker, build_summary_report
from storage.repository import JsonRepository
from alerts.notifier import AlertNotifier

logging.basicConfig(level=logging.WARNING)
console = Console()

def _get_tracker() -> tuple[PriceTracker, JsonRepository]:
    repo = JsonRepository(data_dir=os.getenv("DATA_DIR", "data"))
    notifier = AlertNotifier()
    config = AlertConfig(
        email_to=os.getenv("ALERT_EMAIL_TO"),
        email_from=os.getenv("ALERT_EMAIL_FROM"),
        smtp_password=os.getenv("SMTP_PASSWORD"),
        telegram_token=os.getenv("TELEGRAM_TOKEN"),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),
    )
    return PriceTracker(repo, notifier, config), repo


@click.group()
def cli():
    """🔭 Watchtower Pricing — Automated price intelligence"""


@cli.command()
@click.option("--product-id", default=None, help="Track a specific product ID only")
def track(product_id):
    """Run a price-checking cycle."""
    tracker, repo = _get_tracker()
    if product_id:
        product = repo.get_product(product_id)
        if not product:
            console.print(f"[red]Product {product_id} not found[/red]")
            sys.exit(1)
        products = [product]
    else:
        products = repo.list_products()

    if not products:
        console.print("[yellow]No products to track. Add one with: watchtower add <url>[/yellow]")
        return

    console.print(f"\n[bold green]🔭 Watchtower[/bold green] — checking {len(products)} product(s)\n")
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as progress:
        task = progress.add_task("Scraping prices...", total=len(products))
        changes = tracker.run(products)
        progress.update(task, completed=len(products))

    report = build_summary_report(changes)
    console.print(f"\n{report}\n")


@cli.command()
@click.argument("url")
@click.option("--name", default=None)
@click.option("--target", default=None, type=float, help="Alert me below this price")
@click.option("--currency", default="KES", type=click.Choice(["KES","USD","EUR","GBP"]))
def add(url, name, target, currency):
    """Track a new product URL."""
    _, repo = _get_tracker()
    product = Product(
        url=url,
        name=name,
        currency=Currency(currency),
        target_price=target,
        notify_channels=[AlertChannel.EMAIL, AlertChannel.TELEGRAM],
    )
    product.store = product.detect_store()
    repo.save_product(product)
    console.print(f"\n[green]✓ Now tracking:[/green] {name or url}")
    if target:
        console.print(f"  Alert when price drops below {currency} {target:,.0f}")


@cli.command(name="list")
def list_products():
    """Show all tracked products."""
    _, repo = _get_tracker()
    products = repo.list_products()
    if not products:
        console.print("[yellow]No products tracked yet.[/yellow]")
        return
    table = Table(title="Tracked Products", show_lines=True)
    table.add_column("Name", style="bold")
    table.add_column("Store")
    table.add_column("Current Price")
    table.add_column("Target")
    table.add_column("Status")
    for p in products:
        latest = repo.get_latest_price(p.id)
        price_str = f"{p.currency} {latest.price:,.0f}" if latest else "—"
        target_str = f"{p.currency} {p.target_price:,.0f}" if p.target_price else "—"
        status = "[green]● Active[/green]" if p.is_active else "[red]○ Paused[/red]"
        table.add_row(p.name or p.url[:40], p.store.value, price_str, target_str, status)
    console.print(table)


@cli.command()
@click.argument("product_id")
def remove(product_id):
    """Stop tracking a product."""
    _, repo = _get_tracker()
    repo.delete_product(product_id)
    console.print(f"[green]✓ Removed product {product_id}[/green]")


@cli.command()
@click.option("--interval", default=3600, help="Seconds between runs (default 3600 = 1 hour)")
def schedule(interval):
    """Run the tracker on a loop (local scheduling)."""
    import time
    console.print(f"\n[bold green]🔭 Watchtower Scheduler[/bold green] — running every {interval}s\n")
    while True:
        try:
            ctx = click.Context(track)
            track.invoke(ctx)
        except Exception as exc:
            console.print(f"[red]Error in tracking cycle: {exc}[/red]")
        console.print(f"[dim]Next run in {interval}s...[/dim]")
        time.sleep(interval)


if __name__ == "__main__":
    cli()
