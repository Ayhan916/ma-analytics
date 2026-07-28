"""Google Maps business search and review scraper using Playwright (sync).

Usage:
  businesses = search_businesses("80331", 5, "Supermarkt")
  reviews    = scrape_reviews("https://www.google.com/maps/place/...", max_reviews=200)

Google Maps ToS note: for personal/research use at low volume with rate limiting.
"""
from __future__ import annotations
import re
import time
import random
from dataclasses import dataclass, field
from typing import List, Optional
import structlog

log = structlog.get_logger(__name__)

DELAY_MIN = 2.0
DELAY_MAX = 4.0

CATEGORIES = [
    "Restaurant", "Supermarkt", "Friseur", "Autowerkstatt",
    "Apotheke", "Café", "Bäckerei", "Arzt", "Zahnarzt",
    "Fitnessstudio", "Hotel", "Bar", "Pizzeria", "Tankstelle",
]


@dataclass
class BusinessResult:
    name: str
    maps_url: str
    place_id: str
    address: str
    rating: float
    review_count: int
    category: str


@dataclass
class MapReview:
    text: str
    rating: int
    date_str: str
    author: str = ""
    external_id: str = ""


def _sleep():
    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))


def _parse_rating(text: str) -> float:
    m = re.search(r"(\d[,\.]\d)", text)
    if m:
        return float(m.group(1).replace(",", "."))
    m = re.search(r"(\d)", text)
    return float(m.group(1)) if m else 0.0


def _parse_count(text: str) -> int:
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else 0


def _extract_place_id(url: str) -> str:
    m = re.search(r"place/([^/]+)", url)
    if m:
        return m.group(1)
    # fallback: use a hash of the URL
    return str(abs(hash(url)))[:12]


def search_businesses(
    postal_code: str,
    radius_km: int,
    category: str,
    max_results: int = 20,
) -> List[BusinessResult]:
    """Search Google Maps for businesses near a postal code."""
    from playwright.sync_api import sync_playwright

    results: List[BusinessResult] = []
    query = f"{category} {postal_code} Deutschland"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = browser.new_context(
            locale="de-DE",
            timezone_id="Europe/Berlin",
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = ctx.new_page()

        try:
            url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}"
            log.info("maps_search_start", query=query, url=url)
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            _sleep()

            # Accept cookies if dialog appears
            try:
                accept = page.locator("button:has-text('Alle akzeptieren'), button:has-text('Accept all')").first
                if accept.is_visible(timeout=3_000):
                    accept.click()
                    _sleep()
            except Exception:
                pass

            # Wait for the results feed
            try:
                page.wait_for_selector('[role="feed"]', timeout=15_000)
            except Exception:
                log.warning("maps_feed_not_found", query=query)
                return results

            # Scroll feed to load more results
            for _ in range(4):
                page.evaluate(
                    'document.querySelector(\'[role="feed"]\')?.scrollBy(0, 600)'
                )
                time.sleep(random.uniform(1.0, 1.8))

            # Extract business cards
            cards = page.locator('[role="feed"] .Nv2PK').all()
            if not cards:
                cards = page.locator('[role="feed"] > div > div').all()

            log.info("maps_cards_found", count=len(cards))

            for card in cards[:max_results]:
                try:
                    # Name — several selector strategies
                    name = ""
                    for sel in [".qBF1Pd", "a[aria-label]", "[aria-label]"]:
                        el = card.locator(sel).first
                        try:
                            name = (el.get_attribute("aria-label") or el.inner_text()).strip()
                            if name:
                                break
                        except Exception:
                            continue

                    if not name:
                        continue

                    # Rating
                    rating = 0.0
                    try:
                        rating_el = card.locator(".MW4etd").first
                        rating = _parse_rating(rating_el.inner_text())
                    except Exception:
                        pass

                    # Review count
                    review_count = 0
                    try:
                        count_el = card.locator(".UY7F9").first
                        review_count = _parse_count(count_el.inner_text())
                    except Exception:
                        pass

                    # Maps URL — click card to get canonical URL
                    try:
                        card.click()
                        page.wait_for_load_state("domcontentloaded", timeout=8_000)
                        time.sleep(random.uniform(1.5, 2.5))
                        maps_url = page.url
                    except Exception:
                        maps_url = url
                        continue

                    place_id = _extract_place_id(maps_url)

                    # Address
                    address = ""
                    try:
                        addr_el = page.locator('button[data-item-id="address"]').first
                        address = addr_el.inner_text(timeout=3_000).strip()
                    except Exception:
                        pass

                    results.append(BusinessResult(
                        name=name,
                        maps_url=maps_url,
                        place_id=place_id,
                        address=address,
                        rating=rating,
                        review_count=review_count,
                        category=category,
                    ))
                    log.info("maps_business_found", name=name, rating=rating, reviews=review_count)

                    # Go back to results list
                    page.go_back(wait_until="domcontentloaded", timeout=8_000)
                    _sleep()

                except Exception as e:
                    log.warning("maps_card_extract_failed", error=str(e))
                    try:
                        page.go_back(wait_until="domcontentloaded", timeout=8_000)
                    except Exception:
                        pass
                    continue

        except Exception as e:
            log.error("maps_search_failed", error=str(e))
        finally:
            browser.close()

    log.info("maps_search_done", found=len(results))
    return results


