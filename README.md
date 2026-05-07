# Flipsnack Page Downloader

A Python tool that downloads all pages from any [Flipsnack](https://www.flipsnack.com) publication as high-quality images.

## ✨ Features

- 🔓 **Automatic signature extraction** — handles CloudFront signed URLs transparently
- 📄 **Downloads all pages** — automatically detects the total number of pages
- 🖼️ **Original quality** — saves images in their original resolution (JPG/PNG)
- 🍪 **Cookie consent handling** — dismisses popups automatically
- 🛡️ **Robust error handling** — retries and graceful failure detection

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
│  4. Extract the signed CloudFront URL from the DOM      │
│  5. Replace the page number in the URL (page_1 → page_N)│
│  6. Download all pages sequentially via HTTP             │
│  7. Stop when consecutive 403 errors are detected       │
└─────────────────────────────────────────────────────────┘
```

Flipsnack uses **CloudFront signed URLs** to protect content. The signature, policy, and key-pair parameters are embedded in the image URLs loaded by the player. This tool extracts a valid signed URL from the first page, then reuses the same signature to download all remaining pages — since the CloudFront policy grants access to all resources within the same collection path.

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
  Player iframe bulundu: https://player.flipsnack.com/?hash=...
  Imzali URL bulundu: https://d3u72tnj701eui.cloudfront.net/...

  Indirme basliyor -> flipsnack_pages

  [OK]  Sayfa   1 indirildi (746 KB)
  [OK]  Sayfa   2 indirildi (393 KB)
  [OK]  Sayfa   3 indirildi (381 KB)
  ...
  [--]  Sayfa  64: 403 - sayfa mevcut degil
  [--]  Sayfa  65 de 403 - son sayfa bulundu

=======================================================
  Tamamlandi! 63 sayfa indirildi
  Klasor: C:\...\flipsnack_pages
=======================================================
```

## ⚠️ Disclaimer

This tool is intended for **personal use only**. Please respect copyright and the terms of service of Flipsnack. Only download content you have permission to access.

## 📄 License

MIT License
