import asyncio
import logging
import os
from typing import Optional

import httpx

from .models import CaptureResult, CarouselItem
from app.services.instagram_service import extract_shortcode

logger = logging.getLogger(__name__)

_TIMEOUT_MS = 20_000
_IMAGE_DOWNLOAD_TIMEOUT = 10.0
_MAX_CAROUSEL_SLIDES = 10

# User-agent that Instagram lets through for OGP meta scraping
_USER_AGENT = (
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
)

# JS snippet: extract all candidate CDN image URLs from the rendered page
_JS_EXTRACT_CAROUSEL = """
() => {
    const results = [];

    // Strategy 1: JSON-LD structured data (ImageObject / SocialMediaPosting)
    document.querySelectorAll('script[type="application/ld+json"]').forEach(s => {
        try {
            const data = JSON.parse(s.textContent);
            const images = data.image || [];
            const arr = Array.isArray(images) ? images : [images];
            arr.forEach(img => {
                const url = typeof img === 'string' ? img : img.url;
                if (url) results.push(url);
            });
        } catch {}
    });

    if (results.length > 1) return results;

    // Strategy 2: all <img> tags with Instagram/Facebook CDN src
    const CDN = /(cdninstagram\\.com|fbcdn\\.net)/;
    const SKIP = /(profile_pic|s150x150|s320x320|_nc_ht=scontent)/;
    document.querySelectorAll('img').forEach(img => {
        const src = img.src || img.dataset.src || '';
        if (CDN.test(src) && !SKIP.test(src)) results.push(src);
    });

    return [...new Set(results)];
}
"""


def _is_login_wall(current_url: str, page_content: str) -> bool:
    return (
        "accounts/login" in current_url
        or "Log in to Instagram" in page_content
        or '"loginRequired":true' in page_content
    )


async def _download_images_parallel(
    urls: list[str],
) -> list[Optional[bytes]]:
    """Download multiple images concurrently. Returns None for failed downloads."""
    async def _fetch(url: str) -> Optional[bytes]:
        try:
            async with httpx.AsyncClient(timeout=_IMAGE_DOWNLOAD_TIMEOUT) as client:
                resp = await client.get(url, follow_redirects=True)
                return resp.content if resp.status_code == 200 else None
        except Exception as exc:
            logger.warning("Failed to download image | url=%s error=%s", url[:80], exc)
            return None

    return await asyncio.gather(*[_fetch(u) for u in urls])


async def capture_instagram_post(url: str) -> CaptureResult:
    """
    Headless Chromium capture of a public Instagram post via OGP meta tags.
    Supports single images and carousels via JSON-LD / DOM extraction.
    No session, no login, no OAuth. Public posts only.
    """
    shortcode = extract_shortcode(url)
    _executable = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH") or None

    try:
        from playwright.async_api import async_playwright
        from playwright.async_api import TimeoutError as PlaywrightTimeout
    except ImportError:
        return CaptureResult(
            success=False, url=url, shortcode=shortcode,
            error_type="PARSE_ERROR", error_message="playwright not installed",
        )

    # ── Phase 1: load page, extract OGP + try carousel ────────────────────
    caption: Optional[str] = None
    image_url: Optional[str] = None
    username: Optional[str] = None
    candidate_urls: list[str] = []

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True, executable_path=_executable,
            )
            context = await browser.new_context(
                user_agent=_USER_AGENT, locale="en-US",
            )
            page = await context.new_page()

            try:
                response = await page.goto(
                    url, timeout=_TIMEOUT_MS, wait_until="domcontentloaded",
                )

                if response and response.status == 404:
                    await browser.close()
                    return CaptureResult(
                        success=False, url=url, shortcode=shortcode,
                        error_type="NOT_FOUND", error_message="Post not found (404)",
                    )

                current_url = page.url
                page_content = await page.content()

                if _is_login_wall(current_url, page_content):
                    await browser.close()
                    return CaptureResult(
                        success=False, url=url, shortcode=shortcode,
                        error_type="LOGIN_REQUIRED",
                        error_message="Content requires login — post may be private",
                    )

                # ── OGP meta tags ──────────────────────────────────────────
                caption = await page.evaluate(
                    "() => { const el = document.querySelector('meta[property=\"og:description\"]'); "
                    "return el ? el.getAttribute('content') : null; }"
                )
                image_url = await page.evaluate(
                    "() => { const el = document.querySelector('meta[property=\"og:image\"]'); "
                    "return el ? el.getAttribute('content') : null; }"
                )
                og_title: Optional[str] = await page.evaluate(
                    "() => { const el = document.querySelector('meta[property=\"og:title\"]'); "
                    "return el ? el.getAttribute('content') : null; }"
                )

                if og_title:
                    for sep in (" on Instagram", " • Instagram"):
                        if sep in og_title:
                            username = og_title.split(sep)[0].lstrip("@").strip()
                            break

                if not caption and not image_url:
                    await browser.close()
                    return CaptureResult(
                        success=False, url=url, shortcode=shortcode,
                        error_type="PARSE_ERROR",
                        error_message="No OGP data found — post may have been removed",
                    )

                # ── Carousel extraction (best-effort) ─────────────────────
                try:
                    candidate_urls = await page.evaluate(_JS_EXTRACT_CAROUSEL)
                    candidate_urls = [u for u in candidate_urls if u][:_MAX_CAROUSEL_SLIDES]
                except Exception as exc:
                    logger.debug("Carousel JS extraction failed: %s", exc)
                    candidate_urls = []

            except PlaywrightTimeout:
                await browser.close()
                return CaptureResult(
                    success=False, url=url, shortcode=shortcode,
                    error_type="TIMEOUT",
                    error_message=f"Page load timed out after {_TIMEOUT_MS}ms",
                )
            finally:
                await browser.close()

    except Exception as exc:
        logger.exception("Instagram agent unexpected error | url=%s", url)
        return CaptureResult(
            success=False, url=url, shortcode=shortcode,
            error_type="PARSE_ERROR", error_message=str(exc)[:300],
        )

    # ── Phase 2: download images ───────────────────────────────────────────
    #
    # If carousel extraction found multiple URLs, use those.
    # Otherwise fall back to the single OGP image.
    is_carousel = len(candidate_urls) > 1

    if not candidate_urls and image_url:
        candidate_urls = [image_url]
    elif not is_carousel and image_url and image_url not in candidate_urls:
        # Ensure OGP image is always present as slide 0
        candidate_urls = [image_url] + [u for u in candidate_urls if u != image_url]

    if candidate_urls:
        logger.info(
            "Downloading %d Instagram image(s) | shortcode=%s is_carousel=%s",
            len(candidate_urls), shortcode, is_carousel,
        )
        downloaded = await _download_images_parallel(candidate_urls)
    else:
        downloaded = []

    carousel_items: list[CarouselItem] = []
    for i, (img_url, img_bytes) in enumerate(zip(candidate_urls, downloaded)):
        carousel_items.append(CarouselItem(
            index=i,
            url=img_url,
            media_type="IMAGE",
            image_bytes=img_bytes,
        ))

    # Backward compat: surface first slide on the top-level fields
    first_bytes = carousel_items[0].image_bytes if carousel_items else None

    return CaptureResult(
        success=True,
        url=url,
        caption=caption,
        image_url=candidate_urls[0] if candidate_urls else None,
        image_bytes=first_bytes,
        username=username,
        shortcode=shortcode,
        is_carousel=is_carousel,
        carousel_items=carousel_items,
    )
