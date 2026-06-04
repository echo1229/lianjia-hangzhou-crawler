"""
杭州链家租房数据爬虫（全量慢爬版 + 云码自动验证码）
====================================================
功能：分批慢爬杭州链家全部租房数据
通过 CDP 连接用户已登录的 Edge 浏览器
使用云码平台自动破解 GeeTest v4 点击式验证码
作者：同学A
日期：2026-05-28
"""

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
import requests
import base64
import time
import random
import os
import json
import sys
from datetime import datetime
from pathlib import Path


# 安全停止异常
class CrawlerStopException(Exception):
    """爬虫需要安全停止时抛出"""
    pass

# ============================================================
# 配置
# ============================================================

FIRST_PAGE_URL = "https://hz.lianjia.com/zufang/"
BASE_URL = "https://hz.lianjia.com/zufang/pg{page}/"

# 分区域+租赁方式+租金三重筛选（每组 < 100 页）
DISTRICTS = [
    ("上城区", "shangchengqu"), ("拱墅区", "gongshuqu"),
    ("西湖区", "xihuqu4"), ("滨江区", "binjiangqu"),
    ("余杭区", "yuhangqu"), ("萧山区", "xiaoshanqu"),
    ("临平区", "linpingqu"), ("钱塘区", "qiantangqu"),
    ("富阳区", "fuyangqu"), ("临安区", "linanqu"),
]
RENT_TYPES = [("整租", "rt200600000001"), ("合租", "rt200600000002")]
PRICE_RANGES = [
    ("1000以下", "rp1"), ("1000-1500", "rp2"), ("1500-2000", "rp3"),
    ("2000-2500", "rp4"), ("2500-3500", "rp5"), ("3500-5000", "rp6"),
    ("5000-10000", "rp7"), ("10000以上", "rp8"),
]
MAX_PAGES = 100  # 链家单搜索最大页数
ROOM_TYPES = [("一居", "l0"), ("二居", "l1"), ("三居", "l2"), ("四居+", "l3")]

BATCH_SIZE = 100
DELAY_MIN = 8
DELAY_MAX = 15
BATCH_DELAY = 60
TIMEOUT = 20000
CDP_URL = "http://localhost:9222"

# 云码平台配置
YUNMA_TOKEN = os.environ.get("YUNMA_TOKEN", "your_yunma_token_here")
YUNMA_API = "http://api.jfbym.com/api/YmServer/customApi"

# 进度追踪文件
ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DATA_FILE = ROOT_DIR / "data" / "raw" / "data_raw.csv"
PROGRESS_FILE = ROOT_DIR / "data" / "cache" / "crawl_progress.json"

# ============================================================
# 浏览器连接
# ============================================================

def connect_browser():
    pw = sync_playwright().start()
    browser = pw.chromium.connect_over_cdp(CDP_URL)
    context = browser.contexts[0]
    return pw, browser, context

# ============================================================
# 云码验证码识别
# ============================================================

def recognize_captcha(image_base64, type_id, extra=""):
    """调用云码 API 识别验证码"""
    payload = {
        "token": YUNMA_TOKEN,
        "type": type_id,
        "image": image_base64,
    }
    if extra:
        payload["extra"] = extra
    try:
        resp = requests.post(YUNMA_API, json=payload, timeout=30)
        result = resp.json()
        code = result.get("code")
        msg = result.get("msg", "")
        if code == 10000:
            data = result.get("data", {})
            coords_str = data.get("data", "")
            coords = []
            for pair in coords_str.split("|"):
                parts = pair.split(",")
                if len(parts) == 2:
                    coords.append((int(float(parts[0])), int(float(parts[1]))))
            return coords
        else:
            print(f"  [云码] 返回 code={code}, msg={msg}")
            # 检测积分不足相关错误
            credit_keywords = ["余额", "积分", "不足", "欠费", "充值", "credit", "insufficient", "balance"]
            if any(kw in msg.lower() for kw in credit_keywords):
                print(f"\n  [安全停止] 云码平台积分不足！请充值后运行爬虫")
                raise CrawlerStopException("云码积分不足")
            return None
    except CrawlerStopException:
        raise
    except Exception as e:
        print(f"  [云码] API 错误: {e}")
        return None

