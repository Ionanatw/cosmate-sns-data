#!/usr/bin/env python3
"""
Threads 貼文圖片下載器 — 只抓貼文本體的圖片，跳過頭像/UI 雜圖。

用法：
  python3 scripts/download_threads_images.py <threads_post_url>
  python3 scripts/download_threads_images.py <threads_post_url> --headless
  python3 scripts/download_threads_images.py <threads_post_url> --min-size 400

依賴：
  pip install playwright requests pillow
  python3 -m playwright install chromium
"""
import asyncio
import argparse
import hashlib
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from playwright.async_api import async_playwright
import requests
from PIL import Image


def parse_post_url(url: str) -> tuple[str, str]:
    """從 URL 萃取 username 和 post_id，用於資料夾命名。"""
    # https://www.threads.net/@cosmatedaily/post/DW_JoDWkloS
    # https://www.threads.com/@xxx/post/DW_JoDWkloS
    m = re.search(r"threads\.(?:net|com)/@([^/]+)/post/([^/?#]+)", url)
    if not m:
        sys.exit(f"無法解析 URL: {url}")
    return m.group(1), m.group(2)


def normalize_cdn_url(url: str) -> str:
    """Strip query params to deduplicate same image at different sizes."""
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


async def scrape_image_urls(url: str, headless: bool, login: bool = False) -> list[str]:
    """用 Playwright 開啟貼文頁，只從貼文區域抓圖片 URL。"""
    image_urls: dict[str, str] = {}  # normalized_path -> full_url (keep largest)

    # 用固定的 profile 目錄保存登入狀態，不用每次重新登入
    profile_dir = os.path.expanduser("~/.threads-scraper/browser-profile")
    os.makedirs(profile_dir, exist_ok=True)

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            profile_dir,
            headless=headless,
            viewport={"width": 1200, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.pages[0] if context.pages else await context.new_page()

        # 登入流程：開啟 Threads，等待用戶確認已登入
        if login:
            await page.goto("https://www.threads.net", wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            # 偵測是否已登入：找 nav/profile 元素，而非靠 URL
            logged_in = False
            try:
                await page.wait_for_selector(
                    'a[href*="/profile"], [aria-label*="Profile"], nav svg',
                    timeout=5000
                )
                logged_in = True
            except Exception:
                pass

            if not logged_in:
                print("🔐 請在瀏覽器中登入 Threads（登入完成後腳本會自動繼續）...")
                try:
                    # 等待最多 3 分鐘讓用戶完成登入
                    await page.wait_for_selector(
                        'a[href*="/profile"], [aria-label*="Profile"], nav svg',
                        timeout=180000
                    )
                    print("✅ 登入成功！Session 已保存，下次直接用")
                except Exception:
                    print("⚠️  登入等待逾時，嘗試繼續...")
            else:
                print("✅ 使用已保存的登入 Session")
            await page.wait_for_timeout(1000)

        print("🚀 開啟 Threads 貼文頁面...")
        await page.goto(url, wait_until="networkidle")

        # 等貼文內容出現
        try:
            await page.wait_for_selector("article, [data-pressable-container]", timeout=15000)
            print("✅ 貼文區塊已載入")
        except Exception:
            print("⚠️  找不到貼文區塊，等待 15 秒讓你手動操作...")
            await page.wait_for_timeout(15000)

        # 邊滾邊收集圖片（Threads 會回收已滾過的 DOM 元素）
        async def collect_visible_images():
            """收集當前可見的 CDN 圖片 URL。"""
            selectors = ["article img", "[data-pressable-container] img", "main img"]
            for sel in selectors:
                try:
                    elements = await page.query_selector_all(sel)
                except Exception:
                    return  # page navigated away (e.g. redirected to login)
                for el in elements:
                    try:
                        src = await el.get_attribute("src")
                    except Exception:
                        continue
                    if not src:
                        continue
                    if not ("scontent" in src or "cdninstagram" in src or "fbcdn" in src):
                        continue
                    norm = normalize_cdn_url(src)
                    if norm not in image_urls:
                        image_urls[norm] = src

        # 先收集初始可見圖片
        await collect_visible_images()

        print("📜 開始滾動載入所有回覆...")
        prev_img_count = 0
        no_new_img_count = 0
        scroll_round = 0
        while no_new_img_count < 15:
            scroll_round += 1

            # 只點「展開更多回覆」的連結，避開 action button（回覆、分享、⋯）
            # Threads 的展開連結通常包含數字 + "replies" / "則回覆"
            try:
                expand_links = await page.query_selector_all(
                    '[role="link"]:has-text("more replies"), '
                    '[role="link"]:has-text("更多回覆"), '
                    '[role="link"]:has-text("則回覆")'
                )
                for link in expand_links[:3]:
                    try:
                        text = await link.text_content()
                        # 再次確認文字包含數字（如 "View 5 more replies"），排除誤中
                        if text and re.search(r"\d", text) and await link.is_visible():
                            await link.click()
                            await page.wait_for_timeout(1200)
                    except Exception:
                        pass
            except Exception:
                pass

            # 漸進式滾動（用 JS 滾，不搶 focus）
            await page.evaluate("window.scrollBy(0, window.innerHeight * 1.5)")
            await page.wait_for_timeout(2500)

            # 收集圖片
            await collect_visible_images()
            current_count = len(image_urls)
            if current_count == prev_img_count:
                no_new_img_count += 1
                # 停滯時多等一下，Threads 可能在載入下一批
                if no_new_img_count % 3 == 0:
                    await page.wait_for_timeout(3000)
            else:
                no_new_img_count = 0
                prev_img_count = current_count

            if scroll_round % 10 == 0:
                print(f"  📜 已滾動 {scroll_round} 次，累計收集 {current_count} 張圖片...")
        print(f"  📜 滾動完成，共 {scroll_round} 次，累計 {len(image_urls)} 張圖片")

        await context.close()

    return list(image_urls.values())


def download_images(
    urls: list[str], download_dir: Path, prefix: str, min_size: int
) -> int:
    """下載圖片，用內容 hash 去重，過濾小圖。"""
    download_dir.mkdir(parents=True, exist_ok=True)
    seen_hashes: set[str] = set()
    saved = 0

    for idx, url in enumerate(urls, 1):
        try:
            resp = requests.get(url, timeout=20, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
            })
            resp.raise_for_status()
        except Exception as e:
            print(f"  ❌ 下載失敗 ({idx}): {e}")
            continue

        # 內容 hash 去重
        content_hash = hashlib.md5(resp.content).hexdigest()
        if content_hash in seen_hashes:
            print(f"  ⏭️  跳過重複圖片 ({idx})")
            continue
        seen_hashes.add(content_hash)

        # 驗證圖片 + 尺寸過濾
        try:
            img = Image.open(__import__("io").BytesIO(resp.content))
            w, h = img.size
        except Exception as e:
            print(f"  ❌ 無效圖片 ({idx}): {e}")
            continue

        if w < min_size and h < min_size:
            print(f"  ⏭️  跳過小圖 ({idx}): {w}x{h}")
            continue

        # 決定副檔名
        fmt = img.format or "JPEG"
        ext = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}.get(fmt, ".jpg")
        filename = download_dir / f"{prefix}_{saved + 1:02d}{ext}"

        with open(filename, "wb") as f:
            f.write(resp.content)
        saved += 1
        print(f"  ✅ {filename.name}  ({w}x{h})")

    return saved


