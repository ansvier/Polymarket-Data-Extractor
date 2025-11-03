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

---

##⚙️ Usage

Run interactively:

python main.py


Then:

Enter a keyword (e.g. argentina, soccer, primera) to list related tags.

Copy one or more tag_id values and input them separated by commas.

Wait for data to be fetched.

Results are saved to your working directory:

markets_tag_<tag_id>_<timestamp>.jsonl
markets_tag_<tag_id>_<timestamp>.csv
markets_all_selected_tags_<timestamp>.csv

---

##📊 Output columns
Column	Description
id	Market ID
slug	Market slug
question	Market question text
liquidity	Current liquidity in USDC
volume	Total trading volume
conditionId	On-chain condition ID (used for trade lookups)
num_traders	Unique proxyWallet addresses
total_trades	Total number of trades fetched
first_trade_ts	Timestamp of earliest trade
last_trade_ts	Timestamp of latest trade

---

##🧠 APIs Used
Gamma API

https://gamma-api.polymarket.com

/tags

/markets

Data API

https://data-api.polymarket.com

/trades?market=<conditionId>&takerOnly=false
