"""
Flipsnack Page Downloader
~~~~~~~~~~~~~~~~~~~~~~~~~
Downloads all pages from a Flipsnack publication as high-quality images.

How it works:
  1. Opens the Flipsnack full-view page with Selenium
  2. Switches into the player iframe
  3. Extracts the signed CloudFront image URL from the DOM
  4. Iterates through all pages by modifying the page number in the URL
  5. Downloads each page image until no more pages are found

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
    return webdriver.Chrome(options=options)


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
    iframes = driver.find_elements(By.TAG_NAME, "iframe")

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


def extract_signed_image_url(driver):
    """Extract the signed CloudFront image URL from the page DOM."""
    img = WebDriverWait(driver, 20).until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, "img[class*='PageBackground__PageImg']")
        )
    )
    return img.get_attribute("src")


def download_all_pages(base_url, output_dir, max_pages=200):
    """Download all pages using the signed base URL."""
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n  Indirme basliyor -> {output_dir}\n")
    downloaded = 0
    session = requests.Session()
    session.headers.update({
        "Referer": "https://player.flipsnack.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
    })

    for page_num in range(1, max_pages + 1):
        page_url = re.sub(r'/page_\d+/', f'/page_{page_num}/', base_url, count=1)

        try:
            resp = session.get(page_url, timeout=30)

            if resp.status_code == 200 and len(resp.content) > 1000:
                ct = resp.headers.get("Content-Type", "")
                ext = ".png" if "png" in ct else ".jpg"
                filepath = os.path.join(output_dir, f"page_{page_num:02d}{ext}")

                with open(filepath, "wb") as f:
                    f.write(resp.content)

                size_kb = len(resp.content) // 1024
                downloaded += 1
                print(f"  [OK]  Sayfa {page_num:3d} indirildi ({size_kb} KB)")

            elif resp.status_code == 403:
                print(f"  [--]  Sayfa {page_num}: 403 - sayfa mevcut degil")
                # Confirm end: check next page too
                next_url = re.sub(r'/page_\d+/', f'/page_{page_num + 1}/', base_url, count=1)
                r2 = session.get(next_url, timeout=10)
                if r2.status_code == 403:
                    print(f"  [--]  Sayfa {page_num + 1} de 403 - son sayfa bulundu")
                    break
            else:
                print(f"  [XX]  Sayfa {page_num}: HTTP {resp.status_code}")
                break

        except Exception as e:
            print(f"  [XX]  Sayfa {page_num}: Hata - {e}")
            break

    return downloaded


def main():
    url = get_flipsnack_url()
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "flipsnack_pages")

    print("=" * 55)
    print("  Flipsnack Page Downloader")
    print("=" * 55)
    print(f"\n  URL: {url}")

    print("\n  Chrome baslatiliyor...")
    driver = create_driver()

    try:
        # Load the page
        print("  Flipsnack sayfasi aciliyor...")
        driver.get(url)
        time.sleep(6)

        # Dismiss cookies
        dismiss_cookie_consent(driver)

        # Switch to player iframe
        print("  Player iframe araniyor...")
        if not switch_to_player_iframe(driver):
            print("  HATA: iframe bulunamadi!")
            return

        # Extract signed image URL
        time.sleep(3)
        print("  Sayfa gorseli araniyor...")
        signed_url = extract_signed_image_url(driver)

        if not signed_url:
            print("  HATA: Gorsel URL'si bos!")
            return

        print(f"  Imzali URL bulundu: {signed_url[:80]}...")

        # Validate URL pattern
        if not re.search(r'/page_\d+/', signed_url):
            print("  HATA: URL icinde page_N patterni bulunamadi!")
            return

        # Download all pages
        downloaded = download_all_pages(signed_url, output_dir)

        print(f"\n{'=' * 55}")
        print(f"  Tamamlandi! {downloaded} sayfa indirildi")
        print(f"  Klasor: {os.path.abspath(output_dir)}")
        print(f"{'=' * 55}")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
