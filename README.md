# 杭州链家租房数据全量采集与空间分析系统

> 基于 Playwright + GeeTest v4 自动验证码破解的杭州链家租房数据采集系统，覆盖 10 个行政区 × 2 种租赁方式 × 8 个价格段，共 160 个数据组合，最终获取 46,350 条带精确坐标的租房记录。

## 数据规模

| 指标 | 数值 |
|------|------|
| 覆盖行政区 | 上城、拱墅、西湖、滨江、余杭、萧山、临平、钱塘、富阳、临安 |
| 数据组合 | 160 个（10 区 × 2 租赁方式 × 8 价格段） |
| 原始数据 | 48,308 条 |
| 清洗后数据 | 46,350 条 |
| 地理编码覆盖率 | 99.1%（45,939 条有坐标） |
| 涉及小区 | 5,802 个 |

## 技术方案

**数据采集**：Playwright + CDP 连接已登录的 Edge 浏览器，自动破解 GeeTest v4 点击式验证码（云码平台 API），随机延迟 8-15 秒模拟真实用户行为。

**数据清洗**：去重、租金/面积异常值过滤、行政区域标准化、单价计算。

**地理编码**：高德地图 API，多级地址匹配 + 本地缓存，失败记录保留不丢弃。

## 项目结构

```text
.
├─ src/                        # 主程序源码
│  ├─ main.py                  # 一键执行全流程
│  ├─ 01_rent_crawler.py       # 数据爬虫（Playwright + 验证码破解）
│  ├─ 02_data_cleaning.py      # 数据清洗与预处理
│  ├─ 03_geocoding.py          # 高德地图地理编码
│  └─ geocode_communities.py   # 社区级地理编码
├─ scripts/
│  └─ generate_doc.py          # 论文文档生成
├─ data/
│  ├─ raw/                     # 原始数据
│  ├─ processed/               # 清洗后 / 最终数据
│  └─ cache/                   # 进度与地理编码缓存
├─ docs/
│  ├─ reports/                 # 课程报告
│  └─ course/                  # 课程要求材料
├─ references/                 # 参考资料
├─ requirements.txt
└─ .env.example
```

## 快速开始

### 环境要求

- Python 3.9+
- Microsoft Edge 浏览器
- 高德地图 API Key
- 云码平台 Token

### 安装

```bash
pip install -r requirements.txt
playwright install chromium
```

### 配置

复制 `.env.example` 为 `.env`，填入：

```env
YUNMA_TOKEN=your_yunma_token_here
AMAP_API_KEY=your_amap_api_key_here
```

### 运行

```bash
# 一键执行全流程
python src/main.py

# 或分步执行
python src/01_rent_crawler.py   # 爬取
python src/02_data_cleaning.py  # 清洗
python src/03_geocoding.py      # 地理编码
```

## 数据字段

| 字段 | 类型 | 说明 |
|------|------|------|
| 标题 | string | 房源标题 |
| 小区名称 | string | 所在小区 |
| 行政区域 | string | 所属行政区 |
| 商圈 | string | 商圈名称 |
| 租赁方式 | string | 整租 / 合租 |
| 户型 | string | 几室几厅 |
| 建筑面积 | float | 面积（m²） |
| 朝向 | string | 房屋朝向 |
| 楼层信息 | string | 楼层位置 |
| 租金 | int | 月租金（元） |
| 标签 | string | 房源标签 |
| 链接 | string | 链家详情页 URL |
| 单价 | float | 元/m²/月 |
| 经度 | float | 高德 GCJ-02 经度 |
| 纬度 | float | 高德 GCJ-02 纬度 |

## 注意事项

1. 爬虫依赖 Edge 浏览器登录态，Cookie 过期需重新登录
2. 云码平台按次计费，全量爬取约需 200-500 次识别
3. 高德地图地理编码每日免费额度 5,000 次
4. 数据为采集时点快照，链家房源更新较快

## 许可证

本项目仅供学术研究使用。数据来源于链家网，版权归原作者所有。
