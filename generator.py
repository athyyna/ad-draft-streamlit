"""
generator.py — AI Ad Draft Generator
Uses OpenAI to rank scraped assets and generate ad copy variants for Social, Display, and Search.
"""

import json
from dataclasses import dataclass, field
from typing import Optional
from openai import OpenAI
from scraper import ScrapedContent


@dataclass
class AdVariant:
    format: str          # "social" | "display" | "search"
    headline: str
    body: str
    cta: str
    image_url: str
    image_source: str    # "scraped" | "none"
    landing_page_url: Optional[str] = None   # recommended landing page for this format
    landing_page_label: Optional[str] = None # e.g. "promo", "pricing", "product", "homepage"


@dataclass
class GeneratedAdResult:
    company_name: str
    company_description: str
    brand_tone: str
    key_benefits: list[str]
    selected_image: str
    image_source: str
    variants: list[AdVariant]
    promo_url: Optional[str] = None
    promo_offers: list[str] = field(default_factory=list)
    promo_ctas: list[str] = field(default_factory=list)


# ── Step 1: Rank assets ───────────────────────────────────────────────────────

def rank_assets(client: OpenAI, scraped: ScrapedContent) -> dict:
    image_list = "\n".join(
        f'[{i}] src="{img.src}" alt="{img.alt}" score={img.score}'
        for i, img in enumerate(scraped.images[:10])
    ) or "No images found"

    promo_section = ""
    if scraped.promo:
        p = scraped.promo
        promo_section = (
            f"\n\nPROMO PAGE DETECTED: {p.promo_url}"
            + (f"\nPROMO HEADLINES: {' | '.join(p.promo_headlines)}" if p.promo_headlines else "")
            + (f"\nPROMO OFFERS: {' | '.join(p.promo_offers)}" if p.promo_offers else "")
            + (f"\nPROMO CTAs: {' | '.join(p.promo_ctas)}" if p.promo_ctas else "")
            + "\n(Use these promo details to make the ad copy more specific and offer-driven.)"
        )

    prompt = f"""You are an expert digital advertising strategist. Analyze this scraped website content and select the best assets for ad creation.

WEBSITE URL: {scraped.url}
TITLE: {scraped.title}
DESCRIPTION: {scraped.description}

HEADLINES FOUND:
{chr(10).join(scraped.headlines[:8])}

TAGLINES FOUND:
{chr(10).join(scraped.taglines[:6])}

CTA TEXTS FOUND:
{chr(10).join(scraped.cta_texts[:8])}

BODY COPY FOUND:
{chr(10).join(scraped.body_text[:8])}{promo_section}

IMAGES FOUND (scored 0-100):
{image_list}

Return a JSON object with these exact fields:
- companyName: string (infer from title/URL)
- companyDescription: string (1-2 sentence brand description)
- topHeadlines: string[] (top 3 most impactful headlines from the scraped content)
- topCTAs: string[] (top 3 CTA texts)
- bestImageIndex: number (index of best image from the list, or -1 if none are suitable)
- imagePrompt: string (detailed prompt to generate a brand-appropriate hero image if needed)
- brandTone: string (e.g. "professional", "playful", "bold", "minimalist", "inspirational")
- keyBenefits: string[] (top 3 key product/service benefits inferred from content)"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are an expert digital advertising strategist. Always respond with valid JSON only, no markdown."},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
    )
    return json.loads(response.choices[0].message.content)


# ── Step 2: Generate ad copy ──────────────────────────────────────────────────

def generate_ad_copy(client: OpenAI, ranked: dict, promo_context: Optional[str] = None) -> dict:
    promo_instruction = ""
    if promo_context:
        promo_instruction = (
            f"\n\nACTIVE PROMOTION:\n{promo_context}\n"
            "IMPORTANT: Incorporate the promotion naturally into the ad copy — "
            "reference the specific offer, discount, or deal in the body or CTA where it fits."
        )

    prompt = f"""You are a world-class advertising copywriter. Create compelling ad copy for 3 different formats.

COMPANY: {ranked.get('companyName', '')}
BRAND DESCRIPTION: {ranked.get('companyDescription', '')}
BRAND TONE: {ranked.get('brandTone', 'professional')}
KEY BENEFITS: {', '.join(ranked.get('keyBenefits', []))}
TOP HEADLINES (for reference): {' | '.join(ranked.get('topHeadlines', []))}
TOP CTAs (for reference): {' | '.join(ranked.get('topCTAs', []))}{promo_instruction}

