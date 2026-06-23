# WeChat SPH Video Downloader

Download WeChat Video Account (视频号) videos from SPH share links.

## Features

- Unified download logic for both Telegram and Weixin clients
- Supports video and image-text (carousel) content types
- Saves MP4 + JSON metadata (author, description, likes, forwards, etc.)
- Fallback to sph API when Playwright network interception misses URLs
- Playwright browser download as last resort

## Quick Start

### 1. Install dependencies

```bash
pip install playwright
playwright install chromium
pip install yt-dlp
```

### 2. Download a single video

```bash
# Via wrapper (same interface as before)
python wechat_download3.py AP2nmgMqcb

# Or with full URL
python wechat_download3.py https://weixin.qq.com/sph/AP2nmgMqcb

# Multiple at once
python wechat_download3.py AP2nmgMqcb AwEum95Fq6 Aq7JJ3GATK
```

### 3. Batch download from links file

```bash
# Edit wechat_sph_links.txt with one link per line
python auto_download_wechat_sph.py
```

## File Structure

```
wechat_unified_download.py   # Core download logic
wechat_download3.py          # Wrapper (for Weixin client)
wechat_browser_download.py   # Wrapper (for Telegram)
auto_download_wechat_sph.py  # Batch download wrapper
wechat_sph_links.txt         # Link list for batch mode
```

## Output

Videos saved to `E:\Hermes\Vids\YYYYMMDD\` with companion `.json` metadata files.

## Requirements

- Python 3.11+
- Playwright (chromium)
- yt-dlp

## Notes

- Videos are preview quality (~300-400KB, 13s) from the public API
- Full-quality videos require WeChat session cookies
- Works with both short IDs (e.g. `AP2nmgMqcb`) and full URLs
