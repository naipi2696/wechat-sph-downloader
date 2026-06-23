#!/usr/bin/env python3
"""Download WeChat SPH videos - unified script for both Telegram and Weixin clients."""
import asyncio, json, os, re, sys, hashlib, datetime, urllib.request, ssl, warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", category=ResourceWarning)
from pathlib import Path
from playwright.async_api import async_playwright

OUTPUT_DIR = Path(r"E:\Hermes\Vids")
DATE_STR = datetime.date.today().strftime("%Y%m%d")
OUT = OUTPUT_DIR / DATE_STR
OUT.mkdir(parents=True, exist_ok=True)


def sanitize_filename(name, max_len=80):
    name = re.sub(r'[\\/:*?"<>|\r\n]', '_', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name[:max_len] or "video"


def clean_sph_url(url):
    """Clean WeChat SPH URL to extract just the sph_id."""
    m = re.search(r'/sph/([A-Za-z0-9]+)', url)
    if m:
        return m.group(1)
    return None


async def download_video_from_url(video_url, fpath, sph_id):
    """Download video from a todowload URL, trying multiple methods."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        'Referer': 'https://channels.weixin.qq.com/finder-preview/pages/sph?id=' + sph_id,
        'Origin': 'https://channels.weixin.qq.com',
    }

    # Method 1: Direct HTTP download
    try:
        req = urllib.request.Request(video_url, headers=headers)
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
        if len(data) > 1000:
            with open(fpath, 'wb') as f:
                f.write(data)
            print(f"  Method 1 (HTTP) success: {len(data)/1024:.0f} KB")
            return True
    except Exception as e:
        print(f"  Method 1 (HTTP) failed: {e}")

    return False


async def capture_page_data(page, sph_id):
    """Navigate to SPH page and capture all data + video URLs from network requests."""
    video_url = None
    cover_url = None
    img_urls = []
    feed_info = None

    async def on_response(response):
        nonlocal video_url, cover_url, feed_info
        url = response.url
        status = response.status

        # Capture video URLs from todowload
        if 'finder.video.qq.com' in url and 'stodownload' in url:
            # Skip cover images (scene=2), keep only video (scene=1 or no scene)
            if 'scene=2' not in url and 'picformat' not in url:
                video_url = url
            elif 'scene=2' in url or 'picformat' in url:
                cover_url = url

        # Capture image URLs for image-text content
        if 'finder.video.qq.com' in url and ('picformat' in url or 'img' in url.lower()):
            img_urls.append(url)

        # Capture API response for feed info
        if 'get_feed_info' in url:
            try:
                text = await response.text()
                feed_info = json.loads(text)
            except:
                pass

    page.on('response', on_response)

    try:
        await page.goto(f'https://weixin.qq.com/sph/{sph_id}', wait_until='domcontentloaded', timeout=30000)
        await asyncio.sleep(5)
    except Exception as e:
        print(f"  Nav error: {e}")

    # Also try to extract data from page JS
    try:
        page_data = await page.evaluate('''() => {
            const result = { author: '', desc: '', likes: 0, comments: 0, forwards: 0, favorites: 0 };
            
            // Try to find author and stats from the page
            const allText = document.body.innerText || '';
            const lines = allText.split(/\\n|\\r/).map(l => l.trim()).filter(l => l);
            
            // Find numbers (stats)
            const nums = [];
            for (const line of lines) {
                if (/^\\d+$/.test(line) && line.length <= 5) {
                    nums.push(parseInt(line));
                }
            }
            if (nums.length >= 1) result.likes = nums[0];
            if (nums.length >= 2) result.comments = nums[1];
            if (nums.length >= 3) result.forwards = nums[2];
            if (nums.length >= 4) result.favorites = nums[3];
            
            // Last text line before first number is likely author
            for (let i = lines.length - 1; i >= 0; i--) {
                if (/^\\d+$/.test(lines[i])) {
                    for (let j = i - 1; j >= Math.max(0, i - 5); j--) {
                        if (lines[j].length > 0 && lines[j].length < 50 && !/^\\d+$/.test(lines[j])) {
                            result.author = lines[j];
                            break;
                        }
                    }
                    break;
                }
            }
            
            // Description: lines with hashtags or longer text
            for (const line of lines) {
                if (line.includes('#') || (line.length > 20 && line.length < 200)) {
                    result.desc = line;
                    break;
                }
            }
            
            return result;
        }''')
    except:
        page_data = {}

    return {
        'video_url': video_url,
        'cover_url': cover_url,
        'img_urls': img_urls,
        'feed_info': feed_info,
        'page_data': page_data,
    }


async def resolve_video_urls(page, sph_id):
    """Try to find video URLs from page source code when network interception misses them."""
    page_source = await page.content()
    video_urls = []
    
    # Regex to find todowload URLs in page HTML/JS
    matches = re.findall(r'(https?://finder\.video\.qq\.com/251/\d+/stodownload\?[^\s"\'<>]+)', page_source)
    for m in matches:
        if 'stodownload' in m and 'scene=2' not in m and 'picformat' not in m:
            video_urls.append(m)
    
    return video_urls


async def download_one(sph_id):
    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=True)
    ctx = await browser.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        locale='zh-CN'
    )
    page = await ctx.new_page()

    # Step 1: Navigate and capture network data
    print(f"  Navigating to SPH page...")
    captured = await capture_page_data(page, sph_id)
    
    # Step 2: If no video URL from network, try page source
    video_url = captured['video_url']
    if not video_url:
        print(f"  No video URL from network, checking page source...")
        source_urls = await resolve_video_urls(page, sph_id)
        if source_urls:
            video_url = source_urls[0]
            print(f"  Found video in page source: {video_url[:80]}...")

    # Step 3: Also try sph API as fallback
    if not video_url:
        print(f"  Trying sph API as fallback...")
        try:
            API = "https://sph.litao.workers.dev/api/fetch_video_profile"
            payload = json.dumps({"url": f"https://weixin.qq.com/sph/{sph_id}"}).encode()
            req = urllib.request.Request(API, data=payload, headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0"
            }, method="POST")
            resp = urllib.request.urlopen(req, timeout=15)
            api_data = json.loads(resp.read())
            feed = api_data.get("data", {}).get("feedInfo", {})
            video_url = feed.get("h265VideoInfo", {}).get("videoUrl", "") or feed.get("h264VideoInfo", {}).get("videoUrl", "") or feed.get("videoUrl", "")
            if video_url:
                print(f"  Got video URL from sph API")
            # Also extract feed info from API
            if not captured['feed_info']:
                captured['feed_info'] = api_data
        except Exception as e:
            print(f"  sph API failed: {e}")

    # Extract metadata
    feed = captured.get('feed_info', {}) or {}
    data_section = feed.get('data', {}) or {}
    feed_info = data_section.get('feedInfo', {}) or {}
    author_info = data_section.get('authorInfo', {}) or {}
    
    author = author_info.get('nickname', captured['page_data'].get('author', 'unknown'))
    desc = feed_info.get('description', captured['page_data'].get('desc', 'video')).strip()
    likes = feed_info.get('likeCountFmt', str(captured['page_data'].get('likes', 0)))
    comments = feed_info.get('commentCountFmt', str(captured['page_data'].get('comments', 0)))
    forwards = feed_info.get('forwardCountFmt', str(captured['page_data'].get('forwards', 0)))
    favorites = feed_info.get('favCountFmt', str(captured['page_data'].get('favorites', 0)))
    media_type = feed_info.get('mediaType', 1)

    # Sanitize
    safe_author = sanitize_filename(author or "unknown")
    raw_desc = (desc or "video").split('#')[0].strip() or "video"
    raw_desc = raw_desc.lstrip('. ').strip()
    safe_desc = sanitize_filename(raw_desc)
    if not safe_desc or safe_desc.startswith('.'):
        safe_desc = f"video_{sph_id[:8]}"

    print(f"  Author: {author}")
    print(f"  Desc:   {raw_desc[:60]}")
    print(f"  Likes: {likes}, Comments: {comments}, Forwards: {forwards}, Favorites: {favorites}")
    print(f"  Video URL: {bool(video_url)}")
    print(f"  Media Type: {media_type}")

    # Handle mediaType=2 (image-text carousel)
    if media_type == 2 and captured.get('img_urls'):
        print(f"  Image-text content, downloading {len(captured['img_urls'])} images...")
        pics_saved = []
        for i, img_url in enumerate(captured['img_urls']):
            img_fname = f"{safe_author}_pic{i+1}.jpg"
            img_path = OUT / img_fname
            try:
                req = urllib.request.Request(img_url, headers={
                    'User-Agent': 'Mozilla/5.0',
                    'Referer': 'https://channels.weixin.qq.com/'
                })
                with urllib.request.urlopen(req, timeout=30) as resp:
                    with open(img_path, 'wb') as f:
                        f.write(resp.read())
                pics_saved.append(str(img_path))
                print(f"    Saved: {img_path}")
            except Exception as e:
                print(f"    Failed: {e}")

        meta = {
            'sph_id': sph_id,
            'author': author,
            'description': desc,
            'likes': int(likes), 'comments': int(comments),
            'forwards': int(forwards), 'favorites': int(favorites),
            'media_type': 2,
            'images': pics_saved,
        }
        meta_path = OUT / f"{safe_author}_images_{sph_id[:12]}.json"
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        await browser.close()
        return {'status': 'images', 'author': author, 'desc': desc, 'pics': pics_saved}

    # Download video
    if video_url:
        fname = f"{safe_desc}_{sph_id[:12]}.mp4"
        fpath = OUT / fname

        if fpath.exists():
            print(f"  Already exists: {fpath}")
            await browser.close()
            return {'status': 'skipped', 'path': str(fpath), 'size': fpath.stat().st_size,
                    'author': author, 'desc': desc}

        print(f"  Downloading video...")
        success = await download_video_from_url(video_url, fpath, sph_id)

        if not success or not fpath.exists():
            print(f"  Video download failed, trying Playwright browser download...")
            try:
                browser2 = await p.chromium.launch(headless=True)
                ctx2 = await browser2.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    locale='zh-CN',
                    viewport={'width': 1280, 'height': 720}
                )
                page2 = await ctx2.new_page()
                async with page2.expect_event('download') as dl_info:
                    await page2.goto(video_url, timeout=120000)
                dl = await dl_info.value
                dl_path = str(fpath)
                await dl.save_as(dl_path)
                success = os.path.exists(dl_path)
                print(f"  Browser download: {'success' if success else 'failed'}")
                await browser2.close()
            except Exception as e:
                print(f"  Browser download also failed: {e}")

        if not success or not fpath.exists():
            await browser.close()
            return {'status': 'download_failed', 'error': 'All download methods failed', 'sph_id': sph_id}

        size = fpath.stat().st_size
        print(f"  Saved: {fpath} ({size / 1024 / 1024:.1f} MB)")

        # Validate MP4
        with open(fpath, 'rb') as f:
            header = f.read(12)
        is_mp4 = header[4:8] == b'ftyp'
        if not is_mp4:
            print(f"  WARNING: Not a valid MP4 (header: {header.hex()[:20]}...)")
            fpath.unlink()
            await browser.close()
            return {'status': 'invalid_file', 'error': 'Not a valid MP4', 'sph_id': sph_id}

        # Save metadata
        meta = {
            'sph_id': sph_id,
            'author': author,
            'description': desc,
            'likes': int(likes),
            'comments': int(comments),
            'forwards': int(forwards),
            'favorites': int(favorites),
            'media_type': media_type,
            'file': fname,
            'size_bytes': size,
            'md5': hashlib.md5(open(fpath, 'rb').read()).hexdigest(),
        }
        meta_path = OUT / f"{safe_desc}_{sph_id[:12]}.json"
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        print(f"  Meta: {meta_path}")

        await browser.close()
        return {'status': 'ok', 'path': str(fpath), 'size': size, 'meta': meta_path,
                'author': author, 'desc': desc}

    # No video, no images - maybe text-only or page failed
    await page.screenshot(path=OUT / f"debug_{sph_id}.png")
    print(f"  Screenshot saved: debug_{sph_id}.png")
    await browser.close()
    return {'status': 'no_media', 'error': 'No video or images found', 'url': sph_id}


async def main():
    sph_ids = sys.argv[1:]
    if not sph_ids:
        for line in sys.stdin:
            line = line.strip()
            if line and ('sph/' in line or re.match(r'^[A-Za-z0-9]+$', line)):
                sph_ids.append(line.split('sph/')[-1].split('?')[0])

    if not sph_ids:
        print("Usage: python wechat_unified_download.py <sph_id_or_url1> [sph_id_or_url2] ...")
        return

    results = []
    for sid in sph_ids:
        print(f"\n{'='*60}")
        print(f"Processing: {sid}")
        try:
            r = await download_one(sid)
            results.append(r)
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
            results.append({'status': 'error', 'error': str(e), 'sph_id': sid})

    print(f"\n{'='*60}")
    print("SUMMARY:")
    for r in results:
        status = r.get('status', '?')
        author = r.get('author', '?')
        if status == 'ok':
            print(f"  OK   | {author} | {r.get('path','')} ({r.get('size',0)/1024/1024:.1f} MB)")
        elif status == 'images':
            print(f"  IMG  | {author} | {len(r.get('pics', []))} images")
        elif status == 'skipped':
            print(f"  SKIP | {author} | already exists")
        else:
            print(f"  FAIL | {author} | {status}: {r.get('error', '')}")


if __name__ == '__main__':
    asyncio.run(main())
