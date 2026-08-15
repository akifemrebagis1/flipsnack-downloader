# Flipsnack Page Downloader

A Python tool that downloads all pages from any [Flipsnack](https://www.flipsnack.com) publication as high-quality images.

## ✨ Features

- 🔓 **Automatic signature extraction** — handles CloudFront signed URLs transparently
- 🔁 **Signature auto-refresh** — CloudFront signatures are short-lived; expired ones are renewed mid-download
- 📄 **Downloads all pages** — reads the real page list from the publication's `data.json`
- 🖼️ **Original quality** — saves images in their original resolution (JPG/PNG)
- 🍪 **Cookie consent handling** — dismisses popups automatically
- 🛡️ **Robust error handling** — per-page retry, failure summary, legacy-format fallback

## 📋 Requirements

- **Python 3.7+**
- **Google Chrome** browser installed
- **ChromeDriver** (matching your Chrome version)

### Python Dependencies

```bash
pip install selenium requests
```

## 🚀 Usage

### Command-line

```bash
python flipsnack_downloader.py <FLIPSNACK_URL>
```

**Example:**

```bash
python flipsnack_downloader.py "https://www.flipsnack.com/XXXXX/my-catalog/full-view.html?p=1"
```

### Interactive Mode

Simply run the script without arguments and paste the URL when prompted:

```bash
python flipsnack_downloader.py
# → Flipsnack full-view URL girin: <paste URL here>
```

## ⚙️ How It Works

```
┌─────────────────────────────────────────────────────────┐
│  1. Launch Chrome via Selenium                          │
│  2. Navigate to the Flipsnack full-view page            │
│  3. Switch into the player iframe                       │
│  4. Read the signed CloudFront collection URL the       │
│     player loaded (signature + policy + key-pair id)    │
│  5. Fetch data.json → the ordered list of page IDs      │
│  6. Download every page at /covers/<id>/original        │
│  7. Refresh the signature if it expires mid-download    │
└─────────────────────────────────────────────────────────┘
```

Flipsnack uses **CloudFront signed URLs** to protect content. The signature, policy, and key-pair parameters are embedded in every request the player makes. This tool extracts a valid signed query string, then reuses it for all pages — the CloudFront policy is a wildcard granting access to everything under the same collection path.

### Why page numbers aren't enough

Page images are **not** numbered sequentially in the URL. Each page has its own random ID:

```
https://<cdn>/<account>/collections/<hash>/covers/sb5-NU4WNmbcGMBi/original?Signature=...
                                            ^^^^^^^^^^^^^^^^^^^^^^ random, per page
```

So the page list cannot be guessed by incrementing a counter — it has to come from the publication's `data.json`, where `pages.order` holds the page IDs in reading order. Older publications that still use `/page_N/` paths are handled by a legacy fallback.

The signed URL is also **short-lived** — its policy carries a `DateLessThan` expiry, and once that passes every request returns `403 AccessDenied`. When that happens mid-download, the tool reloads the player in the still-open browser session to mint a fresh signature and continues.

## 📁 Output

Downloaded images are saved to the `flipsnack_pages/` directory:

```
flipsnack_pages/
├── page_01.jpg
├── page_02.jpg
├── page_03.jpg
├── ...
└── page_XX.jpg
```

## 📝 Example Output

```
=======================================================
  Flipsnack Page Downloader
=======================================================

  URL: https://www.flipsnack.com/XXXXX/my-catalog/full-view.html?p=1

  Chrome baslatiliyor...
  Flipsnack sayfasi aciliyor...
  Player iframe araniyor...
  Player iframe bulundu: https://player.flipsnack.com/?hash=...
  Imzali koleksiyon URL'si araniyor...
  Imzali URL bulundu: https://d3u72tnj701eui.cloudfront.net/...
  Sayfa listesi (data.json) aliniyor...
  Toplam 61 sayfa bulundu

  Indirme basliyor -> flipsnack_pages

  [OK]  Sayfa   1/61 indirildi (854 KB)
  [OK]  Sayfa   2/61 indirildi (393 KB)
  [OK]  Sayfa   3/61 indirildi (381 KB)
  ...
  [OK]  Sayfa  61/61 indirildi (693 KB)

=======================================================
  Tamamlandi! 61/61 sayfa indirildi
  Klasor: C:\...\flipsnack_pages
=======================================================
```

## 🩺 Troubleshooting

| Message | Cause / fix |
|---|---|
| `HATA: Imzali URL bulunamadi!` | The player never loaded a signed request — the publication may be private, password-protected, or the page didn't finish loading. Try again, or check that the URL opens normally in a browser. |
| `HATA: iframe bulunamadi!` | The page didn't render the player. Usually a slow network or a cookie wall — rerun the script. |
| `403` on every page | The CloudFront signature expired. The tool refreshes it automatically; if it still fails, the publication's access policy changed. |
| `Ag hatasi (DNS cozumlenemedi)` | Transient DNS/network failure — Chrome may resolve the CDN from its cache while Python cannot. Each request is retried automatically; if it persists, check your DNS/VPN. |
| `HATA: Sayfa listesi alinamadi` | The CDN stayed unreachable across all retries. A connectivity problem, not a signature one — rerun once the network is back. |
| `HATA: data.json icinde sayfa bulunamadi!` | The publication has no page list (empty or non-flipbook content type). |

## ⚠️ Disclaimer

This tool is intended for **personal use only**. Please respect copyright and the terms of service of Flipsnack. Only download content you have permission to access.

## 📄 License

MIT License
