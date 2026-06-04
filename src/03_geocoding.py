"""
高德地图地理编码
功能：将小区地址转换为经纬度坐标，输出最终数据
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pandas as pd
import requests
from tqdm import tqdm


ROOT_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = ROOT_DIR / "data" / "processed" / "data_cleaned.csv"
OUTPUT_FILE = ROOT_DIR / "data" / "processed" / "data_final.csv"

AMAP_KEY = os.environ.get("AMAP_API_KEY", "your_amap_api_key_here")
GEOCODE_URL = "https://restapi.amap.com/v3/geocode/geo"
TIMEOUT = 5
REQUEST_INTERVAL = 0.2


def geocode_address(address: str, city: str = "杭州") -> dict | None:
    params = {
        "key": AMAP_KEY,
        "address": address,
        "city": city,
        "output": "json",
    }
    try:
        resp = requests.get(GEOCODE_URL, params=params, timeout=TIMEOUT)
        data = resp.json()
        if data.get("status") != "1" or data.get("count") == "0":
            return None
        geocode = data["geocodes"][0]
        location = geocode.get("location", "")
        if not location:
            return None
        lng, lat = location.split(",")
        return {"lng": round(float(lng), 6), "lat": round(float(lat), 6)}
    except Exception:
        return None


def batch_geocode(addresses: list[str]) -> list[dict]:
    results: list[dict] = []
    success = 0
    for index, address in enumerate(tqdm(addresses, desc="地理编码")):
        result = geocode_address(address)
        if result:
            results.append(result)
            success += 1
        else:
            results.append({"lng": None, "lat": None})

        if index < len(addresses) - 1:
            time.sleep(REQUEST_INTERVAL)

    print(f"\n编码完成: {success}/{len(addresses)} ({success / len(addresses) * 100:.1f}%)")
    return results


def build_address(row: pd.Series) -> str:
    parts = ["杭州市"]
    if pd.notna(row.get("行政区域")):
        parts.append(str(row["行政区域"]))
    if pd.notna(row.get("商圈")):
        parts.append(str(row["商圈"]))
    if pd.notna(row.get("小区名称")):
        parts.append(str(row["小区名称"]))
    return " ".join(parts)


def generate_mock_coords(df: pd.DataFrame) -> pd.DataFrame:
    import random

    district_coords = {
        "上城区": (120.17, 30.25),
        "西湖区": (120.13, 30.27),
        "余杭区": (120.03, 30.29),
        "滨江区": (120.21, 30.21),
        "拱墅区": (120.15, 30.32),
        "萧山区": (120.27, 30.17),
        "临平区": (120.30, 30.42),
        "钱塘区": (120.49, 30.33),
        "富阳区": (119.95, 30.05),
        "临安区": (119.72, 30.23),
        "桐庐县": (119.68, 29.79),
        "建德市": (119.28, 29.47),
        "淳安县": (119.04, 29.61),
    }

    lngs: list[float] = []
    lats: list[float] = []
    for _, row in df.iterrows():
        district = str(row.get("行政区域", ""))
        if district in district_coords:
            base_lng, base_lat = district_coords[district]
            lng = base_lng + random.uniform(-0.03, 0.03)
            lat = base_lat + random.uniform(-0.02, 0.02)
        else:
            lng = 120.15 + random.uniform(-0.1, 0.1)
            lat = 30.28 + random.uniform(-0.05, 0.05)
        lngs.append(round(lng, 6))
        lats.append(round(lat, 6))

    df["经度"] = lngs
    df["纬度"] = lats
    return df


def process_geocoding(input_file: Path = INPUT_FILE) -> pd.DataFrame:
    print("开始地理编码处理...")

    try:
        df = pd.read_csv(input_file, encoding="utf-8-sig")
    except FileNotFoundError:
        print(f"[错误] 文件不存在: {input_file}")
        return pd.DataFrame()

    print(f"加载数据: {len(df)} 条")

    use_mock = not AMAP_KEY or AMAP_KEY == "your_amap_api_key_here"
    if use_mock:
        print("[信息] 未配置高德 API Key，使用模拟坐标（演示模式）")
        df = generate_mock_coords(df)
    else:
        print("[信息] 使用高德 API 进行地理编码")
        df["完整地址"] = df.apply(build_address, axis=1)
        coords = batch_geocode(df["完整地址"].tolist())
        coords_df = pd.DataFrame(coords)
        df["经度"] = coords_df["lng"]
        df["纬度"] = coords_df["lat"]
        df = df.drop(columns=["完整地址"])

    df["经度"] = df["经度"].round(6)
    df["纬度"] = df["纬度"].round(6)

    has_coords = df["经度"].notna().sum()
    print(f"有坐标: {has_coords}/{len(df)} ({has_coords / len(df) * 100:.1f}%)")
    return df


if __name__ == "__main__":
    df = process_geocoding()
    if not df.empty:
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
        print(f"\n已保存: {OUTPUT_FILE}")
        print(df.head())
