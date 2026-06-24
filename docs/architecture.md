# Mineral Daily Agent - 项目技术文档

## 1. 项目概述

Mineral Daily Agent 是一个矿业每日简报自动生成系统。用户输入一句自然语言查询（如"给我生成一份关于 Pilbara 锂矿的今日简报"），系统自动完成新闻搜索、PDF 储量报告解析、大宗商品价格获取，最终输出一份结构化的 Markdown 简报。

系统采用 **Agent + MCP (Model Context Protocol)** 架构：

- **Agent 层**：基于 LangGraph 的状态机，负责流程编排、数据归一化、质量验证
- **工具层**：3 个独立的 MCP Server，分别负责新闻、PDF、价格三个数据域
- **通信层**：Agent 通过 stdio（标准输入/输出）的 JSON-RPC 协议与 MCP Server 通信

技术栈：Python 3.11、LangGraph、FastMCP、FastAPI、httpx、PyMuPDF、pdfplumber、trafilatura。

---

## 2. 系统架构

```
用户
 │
 ├─ CLI:  python -m app.cli "查询内容"
 └─ API:  POST /api/v1/briefs
      │
      ▼
┌──────────────────────────────────────────────────────────────┐
│                  DailyBriefAgent                             │
│                  (LangGraph StateGraph)                      │
│                                                              │
│  parse_query ─► resolve_entity ─► build_plan                 │
│       ─► fetch_data (并行) ─► normalize ─► verify_evidence   │
│       ─► analyze_risks ─► compose_report ─► final_verify     │
└───────────────────────┬──────────────────────────────────────┘
                        │
              MCPClientManager
              (stdio 子进程管理)
           ┌────────┼────────┐
           ▼        ▼        ▼
    ┌──────────┐┌────────┐┌──────────┐
    │mining-   ││mineral-││lme-price-│
    │news-mcp  ││pdf-mcp ││mcp       │
    └──────────┘└────────┘└──────────┘
         │          │          │
         ▼          ▼          ▼
    RSS 抓取    PDF 下载   TradingEconomics
    正文提取    表格解析   网页价格抓取
                LLM 降级   私有 API (可选)
```

---

## 3. 目录结构

```
mineral-daily-agent/
├── apps/
│   └── daily_agent/               # Agent 主应用
│       ├── app/
│       │   ├── agent/
│       │   │   ├── graph.py           # LangGraph 图定义 + DailyBriefAgent 类
│       │   │   ├── state.py           # DailyBriefState TypedDict
│       │   │   └── nodes/
│       │   │       ├── parse_query.py      # 节点1: 解析用户查询
│       │   │       ├── resolve_entity.py   # 节点2: 实体匹配
│       │   │       ├── build_plan.py       # 节点3: 生成数据获取计划
│       │   │       ├── fetch_news.py       # 节点4a: 调用新闻 MCP
│       │   │       ├── fetch_resources.py  # 节点4b: 调用 PDF MCP
│       │   │       ├── fetch_prices.py     # 节点4c: 调用价格 MCP
│       │   │       ├── normalize.py        # 节点5: 数据归一化
│       │   │       ├── verify_evidence.py  # 节点6: 证据校验
│       │   │       ├── analyze_risks.py    # 节点7: 风险分析
│       │   │       ├── compose_report.py   # 节点8: 组装 Markdown
│       │   │       └── final_verify.py     # 节点9: 最终质量检查
│       │   ├── api/
│       │   │   ├── routes.py          # FastAPI 路由
│       │   │   └── schemas.py         # 请求/响应模型
│       │   ├── mcp_client/
│       │   │   └── manager.py         # MCP 客户端管理器
│       │   ├── reports/
│       │   │   ├── renderer.py        # Jinja2 渲染器（备用）
│       │   │   └── templates/
│       │   │       └── daily_brief.md.j2  # Jinja2 报告模板
│       │   ├── verification/
│       │   │   ├── citations.py       # 引用完整性校验
│       │   │   ├── numbers.py         # 数值合理性校验
│       │   │   └── claims.py          # 报告结构校验
│       │   ├── cli.py                 # CLI 入口
│       │   └── main.py                # FastAPI 入口
│       └── pyproject.toml
│
├── mcp_servers/
│   ├── mining_news/               # 新闻 MCP Server
│   │   ├── app/
│   │   │   ├── server.py              # FastMCP 注册 search + fetch_article
│   │   │   └── providers/
│   │   │       ├── rss.py             # live: RSS 抓取 + 关键词匹配
│   │   │       ├── article.py         # live: 文章正文提取
│   │   │       └── fixture.py         # fixture: 本地 JSON 数据
│   │   └── pyproject.toml
│   │
│   ├── mineral_pdf/               # PDF 储量 MCP Server
│   │   ├── app/
│   │   │   ├── server.py              # FastMCP 注册 extract_resources
│   │   │   └── providers/
│   │   │       ├── pdf_extractor.py   # 页面定位 + 表格/正文解析
│   │   │       ├── llm_structurer.py  # LLM 降级结构化提取
│   │   │       └── fixture.py         # fixture: 本地 JSON 数据
│   │   └── pyproject.toml
│   │
│   └── lme_price/                 # 价格 MCP Server
│       ├── app/
│       │   ├── server.py              # FastMCP 注册 get_price + get_trend
│       │   └── providers/
│       │       ├── base.py            # PriceProvider 抽象基类
│       │       ├── live.py            # live: 策略链 (API → 网页)
│       │       ├── public_web.py      # 公开网页抓取 TradingEconomics
│       │       └── fixture.py         # fixture: CSV + 随机生成
│       └── pyproject.toml
│
├── packages/
│   ├── contracts/                 # 共享数据契约
│   │   └── contracts/
│   │       ├── tools.py               # 工具输入/输出 Pydantic 模型
│   │       ├── evidence.py            # EvidenceItem 模型
│   │       └── errors.py             # 统一错误码 + ToolError 模型
│   └── common/                    # 共享工具库
│       └── common/
│           ├── config.py              # 配置加载
│           ├── http_client.py         # 安全 HTTP 客户端 (SSRF 防护)
│           ├── retry.py               # 异步重试 (指数退避)
│           └── log.py                 # 日志配置
│
├── config/
│   ├── project_registry.yaml      # 矿业项目注册表（实体匹配数据库）
│   ├── commodity_mapping.yaml     # 矿种别名 + 基准价格映射
│   ├── sources.yaml               # 数据源配置（RSS 源、价格 API、PDF 参数）
│   └── risk_rules.yaml            # 风险规则定义
│
├── data/
│   ├── fixtures/                  # fixture 模式数据
│   │   ├── news.json                  # 3 条 Pilbara 相关新闻
│   │   ├── resources.json             # Pilgangoora 储量数据 (3 行)
│   │   └── prices.csv                 # 30 天碳酸锂价格序列
│   ├── reports/                   # 生成的报告输出目录
│   └── cache/                     # PDF 下载缓存目录
│
├── scripts/
│   └── smoke_test.py              # 三服务冒烟测试
│
├── mcp-config.json                # Claude Desktop / Cursor MCP 配置
├── Dockerfile                     # Docker 镜像定义
├── docker-compose.yml             # Docker Compose 编排
├── .dockerignore
├── .env.example                   # 环境变量模板
└── RUN.md                         # 运行指南
```

