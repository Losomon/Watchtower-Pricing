# 📡 Watchtower Pricing

**Automated Price Intelligence System**  
Track product prices across the web, store historical trends, and get notified of price changes in real-time.

Built with modular automation, intelligent scraping, and scheduled workflows — perfect for both personal use and as a scalable SaaS foundation.

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-2088FF?style=for-the-badge&logo=github-actions&logoColor=white)
![Pytest](https://img.shields.io/badge/Pytest-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

---

## 🚀 Overview

Watchtower Pricing is a robust, modular price tracking automation system that monitors product prices from multiple online stores, logs historical data, detects significant changes, and sends smart alerts.

It serves two purposes:
- A **practical daily-use automation tool** for savvy shoppers and deal hunters
- A **production-grade SaaS-style architecture project** showcasing modern backend engineering, DevOps, and scalable system design

---

## ✨ Key Features

- 🔍 **Powerful Web Scraping Engine** – Reliable price extraction with anti-blocking techniques
- ⏱ **Automated Scheduling** – Supports cron jobs and GitHub Actions
- 📊 **Price History Tracking** – Persistent storage in JSON & CSV formats
- 📉 **Smart Change Detection** – Identifies price drops, increases, and percentage changes
- 🔔 **Multi-Channel Alerts** – Ready for Email and Telegram (easily extensible)
- 🧩 **Highly Modular Architecture** – Easy to add new stores and features
- 🧪 **Comprehensive Test Coverage** – Built with reliability and maintainability in mind
- 📈 **Scalable Design** – Prepared for future web dashboard and cloud deployment

---

## 🏗️ Project Structure

```bash
Watchtower-Pricing/
├── price_watcher/
│   ├── scraper.py          # Core web scraping logic
│   ├── tracker.py          # Price comparison & history management
│   ├── parser.py           # HTML/JSON parsing utilities
│   └── __init__.py
├── automation/
│   ├── scheduler.py        # Local task scheduling
│   └── github_actions_runner.py
├── alerts/
│   ├── email_alerts.py     # Email notification system
│   ├── telegram_alerts.py  # Telegram bot integration
│   └── __init__.py
├── data/
│   ├── prices.json         # Current product prices
│   └── history.csv         # Historical price data (timestamped)
├── tests/
│   ├── test_scraper.py
│   └── test_tracker.py
├── docs/
│   ├── architecture.md
│   ├── api_design.md
│   └── roadmap.md
├── .github/
│   └── workflows/
│       ├── run.yml         # Scheduled price tracking workflow
│       └── test.yml        # CI testing workflow
├── README.md
├── requirements.txt
└── .gitignore

```
##  ⚙️ Installation
```bash
# 1. Clone the repository
git clone https://github.com/your-username/Watchtower-Pricing.git

# 2. Navigate into the project directory
cd Watchtower-Pricing

# 3. Install dependencies
pip install -r requirements.txt

```
## ▶️ Usage
# Run Manually
```bash
# Run a single price tracking cycle
python -m price_watcher.tracker
```
# Run Full Automation Pipeline
```bash
python -m automation.scheduler
```
## 🔁 Automated Execution with GitHub Actions
```bash
# .github/workflows/run.yml
name: Watchtower Price Tracking

on:
  schedule:
    - cron: "0 * * * *"   # Runs every hour
  workflow_dispatch:       # Allows manual trigger from GitHub

jobs:
  track-prices:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run price tracker
        run: python -m price_watcher.tracker
```
# 🧪 Testing
```bash
pytest tests/ -v
```
## 📈 Roadmap

 - [ ] Add support for more platforms (Amazon, Jumia, eBay, AliExpress, Kilimall, etc.)
 - [ ] Build a web dashboard (React / Next.js + FastAPI)
 - [ ] Real-time notifications via Telegram Bot + Email
 - [ ] AI-based price prediction and forecasting
 - [ ] User authentication and multi-product watchlists
 - [ ] Mobile push notification integration
 - [ ] Docker support + Cloud deployment (SaaS-ready version)


## 🧠 Why This Project Matters
Watchtower Pricing demonstrates real-world skills in:

- Modern web scraping best practices
- Clean, modular backend system design
- Data persistence and historical analytics
- DevOps & automation using GitHub Actions
- Scalable SaaS architecture thinking
- Production-ready code structure and testing

Great addition to any developer portfolio or as a base for a micro-SaaS product.

## 🤝 Contributing
Contributions are welcome and appreciated! 💡
You can help by:

- Adding scrapers for new e-commerce websites
- Improving scraping robustness and anti-detection
- Enhancing the alert system
- Adding new features or fixing bugs
- Improving documentation

Feel free to open an issue or submit a pull request.

## 📄 License
-This project is licensed under the MIT License — you are free to use, modify, and distribute it.

```center
Made with ❤️ for deal hunters, automation enthusiasts, and developers building real-world systems.
```
