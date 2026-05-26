#!/usr/bin/env python3
"""
Threads 貼文爬蟲 — Threads Analytics Skill 附屬腳本
用法:
  python3 scrape_threads.py \
    --targets "hashtag:交友,hashtag:徵友,keyword:交友軟體" \
    --output /path/to/posts_raw.json \
    --scroll 10

依賴: playwright, browser-cookie3
  pip3 install playwright browser-cookie3 --break-system-packages
  python3 -m playwright install chromium

注意：此檔是 vendor copy，源自
  cosmate-ai-nexus/skills/threads-analytics/scripts/scrape_threads.py
為了讓 GHA CI self-contained（不用 clone 外部 repo）所以複製進此 repo。
若 Threads DOM selector 失效需更新，請同時改 upstream + 重新 vendor。
"""

import argparse, json, re, time, os, sys
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

POST_CONTAINER = 'div.xrvj5dj.xd0jker'  # 已驗證 2026-04，Threads DOM


def get_cookies_from_chrome():
    """從本機 Chrome 即時讀 cookies（需本機登入 Threads）"""
    import browser_cookie3
    cookies = []
    for domain in [".threads.com", "threads.com"]:
        try:
            for c in browser_cookie3.chrome(domain_name=domain):
                cookies.append({
                    "name": c.name, "value": c.value,
                    "domain": c.domain, "path": c.path,
                    "secure": bool(c.secure), "httpOnly": False, "sameSite": "Lax"
                })
        except Exception as e:
            print(f"  ⚠️  cookie 提取部分失敗 ({domain}): {e}")
    print(f"🍪 Chrome 本機讀 {len(cookies)} 個 Threads cookie")
    return cookies


def get_cookies_from_file(path):
    """從 JSON 檔讀 cookies（跨機器用）"""
    p = Path(path).expanduser()
    if not p.exists():
        print(f"❌ cookies file 不存在: {p}")
        return []
    cookies = json.loads(p.read_text())
    print(f"🍪 從 {p} 載入 {len(cookies)} 個 cookie")
    return cookies


def get_cookies(cookies_file=None):
    """優先順序：env var COSMATE_THREADS_COOKIES_FILE > --cookies-file > live Chrome"""
    if cookies_file:
        return get_cookies_from_file(cookies_file)
    env_file = os.environ.get("COSMATE_THREADS_COOKIES_FILE")
    if env_file:
        return get_cookies_from_file(env_file)
    return get_cookies_from_chrome()


def dump_cookies(output_path):
    """從目前本機 Chrome 匯出 cookies 到 JSON（之後任何機器都能用）"""
    cookies = get_cookies_from_chrome()
    if not cookies:
        print("❌ 無法從 Chrome 匯出；請確認已登入 Threads 且 Chrome 未在無痕模式")
        sys.exit(1)
    out = Path(output_path).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(cookies, ensure_ascii=False, indent=2))
    os.chmod(out, 0o600)
    print(f"✅ 已匯出 {len(cookies)} 個 cookie 到 {out}")
    print(f"   權限已設 600（owner-only 讀寫）")
    print(f"   提醒：cookies 含 session，**不要** commit 或 share")


def parse_count(text):
    if not text: return 0
    text = text.strip().replace(",", "").replace(" ", "").replace(" ", "")
    m = re.match(r"([\d.]+)([萬kKmM]?)", text)
    if not m: return 0
    num = float(m.group(1))
    u = m.group(2).lower()
    if u == "萬": num *= 10000
    elif u == "k": num *= 1000
    elif u == "m": num *= 1000000
    return int(num)