# ============================================================
# GeeTest v4 点击验证码自动破解
# ============================================================

def is_captcha_page(html: str) -> bool:
    lower = html.lower()
    return "captcha" in lower and "geetest" in lower

def auto_solve_captcha(page, max_attempts=5):
    """自动破解 GeeTest v4 点击式验证码
    方案：截取整个弹窗（含指令文字+验证图片）→ 云码 88888 接口 → JS 原生点击
    """
    import cv2

    for attempt in range(max_attempts):
        try:
            print(f"\n  [验证码] 第 {attempt+1} 次尝试...")

            # 检查弹窗是否已打开
            popup_h = page.evaluate('''() => {
                const els = document.querySelectorAll('[class*="geetest_box"]');
                let maxH = 0;
                for (const el of els) { if (el.offsetHeight > maxH) maxH = el.offsetHeight; }
                return maxH;
            }''')

            if popup_h <= 100:
                # 弹窗未打开，点击验证按钮
                time.sleep(1)
                btn = page.query_selector("[class*='geetest_btn_click']")
                if btn:
                    btn.click(force=True)
                # 等待弹窗展开
                for _ in range(15):
                    time.sleep(1)
                    h = page.evaluate('''() => {
                        const els = document.querySelectorAll('[class*="geetest_box"]');
                        let maxH = 0;
                        for (const el of els) { if (el.offsetHeight > maxH) maxH = el.offsetHeight; }
                        return maxH;
                    }''')
                    if h > 100:
                        break
            else:
                # 弹窗已打开（刷新重试），等待新图片加载
                time.sleep(2)

            time.sleep(1)

            # 先滚动弹窗到可见区域，再获取坐标
            page.evaluate('''() => {
                const els = document.querySelectorAll('[class*="geetest_box"]');
                for (const el of els) { el.scrollIntoView({block: 'center'}); }
            }''')
            time.sleep(0.5)

            # 获取弹窗在页面视口中的绝对坐标（考虑iframe偏移）
            popup = page.evaluate('''() => {
                const els = document.querySelectorAll('[class*="geetest_box"]');
                let maxH = 0, target = null;
                for (const el of els) {
                    if (el.offsetHeight > maxH) { maxH = el.offsetHeight; target = el; }
                }
                if (!target || maxH <= 100) return null;
                const rect = target.getBoundingClientRect();
                // 计算元素在页面中的绝对位置
                let x = rect.x, y = rect.y;
                let win = target.ownerDocument.defaultView;
                while (win.frameElement) {
                    const frameRect = win.frameElement.getBoundingClientRect();
                    x += frameRect.x;
                    y += frameRect.y;
                    win = win.parent;
                }
                return {x: x, y: y, w: rect.width, h: rect.height};
            }''')

            if not popup or popup['h'] <= 100:
                print("  [验证码] 弹窗未展开")
                continue

            print(f"  [验证码] 弹窗坐标: x={popup['x']:.0f}, y={popup['y']:.0f}, w={popup['w']:.0f}, h={popup['h']:.0f}")

            # 用 clip 参数截取弹窗区域
            popup_bytes = page.screenshot(clip={"x": max(0, popup['x']), "y": max(0, popup['y']), "width": popup['w'], "height": popup['h']})
            popup_b64 = base64.b64encode(popup_bytes).decode("utf-8")

            # 调用云码 88888 接口（弹窗截图包含指令文字+图片）
            coords = recognize_captcha(popup_b64, "88888")

            if not coords or len(coords) < 3:
                print(f"  [验证码] 云码识别失败，刷新验证码...")
                refresh = page.query_selector("[class*='geetest_refresh']")
                if refresh:
                    try:
                        refresh.click(force=True)
                        time.sleep(2)
                    except:
                        pass
                continue

            # 检测设备像素比，坐标需要除以 DPR
            dpr = page.evaluate("() => window.devicePixelRatio") or 1
            print(f"  [云码] 识别成功！坐标: {coords}  DPR={dpr}")

            # 点击坐标（云码坐标是截图像素，需除以DPR转为CSS像素）
            for i, (cx, cy) in enumerate(coords[:3]):
                page_x = popup['x'] + cx / dpr
                page_y = popup['y'] + cy / dpr
                print(f"  [验证码] 点击 #{i+1}: 云码({cx},{cy}) -> 页面({page_x:.0f},{page_y:.0f})")

                page.evaluate('''([x, y]) => {
                    const el = document.elementFromPoint(x, y);
                    if (!el) return;
                    for (const evt of ['pointerdown','mousedown','pointerup','mouseup','click']) {
                        el.dispatchEvent(new MouseEvent(evt, {
                            bubbles: true, cancelable: true,
                            clientX: x, clientY: y, button: 0
                        }));
                    }
                }''', [page_x, page_y])
                time.sleep(0.5)

            # 点击确定按钮
            time.sleep(1)
            submit_state = page.evaluate('''() => {
                const btn = document.querySelector('[class*="geetest_submit"]');
                if (!btn) return 'not found';
                return btn.getAttribute('class').includes('disable') ? 'disabled' : 'enabled';
            }''')

            if submit_state == 'enabled':
                submit = page.query_selector("[class*='geetest_submit']")
                if submit:
                    sb = submit.bounding_box()
                    if sb and sb['width'] > 0:
                        print(f"  [验证码] 点击确定...")
                        page.mouse.click(sb['x'] + sb['width']/2, sb['y'] + sb['height']/2)
            else:
                print(f"  [验证码] 确定按钮禁用，尝试 Playwright mouse 点击...")
                # 回退方案：用 Playwright mouse 点击
                for i, (cx, cy) in enumerate(coords[:3]):
                    page_x = popup['x'] + cx / dpr
                    page_y = popup['y'] + cy / dpr
                    page.mouse.click(page_x, page_y, delay=80)
                    time.sleep(0.5)
                time.sleep(1)
                submit = page.query_selector("[class*='geetest_submit']")
                if submit:
                    sb = submit.bounding_box()
                    if sb and sb['width'] > 0:
                        page.mouse.click(sb['x'] + sb['width']/2, sb['y'] + sb['height']/2)

            # 等待结果
            time.sleep(3)

            # 检查是否成功（页面正在导航说明验证码已通过）
            try:
                html_check = page.content()
            except Exception:
                print(f"  [验证码] 页面正在导航，验证码破解成功！")
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
                return True
            if "geetest" not in html_check.lower():
                print(f"  [验证码] 验证码破解成功！")
                return True

            # 检查成功图标
            has_success = page.evaluate('''() => {
                const el = document.querySelector('[class*="geetest_success"]');
                return el && el.offsetHeight > 0;
            }''')
            if has_success:
                print(f"  [验证码] 验证码破解成功！（成功图标）")
                time.sleep(1)
                return True

            # 检查错误提示
            err = page.evaluate('''() => {
                const el = document.querySelector('[class*="geetest_err_tip"]');
                return el && el.offsetHeight > 0 ? el.textContent.trim() : '';
            }''')
            if err:
                print(f"  [验证码] 错误: {err}")

            print(f"  [验证码] 第 {attempt+1} 次失败，刷新重试...")
            time.sleep(1)
            refresh = page.query_selector("[class*='geetest_refresh']")
            if refresh:
                try:
                    refresh.click(force=True)
                    time.sleep(2)
                except:
                    pass

        except CrawlerStopException:
            raise
        except Exception as e:
            import traceback
            print(f"  [验证码] 异常: {e}")
            traceback.print_exc()
            time.sleep(2)

    print(f"  [验证码] {max_attempts} 次尝试均失败")
    return False