---

## 4. Agent 工作流详解

Agent 使用 LangGraph `StateGraph` 编排 9 个节点，以线性流水线执行。所有节点共享一个 `DailyBriefState`（TypedDict），每个节点接收当前 state，返回一个 dict 来合并更新 state。

### 4.1 State 定义

```python
class DailyBriefState(TypedDict, total=False):
    # 输入
    request_id: str                    # 请求 ID (req_20260624_a3f2c1)
    user_query: str                    # 原始查询
    report_date: str                   # 报告日期 (ISO)
    requested_news_days: int           # API 传入的新闻天数
    requested_price_days: int          # API 传入的价格天数

    # 中间状态
    parsed_intent: dict                # 解析后的意图
    entity: dict                       # 匹配到的矿业实体
    plan: dict                         # 数据获取计划

    # 工具返回的原始数据
    news_search_results: list[dict]    # 新闻搜索结果
    articles: list[dict]               # 文章正文
    resource_report: dict | None       # PDF 报告元数据
    resource_rows: list[dict]          # 储量数据行
    price_result: dict | None          # 当日价格
    price_trend: dict | None           # 价格趋势

    # 处理后的数据
    normalized_evidence: list[dict]    # 统一格式的证据列表
    warnings: list[dict]               # 告警列表
    risks: list[dict]                  # 风险列表

    # 输出
    draft_markdown: str | None         # 草稿 Markdown
    verification: dict | None          # 验证结果
    revision_count: int                # 修订次数
    final_markdown: str | None         # 最终 Markdown

    tool_status: dict                  # 各工具状态 {news: "success", ...}
```

### 4.2 图定义

```python
g = StateGraph(DailyBriefState)

g.set_entry_point("parse_query")
g.add_edge("parse_query",      "resolve_entity")
g.add_edge("resolve_entity",   "build_plan")
g.add_edge("build_plan",       "fetch_data")
g.add_edge("fetch_data",       "normalize")
g.add_edge("normalize",        "verify_evidence")
g.add_edge("verify_evidence",  "analyze_risks")
g.add_edge("analyze_risks",    "compose_report")
g.add_edge("compose_report",   "final_verify")
g.add_edge("final_verify",     END)
```

### 4.3 节点详解

#### 节点 1: parse_query

**文件**: `apps/daily_agent/app/agent/nodes/parse_query.py`

从用户自然语言中提取结构化参数。不依赖 LLM，使用前缀/后缀剥离 + 正则匹配。