def diagnose_container(page):
    """當 POST_CONTAINER 找不到時，自動偵測新的 container selector"""
    result = page.evaluate("""() => {
        const links = document.querySelectorAll('a[href*="/post/"]');
        const found = [];
        for (let l of links) {
            let el = l;
            for (let i = 0; i < 12; i++) {
                el = el.parentElement;
                if (!el) break;
                const nums = [...el.querySelectorAll('span')]
                    .filter(s => /^[0-9,]+$/.test(s.innerText.trim()) && !s.children.length);
                if (nums.length >= 2) {
                    found.push(el.className.split(' ').slice(0, 3).join('.'));
                    break;
                }
            }
        }
        const counts = {};
        for (let f of found) { counts[f] = (counts[f] || 0) + 1; }
        return counts;
    }""")
    if result:
        best = max(result, key=result.get)
        print(f"  🔍 診斷建議 selector: div.{best}（出現 {result[best]} 次）")
        return f"div.{best}"
    return None


def extract_posts(page, label, container_sel):
    posts = []
    seen  = set()

    containers = page.query_selector_all(container_sel)
    if not containers:
        new_sel = diagnose_container(page)
        if new_sel:
            containers = page.query_selector_all(new_sel)
        if not containers:
            print(f"  ⚠️  {label}: 找不到貼文容器，跳過")
            return posts

    print(f"  📄 {label}: {len(containers)} 個容器")

    for cont in containers:
        try:
            # 帳號
            account = ""
            for ael in cont.query_selector_all('a[href*="/@"]'):
                href = ael.get_attribute("href") or ""
                m = re.search(r'/@([^/?#]+)', href)
                if m:
                    account = "@" + m.group(1)
                    break
            if not account:
                continue

            # 貼文連結 + shortcode（從 a[href*="/post/"] 取）
            post_url = ""
            post_code = ""
            for ael in cont.query_selector_all('a[href*="/post/"]'):
                href = ael.get_attribute("href") or ""
                m = re.search(r'/post/([A-Za-z0-9_-]+)', href)
                if m:
                    post_code = m.group(1)
                    # 組完整 URL
                    if href.startswith("http"):
                        post_url = href.split("?")[0]
                    else:
                        post_url = f"https://www.threads.com{href.split('?')[0]}"
                    break

            # 時間戳（從 <time datetime="..."> 取）
            post_ts = ""
            try:
                time_el = cont.query_selector('time')
                if time_el:
                    post_ts = time_el.get_attribute("datetime") or ""
            except Exception:
                pass

            # 內文（取最長 span[dir=auto]，跳過與帳號相同的）
            content = ""
            for sel in ['span[dir="auto"]', 'div[dir="auto"]']:
                for el in cont.query_selector_all(sel):
                    try:
                        txt = el.inner_text().strip()
                        if txt.lstrip("@").lower() != account.lstrip("@").lower() and len(txt) > len(content):
                            content = txt
                    except Exception:
                        continue
            content = content[:300]

            key = (account, content[:60])
            if key in seen:
                continue
            seen.add(key)

            # 互動數：純數字 span，取最後 4 個 = [likes, comments, reposts, shares]
            num_spans = []
            for span in cont.query_selector_all('span'):
                try:
                    txt = span.inner_text().strip().replace(",", "")
                    if re.match(r'^\d+$', txt) and not span.query_selector('*'):
                        num_spans.append(int(txt))
                except Exception:
                    continue

            if   len(num_spans) >= 4: likes, comments, reposts, shares = num_spans[-4], num_spans[-3], num_spans[-2], num_spans[-1]
            elif len(num_spans) == 3: likes, comments, reposts, shares = num_spans[0], num_spans[1], num_spans[2], 0
            elif len(num_spans) == 2: likes, comments, reposts, shares = num_spans[0], num_spans[1], 0, 0
            elif len(num_spans) == 1: likes, comments, reposts, shares = num_spans[0], 0, 0, 0
            else:                     likes = comments = reposts = shares = 0

            posts.append({
                "account": account,
                "url": post_url,
                "code": post_code,
                "timestamp": post_ts,
                "content_summary": content,
                "likes": likes,
                "comments": comments,
                "reposts": reposts,
                "shares": shares,
                "total_interactions": likes + comments + reposts + shares,
                "source": label,
                "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "type": ""
            })
        except Exception:
            continue

    return posts


