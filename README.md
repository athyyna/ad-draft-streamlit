# Ad Draft Generator — Streamlit App

A standalone AI-powered tool that turns any company website into polished, ready-to-use ad drafts.

## Features

- **Web scraper** — extracts images, headlines, taglines, CTAs, and body copy from any public URL
- **Promo detection** — automatically discovers and scrapes active promotion/offer pages
- **AI asset ranking** — GPT-4o selects the most impactful images and copy
- **Ad copy generation** — produces 3 format variants: Social (1080×1080), Display (1200×628), Search
- **Promo-aware copy** — when a promotion is detected, ad copy references the active offer
- **Download** — export each variant or all drafts as a `.txt` file

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the app
streamlit run app.py
```

Then open http://localhost:8501 in your browser.

## Usage

1. Enter your **OpenAI API key** in the sidebar (session-only, never stored)
2. Paste any company website URL (e.g. `https://business.meta.com/`)
3. Click **Generate Ads**
4. Review the 3 ad draft cards and download what you need

## File Structure

```
app.py           ← Main Streamlit UI
scraper.py       ← Web scraper with promo page detection
generator.py     ← AI asset ranker + ad copy generator (GPT-4o)
requirements.txt ← Python dependencies
README.md        ← This file
```

## Notes

- Requires an OpenAI API key with GPT-4o access
- Works best on publicly accessible pages (no login walls)
- Meta/Facebook sites are fully supported (browser-level headers used)
- Promo detection scans homepage links for offer/deal/sale/pricing/trial patterns
