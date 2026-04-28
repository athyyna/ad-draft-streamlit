"""
scraper.py — Web scraper for Ad Draft Generator
Fetches a URL and extracts images, headlines, CTAs, body copy, and promo page content.
"""

import re
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from dataclasses import dataclass, field
from typing import Optional

# ── Browser-level headers to pass bot detection ──────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

# ── Image scoring patterns ────────────────────────────────────────────────────
SKIP_PATTERNS = [
    re.compile(p, re.I) for p in [
        r"logo", r"icon", r"avatar", r"sprite", r"pixel", r"tracking",
        r"1x1", r"spacer", r"blank", r"placeholder", r"\.gif$",
        r"data:image", r"gravatar", r"captcha",
    ]
]
PREFER_PATTERNS = [
    re.compile(p, re.I) for p in [
        r"hero", r"banner", r"feature", r"product", r"cover",
        r"main", r"promo", r"campaign", r"bg", r"background",
    ]
]

# ── Promo link detection ──────────────────────────────────────────────────────
PROMO_HREF_RE = re.compile(
    r"/(promo|promotion|promotions|offer|offers|deal|deals|sale|sales|"
    r"discount|discounts|coupon|coupons|special|specials|campaign|campaigns|"
    r"pricing|plans|free-trial|trial|limited-time|flash-sale|bundle|packages)",
    re.I,
)
PROMO_TEXT_RE = re.compile(
    r"\b(promo|promotion|offer|deal|sale|discount|coupon|special|"
    r"limited.?time|flash.?sale|free.?trial|save|off|bundle|package|"
    r"exclusive|new.?offer|today.?only|expires?)\b",
    re.I,
)

# ── Offer extraction patterns ─────────────────────────────────────────────────
OFFER_PATTERNS = [
    re.compile(p, re.I) for p in [
        r"\d+\s*%\s*off",
        r"free\s+\w+(\s+for\s+\d+\s+\w+)?",
        r"save\s+\$?\d+",
        r"\$\d+[\d,.]*\s*(\/\s*(mo|month|yr|year|week))?",
        r"limited.?time\s+offer",
        r"buy\s+\d+\s+get\s+\d+",
        r"no\s+credit\s+card\s+required",
        r"try\s+\w+\s+free",
        r"first\s+\d+\s+(days?|months?)\s+free",
        r"starting\s+at\s+\$[\d.]+",
        r"ends?\s+(today|tomorrow|soon|\w+\s+\d+)",
        r"expires?\s+(today|tomorrow|soon|\w+\s+\d+)",
        r"through\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d+",
        r"valid\s+(until|through|till)\s+\w+",
        r"for\s+a\s+limited\s+time",
        r"\d+\s+(hours?|days?)\s+(left|only|remaining)",
    ]
]


@dataclass
class ImageCandidate:
    src: str
    alt: str
    score: int
    width: Optional[int] = None
    height: Optional[int] = None


@dataclass
class PromoContent:
    promo_url: str
    promo_headlines: list[str] = field(default_factory=list)
    promo_offers: list[str] = field(default_factory=list)
    promo_ctas: list[str] = field(default_factory=list)
    promo_images: list[ImageCandidate] = field(default_factory=list)


@dataclass
class ScrapedContent:
    url: str
    title: str
    description: str
    headlines: list[str]
    taglines: list[str]
    cta_texts: list[str]
    body_text: list[str]
    images: list[ImageCandidate]
    og_image: Optional[str] = None
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    favicon_url: Optional[str] = None
    promo: Optional[PromoContent] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def resolve_url(src: str, base: str) -> str:
    if not src:
        return ""
    if src.startswith(("http://", "https://")):
        return src
    if src.startswith("//"):
        return "https:" + src
    try:
        return urljoin(base, src)
    except Exception:
        return ""