# ============================================================
# 页面请求
# ============================================================

def fetch_page(page, url: str, retries: int = 3) -> BeautifulSoup | None:
    for attempt in range(retries):
        try:
            page.goto(url, wait_until="networkidle", timeout=TIMEOUT)

            # 检测登录过期
            current_url = page.url
            if "clogin.lianjia.com" in current_url or "login" in current_url.split("/")[-2:]:
                print(f"\n  [安全停止] 检测到登录页面: {current_url}")
                print(f"  [安全停止] 链家登录已过期，请重新登录后运行爬虫")
                raise CrawlerStopException("登录过期")

            html = page.content()

            # 额外检查HTML中是否有登录提示
            if "用户登录" in html and "captcha" not in html.lower() and "zufang" not in html.lower():
                print(f"\n  [安全停止] 页面内容显示需要登录")
                raise CrawlerStopException("登录过期")

            if is_captcha_page(html):
                print(f"\n  [验证码] 检测到 GeeTest 验证码，自动破解中...")
                if auto_solve_captcha(page):
                    # 验证码通过后页面可能跳转，重新导航回目标URL
                    print(f"  [验证码] 重新导航回: {url}")
                    page.goto(url, wait_until="networkidle", timeout=TIMEOUT)
                    html = page.content()
                    if is_captcha_page(html):
                        print(f"  [验证码] 破解后仍为验证码页，重试请求...")
                        continue
                else:
                    print(f"  [验证码] 自动破解失败，等待 30 秒后重试...")
                    time.sleep(30)
                    continue

            return BeautifulSoup(html, "lxml")
        except CrawlerStopException:
            raise
        except Exception as e:
            if attempt < retries - 1:
                wait = (attempt + 1) * 5
                print(f"  [重试] 第{attempt+1}次失败，{wait}秒后重试: {e}")
                time.sleep(wait)
            else:
                print(f"  [错误] 请求失败（已重试{retries}次）: {url}")
                return None
    return None

