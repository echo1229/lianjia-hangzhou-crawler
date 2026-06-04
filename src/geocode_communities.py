from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


ROOT_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = ROOT_DIR / "data" / "processed" / "data_cleaned.csv"
OUTPUT_FILE = ROOT_DIR / "data" / "processed" / "data_final.csv"
CACHE_FILE = ROOT_DIR / "data" / "cache" / "geocode_cache.json"

API_KEY = os.environ.get("AMAP_API_KEY", "your_amap_api_key_here")


def load_cache() -> dict:
    if CACHE_FILE.exists():
        with open(CACHE_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    return {}


def save_cache(cache: dict) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as file:
        json.dump(cache, file, ensure_ascii=False, indent=2)


def geocode(address: str, city: str = "杭州") -> tuple[float | None, float | None]:
    url = f"https://restapi.amap.com/v3/geocode/geo?address={address}&city={city}&key={API_KEY}"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data.get("status") == "1" and data.get("geocodes"):
            geo = data["geocodes"][0]
            location = geo.get("location", "")
            if location:
                lng, lat = location.split(",")
                return float(lng), float(lat)
    except Exception as exc:
        print(f"  错误: {exc}")
    return None, None


def main() -> None:
    df = pd.read_csv(INPUT_FILE, encoding="utf-8-sig")
    communities = df["小区名称"].dropna().unique()

    cache = load_cache()
    print(f"已有缓存: {len(cache)} 个小区")
    print(f"需要编码: {len(communities)} 个小区")

    new_count = 0
    fail_count = 0

    for index, name in enumerate(communities):
        if name in cache:
            continue

        rows = df[df["小区名称"] == name]
        district = rows["行政区域"].iloc[0] if len(rows) > 0 else ""
        address = f"{district}{name}" if district else name

        lng, lat = geocode(address)
        if lng is None or lat is None:
            lng, lat = geocode(name)

        if lng is not None and lat is not None:
            cache[name] = {"lng": lng, "lat": lat}
            new_count += 1
        else:
            cache[name] = {"lng": None, "lat": None}
            fail_count += 1

        if (index + 1) % 100 == 0:
            save_cache(cache)
            print(f"  进度: {index + 1}/{len(communities)}, 新增: {new_count}, 失败: {fail_count}")

        time.sleep(0.1)

    save_cache(cache)
    print(f"\n完成: 新增 {new_count}, 失败 {fail_count}")

    df["经度"] = df["小区名称"].map(lambda value: cache.get(value, {}).get("lng"))
    df["纬度"] = df["小区名称"].map(lambda value: cache.get(value, {}).get("lat"))

    before = len(df)
    df = df.dropna(subset=["经度", "纬度"])
    print(f"删除无坐标记录: {before - len(df)} 条")
    print(f"最终数据: {len(df)} 条")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    print(f"已保存: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
