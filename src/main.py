"""
杭州链家租房数据采集与处理系统
功能：一键执行爬取 -> 清洗 -> 地理编码
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parent
ROOT_DIR = SRC_DIR.parent
RAW_DATA_FILE = ROOT_DIR / "data" / "raw" / "data_raw.csv"
FINAL_DATA_FILE = ROOT_DIR / "data" / "processed" / "data_final.csv"


def print_banner() -> None:
    print("=" * 60)
    print("杭州链家租房数据采集与处理系统")
    print(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


def run_step(name: str, script_name: str) -> bool:
    script_path = SRC_DIR / script_name
    print(f"\n{'=' * 60}")
    print(f"步骤: {name}")
    print(f"脚本: {script_path}")
    print("=" * 60)

    if not script_path.exists():
        print(f"[错误] 脚本不存在: {script_path}")
        return False

    result = subprocess.run([sys.executable, str(script_path)], cwd=ROOT_DIR)
    if result.returncode == 0:
        print(f"\n[完成] {name}")
        return True

    print(f"\n[失败] {name} (退出码: {result.returncode})")
    return False


def main() -> None:
    print_banner()

    steps = [
        ("1. 租房数据爬取", "01_rent_crawler.py"),
        ("2. 数据清洗", "02_data_cleaning.py"),
        ("3. 地理编码", "03_geocoding.py"),
    ]

    for name, script_name in steps:
        if not run_step(name, script_name):
            print(f"\n流程在 [{name}] 中断")
            return

    print(f"\n{'=' * 60}")
    print("全部完成")
    print("=" * 60)

    for path, desc in [
        (RAW_DATA_FILE, "原始数据"),
        (FINAL_DATA_FILE, "最终数据（带经纬度）"),
    ]:
        if path.exists():
            size_kb = path.stat().st_size / 1024
            print(f"  {path.relative_to(ROOT_DIR)} ({desc}) - {size_kb:.1f} KB")


if __name__ == "__main__":
    main()
