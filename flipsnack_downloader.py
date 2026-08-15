"""
Flipsnack Page Downloader
~~~~~~~~~~~~~~~~~~~~~~~~~
Downloads all pages from a Flipsnack publication as high-quality images.

How it works:
  1. Opens the Flipsnack full-view page with Selenium
  2. Switches into the player iframe
  3. Reads the signed CloudFront collection URL that the player loaded
  4. Fetches the collection's data.json to get the real page order and IDs
  5. Downloads every page image at original resolution

Note: Flipsnack page images are NOT numbered sequentially in the URL. Each page
has its own random ID (.../covers/<id>/original), so the page list has to come
from data.json. Older publications that still use /page_N/ paths are handled by
a legacy fallback.

The CloudFront signature is short-lived, so it is refreshed automatically from
the browser session if it expires mid-download.

Usage:
  python flipsnack_downloader.py <FLIPSNACK_FULL_VIEW_URL>
  python flipsnack_downloader.py https://www.flipsnack.com/XXXXX/my-catalog/full-view.html?p=1

Requirements:
  pip install selenium requests
  Google Chrome + ChromeDriver
"""

import os
import re
import sys
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options


# Matches a signed collection resource, e.g.
#   https://<cdn>/<account>/collections/<hash>/data.json?Signature=...
# group(1) = collection base URL, group(2) = signed query string
COLLECTION_RE = re.compile(r'(https://[^?]*?/collections/[^/?]+)/[^?]*\?(.+)')

# Transient network failures (DNS hiccups, resets) get retried locally.
NETWORK_RETRIES = 3
RETRY_BACKOFF = 3  # seconds, multiplied by the attempt number

# JS run inside the player iframe: every URL the player has loaded, plus the
# <img> sources currently in the DOM.
COLLECT_URLS_JS = """
const res = performance.getEntriesByType('resource').map(r => r.name);
const imgs = Array.from(document.querySelectorAll('img'))
                  .map(i => i.currentSrc || i.src || '');
return res.concat(imgs).filter(u => u && u.includes('/collections/'));
"""


def get_flipsnack_url():
    """Get the Flipsnack URL from command-line args or user input."""
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = input("Flipsnack full-view URL girin: ").strip()

    if not url:
        print("HATA: URL bos olamaz!")
        sys.exit(1)

    # Ensure it has ?p=1
    if "full-view.html" in url and "?p=" not in url:
        url += "?p=1"
    elif "full-view.html" not in url:
        # Try to construct full-view URL
        url = url.rstrip("/") + "/full-view.html?p=1"

    return url


def create_driver():
    """Create and configure Chrome WebDriver."""
    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--log-level=3")
    return webdriver.Chrome(options=options)


def make_session():
    """HTTP session with the headers CloudFront expects from the player."""
    session = requests.Session()
    session.headers.update({
        "Referer": "https://player.flipsnack.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
    })
    return session


def short_error(exc):
    """Condense a requests exception into one printable line.

    Raw requests errors embed the whole signed URL, which floods the console.
    """
    text = str(exc)
    if "getaddrinfo failed" in text or "NameResolutionError" in text:
        return "DNS cozumlenemedi"
    if "timed out" in text.lower() or "ReadTimeout" in text:
        return "zaman asimi"
    if "Connection aborted" in text or "ConnectionReset" in text:
        return "baglanti kesildi"
    if "SSLError" in text:
        return "SSL hatasi"
    return f"{type(exc).__name__}"


def get_with_retry(session, url, timeout=60, retries=NETWORK_RETRIES, label=""):
    """GET with retries for transient network failures (DNS blips, resets).

    Network problems are separate from signature problems: reloading the
    browser cannot fix a DNS failure, so those are simply retried here.
    Raises the last requests exception if every attempt fails.
    """
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            return session.get(url, timeout=timeout)
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < retries:
                wait = RETRY_BACKOFF * attempt
                print(f"  [..]  {label}Ag hatasi ({short_error(exc)}), "
                      f"{wait}s sonra tekrar deneniyor ({attempt}/{retries - 1})...")
                time.sleep(wait)
    raise last_exc


def ascii_safe(text):
    """Strip characters the Windows console codepage cannot print."""
    return str(text).encode("ascii", "replace").decode("ascii")


def dismiss_cookie_consent(driver):
    """Dismiss cookie consent dialog if present."""
    try:
        btns = driver.find_elements(
            By.XPATH,
            "//button[contains(text(),'Accept') or contains(text(),'Kabul') or contains(text(),'agree')]"
        )
        if btns:
            btns[0].click()
            time.sleep(1)
    except Exception:
        pass


