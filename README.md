# 基于 GIS 的杭州城市租房价格空间监测与通勤因果分析系统

> 杭州市链家租房数据采集、清洗、地理编码与课程材料整理仓库

## 结论

这个仓库现在已经按适合上传 GitHub 的方式整理为“源码、数据、文档、参考资料”分层结构，原有材料保留，没有删除。

## 当前目录结构

```text
.
├─ src/                        # 主程序源码
│  ├─ 01_rent_crawler.py
│  ├─ 02_data_cleaning.py
│  ├─ 03_geocoding.py
│  ├─ geocode_communities.py
│  └─ main.py
├─ scripts/                    # 辅助脚本
│  └─ generate_doc.py
├─ data/
│  ├─ raw/                     # 原始数据
│  ├─ processed/               # 清洗后/最终数据
│  └─ cache/                   # 进度与地理编码缓存
├─ docs/
│  ├─ reports/                 # 课程报告
│  └─ course/                  # 课程要求材料
├─ references/
│  └─ Scrapling-Skill/         # 参考资料，非项目核心源码
├─ .env.example
├─ .gitignore
├─ README.md
└─ requirements.txt
```

## 运行说明

### 环境要求

- Python 3.9+
- Microsoft Edge
- 高德地图 API Key
- 云码平台 Token

### 安装依赖

```bash
pip install -r requirements.txt
playwright install chromium
```

### 配置环境变量

复制 `.env.example`，在本地配置：

```env
YUNMA_TOKEN=your_yunma_token_here
AMAP_API_KEY=your_amap_api_key_here
```

### 运行入口

一键执行全流程：

```bash
python src/main.py
```

分步执行：

```bash
python src/01_rent_crawler.py
python src/02_data_cleaning.py
python src/03_geocoding.py
```

## 数据文件位置

- 原始数据：`data/raw/data_raw.csv`
- 清洗结果：`data/processed/data_cleaned.csv`
- 最终结果：`data/processed/data_final.csv`
- 地理编码缓存：`data/cache/geocode_cache.json`
- 爬取进度：`data/cache/crawl_progress.json`

## 已做的整理

1. 把主脚本统一归到 `src/`
2. 把生成脚本移到 `scripts/`
3. 把原始数据、处理结果、缓存分开存放
4. 把课程报告与课程要求移到 `docs/`
5. 把外部参考材料移到 `references/`
6. 修正了主流程脚本和数据处理脚本的路径引用
7. 补全了 `requirements.txt` 中缺失的依赖
8. 统一了清洗结果文件名为 `data_cleaned.csv`

## 上传 GitHub 的建议

建议上传：

- `src/`
- `scripts/`
- `docs/`
- `references/`（如果你想保留学习资料）
- `.env.example`
- `.gitignore`
- `README.md`
- `requirements.txt`

默认不要上传：

- `data/raw/*.csv`
- `data/processed/*.csv`
- `data/cache/*.json`
- 本地 `.env`

如果老师要求展示结果，建议单独补一个脱敏后的样例数据文件，而不是直接上传全量爬取结果。

## 注意事项

1. 该项目依赖浏览器登录态和第三方服务，不是纯离线脚本。
2. 公开仓库里不要提交真实 Token、Key、Cookie。
3. 链家原始数据和全量派生数据不建议公开分发。
4. 当前有一个正在被 Office 占用的 `数据采集部分.docx`，所以还留在仓库根目录，关闭占用后可以再移动到 `docs/reports/`。
