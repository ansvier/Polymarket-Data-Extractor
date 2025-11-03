# Polymarket Data Extractor

A lightweight Python/Colab-ready utility for extracting **Polymarket markets, tags, and trade metrics** using both **Gamma API** and **Data API**.

## ✨ Features
- Search tags by keyword (`/tags` endpoint)
- Download all **markets** (open + closed) for selected tag IDs
- Retrieve **trades** for each market via `Data API`
- Compute:
  - Number of unique traders (`proxyWallet`)
  - Total number of trades
  - First and last trade timestamps
- Export per-tag dumps (`.jsonl` + `.csv`)
- Build a combined CSV with all markets across selected tags

---

## 🧩 Installation

Clone the repository and install dependencies:
```bash
git clone https://github.com/YOUR_USERNAME/polymarket-data-extractor.git
cd polymarket-data-extractor
pip install -r requirements.txt
Data API

https://data-api.polymarket.com

/trades?market=<conditionId>&takerOnly=false