def main():
    parser = argparse.ArgumentParser(description="Threads 貼文爬蟲")
    parser.add_argument("--targets",
        help='搜尋目標，格式: "hashtag:交友,keyword:交友軟體"')
    parser.add_argument("--output", help="輸出 JSON 路徑")
    parser.add_argument("--scroll", type=int, default=10, help="每個目標捲動次數（預設10）")
    parser.add_argument("--screenshot-dir", default="", help="截圖存放目錄（可選）")
    parser.add_argument("--cookies-file",
        help="從 JSON 檔讀 cookies（跨機器用，取代本機 Chrome 讀取）")
    parser.add_argument("--dump-cookies",
        metavar="PATH",
        help="一次性：從本機 Chrome 匯出 Threads cookies 到 PATH 後結束")
    args = parser.parse_args()

    # dump-cookies 子指令：匯出後結束
    if args.dump_cookies:
        dump_cookies(args.dump_cookies)
        return

    # 一般爬取需要 --targets + --output
    if not args.targets or not args.output:
        parser.error("需同時指定 --targets 與 --output（或用 --dump-cookies）")

    # 解析目標
    targets = []
    for item in args.targets.split(","):
        item = item.strip()
        if ":" not in item:
            continue
        ttype, value = item.split(":", 1)
        label = f"{ttype[:3]}_{value}"
        targets.append((ttype.strip(), value.strip(), label))

    if args.screenshot_dir:
        os.makedirs(args.screenshot_dir, exist_ok=True)

    cookies = get_cookies(cookies_file=args.cookies_file)
    if not cookies:
        print("❌ 無法取得 Cookie；請確認 Chrome 已登入 Threads，或提供 --cookies-file")
        return

    all_posts = []
    progress  = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="zh-TW",
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        ctx.add_cookies(cookies)
        page = ctx.new_page()

        # 驗證登入
        print("📌 驗證 Threads 登入狀態...")
        try:
            page.goto("https://www.threads.com", wait_until="networkidle", timeout=20000)
        except PWTimeout:
            page.goto("https://www.threads.com", wait_until="domcontentloaded", timeout=15000)
        time.sleep(3)

        if "login" in page.url.lower():
            print("❌ Cookie 無效，仍在登入頁。請確認 Chrome 已登入 Threads（非無痕模式）。")
            browser.close()
            return
        print(f"✅ 登入確認\n")

        container_sel = POST_CONTAINER  # 可能在診斷後更新

        for ttype, value, label in targets:
            print(f"\n{'='*50}")
            print(f"🔍 [{label}]")

            url = (f"https://www.threads.com/tag/{value}"
                   if ttype == "hashtag"
                   else f"https://www.threads.com/search?q={value}")

            try:
                page.goto(url, wait_until="networkidle", timeout=20000)
            except PWTimeout:
                page.goto(url, wait_until="domcontentloaded", timeout=15000)
            time.sleep(4)

            if args.screenshot_dir:
                page.screenshot(path=f"{args.screenshot_dir}/{label}_init.png")

            for i in range(args.scroll):
                try:
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                except Exception:
                    page.keyboard.press("End")
                time.sleep(3.0)
                if (i + 1) % 4 == 0:
                    print(f"  ↕  {i+1}/{args.scroll}")

            posts = extract_posts(page, label, container_sel)
            print(f"  ✅ {len(posts)} 筆")
            all_posts.extend(posts)
            progress[label] = len(posts)
            time.sleep(2)

        browser.close()

    # 去重
    seen, deduped = set(), []
    for post in all_posts:
        key = (post["account"], post["content_summary"][:60])
        if key not in seen:
            seen.add(key)
            deduped.append(post)

    print(f"\n{'='*50}")
    print(f"📊 原始 {len(all_posts)} 筆 → 去重後 {len(deduped)} 筆")

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump({
            "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M GMT+8"),
            "total_posts": len(deduped),
            "source_counts": progress,
            "posts": deduped
        }, f, ensure_ascii=False, indent=2)

    print(f"💾 {args.output}")


if __name__ == "__main__":
    main()