Create ad copy for these 3 formats:

1. SOCIAL AD (Instagram/Facebook)
   - Headline: 6-10 words, punchy and emotional
   - Body: 2-3 sentences, conversational, benefit-driven, max 125 chars
   - CTA: 2-4 words, action-oriented

2. DISPLAY AD (Banner/GDN)
   - Headline: 5-8 words, clear value proposition
   - Body: 1-2 sentences, concise, max 90 chars
   - CTA: 2-3 words

3. SEARCH AD (Google Search)
   - Headline: 5-7 words, keyword-rich, max 30 chars
   - Body: 1 sentence, feature + benefit, max 90 chars
   - CTA: 2-3 words

Return valid JSON:
{{
  "social": {{"headline": "...", "body": "...", "cta": "..."}},
  "display": {{"headline": "...", "body": "...", "cta": "..."}},
  "search": {{"headline": "...", "body": "...", "cta": "..."}}
}}"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a world-class advertising copywriter. Always respond with valid JSON only, no markdown."},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.7,
    )
    return json.loads(response.choices[0].message.content)


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_ad_drafts(api_key: str, scraped: ScrapedContent) -> GeneratedAdResult:
    client = OpenAI(api_key=api_key)

    # Build promo context
    promo_context: Optional[str] = None
    if scraped.promo:
        p = scraped.promo
        parts = []
        if p.promo_offers:
            parts.append(f"Offers: {' | '.join(p.promo_offers)}")
        if p.promo_ctas:
            parts.append(f"CTAs: {' | '.join(p.promo_ctas)}")
        if p.promo_headlines:
            parts.append(f"Promo Headlines: {' | '.join(p.promo_headlines[:2])}")
        if parts:
            promo_context = ". ".join(parts)

    ranked = rank_assets(client, scraped)
    ad_copy = generate_ad_copy(client, ranked, promo_context)

    # Select best image
    best_idx = ranked.get("bestImageIndex", -1)
    selected_image = ""
    image_source = "none"
    if isinstance(best_idx, (int, float)) and 0 <= int(best_idx) < len(scraped.images):
        img = scraped.images[int(best_idx)]
        if img.score >= 40:
            selected_image = img.src
            image_source = "scraped"
    if not selected_image and scraped.og_image:
        selected_image = scraped.og_image
        image_source = "scraped"

    # Assign landing pages per format
    lp = scraped.landing_page_candidates
    promo_lp = next((c for c in lp if c.label == "promo"), None)
    pricing_lp = next((c for c in lp if c.label in ("pricing", "signup")), None)
    product_lp = next((c for c in lp if c.label in ("product", "features")), None)
    fallback_lp = lp[0] if lp else None

    format_landing = {
        "social": promo_lp or product_lp or fallback_lp,
        "display": promo_lp or product_lp or fallback_lp,
        "search": pricing_lp or promo_lp or fallback_lp,
    }

    formats = ["social", "display", "search"]
    variants = [
        AdVariant(
            format=fmt,
            headline=ad_copy.get(fmt, {}).get("headline", ""),
            body=ad_copy.get(fmt, {}).get("body", ""),
            cta=ad_copy.get(fmt, {}).get("cta", ""),
            image_url=selected_image,
            image_source=image_source,
            landing_page_url=format_landing[fmt].url if format_landing[fmt] else None,
            landing_page_label=format_landing[fmt].label if format_landing[fmt] else None,
        )
        for fmt in formats
    ]

    return GeneratedAdResult(
        company_name=ranked.get("companyName", scraped.title),
        company_description=ranked.get("companyDescription", scraped.description),
        brand_tone=ranked.get("brandTone", "professional"),
        key_benefits=ranked.get("keyBenefits", []),
        selected_image=selected_image,
        image_source=image_source,
        variants=variants,
        promo_url=scraped.promo.promo_url if scraped.promo else None,
        promo_offers=scraped.promo.promo_offers if scraped.promo else [],
        promo_ctas=scraped.promo.promo_ctas if scraped.promo else [],
    )