# ============================================================
# 数据解析
# ============================================================

def parse_rent_list(soup: BeautifulSoup, combo_label: str = "", page_num: int = 0) -> list[dict]:
    rent_list = []
    content = soup.find("div", class_="content__list")
    if not content:
        return rent_list

    for item in content.find_all("div", class_="content__list--item"):
        try:
            title_div = item.find("p", class_="content__list--item--title")
            if not title_div:
                continue
            title_link = title_div.find("a")
            title = title_link.text.strip() if title_link else ""
            link_href = title_link.get("href", "") if title_link else ""
            detail_url = ("https://hz.lianjia.com" + link_href) if link_href.startswith("/") else link_href

            rent_type = ""
            if "·" in title:
                rent_type = title.split("·")[0].strip()
            elif "整租" in title:
                rent_type = "整租"
            elif "合租" in title:
                rent_type = "合租"

            community_name = ""
            if "·" in title:
                name_part = title.split("·")[1].strip()
                community_name = name_part.split()[0] if name_part else ""

            des_div = item.find("p", class_="content__list--item--des")
            if not des_div:
                continue

            des_text = des_div.text.strip()
            des_links = des_div.find_all("a")
            district = des_links[0].text.strip() if len(des_links) > 0 else ""
            area_name = des_links[1].text.strip() if len(des_links) > 1 else ""

            des_parts = [p.strip() for p in des_text.split("/")]
            area = ""
            orientation = ""
            layout = ""
            floor_info = ""

            for part in des_parts:
                if "㎡" in part:
                    area = part
                elif part in ["东", "南", "西", "北", "东南", "东北", "西南", "西北", "南北", "东西"]:
                    orientation = part
                elif "室" in part or "厅" in part:
                    layout = part
                elif "楼层" in part:
                    floor_info = part

            price_span = item.find("span", class_="content__list--item-price")
            if not price_span:
                continue
            price_em = price_span.find("em")
            rent_price = price_em.text.strip() if price_em else ""

            tags_div = item.find("p", class_="content__list--item--brand")
            tags = tags_div.text.strip() if tags_div else ""

            rent_list.append({
                "标题": title,
                "小区名称": community_name,
                "行政区域": district,
                "商圈": area_name,
                "租赁方式": rent_type,
                "户型": layout,
                "建筑面积": area,
                "朝向": orientation,
                "楼层信息": floor_info,
                "租金": rent_price,
                "标签": tags,
                "链接": detail_url,
                "组合": combo_label,
                "页数": page_num,
            })
        except Exception:
            continue

    return rent_list

