"""
杭州链家租房数据清洗
功能：清洗原始数据并输出处理后数据
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = ROOT_DIR / "data" / "raw" / "data_raw.csv"
OUTPUT_FILE = ROOT_DIR / "data" / "processed" / "data_cleaned.csv"


def parse_number(text: str) -> float:
    if pd.isna(text) or not isinstance(text, str):
        return np.nan
    match = re.search(r"(\d+\.?\d*)", text)
    return float(match.group(1)) if match else np.nan


def parse_rent(text: str) -> str:
    if pd.isna(text) or not isinstance(text, str):
        return ""
    return text.strip()


def calc_unit_rent(rent_str: str, area: float) -> float:
    if pd.isna(rent_str) or pd.isna(area) or area <= 0:
        return np.nan
    if "-" in str(rent_str):
        return np.nan
    try:
        rent = float(rent_str)
        return round(rent / area, 2)
    except Exception:
        return np.nan


def parse_layout(layout_str: str) -> str:
    if pd.isna(layout_str) or not isinstance(layout_str, str):
        return ""
    return layout_str.strip()


def parse_floor(floor_str: str) -> str:
    if pd.isna(floor_str) or not isinstance(floor_str, str):
        return ""
    for keyword in ["高楼层", "中楼层", "低楼层"]:
        if keyword in floor_str:
            return keyword
    return floor_str.strip()


def clean_data(input_file: Path = INPUT_FILE) -> pd.DataFrame:
    print("开始清洗数据...")

    try:
        df = pd.read_csv(input_file, encoding="utf-8-sig")
    except FileNotFoundError:
        print(f"[错误] 文件不存在: {input_file}")
        return pd.DataFrame()

    print(f"原始数据: {len(df)} 条")

    df = df.drop_duplicates(subset=["标题", "小区名称", "租金"], keep="first")
    print(f"去重后: {len(df)} 条")

    df = df.dropna(subset=["小区名称", "租金"])
    print(f"剔除关键字段缺失后: {len(df)} 条")

    df["面积_平米"] = df["建筑面积"].apply(parse_number)
    df["月租金_原始"] = df["租金"].apply(parse_rent)
    df["单位租金_元每平米每月"] = df.apply(
        lambda row: calc_unit_rent(row["月租金_原始"], row["面积_平米"]),
        axis=1,
    )
    df["户型_clean"] = df["户型"].apply(parse_layout)
    df["楼层类型_clean"] = df["楼层信息"].apply(parse_floor)
    df["朝向_clean"] = df["朝向"].fillna("未知").apply(
        lambda value: value.strip() if isinstance(value, str) else "未知"
    )
    df["标签_clean"] = df["标签"].fillna("")

    before = len(df)
    df = df[
        (df["面积_平米"].isna()) | ((df["面积_平米"] >= 10) & (df["面积_平米"] <= 500))
    ]
    print(f"剔除面积异常: {before - len(df)} 条")

    final = pd.DataFrame(
        {
            "小区名称": df["小区名称"],
            "行政区域": df["行政区域"],
            "商圈": df["商圈"],
            "月租金(元/月)": df["月租金_原始"],
            "单位租金(元/平米/月)": df["单位租金_元每平米每月"],
            "面积(平米)": df["面积_平米"],
            "户型": df["户型_clean"],
            "朝向": df["朝向_clean"],
            "租赁方式": df["租赁方式"],
            "楼层类型": df["楼层类型_clean"],
            "标签": df["标签_clean"],
        }
    ).reset_index(drop=True)

    print(f"\n清洗完成: {len(final)} 条")
    print(f"字段: {list(final.columns)}")

    if "行政区域" in final.columns:
        print("行政区分布:")
        for area, count in final["行政区域"].value_counts().items():
            print(f"  {area}: {count}")

    return final


if __name__ == "__main__":
    df = clean_data()
    if not df.empty:
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
        print(f"\n已保存: {OUTPUT_FILE}")
        print(df.head())