- 剥离中文前缀（"给我生成一份关于"）和后缀（"的今日简报"），提取核心目标文本
- 正则 `(\d+)\s*[天日]` 提取 `news_days`（默认 1）
- 正则 `(\d+)\s*[天日]?趋势` 提取 `price_days`（默认 30）
- API 传入的 `requested_news_days` / `requested_price_days` 有更高优先级

**示例**:

```
输入: "给我生成一份关于 Pilbara 锂矿的今日简报"
输出: { target_text: "Pilbara 锂矿", news_days: 1, price_days: 30 }
```

#### 节点 2: resolve_entity

**文件**: `apps/daily_agent/app/agent/nodes/resolve_entity.py`

将自由文本匹配到 `config/project_registry.yaml` 中的已知矿业项目。

匹配算法：
1. 遍历注册表中所有项目的 aliases（别名列表）
2. 对每个 alias 计算包含关系得分：alias 出现在 target_text 中 → `0.5 + len(alias)/len(target) * 0.5`
3. 取最高分匹配，阈值 ≥ 0.3
4. 匹配失败时，将 target_text 本身作为 entity 返回，confidence = 0.0

匹配成功后，entity 中携带该项目的完整元数据：

```yaml
entity:
  company: "Pilbara Minerals"
  project: "Pilgangoora Operation"
  commodity: "lithium"
  country: "Australia"
  news_queries: ["Pilbara Minerals lithium", "Pilgangoora lithium"]
  price_benchmark: { commodity: "lithium_carbonate" }
  technical_reports: [{ url: "https://pls.com/...pdf" }]
```

#### 节点 3: build_plan

**文件**: `apps/daily_agent/app/agent/nodes/build_plan.py`

根据 entity 生成三路数据获取计划。这一步决定了哪些 MCP 工具会被调用、用什么参数。

```python
plan = {
    "news": {
        "enabled": True,                  # 总是启用
        "queries": entity["news_queries"],  # 从注册表获取
        "days": intent["news_days"],
        "limit": 10,
        "fetch_top_articles": 5,          # 搜索后取 top 5 抓正文
    },
    "resources": {
        "enabled": bool(technical_reports),  # 有 PDF URL 才启用
        "pdf_url": reports[0]["url"],
        "project_hint": "Pilgangoora Operation",
        "categories": ["Indicated", "Inferred"],
    },
    "price": {
        "enabled": bool(price_benchmark),   # 有价格基准才启用
        "commodity": "lithium_carbonate",
        "days": 30,
    },
}
```

#### 节点 4: fetch_data（并行）

**文件**: `apps/daily_agent/app/agent/graph.py` (_fetch_data_parallel 方法)

用 `asyncio.gather` 并行执行三个 fetch 函数，每个都有独立的 try/except 包装，任一失败不阻塞其他。

```python
news_result, resource_result, price_result = await asyncio.gather(
    _safe_fetch_news(),        # → fetch_news.py
    _safe_fetch_resources(),   # → fetch_resources.py
    _safe_fetch_prices(),      # → fetch_prices.py
)
```

**fetch_news** (`fetch_news.py`):

1. 对 `plan.news.queries` 中的每个查询词调用 `mining-news-mcp` 的 `search` 工具
2. 合并结果，按 `relevance_score` 排序，去重
3. 取 top 5 篇文章，逐一调用 `fetch_article` 工具获取正文
4. 返回 `news_search_results`（搜索结果摘要）和 `articles`（完整正文）

**fetch_resources** (`fetch_resources.py`):

1. 调用 `mineral-pdf-mcp` 的 `extract_resources` 工具
2. 传入 `pdf_url`、`project_hint`、`categories`
3. 返回 `resource_report`（报告元数据）和 `resource_rows`（储量数据行）

**fetch_prices** (`fetch_prices.py`):

1. 调用 `lme-price-mcp` 的 `get_price` 工具获取当日价格
2. 调用 `lme-price-mcp` 的 `get_trend` 工具获取 N 天趋势
3. 两个调用独立处理错误，一个失败不影响另一个

#### 节点 5: normalize

**文件**: `apps/daily_agent/app/agent/nodes/normalize.py`

将三种异构数据统一为 `evidence` 格式，每条分配唯一的证据 ID。

| 数据来源 | evidence_id 前缀 | evidence_type |
|----------|-----------------|---------------|
| 文章正文 / 搜索结果 | N1, N2, ... | news |
| 储量数据行 | R1, R2, ... | resource |
| 当日价格 | P1 | price |
| 价格趋势 | P2 | price |

每条 evidence 包含统一字段：`evidence_id`, `evidence_type`, `title`, `content`, `source_url`, `published_at`, `page_number`, `confidence`, `metadata`。

confidence 赋值逻辑：
- 文章正文 → 使用 trafilatura 解析的 confidence
- 储量行 → PDF 提取的 confidence（表格 0.85，正文 0.8，LLM 0.7）
- 价格 → live 非 demo = 1.0，公开网页估算 = 0.85，demo = 0.7