def score_image(src: str, alt: str, width: Optional[int], height: Optional[int]) -> int:
    if any(p.search(src) for p in SKIP_PATTERNS):
        return 0
    score = 50
    if any(p.search(src) or p.search(alt) for p in PREFER_PATTERNS):
        score += 20
    if width and height:
        area = width * height
        if area > 200_000:
            score += 20
        elif area > 50_000:
            score += 10
        elif area < 5_000:
            score -= 30
        if width > height * 1.2:
            score += 10
    if alt and len(alt) > 5:
        score += 5
    if re.search(r"\.(jpg|jpeg|png|webp)(\?|$)", src, re.I):
        score += 5
    if re.search(r"\.svg(\?|$)", src, re.I):
        score -= 10
    return max(0, min(100, score))


def fetch_html(url: str, timeout: int = 20) -> tuple[str, int]:
    """Returns (html, status_code). html is empty string on failure."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        return resp.text if resp.ok else "", resp.status_code
    except Exception:
        return "", 0


def extract_text_nodes(soup: BeautifulSoup, selectors: list[str], limit: int = 8) -> list[str]:
    results = []
    seen = set()
    for sel in selectors:
        for el in soup.select(sel):
            text = el.get_text(strip=True)
            if 3 < len(text) < 300 and text not in seen:
                results.append(text)
                seen.add(text)
            if len(results) >= limit:
                return results
    return results


def extract_images(soup: BeautifulSoup, base_url: str, seen: set[str] | None = None) -> list[ImageCandidate]:
    if seen is None:
        seen = set()
    images = []
    for img in soup.find_all("img"):
        src = resolve_url(
            img.get("src") or img.get("data-src") or img.get("data-lazy-src") or "",
            base_url,
        )
        if not src or src in seen:
            continue
        alt = img.get("alt", "")
        width = int(img.get("width", 0) or 0) or None
        height = int(img.get("height", 0) or 0) or None
        s = score_image(src, alt, width, height)
        if s > 0:
            images.append(ImageCandidate(src=src, alt=alt, score=s, width=width, height=height))
            seen.add(src)
    # CSS background images
    for el in soup.find_all(style=True):
        style = el.get("style", "")
        m = re.search(r"url\(['\"]?([^'\")\s]+)['\"]?\)", style)
        if m:
            src = resolve_url(m.group(1), base_url)
            if src and src not in seen:
                s = score_image(src, "", None, None)
                if s > 0:
                    images.append(ImageCandidate(src=src, alt="", score=s + 5))
                    seen.add(src)
    return sorted(images, key=lambda i: i.score, reverse=True)


# ── Promo discovery ───────────────────────────────────────────────────────────

def discover_promo_links(soup: BeautifulSoup, base_url: str) -> list[str]:
    base_host = urlparse(base_url).hostname
    candidates: list[tuple[str, int]] = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        resolved = resolve_url(href, base_url)
        if not resolved:
            continue
        try:
            if urlparse(resolved).hostname != base_host:
                continue
        except Exception:
            continue
        sc = 0
        if PROMO_HREF_RE.search(resolved):
            sc += 3
        if PROMO_TEXT_RE.search(text):
            sc += 2
        if sc > 0 and resolved not in seen:
            candidates.append((resolved, sc))
            seen.add(resolved)
    candidates.sort(key=lambda x: x[1], reverse=True)
    return [url for url, _ in candidates[:3]]


def scrape_promo_page(promo_url: str) -> Optional[PromoContent]:
    html, status = fetch_html(promo_url, timeout=12)
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "aside"]):
        tag.decompose()

    promo_headlines = extract_text_nodes(soup, ["h1", "h2", "h3"], limit=5)

    # Extract offer strings
    offer_texts = []
    all_texts = extract_text_nodes(
        soup, ["p", "li", "span", "div", "strong", "em", "b"], limit=60
    )
    for text in all_texts:
        if len(text) < 120 and any(p.search(text) for p in OFFER_PATTERNS):
            offer_texts.append(text)
        if len(offer_texts) >= 6:
            break

    # Promo CTAs
    promo_ctas = []
    cta_re = re.compile(
        r"\b(get|claim|redeem|start|try|sign|buy|shop|join|free|now|today|save|unlock|activate)\b",
        re.I,
    )
    for el in soup.find_all(["a", "button"]):
        text = el.get_text(strip=True)
        if 1 < len(text) < 60 and cta_re.search(text):
            promo_ctas.append(text)
        if len(promo_ctas) >= 5:
            break

    promo_images = extract_images(soup, promo_url)[:5]

    if not offer_texts and not promo_headlines:
        return None

    return PromoContent(
        promo_url=promo_url,
        promo_headlines=list(dict.fromkeys(promo_headlines)),
        promo_offers=list(dict.fromkeys(offer_texts)),
        promo_ctas=list(dict.fromkeys(promo_ctas)),
        promo_images=promo_images,
    )


# ── Main entry point ──────────────────────────────────────────────────────────

def scrape_website(url: str) -> ScrapedContent:
    html, status = fetch_html(url)

    if not html:
        if status in (403, 429):
            raise ValueError(
                f"This website blocks automated access (HTTP {status}). "
                "Try a different URL or a publicly accessible page."
            )
        if status == 400:
            raise ValueError(
                "The website rejected the request (HTTP 400). "
                "It may require a browser session or block scrapers."
            )
        raise ValueError(f"Failed to fetch URL (HTTP {status or 'timeout'}).")

    soup = BeautifulSoup(html, "html.parser")

    # Remove noise
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "aside"]):
        tag.decompose()

    # Meta tags
    og_image = (soup.find("meta", property="og:image") or {}).get("content", "")
    og_title = (soup.find("meta", property="og:title") or {}).get("content", "")
    og_description = (soup.find("meta", property="og:description") or {}).get("content", "")
    meta_desc = (soup.find("meta", attrs={"name": "description"}) or {}).get("content", "")
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else og_title

    # Favicon
    fav_tag = soup.find("link", rel=lambda r: r and ("icon" in r or "shortcut icon" in r))
    favicon_url = resolve_url(fav_tag["href"] if fav_tag and fav_tag.get("href") else "/favicon.ico", url)

    # Text content
    headlines = extract_text_nodes(soup, ["h1", "h2"], limit=8)
    taglines = extract_text_nodes(soup, ["h3", "h4", "[class*=tagline]", "[class*=subtitle]"], limit=6)

    cta_re = re.compile(
        r"\b(get|start|try|sign|learn|discover|explore|buy|shop|join|contact|request|demo|free|now)\b",
        re.I,
    )
    cta_texts = []
    for el in soup.find_all(["a", "button"]):
        text = el.get_text(strip=True)
        if 1 < len(text) < 60 and cta_re.search(text):
            cta_texts.append(text)
        if len(cta_texts) >= 8:
            break

    body_text = extract_text_nodes(soup, ["p", "li"], limit=12)

    # Images
    seen_srcs: set[str] = set()
    images: list[ImageCandidate] = []
    if og_image:
        resolved_og = resolve_url(og_image, url)
        if resolved_og:
            images.append(ImageCandidate(src=resolved_og, alt=og_title or "Hero image", score=90))
            seen_srcs.add(resolved_og)
    images.extend(extract_images(soup, url, seen_srcs))
    images = sorted(images, key=lambda i: i.score, reverse=True)[:20]

    # Promo discovery — use original HTML (with nav) for link scanning
    promo: Optional[PromoContent] = None
    try:
        full_soup = BeautifulSoup(html, "html.parser")
        promo_links = discover_promo_links(full_soup, url)
        for link in promo_links:
            result = scrape_promo_page(link)
            if result:
                promo = result
                break
    except Exception:
        pass

    return ScrapedContent(
        url=url,
        title=title,
        description=og_description or meta_desc,
        headlines=list(dict.fromkeys(headlines)),
        taglines=list(dict.fromkeys(taglines)),
        cta_texts=list(dict.fromkeys(cta_texts)),
        body_text=list(dict.fromkeys(body_text)),
        images=images,
        og_image=resolve_url(og_image, url) if og_image else None,
        og_title=og_title,
        og_description=og_description,
        favicon_url=favicon_url,
        promo=promo,
    )