def switch_to_player_iframe(driver):
    """Find and switch to the Flipsnack player iframe."""
    driver.switch_to.default_content()
    try:
        iframes = WebDriverWait(driver, 20).until(
            lambda d: d.find_elements(By.TAG_NAME, "iframe") or False
        )
    except Exception:
        return False

    for iframe in iframes:
        src = iframe.get_attribute("src") or ""
        if "player.flipsnack" in src or "flipsnack" in src:
            driver.switch_to.frame(iframe)
            print(f"  Player iframe bulundu: {src[:80]}...")
            return True

    # Fallback: try the first iframe
    if iframes:
        driver.switch_to.frame(iframes[0])
        print("  Ilk iframe'e gecildi (fallback)")
        return True

    return False


def extract_signed_collection_url(driver, timeout=30):
    """Return a signed CloudFront collection URL loaded by the player.

    Prefers data.json, since that is the one request guaranteed to be present
    even before any page image has finished loading.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urls = driver.execute_script(COLLECT_URLS_JS) or []
        except Exception:
            urls = []

        signed = [u for u in urls if "Signature=" in u]
        for url in signed:
            if "data.json" in url:
                return url
        if signed:
            return signed[0]

        time.sleep(1)

    return None


def parse_collection_url(url):
    """Split a signed collection URL into (base_url, signed_query)."""
    match = COLLECTION_RE.match(url)
    if not match:
        return None, None
    return match.group(1), match.group(2)


def fetch_page_ids(base_url, query, session, refresh=None):
    """Fetch data.json and return (page_ids, title, query).

    Only a rejected signature (403) triggers a refresh — network errors are
    already retried by ``get_with_retry``. The query is returned because a
    refresh replaces it, and the page downloads need the fresh one.
    """
    url = f"{base_url}/data.json?{query}"
    resp = get_with_retry(session, url, timeout=30, label="data.json: ")

    if resp.status_code == 403 and refresh:
        print("  data.json 403 - imza suresi dolmus, yenileniyor...")
        new_query = refresh()
        if new_query:
            query = new_query
            resp = get_with_retry(session, f"{base_url}/data.json?{query}",
                                  timeout=30, label="data.json: ")

    resp.raise_for_status()
    data = resp.json()

    pages = data.get("pages") or {}
    page_ids = pages.get("order") or []
    title = (data.get("properties") or {}).get("title") or ""
    return page_ids, title, query


def download_all_pages(base_url, query, page_ids, output_dir, session, refresh=None):
    """Download every page image at original resolution.

    ``refresh`` is an optional callable returning a fresh signed query string,
    used when CloudFront rejects an expired signature.
    """
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n  Indirme basliyor -> {output_dir}\n")
    total = len(page_ids)
    width = max(2, len(str(total)))
    downloaded = 0
    failed = []

    for index, page_id in enumerate(page_ids, start=1):
        label = f"Sayfa {index}: "
        try:
            resp = get_with_retry(
                session, f"{base_url}/covers/{page_id}/original?{query}", label=label
            )

            # Expired signature: pull a fresh one from the live browser session.
            if resp.status_code == 403 and refresh:
                print(f"  [..]  Sayfa {index:3d}: imza suresi doldu, yenileniyor...")
                new_query = refresh()
                if new_query:
                    query = new_query
                    resp = get_with_retry(
                        session, f"{base_url}/covers/{page_id}/original?{query}",
                        label=label
                    )
        except requests.RequestException as exc:
            print(f"  [XX]  Sayfa {index:3d}: {short_error(exc)}")
            failed.append(index)
            continue

        if resp.status_code == 200 and len(resp.content) > 1000:
            ct = resp.headers.get("Content-Type", "")
            ext = ".png" if "png" in ct else ".jpg"
            filepath = os.path.join(output_dir, f"page_{index:0{width}d}{ext}")

            with open(filepath, "wb") as f:
                f.write(resp.content)

            downloaded += 1
            print(f"  [OK]  Sayfa {index:3d}/{total} indirildi "
                  f"({len(resp.content) // 1024} KB)")
        else:
            print(f"  [XX]  Sayfa {index:3d}: HTTP {resp.status_code}")
            failed.append(index)

    if failed:
        print(f"\n  UYARI: {len(failed)} sayfa indirilemedi: "
              f"{', '.join(str(n) for n in failed)}")

    return downloaded, query


def download_legacy_numbered_pages(base_url, output_dir, session, max_pages=200):
    """Fallback for older publications whose image URLs contain /page_N/."""
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n  Eski format (page_N) tespit edildi -> {output_dir}\n")
    downloaded = 0

    for page_num in range(1, max_pages + 1):
        page_url = re.sub(r'/page_\d+/', f'/page_{page_num}/', base_url, count=1)

        try:
            resp = get_with_retry(session, page_url, timeout=30,
                                  label=f"Sayfa {page_num}: ")

            if resp.status_code == 200 and len(resp.content) > 1000:
                ct = resp.headers.get("Content-Type", "")
                ext = ".png" if "png" in ct else ".jpg"
                filepath = os.path.join(output_dir, f"page_{page_num:02d}{ext}")

                with open(filepath, "wb") as f:
                    f.write(resp.content)

                downloaded += 1
                print(f"  [OK]  Sayfa {page_num:3d} indirildi "
                      f"({len(resp.content) // 1024} KB)")

            elif resp.status_code == 403:
                print(f"  [--]  Sayfa {page_num}: 403 - sayfa mevcut degil")
                next_url = re.sub(r'/page_\d+/', f'/page_{page_num + 1}/',
                                  base_url, count=1)
                if get_with_retry(session, next_url, timeout=10).status_code == 403:
                    print(f"  [--]  Sayfa {page_num + 1} de 403 - son sayfa bulundu")
                    break
            else:
                print(f"  [XX]  Sayfa {page_num}: HTTP {resp.status_code}")
                break

        except requests.RequestException as exc:
            print(f"  [XX]  Sayfa {page_num}: {short_error(exc)}")
            break

    return downloaded


def main():
    url = get_flipsnack_url()
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "flipsnack_pages")
    session = make_session()

    print("=" * 55)
    print("  Flipsnack Page Downloader")
    print("=" * 55)
    print(f"\n  URL: {url}")

    print("\n  Chrome baslatiliyor...")
    driver = create_driver()

    try:
        print("  Flipsnack sayfasi aciliyor...")
        driver.get(url)
        time.sleep(6)

        dismiss_cookie_consent(driver)

        print("  Player iframe araniyor...")
        if not switch_to_player_iframe(driver):
            print("  HATA: iframe bulunamadi!")
            return

        print("  Imzali koleksiyon URL'si araniyor...")
        signed_url = extract_signed_collection_url(driver)

        if not signed_url:
            print("  HATA: Imzali URL bulunamadi! (yayin gizli veya sifreli olabilir)")
            return

        print(f"  Imzali URL bulundu: {signed_url[:80]}...")

        # Legacy publications: page number lives in the URL path.
        if re.search(r'/page_\d+/', signed_url):
            downloaded = download_legacy_numbered_pages(signed_url, output_dir, session)
            print(f"\n{'=' * 55}")
            print(f"  Tamamlandi! {downloaded} sayfa indirildi")
            print(f"  Klasor: {os.path.abspath(output_dir)}")
            print(f"{'=' * 55}")
            return

        base_url, query = parse_collection_url(signed_url)
        if not base_url:
            print("  HATA: Koleksiyon URL'si cozumlenemedi!")
            print(f"  URL: {signed_url[:200]}")
            return

        def refresh_query():
            """Re-read a fresh signature from the still-open browser session."""
            driver.switch_to.default_content()
            driver.get(url)
            time.sleep(6)
            if not switch_to_player_iframe(driver):
                return None
            fresh = extract_signed_collection_url(driver)
            if not fresh:
                return None
            return parse_collection_url(fresh)[1]

        print("  Sayfa listesi (data.json) aliniyor...")
        try:
            page_ids, title, query = fetch_page_ids(
                base_url, query, session, refresh=refresh_query
            )
        except requests.RequestException as exc:
            print(f"  HATA: Sayfa listesi alinamadi - {short_error(exc)}")
            print("  Internet baglantinizi kontrol edip tekrar deneyin.")
            return
        except ValueError:
            print("  HATA: data.json cozumlenemedi (beklenmeyen icerik)")
            return

        if not page_ids:
            print("  HATA: data.json icinde sayfa bulunamadi!")
            return

        if title:
            print(f"  Yayin: {ascii_safe(title)}")
        print(f"  Toplam {len(page_ids)} sayfa bulundu")

        downloaded, _ = download_all_pages(
            base_url, query, page_ids, output_dir, session, refresh=refresh_query
        )

        print(f"\n{'=' * 55}")
        print(f"  Tamamlandi! {downloaded}/{len(page_ids)} sayfa indirildi")
        print(f"  Klasor: {os.path.abspath(output_dir)}")
        print(f"{'=' * 55}")

    finally:
        driver.quit()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  Iptal edildi.")
        sys.exit(130)
    except Exception as exc:
        print(f"\n  HATA: {type(exc).__name__} - {short_error(exc)}")
        sys.exit(1)