#### 节点 6: verify_evidence

**文件**: `apps/daily_agent/app/agent/nodes/verify_evidence.py`

对每条 evidence 执行数据质量规则检查：

| evidence_type | 检查项 |
|---------------|--------|
| news | source_url 是否存在；title 是否为空 |
| resource | page_number 是否存在；ore_tonnage 和 grade 是否 > 0 |
| price | 是否为 demo/fixture 数据 |

有问题的 evidence 被标记 `verification_issues` 字段，同时追加到全局 `warnings`。

输出统计：`{ total: 6, with_issues: 1, clean: 5 }`

#### 节点 7: analyze_risks

**文件**: `apps/daily_agent/app/agent/nodes/analyze_risks.py`

基于规则引擎分析风险信号，规则定义在 `config/risk_rules.yaml`，代码中硬编码执行：

| 规则 ID | 触发条件 | 严重度 |
|---------|---------|--------|
| price_drop_significant | 价格变动 < -5% | high |
| price_rise_significant | 价格变动 > +10% | medium |
| news_negative_sentiment | 新闻含 shutdown/strike/lawsuit 等关键词 | medium |
| resource_low_confidence | 储量提取 confidence < 0.7 | low |
| data_source_demo | 价格数据来自 fixture | low |
| missing_data_section | tool_status 中有 error/unavailable | medium |

每条 risk 关联对应的 `evidence_ids`，以便报告中交叉引用。

#### 节点 8: compose_report

**文件**: `apps/daily_agent/app/agent/nodes/compose_report.py`

组装最终 Markdown 简报，包含 6 个章节：

```markdown
# {项目名} / {公司名} 今日简报
> 报告日期: 2026-06-24

## 1. 结论摘要        ← LLM 生成或降级拼接
## 2. 新闻摘要        ← 每条新闻带 [N1] 引用和来源链接
## 3. 储量数据        ← Markdown 表格
## 4. 价格走势        ← 变动百分比、区间、数据源
## 5. 风险提示        ← 红/橙/绿标记 + evidence_ids
## 6. 引用            ← 每条 evidence 的溯源信息
```

**摘要生成策略**：
- 有 `LLM_API_KEY` → 调用 OpenAI 兼容 API，system prompt 要求基于 evidence 写 1-3 句摘要，引用 [N1] [R1] [P1]
- 无 `LLM_API_KEY` → `_fallback_summary()` 模板拼接："本日共获取 N 条相关新闻..."

**降级显示**：当某个数据源不可用时（`tool_status` 为 error/unavailable），对应章节显示"本次未获得可验证的 X 数据，因此不对 X 作结论"，而不是报错。

#### 节点 9: final_verify

**文件**: `apps/daily_agent/app/agent/nodes/final_verify.py`

最终质量门控：

1. 检查 5 个必要章节是否都存在：新闻摘要、储量数据、价格走势、风险提示、引用
2. 检查正文中引用的 `[N1]` `[R1]` `[P1]` 是否在引用章节有对应条目
3. 有问题 → 在报告末尾追加警告；无问题 → 原样通过

输出 `final_markdown`（最终报告）和 `verification.passed`（是否通过）。

---

## 5. MCP Server（工具）实现

三个 MCP Server 都使用 `mcp.server.fastmcp.FastMCP` 框架，以 stdio 传输方式运行。每个 Server 是独立的 Python 子项目，有自己的 `pyproject.toml` 和虚拟环境。

### 5.1 mining-news-mcp（新闻服务）

**文件**: `mcp_servers/mining_news/app/server.py`

注册 2 个工具：

#### 工具: search

```python
@mcp.tool()
async def search(query: str, days: int = 1, limit: int = 10) -> dict
```

搜索矿业新闻文章。

**fixture 模式** (`providers/fixture.py`):
- 读取 `data/fixtures/news.json`（3 条 Pilbara 相关预置新闻）
- 用查询词分词后与标题/摘要做关键词匹配
- 非矿种通用词（如 "Pilbara"）必须命中才算匹配
- 返回按 relevance_score 排序的结果

**live 模式** (`providers/rss.py`):
- 硬编码 2 个 RSS 源：MINING.COM (`mining.com/feed/`) 和 Mining Weekly (`miningweekly.com/page/rss`)
- 用 `httpx` 拉取 RSS feed，`feedparser` 解析
- 按 `published_at` 过滤时间范围（cutoff = now - days）
- 对每篇文章计算 relevance_score（查询词命中数 / 总查询词数）
- 要求非矿种关键词（如公司名 "Pilbara"）至少命中一个，否则 score = 0
- 过滤 score < 0.3 的结果