def main():
    parser = argparse.ArgumentParser(description="下載 Threads 貼文圖片")
    parser.add_argument("url", help="Threads 貼文 URL")
    parser.add_argument("--headless", action="store_true", help="無瀏覽器視窗模式")
    parser.add_argument("--login", action="store_true", help="先開啟登入頁面（需要看完整回覆時使用）")
    parser.add_argument("--min-size", type=int, default=200, help="最小邊長（過濾頭像等小圖）")
    args = parser.parse_args()

    username, post_id = parse_post_url(args.url)
    download_dir = Path(f"{username}_{post_id}")
    prefix = username

    print(f"📌 目標: @{username} / {post_id}")
    print(f"📁 儲存到: {download_dir}/\n")

    urls = asyncio.run(scrape_image_urls(args.url, args.headless, args.login))
    print(f"\n📊 找到 {len(urls)} 張候選圖片，開始下載與過濾...\n")

    if not urls:
        print("⚠️  沒有找到圖片。可能需要登入或頁面結構有變。")
        sys.exit(1)

    saved = download_images(urls, download_dir, prefix, args.min_size)
    print(f"\n🎉 完成！保存 {saved} 張貼文圖片 → {download_dir}/")

    if saved > 0 and sys.platform == "darwin":
        os.system(f"open '{download_dir}'")


if __name__ == "__main__":
    main()