# ============================================================
# 增量保存
# ============================================================

def load_existing_data(filepath: str) -> pd.DataFrame:
    if os.path.exists(filepath):
        try:
            df = pd.read_csv(filepath, encoding="utf-8-sig")
            print(f"[续爬] 已有 {len(df)} 条数据，将从第 {len(df)//30 + 1} 页继续")
            return df
        except:
            pass
    return pd.DataFrame()

def save_data(df: pd.DataFrame, filepath: str):
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(filepath, index=False, encoding="utf-8-sig")

# ============================================================
# 进度追踪
# ============================================================

def load_progress() -> set:
    """加载已完成的组合索引集合"""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data.get("completed", []))
        except:
            pass
    return set()

def save_progress(completed: set, total_combos: int, df_count: int):
    """保存进度到文件"""
    data = {
        "completed": sorted(completed),
        "total_combos": total_combos,
        "completed_count": len(completed),
        "data_count": df_count,
        "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ============================================================
# 主爬虫
# ============================================================

def crawl_pages(page, df, base_url, label, total, output_path):
    """爬取指定组合的所有页面"""
    total_pages = min((total + 29) // 30, MAX_PAGES)
    new_items = []
    for page_num in range(1, total_pages + 1):
        url = base_url if page_num == 1 else base_url + f"pg{page_num}/"
        soup = fetch_page(page, url)
        if not soup:
            print(f"    [中断] {label} 第{page_num}页失败")
            break
        items = parse_rent_list(soup, combo_label=label, page_num=page_num)
        new_items.extend(items)
        if len(new_items) >= 50:
            df = pd.concat([df, pd.DataFrame(new_items)], ignore_index=True)
            df = df.drop_duplicates(subset=["标题", "小区名称", "租金"], keep="first")
            new_items = []
            save_data(df, output_path)
        print(f"    [{len(df)+len(new_items)}/{total}] {label} 第{page_num}/{total_pages}页 +{len(items)}条", end="\r")
        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
    if new_items:
        df = pd.concat([df, pd.DataFrame(new_items)], ignore_index=True)
        df = df.drop_duplicates(subset=["标题", "小区名称", "租金"], keep="first")
    save_data(df, output_path)
    return df


def crawl_filter(page, df, base_url, label, output_path):
    """爬取一个筛选组合，超过100页时自动加户型筛选"""
    soup = fetch_page(page, base_url)
    if not soup:
        print(f"  [跳过] {label} 无法访问")
        return df, 0

    total_el = soup.find("span", class_="content__title--hl")
    total = int(total_el.text.strip()) if total_el else 0

    # 页数为0时刷新一次再检查
    if total == 0:
        print(f"  {label}: 页数为0，刷新重试...")
        time.sleep(3)
        soup = fetch_page(page, base_url)
        if soup:
            total_el = soup.find("span", class_="content__title--hl")
            total = int(total_el.text.strip()) if total_el else 0
        if total == 0:
            print(f"  {label}: 刷新后仍为0，跳过")
            return df, 0

    total_pages = (total + 29) // 30

    if total_pages <= MAX_PAGES:
        print(f"  {label}: {total} 条, {total_pages} 页")
        df = crawl_pages(page, df, base_url, label, total, output_path)
        print()
        return df, total
    else:
        # 超过100页，加户型筛选
        print(f"  {label}: {total} 条, {total_pages} 页 [超限，加户型筛选]")
        crawled = 0
        for rt_name, rt_code in ROOM_TYPES:
            sub_url = base_url.rstrip('/') + f"/{rt_code}/"
            sub_label = f"{label}·{rt_name}"
            sub_soup = fetch_page(page, sub_url)
            if not sub_soup:
                continue
            sub_total_el = sub_soup.find("span", class_="content__title--hl")
            sub_total = int(sub_total_el.text.strip()) if sub_total_el else 0
            if sub_total == 0:
                continue
            print(f"    {sub_label}: {sub_total} 条")
            df = crawl_pages(page, df, sub_url, sub_label, sub_total, output_path)
            crawled += sub_total
            print()
            time.sleep(random.uniform(2, 4))
        return df, crawled


def crawl_all() -> pd.DataFrame:
    output_path = str(RAW_DATA_FILE)
    df = load_existing_data(output_path)

    # 加载进度
    completed = load_progress()

    print("正在连接 Edge 浏览器...")
    pw, browser, context = connect_browser()
    page = context.new_page()
    page.set_viewport_size({"width": 1280, "height": 800})

    # 生成所有筛选组合
    combos = []
    for d_name, d_code in DISTRICTS:
        for r_name, r_code in RENT_TYPES:
            for p_name, p_code in PRICE_RANGES:
                url = f"https://hz.lianjia.com/zufang/{d_code}/{r_code}/{p_code}/"
                label = f"{d_name}·{r_name}·{p_name}"
                combos.append((url, label))

    print(f"共 {len(combos)} 个筛选组合")
    print(f"每页间隔: {DELAY_MIN}-{DELAY_MAX}秒")
    if completed:
        print(f"已完成 {len(completed)} 个组合，从第 {len(completed)+1} 个继续")
    print("=" * 60)

    grand_total = 0
    stop_reason = None
    for idx, (url, label) in enumerate(combos):
        # 跳过已完成的组合
        if idx in completed:
            continue

        try:
            print(f"\n[{idx+1}/{len(combos)}] {label}")
            df, count = crawl_filter(page, df, url, label, output_path)
            grand_total += count

            # 标记组合完成并保存进度
            completed.add(idx)
            save_progress(completed, len(combos), len(df))
            print(f"  完成！累计 {len(df)} 条数据")

            # 组合间短暂休息
            if idx < len(combos) - 1:
                time.sleep(random.uniform(3, 6))

        except CrawlerStopException as e:
            stop_reason = str(e)
            print(f"\n{'='*60}")
            print(f"[安全停止] 原因: {stop_reason}")
            print(f"[安全停止] 已完成 {len(completed)}/{len(combos)} 个组合")
            print(f"[安全停止] 已采集 {len(df)} 条数据")
            print(f"[安全停止] 进度已保存，解决问题后可继续运行")
            print(f"{'='*60}")
            save_data(df, output_path)
            save_progress(completed, len(combos), len(df))
            break

    try:
        page.close()
    except:
        pass
    try:
        browser.close()
    except:
        pass
    try:
        pw.stop()
    except:
        pass

    if stop_reason:
        print(f"\n爬虫因 [{stop_reason}] 安全停止，共 {len(df)} 条数据 -> {output_path}")
    else:
        print(f"\n{'='*60}")
        print(f"爬取完成！共 {len(df)} 条数据 -> {output_path}")
    return df

# ============================================================
# 入口
# ============================================================

if __name__ == "__main__":
    df = crawl_all()
    if not df.empty:
        print(f"\n数据预览:")
        print(df.head(3))