**返回格式**:
```json
{
  "query": "Pilbara Minerals lithium",
  "days": 1,
  "total": 3,
  "items": [
    {
      "article_id": "news_001",
      "title": "Pilbara Minerals updates FY26 production guidance...",
      "url": "https://www.mining.com/...",
      "source_name": "MINING.COM",
      "published_at": "2026-06-23T02:00:00Z",
      "snippet": "...",
      "relevance_score": 0.95,
      "matched_terms": ["pilbara", "minerals", "lithium"]
    }
  ],
  "warnings": []
}
```

#### 工具: fetch_article

```python
@mcp.tool()
async def fetch_article(url: str) -> dict
```

抓取并提取新闻文章正文。

**安全防护** (`providers/article.py`):
- URL scheme 必须为 http/https
- 黑名单主机拦截（localhost, 127.0.0.1 等）
- DNS 解析后检查是否指向私有 IP（SSRF 防护）
- 响应大小限制 10MB

**内容提取（三级降级）**:
1. **trafilatura**（首选）→ confidence 0.9，提取纯文本正文
2. **BeautifulSoup**（trafilatura 失败时）→ confidence 0.7，找 `<article>` 标签
3. 都失败 → content 为空，confidence 0.0

**返回格式**:
```json
{
  "article_id": "news_a3f2c1",
  "title": "Pilbara Minerals updates...",
  "published_at": "2026-06-23",
  "source_name": "MINING",
  "source_url": "https://www.mining.com/...",
  "content": "（文章正文，最多 10000 字符）",
  "parser": "trafilatura",
  "confidence": 0.9,
  "warnings": []
}
```

### 5.2 mineral-pdf-mcp（PDF 储量服务）

**文件**: `mcp_servers/mineral_pdf/app/server.py`

注册 1 个工具：

#### 工具: extract_resources

```python
@mcp.tool()
async def extract_resources(
    pdf_url: str,
    project_hint: str | None = None,
    categories: list[str] | None = None,
    commodities: list[str] | None = None,
    include_evidence: bool = True,
) -> dict
```

从矿业技术报告 PDF 中提取结构化储量数据。

**fixture 模式** (`providers/fixture.py`):
- 读取 `data/fixtures/resources.json`
- 按 `pdf_url` 精确匹配，或按 `project_hint` 模糊匹配

**live 模式**执行流程：

**第一步：PDF 下载**
- URL 安全校验（scheme、黑名单、DNS 解析检查私有 IP）
- HEAD 请求检查 content-type 和大小（上限 50MB）
- 下载到 `data/cache/` 目录，以 URL 的 MD5 作为文件名缓存
- 二次请求命中缓存时直接使用

**第二步：定位资源量页面** (`providers/pdf_extractor.py` → `find_resource_pages`)
- PyMuPDF 逐页扫描，统计每页包含多少个资源量关键词（"mineral resource", "indicated", "inferred", "ore tonnage", "grade" 等）
- 关键词命中 ≥ 2 个的页被标记为资源量页

**第三步：数据提取（三级降级链）**

| 级别 | 方法 | 工具 | confidence |
|------|------|------|-----------|
| Level 1 | 表格提取 | pdfplumber `extract_tables()` → `parse_resource_table()` | 0.85 |
| Level 2 | 正文正则 | PyMuPDF `get_text()` → `parse_resource_text()` | 0.80 |
| Level 3 | LLM 结构化 | OpenAI API → `structure_with_llm()` | 0.70 |

**Level 1 - 表格提取** (`parse_resource_table`):
- 解析表头，自动映射列（category/tonnage/grade/contained 等）
- 逐行用正则匹配 category（Measured/Indicated/Inferred）
- 提取数值、检测品位单位（% Li2O / % Cu / % Fe / g/t）

**Level 2 - 正文正则** (`parse_resource_text`):
- 按行扫描，识别 "Indicated" / "Inferred" 等分类标签
- 向下查找相邻的数字行，提取矿石量和品位
- 支持识别 "in-situ" vs "stockpiles" 等子类别

**Level 3 - LLM 结构化** (`providers/llm_structurer.py`):
- 将页面文本（最多 3000 字/页）发送给 OpenAI 兼容 API
- System prompt 要求返回 JSON 数组，字段为 category/ore_tonnage/grade/grade_unit
- `temperature=0`, `response_format=json_object`
- 无 `LLM_API_KEY` 时跳过此步

**返回格式**:
```json
{
  "report": {
    "title": "Pilgangoora Operation Technical Report",
    "project_name": "Pilgangoora Operation",
    "pdf_url": "https://pls.com/...pdf"
  },
  "resources": [
    {
      "deposit_name": "Pilgangoora Operation",
      "category": "Indicated",
      "commodity": "lithium",
      "ore_tonnage": 349.0,
      "ore_tonnage_unit": "Mt",
      "grade": 1.29,
      "grade_unit": "% Li2O",
      "page_number": 32,
      "evidence_text": "Indicated 349.0 1.29 ...",
      "confidence": 0.80
    }
  ],
  "status": "success",
  "warnings": []
}
```

