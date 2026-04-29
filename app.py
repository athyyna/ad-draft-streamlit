"""
Ad Draft Generator — Streamlit App
────────────────────────────────────────────────────────────────────────────────
HOW TO USE:
  1. Enter your OpenAI API key in the sidebar (never stored, session-only).
  2. Paste any company website URL in the input field.
  3. Click "Generate Ads" — the tool will:
       • Scrape the website for images, headlines, CTAs, and body copy
       • Detect any active promo/offer pages and extract offer details
       • Rank assets and generate 3 ad variants (Social, Display, Search) via GPT-4o
  4. Review the generated ad drafts, copy individual variants, or download all as text.

TIPS FOR BEST RESULTS:
  • Use the homepage URL (e.g. https://business.meta.com/)
  • Works best on publicly accessible sites without login walls
  • Sites with rich content (product pages, landing pages) produce better copy
  • If a promo is detected, ad copy will automatically reference the active offer

REQUIREMENTS:
  pip install streamlit openai beautifulsoup4 requests Pillow
  streamlit run app.py
"""

import streamlit as st
import time
import json
from io import StringIO

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Ad Draft Generator",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Playfair+Display:wght@700&display=swap');

  html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

  .hero-title {
    font-family: 'Playfair Display', serif;
    font-size: 2.6rem;
    font-weight: 700;
    line-height: 1.2;
    color: #0f172a;
    margin-bottom: 0.5rem;
  }
  .hero-accent { color: #6366f1; }
  .hero-sub {
    font-size: 1.05rem;
    color: #64748b;
    margin-bottom: 2rem;
    line-height: 1.6;
  }

  /* Ad card */
  .ad-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 16px;
    padding: 0;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 4px 16px rgba(0,0,0,0.04);
    margin-bottom: 1.5rem;
  }
  .ad-card-header {
    padding: 1rem 1.25rem 0.75rem;
    border-bottom: 1px solid #f1f5f9;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .format-badge {
    display: inline-flex;
    align-items: center;
    padding: 0.2rem 0.65rem;
    border-radius: 999px;
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }
  .badge-social  { background: #ede9fe; color: #6d28d9; }
  .badge-display { background: #dbeafe; color: #1d4ed8; }
  .badge-search  { background: #dcfce7; color: #15803d; }
  .ad-card-body { padding: 1.25rem; }
  .ad-headline {
    font-size: 1.15rem;
    font-weight: 700;
    color: #0f172a;
    margin-bottom: 0.5rem;
    line-height: 1.35;
  }
  .ad-body-text {
    font-size: 0.9rem;
    color: #475569;
    line-height: 1.6;
    margin-bottom: 0.75rem;
  }
  .ad-cta {
    display: inline-block;
    background: #6366f1;
    color: #ffffff !important;
    padding: 0.4rem 1rem;
    border-radius: 8px;
    font-size: 0.82rem;
    font-weight: 600;
    text-decoration: none;
  }
  .ad-image-container {
    width: 100%;
    max-height: 200px;
    overflow: hidden;
    background: #f8fafc;
  }
  .ad-image-container img {
    width: 100%;
    height: 200px;
    object-fit: cover;
  }

  /* Promo panel */
  .promo-panel {
    background: #fffbeb;
    border: 1px solid #fcd34d;
    border-radius: 12px;
    padding: 1rem 1.25rem;
    margin: 1.5rem 0;
  }
  .promo-title {
    font-weight: 700;
    color: #92400e;
    font-size: 0.9rem;
    margin-bottom: 0.5rem;
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }
  .promo-offer-tag {
    display: inline-block;
    background: #fef3c7;
    border: 1px solid #fcd34d;
    color: #92400e;
    padding: 0.2rem 0.6rem;
    border-radius: 6px;
    font-size: 0.78rem;
    font-weight: 600;
    margin: 0.15rem;
  }

  /* Company header */
  .company-header {
    background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
    border: 1px solid #e2e8f0;
    border-radius: 16px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
  }
  .company-name {
    font-size: 1.5rem;
    font-weight: 700;
    color: #0f172a;
    margin-bottom: 0.25rem;
  }
  .company-desc {
    font-size: 0.9rem;
    color: #64748b;
    line-height: 1.6;
  }
  .stat-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 999px;
    padding: 0.25rem 0.75rem;
    font-size: 0.78rem;
    color: #475569;
    font-weight: 500;
    margin-right: 0.5rem;
    margin-top: 0.75rem;
  }

  /* Step indicator */
  .step-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.4rem 0;
    font-size: 0.88rem;
    color: #64748b;
  }
  .step-active { color: #6366f1; font-weight: 600; }
  .step-done   { color: #16a34a; font-weight: 500; }

  /* Sidebar */
  section[data-testid="stSidebar"] { background: #f8fafc; }

  /* Hide Streamlit branding */
  #MainMenu, footer, header { visibility: hidden; }
  .block-container { padding-top: 2rem; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
# ── Auto-load API key from Streamlit Secrets if available ────────────────────
_secret_key = ""
try:
    _secret_key = st.secrets.get("OPENAI_API_KEY", "")
except Exception:
    pass

with st.sidebar:
    st.markdown("### ✦ Ad Draft Generator")
    st.markdown("---")
    if _secret_key:
        api_key = _secret_key
        st.success("API key configured ✓", icon="🔑")
    else:
        st.markdown("**OpenAI API Key**")
        api_key = st.text_input(
            "API Key",
            type="password",
            placeholder="sk-...",
            label_visibility="collapsed",
            help="Your key is used only for this session and never stored.",
        )
        if api_key:
            st.success("API key set ✓", icon="🔑")
        else:
            st.info("Enter your OpenAI API key to get started.", icon="ℹ️")

    st.markdown("---")
    st.markdown("**How it works**")
    st.markdown("""
- Scrapes the website for images, headlines, CTAs & body copy
- Detects active promo/offer pages automatically
- Ranks assets and generates ad copy via GPT-4o
- Produces 3 format variants: Social, Display, Search
""")
    st.markdown("---")
    st.markdown("**Try these URLs**")
    example_urls = [
        "https://business.meta.com/",
        "https://www.shopify.com/",
        "https://notion.so/",
        "https://www.figma.com/",
        "https://metaforbusiness.cn/",
    ]
    for ex in example_urls:
        st.markdown(f"• `{ex}`")

    st.markdown("---")
    st.caption("Built with Streamlit + GPT-4o")

# ── Main content ──────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero-title">
  Turn any website into<br>
  <span class="hero-accent">polished ad drafts</span>
</div>
<p class="hero-sub">
  Paste a URL. The AI scrapes the site, detects active promotions, ranks the best assets,<br>
  and generates ready-to-use ad copy for Social, Display, and Search — in seconds.
</p>
""", unsafe_allow_html=True)

# ── URL input ─────────────────────────────────────────────────────────────────
col_input, col_btn = st.columns([5, 1])
with col_input:
    url = st.text_input(
        "Website URL",
        placeholder="https://yourcompany.com",
        label_visibility="collapsed",
    )
with col_btn:
    generate_clicked = st.button("Generate Ads →", type="primary", use_container_width=True)

st.markdown("")

# ── Generation flow ───────────────────────────────────────────────────────────
if generate_clicked:
    if not api_key:
        st.error("Please enter your OpenAI API key in the sidebar first.")
        st.stop()
    if not url or not url.startswith("http"):
        st.error("Please enter a valid URL starting with http:// or https://")
        st.stop()

    # Import here to keep startup fast
    from scraper import scrape_website
    from generator import generate_ad_drafts

    # Progress steps
    status_placeholder = st.empty()

    def show_step(step: int, label: str, done_steps: list[str]):
        steps = [
            ("🌐", "Fetching website"),
            ("🔍", "Extracting content & detecting promos"),
            ("🤖", "Ranking assets with AI"),
            ("✍️", "Generating ad copy variants"),
        ]
        html = ""
        for i, (icon, name) in enumerate(steps):
            if i < len(done_steps):
                html += f'<div class="step-row step-done">✓ {icon} {name}</div>'
            elif i == step:
                html += f'<div class="step-row step-active">⟳ {icon} {label}</div>'
            else:
                html += f'<div class="step-row">○ {icon} {name}</div>'
        status_placeholder.markdown(html, unsafe_allow_html=True)

    done = []
    try:
        # Step 1 & 2: Scrape
        show_step(0, "Fetching website...", done)
        scraped = None
        with st.spinner(""):
            scraped = scrape_website(url)
        done.append("fetch")
        show_step(1, "Extracting content & detecting promos...", done)
        time.sleep(0.3)
        done.append("extract")

        # Step 3 & 4: Generate
        show_step(2, "Ranking assets with AI...", done)
        result = None
        with st.spinner(""):
            result = generate_ad_drafts(api_key, scraped)
        done.append("rank")
        show_step(3, "Generating ad copy variants...", done)
        time.sleep(0.3)
        done.append("generate")
        show_step(4, "", done)

        status_placeholder.empty()

    except ValueError as e:
        status_placeholder.empty()
        st.error(f"**Scraping failed:** {e}")
        st.stop()
    except Exception as e:
        status_placeholder.empty()
        st.error(f"**An error occurred:** {e}")
        st.stop()

    # ── Company header ────────────────────────────────────────────────────────
    tone_emoji = {
        "professional": "💼", "playful": "🎉", "bold": "⚡",
        "minimalist": "◻️", "inspirational": "✨", "friendly": "😊",
    }.get(result.brand_tone.lower(), "🎯")

    promo_pill = ""
    if result.promo_url:
        promo_pill = '<span class="stat-pill">🏷️ Promo Detected</span>'

    st.markdown(f"""
<div class="company-header">
  <div class="company-name">{result.company_name}</div>
  <div class="company-desc">{result.company_description}</div>
  <div>
    <span class="stat-pill">📄 3 Ad Variants</span>
    <span class="stat-pill">{tone_emoji} {result.brand_tone.capitalize()} Tone</span>
    <span class="stat-pill">🖼️ Image: {result.image_source.capitalize()}</span>
    {promo_pill}
  </div>
</div>
""", unsafe_allow_html=True)

    # ── Promo panel ───────────────────────────────────────────────────────────
    if result.promo_url:
        offer_tags = "".join(
            f'<span class="promo-offer-tag">{o}</span>'
            for o in result.promo_offers[:5]
        )
        cta_list = " · ".join(result.promo_ctas[:3]) if result.promo_ctas else ""
        st.markdown(f"""
<div class="promo-panel">
  <div class="promo-title">🏷️ Active Promotion Found</div>
  <div style="font-size:0.82rem; color:#78350f; margin-bottom:0.5rem;">
    Source: <a href="{result.promo_url}" target="_blank" style="color:#b45309;">{result.promo_url}</a>
  </div>
  {offer_tags}
  {f'<div style="margin-top:0.5rem; font-size:0.8rem; color:#92400e;"><strong>Promo CTAs:</strong> {cta_list}</div>' if cta_list else ""}
  <div style="margin-top:0.5rem; font-size:0.78rem; color:#a16207; font-style:italic;">
    Ad copy below has been tailored to incorporate this promotion.
  </div>
</div>
""", unsafe_allow_html=True)

    # ── Ad draft cards ────────────────────────────────────────────────────────
    format_meta = {
        "social":  {"label": "Social",  "badge": "badge-social",  "icon": "📱", "dims": "1080 × 1080"},
        "display": {"label": "Display", "badge": "badge-display", "icon": "🖥️", "dims": "1200 × 628"},
        "search":  {"label": "Search",  "badge": "badge-search",  "icon": "🔍", "dims": "Text only"},
    }

    cols = st.columns(3)
    all_copy_text = f"Ad Drafts for {result.company_name}\nGenerated from: {url}\n{'='*60}\n\n"

    for i, variant in enumerate(result.variants):
        meta = format_meta[variant.format]
        with cols[i]:
            # Image (social + display only)
            if variant.image_url and variant.format != "search":
                st.markdown(f"""
<div class="ad-image-container">
  <img src="{variant.image_url}" alt="Ad visual" onerror="this.style.display='none'">
</div>""", unsafe_allow_html=True)
            elif variant.format != "search":
                st.markdown("""
<div class="ad-image-container" style="display:flex;align-items:center;justify-content:center;height:200px;">
  <span style="color:#94a3b8;font-size:0.85rem;">No image available</span>
</div>""", unsafe_allow_html=True)

            # Landing page snippet
            lp_html = ""
            if variant.landing_page_url:
                lp_label_badge = {
                    "promo": ("#f59e0b", "#fffbeb", "Promo"),
                    "pricing": ("#6366f1", "#eef2ff", "Pricing"),
                    "signup": ("#10b981", "#ecfdf5", "Sign Up"),
                    "product": ("#3b82f6", "#eff6ff", "Product"),
                    "features": ("#8b5cf6", "#f5f3ff", "Features"),
                    "homepage": ("#64748b", "#f8fafc", "Homepage"),
                }.get(variant.landing_page_label or "", ("#64748b", "#f8fafc", variant.landing_page_label or "Page"))
                lp_color, lp_bg, lp_name = lp_label_badge
                display_url = variant.landing_page_url.replace("https://", "").replace("http://", "")
                if len(display_url) > 50:
                    display_url = display_url[:47] + "..."
                lp_html = f"""
  <div style="margin-top:0.75rem; padding:0.5rem 0.75rem; background:{lp_bg}; border-radius:8px; border:1px solid {lp_color}22; display:flex; align-items:center; gap:0.5rem;">
    <span style="font-size:0.65rem; font-weight:700; text-transform:uppercase; letter-spacing:0.05em; color:{lp_color}; background:{lp_color}18; padding:2px 6px; border-radius:4px;">{lp_name}</span>
    <a href="{variant.landing_page_url}" target="_blank" style="font-size:0.75rem; color:{lp_color}; text-decoration:none; font-weight:500; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="{variant.landing_page_url}">{display_url} ↗</a>
  </div>"""

            # Card content
            st.markdown(f"""
<div class="ad-card">
  <div class="ad-card-header">
    <span class="format-badge {meta['badge']}">{meta['icon']} {meta['label']}</span>
    <span style="font-size:0.75rem; color:#94a3b8; margin-left:auto;">{meta['dims']}</span>
  </div>
  <div class="ad-card-body">
    <div class="ad-headline">{variant.headline}</div>
    <div class="ad-body-text">{variant.body}</div>
    <span class="ad-cta">{variant.cta}</span>
    {lp_html}
  </div>
</div>
""", unsafe_allow_html=True)

            # Copy button
            lp_line = f"\nLanding Page: {variant.landing_page_url}" if variant.landing_page_url else ""
            copy_text = f"{meta['label']} Ad\nHeadline: {variant.headline}\nBody: {variant.body}\nCTA: {variant.cta}{lp_line}"
            st.download_button(
                label=f"⬇ Download {meta['label']}",
                data=copy_text,
                file_name=f"ad_{variant.format}_{result.company_name.replace(' ', '_').lower()}.txt",
                mime="text/plain",
                use_container_width=True,
                key=f"dl_{variant.format}",
            )

            all_copy_text += f"── {meta['label'].upper()} AD ({meta['dims']}) ──\n"
            all_copy_text += f"Headline:     {variant.headline}\n"
            all_copy_text += f"Body:         {variant.body}\n"
            all_copy_text += f"CTA:          {variant.cta}\n"
            if variant.landing_page_url:
                all_copy_text += f"Landing Page: {variant.landing_page_url}\n"
            all_copy_text += "\n"

    # ── Download all ──────────────────────────────────────────────────────────
    st.markdown("---")
    col_dl, col_info = st.columns([2, 3])
    with col_dl:
        if result.promo_url:
            all_copy_text += f"── PROMO DETECTED ──\nURL: {result.promo_url}\n"
            if result.promo_offers:
                all_copy_text += f"Offers: {', '.join(result.promo_offers)}\n"
        st.download_button(
            label="⬇ Download All Ad Drafts (.txt)",
            data=all_copy_text,
            file_name=f"ad_drafts_{result.company_name.replace(' ', '_').lower()}.txt",
            mime="text/plain",
            use_container_width=True,
        )
    with col_info:
        if result.key_benefits:
            st.markdown(
                "**Key benefits identified:** " +
                " · ".join(f"`{b}`" for b in result.key_benefits[:3])
            )

    # ── UTM Parameter Builder ─────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🔗 UTM Parameter Builder")
    st.markdown(
        "Build tracking URLs for each ad format — ready to paste into Ads Manager. "
        "Parameters are auto-filled with smart defaults per format."
    )

    # Collect landing pages per format
    lp_by_format = {v.format: v.landing_page_url for v in result.variants}
    has_any_lp = any(lp_by_format.values())

    utm_col1, utm_col2 = st.columns([1, 1])
    with utm_col1:
        utm_campaign = st.text_input(
            "utm_campaign *",
            value=result.company_name.lower().replace(" ", "_")[:40] if result.company_name else "brand_awareness",
            placeholder="brand_awareness_2026",
            key="utm_campaign",
        )
        utm_source = st.text_input(
            "utm_source * (overrides format default)",
            value="",
            placeholder="meta / google / linkedin (leave blank for format default)",
            key="utm_source",
        )
        utm_medium = st.text_input(
            "utm_medium * (overrides format default)",
            value="",
            placeholder="paid_social / cpc / display (leave blank for format default)",
            key="utm_medium",
        )
        utm_content = st.text_input(
            "utm_content (optional)",
            value="",
            placeholder="social_v1 / display_v2",
            key="utm_content",
        )
        utm_term = st.text_input(
            "utm_term (optional, search only)",
            value="",
            placeholder="keyword phrase",
            key="utm_term",
        )

    with utm_col2:
        # Format-specific defaults
        FORMAT_UTM_DEFAULTS = {
            "social":  {"source": "meta",   "medium": "paid_social"},
            "display": {"source": "google", "medium": "display"},
            "search":  {"source": "google", "medium": "cpc"},
        }

        def build_utm_url(base_url: str, source: str, medium: str, campaign: str, content: str = "", term: str = "") -> str:
            if not base_url:
                return ""
            try:
                from urllib.parse import urlparse, urlencode, urlunparse, parse_qs
                parsed = urlparse(base_url)
                from urllib.parse import parse_qsl
                qp = dict(parse_qsl(parsed.query))
                if source:   qp["utm_source"]   = source
                if medium:   qp["utm_medium"]   = medium
                if campaign: qp["utm_campaign"] = campaign
                if content:  qp["utm_content"]  = content
                if term:     qp["utm_term"]     = term
                new_query = urlencode(qp)
                return urlunparse(parsed._replace(query=new_query))
            except Exception:
                return base_url

        if not has_any_lp:
            st.info("No landing pages were detected for this site. Generate ads from a URL with product/pricing/promo pages for best results.")
        else:
            utm_urls_text = "UTM TRACKING URLS\n\n"
            for fmt in ["social", "display", "search"]:
                defaults = FORMAT_UTM_DEFAULTS[fmt]
                base = lp_by_format.get(fmt) or ""
                src = utm_source.strip() or defaults["source"]
                med = utm_medium.strip() or defaults["medium"]
                url = build_utm_url(base, src, med, utm_campaign, utm_content, utm_term if fmt == "search" else "")
                label_map = {"social": "📱 Social", "display": "🖥 Display", "search": "🔍 Search"}
                if url:
                    st.markdown(f"**{label_map[fmt]}** (`{defaults['source']}` / `{defaults['medium']}`):")
                    st.code(url, language=None)
                    utm_urls_text += f"── {fmt.upper()} ──\n{url}\n\n"
                else:
                    st.markdown(f"**{label_map[fmt]}**: _No landing page detected_")

            st.download_button(
                label="⬇ Download All UTM URLs (.txt)",
                data=utm_urls_text,
                file_name=f"utm_urls_{utm_campaign}.txt",
                mime="text/plain",
                use_container_width=True,
                key="dl_utm",
            )

    # ── Scraped assets expander ───────────────────────────────────────────────
    with st.expander("🔍 View scraped assets used"):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Headlines found**")
            for h in scraped.headlines[:6]:
                st.markdown(f"- {h}")
            st.markdown("**CTAs found**")
            for c in scraped.cta_texts[:5]:
                st.markdown(f"- {c}")
        with c2:
            st.markdown("**Top images scored**")
            for img in scraped.images[:5]:
                st.markdown(f"- Score **{img.score}** — `{img.src[:60]}...`" if len(img.src) > 60 else f"- Score **{img.score}** — `{img.src}`")
            if scraped.promo:
                st.markdown("**Promo page content**")
                for offer in scraped.promo.promo_offers[:4]:
                    st.markdown(f"- {offer}")

# ── Empty state ───────────────────────────────────────────────────────────────
elif not generate_clicked:
    st.markdown("""
<div style="text-align:center; padding: 3rem 0; color: #94a3b8;">
  <div style="font-size: 3rem; margin-bottom: 1rem;">✦</div>
  <div style="font-size: 1rem;">Enter a URL above and click <strong>Generate Ads</strong> to get started.</div>
  <div style="font-size: 0.85rem; margin-top: 0.5rem;">Works best with product pages, landing pages, and company homepages.</div>
</div>
""", unsafe_allow_html=True)