def scrape_reviews(maps_url: str, max_reviews: int = 200) -> List[MapReview]:
    """Scrape reviews from a Google Maps business page."""
    from playwright.sync_api import sync_playwright

    reviews: List[MapReview] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = browser.new_context(
            locale="de-DE",
            timezone_id="Europe/Berlin",
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = ctx.new_page()

        try:
            log.info("maps_reviews_start", url=maps_url, max=max_reviews)
            page.goto(maps_url, wait_until="domcontentloaded", timeout=30_000)
            _sleep()

            # Accept cookies
            try:
                accept = page.locator("button:has-text('Alle akzeptieren'), button:has-text('Accept all')").first
                if accept.is_visible(timeout=3_000):
                    accept.click()
                    _sleep()
            except Exception:
                pass

            # Click "Rezensionen" tab
            try:
                tab = page.locator("button[aria-label*='Rezension'], div[role='tab']:has-text('Rezension')").first
                tab.click(timeout=8_000)
                time.sleep(random.uniform(1.5, 2.5))
            except Exception:
                # Try by index — reviews tab is usually index 1
                try:
                    tabs = page.locator("div[role='tablist'] button, div[role='tablist'] div[role='tab']").all()
                    if len(tabs) > 1:
                        tabs[1].click()
                        time.sleep(random.uniform(1.5, 2.5))
                except Exception as e:
                    log.warning("maps_reviews_tab_not_found", error=str(e))

            # Sort by newest for freshest reviews
            try:
                sort_btn = page.locator("button[aria-label*='Sortieren'], button[data-value='sort']").first
                sort_btn.click(timeout=5_000)
                time.sleep(0.8)
                newest = page.locator("li[data-index='1'], [role='menuitem']:nth-child(2)").first
                newest.click(timeout=3_000)
                time.sleep(random.uniform(1.0, 2.0))
            except Exception:
                pass

            # Scroll to load reviews
            scrollable = page.locator(".m6QErb[data-scroll-hide], .DxyBCb").first
            prev_count = 0
            stall_count = 0

            while len(reviews) < max_reviews and stall_count < 4:
                # Expand all "Mehr" (more) buttons
                try:
                    more_buttons = page.locator("button.w8nwRe, button[aria-label*='Mehr']").all()
                    for btn in more_buttons:
                        try:
                            btn.click()
                        except Exception:
                            pass
                except Exception:
                    pass

                # Extract review cards
                cards = page.locator(".jftiEf, div[data-review-id]").all()

                for card in cards[len(reviews):]:
                    if len(reviews) >= max_reviews:
                        break
                    try:
                        # Review text
                        text = ""
                        for sel in [".wiI7pd", "span[data-expandable-section]", ".MyEned span"]:
                            try:
                                text = card.locator(sel).first.inner_text(timeout=2_000).strip()
                                if text:
                                    break
                            except Exception:
                                continue

                        if not text:
                            continue

                        # Rating
                        rating = 0
                        try:
                            rating_el = card.locator("span[role='img'][aria-label]").first
                            aria = rating_el.get_attribute("aria-label") or ""
                            m = re.search(r"(\d)", aria)
                            rating = int(m.group(1)) if m else 0
                        except Exception:
                            pass

                        # Date
                        date_str = ""
                        try:
                            date_str = card.locator(".rsqaWe").first.inner_text(timeout=2_000).strip()
                        except Exception:
                            pass

                        # Author
                        author = ""
                        try:
                            author = card.locator(".d4r55, .T56lfb").first.inner_text(timeout=2_000).strip()
                        except Exception:
                            pass

                        # External ID from data-review-id attribute
                        ext_id = card.get_attribute("data-review-id") or f"{len(reviews)}"

                        reviews.append(MapReview(
                            text=text,
                            rating=rating,
                            date_str=date_str,
                            author=author,
                            external_id=ext_id,
                        ))

                    except Exception as e:
                        log.debug("maps_review_extract_failed", error=str(e))
                        continue

                # Check for stall
                if len(reviews) == prev_count:
                    stall_count += 1
                else:
                    stall_count = 0
                prev_count = len(reviews)

                # Scroll down
                try:
                    scrollable.evaluate("el => el.scrollBy(0, 800)")
                except Exception:
                    page.evaluate("window.scrollBy(0, 800)")
                time.sleep(random.uniform(1.5, 2.5))

        except Exception as e:
            log.error("maps_reviews_failed", error=str(e))
        finally:
            browser.close()

    log.info("maps_reviews_done", count=len(reviews), url=maps_url)
    return reviews