### 5.3 lme-price-mcp（价格服务）

**文件**: `mcp_servers/lme_price/app/server.py`

注册 2 个工具，背后通过 Provider 策略模式支持多数据源：

```
LivePriceProvider（策略链，按顺序尝试）
  ├── HttpApiPriceProvider    ← 私有 API（需配置 BASE_URL + API_KEY）
  └── TradingEconomicsWebProvider  ← 公开网页抓取（默认可用）

CsvFixtureProvider           ← fixture 模式
```

#### 工具: get_price

```python
@mcp.tool()
async def get_price(commodity: str, date: str, benchmark: str | None = None) -> dict
```

获取某日某矿种的价格。

**fixture 模式** (`providers/fixture.py`):
- 读取 `data/fixtures/prices.csv`（30 天碳酸锂价格）
- 精确匹配日期；无精确匹配时取最近日期
- CSV 为空时，使用内置参数（base_price + 随机波动）生成确定性伪随机价格

**live 模式 - 私有 API** (`providers/live.py` → `HttpApiPriceProvider`):
- `GET {PRICE_LIVE_BASE_URL}/price?commodity=...&date=...&benchmark=...`
- Bearer token 认证
- 需要配置 `PRICE_LIVE_BASE_URL` + `PRICE_LIVE_API_KEY`

**live 模式 - 公开网页** (`providers/public_web.py` → `TradingEconomicsWebProvider`):
- 支持 5 种商品：copper, nickel, zinc, lithium_carbonate, iron_ore
- 抓取 `tradingeconomics.com/commodity/{name}` 页面
- 从 `<meta id="metaDesc">` 标签用正则提取：
  - 当前价格、货币、单位、日期
  - 日涨跌幅
- 解析 `TEChartsMeta` JS 变量获取基准名称

**返回格式**:
```json
{
  "commodity": "lithium_carbonate",
  "benchmark": "Lithium Carbonate 99.5% min",
  "date": "2026-06-23",
  "price": 97500.0,
  "currency": "CNY",
  "unit": "tonne",
  "price_type": "public_page_latest",
  "source": "tradingeconomics-public-web",
  "source_url": "https://tradingeconomics.com/commodity/lithium",
  "is_delayed": false,
  "is_demo": false,
  "warnings": ["Price was parsed from a public commodity webpage..."]
}
```

#### 工具: get_trend

```python
@mcp.tool()
async def get_trend(commodity: str, days: int = 30, benchmark: str | None = None) -> dict
```

获取价格趋势。

**fixture 模式**: 逐日调用 `get_price` 生成完整点序列，计算统计量。

**live 公开网页模式**:
- 没有完整历史 API，从页面描述文本重建趋势
- 正则匹配 "Over the past month, ... has fallen 3.5%" 或 "it is still 12% higher than a year ago"
- 根据请求天数与描述周期做比例缩放
- 反推 start_price = end_price / (1 + change_percent)
- 只有 2 个数据点（start, end），标记 `is_estimated: true`

**返回格式**:
```json
{
  "commodity": "lithium_carbonate",
  "benchmark": "Lithium Carbonate 99.5% min",
  "period": { "start": "2026-05-24", "end": "2026-06-23", "days": 30 },
  "start_price": 100515.46,
  "end_price": 97500.0,
  "change": -3015.46,
  "change_percent": -3.0,
  "min_price": 97500.0,
  "max_price": 100515.46,
  "currency": "CNY",
  "unit": "tonne",
  "points": [
    { "date": "2026-05-24", "price": 100515.46 },
    { "date": "2026-06-23", "price": 97500.0 }
  ],
  "source": "tradingeconomics-public-web",
  "is_estimated": true,
  "warnings": ["Trend was reconstructed from public 30-day summary..."]
}
```

---

## 6. MCP 通信机制

### 6.1 MCPClientManager

**文件**: `apps/daily_agent/app/mcp_client/manager.py`

管理 3 个 MCP Server 的生命周期和工具调用。

**连接建立**:

```python
async def connect_all(self):
    for name, cfg in SERVER_CONFIGS.items():
        # 1. 构造 stdio 启动参数
        params = StdioServerParameters(
            command="uv",
            args=["--directory", cfg["directory"], "run", "python", "-m", cfg["module"]],
        )
        # 2. 启动子进程，建立 stdin/stdout 通道
        ctx = stdio_client(params)
        read_stream, write_stream = await ctx.__aenter__()
        # 3. 在通道上建立 MCP 会话
        session = ClientSession(read_stream, write_stream)
        await session.__aenter__()
        # 4. MCP 协议握手
        await session.initialize()
```

每个 MCP Server 是一个 **子进程**，Agent 通过 stdin/stdout 的 JSON-RPC 协议与之通信。不需要 HTTP 端口、不需要手动启动 Server。

**工具调用**:

```python
async def call_tool(self, server: str, tool_name: str, arguments: dict) -> dict:
    session = self._sessions[server]
    result = await session.call_tool(tool_name, arguments)
    text = result.content[0].text        # MCP 返回的是 TextContent
    return json.loads(text)              # 解析为 Python dict
```

**调用链路图**:

```
Agent 进程                              MCP Server 子进程
    │                                        │
    │  ── stdin 写入 JSON-RPC ──────────►    │
    │  {                                     │
    │    "method": "tools/call",             │
    │    "params": {                         │
    │      "name": "search",                 │
    │      "arguments": {                    │
    │        "query": "Pilbara Minerals",    │
    │        "days": 1                       │
    │      }                                 │
    │    }                                   │
    │  }                                     │
    │                                        │  → @mcp.tool() search()
    │                                        │  → rss.py / fixture.py
    │                                        │
    │  ◄── stdout 返回 JSON-RPC ──────────   │
    │  {                                     │
    │    "content": [{                       │
    │      "type": "text",                   │
    │      "text": "{\"query\":...,          │
    │        \"items\":[...]}"               │
    │    }]                                  │
    │  }                                     │
```

**生命周期**: Agent.run() 开始时 `connect_all()`，结束时 `close()`。`close()` 按逆序退出所有 context manager（先关 session，再关 stdio transport，子进程随之终止）。

### 6.2 直接接入 Claude Desktop / Cursor

项目提供 `mcp-config.json`，用户可将其内容复制到 Claude Desktop 或 Cursor 的 MCP 配置中，直接在对话中使用三个工具：

```json
{
  "mcpServers": {
    "mining-news-mcp": {
      "command": "uv",
      "args": ["--directory", "D:/mineral-daily-agent/mcp_servers/mining_news",
               "run", "python", "-m", "app.server"]
    },
    "mineral-pdf-mcp": { ... },
    "lme-price-mcp": { ... }
  }
}
```

---

## 7. 共享包

### 7.1 contracts（数据契约）

**目录**: `packages/contracts/contracts/`

定义所有工具的输入/输出 Pydantic 模型和统一错误码：

- `tools.py`: 工具参数和返回值模型（SearchNewsInput/Output, ExtractResourcesInput/Output, GetPriceInput/Output 等）
- `evidence.py`: `EvidenceItem` 模型，evidence_type 限定为 `news | resource | price`
- `errors.py`: 统一错误码集合 + `ToolError` 模型

**统一错误码**:

| 错误码 | 含义 | 可重试 |
|--------|------|--------|
| NEWS_SEARCH_FAILED | 新闻搜索失败 | 是 |
| ARTICLE_PARSE_FAILED | 文章解析失败 | 是 |
| PDF_DOWNLOAD_FAILED | PDF 下载失败 | 是 |
| PDF_TOO_LARGE | PDF 超过 50MB | 否 |
| RESOURCE_TABLE_NOT_FOUND | 未找到资源量表 | 否 |
| UNSUPPORTED_COMMODITY | 不支持的矿种 | 否 |
| PRICE_NOT_FOUND | 未找到价格 | 否 |
| PRICE_PROVIDER_UNAVAILABLE | 价格服务不可用 | 是 |
| INVALID_ARGUMENT | 参数无效 | 否 |
| RATE_LIMITED | 频率限制 | 是 |
| INTERNAL_ERROR | 内部错误 | 是 |

### 7.2 common（共享工具库）

**目录**: `packages/common/common/`

- `config.py`: 项目根目录定位 + YAML 配置加载
- `http_client.py`: 安全 HTTP 客户端，内置 SSRF 防护（私有 IP 拦截、metadata 端点拦截）
- `retry.py`: 异步重试装饰器，指数退避（1s → 2s），最多 2 次重试
- `log.py`: 日志配置

---

## 8. 配置文件

### 8.1 project_registry.yaml

矿业项目注册表，是实体匹配的核心数据库。每个项目包含：

```yaml
pilgangoora:
  display_name: Pilgangoora Operation
  company: Pilbara Minerals
  aliases: [Pilbara, Pilbara lithium, Pilbara 锂矿, PLS, ...]
  commodities: [lithium]
  country: Australia
  region: Western Australia
  news_queries: ["Pilbara Minerals lithium", "Pilgangoora lithium"]
  price_benchmark:
    commodity: lithium_carbonate
    benchmark: configured_lithium_benchmark
  technical_reports:
    - title: "Pilbara Minerals Annual Report 2025"
      url: "https://pls.com/...pdf"
```

当前注册了 2 个项目：Pilgangoora（锂）和 Escondida（铜）。

### 8.2 commodity_mapping.yaml

矿种别名和基准价格映射，当前覆盖锂、铜、铁矿石。每种矿种包含多语言别名、基准价格名称、品位单位。

### 8.3 sources.yaml

数据源配置：RSS feed 列表、可抓取域名白名单、价格 Provider 优先级、PDF 提取参数（最大文件、最大页数、缓存目录）。

### 8.4 risk_rules.yaml

风险规则定义：规则 ID、触发条件、严重度、模板文本。

---

## 9. 验证系统

项目在多个层面实施验证，确保输出质量：

### 9.1 证据校验 (verify_evidence)

节点 6 对每条 evidence 执行字段完整性和数值合理性检查。

### 9.2 引用校验 (verification/citations.py)

```python
def verify_citations(markdown, evidence) -> list[str]:
```
- 报告中引用的 [N1] 是否在 evidence 列表中存在
- news evidence 是否有 source_url
- resource evidence 是否有 page_number
- price evidence 是否有 date 和 currency

### 9.3 数值校验 (verification/numbers.py)

```python
def verify_numbers(resource_rows) -> list[str]:
```
- ore_tonnage > 0 且 < 100,000 Mt
- grade > 0 且 < 100%
- contained_metal ≥ 0

### 9.4 结构校验 (verification/claims.py)

```python
def verify_report_structure(markdown) -> list[str]:
```
- 5 个必要章节（新闻摘要、储量数据、价格走势、风险提示、引用）是否都存在
- 正文中引用的 [N1] [R1] [P1] 是否在引用章节有对应条目

### 9.5 最终门控 (final_verify)

节点 9 执行上述检查的简化版本，发现问题在报告末尾追加警告而不阻断输出。

---

## 10. 数据模式切换

通过 `.env` 中的环境变量统一控制所有 MCP Server 的数据模式：

```env
NEWS_DATA_MODE=fixture|live     # 新闻
PDF_DATA_MODE=fixture|live      # PDF 储量
PRICE_DATA_MODE=fixture|live    # 价格
```

每个 MCP Server 启动时读取对应变量，决定使用 fixture provider 还是 live provider。未显式设置时，`APP_ENV=development` 默认 fixture，`APP_ENV=production` 默认 live。

| 模式 | 新闻来源 | 储量来源 | 价格来源 | 需要网络 |
|------|---------|---------|---------|---------|
| fixture | data/fixtures/news.json | data/fixtures/resources.json | data/fixtures/prices.csv | 否 |
| live | mining.com + miningweekly.com RSS | 真实 PDF 下载+解析 | tradingeconomics.com 抓取 | 是 |

---

## 11. 部署

### Docker

```bash
cp .env.example .env
docker compose up -d
```

Dockerfile 基于 `python:3.11-slim`，安装 `uv`，sync 所有子项目依赖。docker-compose 暴露 8000 端口，挂载 `data/reports` 和 `data/cache` 到宿主机。

### 本地开发

```powershell
uv sync
uv --directory ./mcp_servers/mining_news sync
uv --directory ./mcp_servers/mineral_pdf sync
uv --directory ./mcp_servers/lme_price sync
uv --directory ./apps/daily_agent sync

uv run python scripts/smoke_test.py
uv --directory ./apps/daily_agent run python -m app.cli "给我生成一份关于 Pilbara 锂矿的今日简报"
```

---

## 12. 完整数据流

```
用户: "给我生成一份关于 Pilbara 锂矿的今日简报"
  │
  ▼ [parse_query]
target_text="Pilbara 锂矿", news_days=1, price_days=30
  │
  ▼ [resolve_entity]
entity = Pilgangoora Operation / Pilbara Minerals / lithium
  │
  ▼ [build_plan]
plan.news.queries = ["Pilbara Minerals lithium", "Pilgangoora lithium"]
plan.resources.pdf_url = "https://pls.com/...pdf"
plan.price.commodity = "lithium_carbonate"
  │
  ▼ [fetch_data] ── asyncio.gather 并行 ──
  │                                        │                          │
  │ mining-news-mcp                        │ mineral-pdf-mcp          │ lme-price-mcp
  │ search("Pilbara Minerals lithium")     │ extract_resources(       │ get_price(
  │ search("Pilgangoora lithium")          │   pdf_url, hint)         │   "lithium_carbonate",
  │ fetch_article(url) × 5                 │                          │   "2026-06-24")
  │                                        │                          │ get_trend(
  │ → articles[5]                          │ → resource_rows[2]       │   "lithium_carbonate",
  │                                        │                          │   days=30)
  │                                        │                          │ → price_result, price_trend
  │
  ▼ [normalize]
evidence = [N1, N2, N3, N4, N5, R1, R2, P1, P2]
  │
  ▼ [verify_evidence]
标记 verification_issues，统计 { total: 9, with_issues: 1, clean: 8 }
  │
  ▼ [analyze_risks]
risks = [价格下跌 -3.0% (不触发高风险), demo 数据警告, ...]
  │
  ▼ [compose_report]
draft_markdown = "# Pilgangoora Operation / Pilbara Minerals 今日简报\n..."
  │
  ▼ [final_verify]
检查 5 个章节 + 引用一致性 → final_markdown
  │
  ▼
输出 Markdown 到终端 / API 响应 / data/reports/brief_20260624_143052.md
```
