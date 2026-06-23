# Mining Daily Brief Agent - 本地运行指南

## 目标

这份文档只覆盖本地运行，不包含 Docker 部署。

当前项目已经可以在本地完成以下链路：

- `mining-news-mcp`：新闻搜索与正文抓取
- `mineral-pdf-mcp`：真实 PDF 下载与资源量抽取
- `lme-price-mcp`：真实价格获取
- `daily_agent`：汇总新闻、资源量、价格并输出 Markdown 简报

## 环境要求

- Python 3.11+
- `uv`
- Node.js 18+
  仅在使用 MCP Inspector 时需要

## 运行模式

通过 `.env` 统一控制三类数据源：

```env
NEWS_DATA_MODE=fixture|live
PDF_DATA_MODE=fixture|live
PRICE_DATA_MODE=fixture|live
```

推荐用法：

- 本地快速演示：三个都用 `fixture`
- 半真实演示：`NEWS_DATA_MODE=live`、`PDF_DATA_MODE=live`、`PRICE_DATA_MODE=live`
- 调试单个模块：只切换目标模块为 `live`

说明：

- `NEWS_DATA_MODE=live` 会真实抓 RSS 和文章正文
- `PDF_DATA_MODE=live` 会真实下载 PDF 并抽取资源量
- `PRICE_DATA_MODE=live` 会优先调用私有价格 API；如果未配置，则回退到公开价格网页抓取

## 5 分钟快速启动

### 1. 准备环境变量

```powershell
cd D:\mineral-daily-agent
copy .env.example .env
```

建议先用下面这份最小配置：

```env
APP_ENV=development
LOG_LEVEL=INFO

LLM_PROVIDER=openai
LLM_API_KEY=
LLM_MODEL=gpt-4o-mini
LLM_BASE_URL=

NEWS_DATA_MODE=fixture
PDF_DATA_MODE=fixture
PRICE_DATA_MODE=fixture

PRICE_LIVE_BASE_URL=
PRICE_LIVE_API_KEY=
PRICE_LIVE_TIMEOUT_SECONDS=30
PRICE_PUBLIC_WEB_ENABLED=1
PRICE_PUBLIC_WEB_TIMEOUT_SECONDS=30
```

说明：

- 不填 `LLM_API_KEY` 也能跑完整流程
- 未配置 LLM 时，PDF 结构化和报告摘要会使用降级逻辑
- `PRICE_PUBLIC_WEB_ENABLED=1` 时，价格服务可直接抓公开 commodity 页面
- 如果你有自己的价格接口，再补 `PRICE_LIVE_BASE_URL` 和 `PRICE_LIVE_API_KEY`

### 2. 安装依赖

```powershell
uv sync
uv --directory ./mcp_servers/lme_price sync
uv --directory ./mcp_servers/mining_news sync
uv --directory ./mcp_servers/mineral_pdf sync
uv --directory ./apps/daily_agent sync
```

### 3. 跑 smoke test

```powershell
uv run python scripts/smoke_test.py
```

预期结果：

- 能发现 3 个 MCP Server
- 能完成 3 次 `tools/call`
- 输出 `Overall: ALL PASSED`

### 4. 跑 Agent CLI

```powershell
uv --directory ./apps/daily_agent run python -m app.cli "给我生成一份关于 Pilbara 锂矿的今日简报"
```

输出结果：

- 终端打印 Markdown 简报
- 同时保存到 `data/reports/`

### 5. 跑 Agent API

```powershell
uv --directory ./apps/daily_agent run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

接口文档：

```text
http://127.0.0.1:8000/docs
```

请求示例：

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/briefs ^
  -H "Content-Type: application/json" ^
  -d "{\"query\":\"给我生成一份关于 Pilbara 锂矿的今日简报\",\"news_days\":1,\"price_days\":30}"
```

## 单独验证 MCP Server

### 新闻服务

```powershell
uv --directory ./mcp_servers/mining_news run python -m app.server
```

### PDF 服务

```powershell
uv --directory ./mcp_servers/mineral_pdf run python -m app.server
```

### 价格服务

```powershell
uv --directory ./mcp_servers/lme_price run python -m app.server
```

### 用 MCP Inspector 验证

```powershell
npx @modelcontextprotocol/inspector uv --directory ./mcp_servers/lme_price run python -m app.server
```

## Claude Desktop / Cursor 接入

把 [mcp-config.json](D:/mineral-daily-agent/mcp-config.json) 的内容复制到：

- Claude Desktop：`%APPDATA%\Claude\claude_desktop_config.json`
- Cursor：`Settings -> MCP Servers`

当前 `mcp-config.json` 已支持：

- `NEWS_DATA_MODE`
- `PDF_DATA_MODE`
- `PRICE_DATA_MODE`
- `LLM_*`
- `PRICE_LIVE_*`
- `PRICE_PUBLIC_WEB_*`

## 当前真实数据链路

### Pilbara 资源量文档

当前项目已切到可访问的官方文档：

- `https://pls.com/wp-content/uploads/2025/08/2025AnnualReportincorporatingAppendix4E.pdf`

当前 live 抽取已能从该文档第 32 页提取出：

- `Indicated 349.0 Mt @ 1.29 % Li2O`
- `Inferred 70.0 Mt @ 1.25 % Li2O`

### 价格 live 模式

`PRICE_DATA_MODE=live` 时的优先顺序：

1. 私有价格 API
2. 公开价格网页抓取

公开网页抓取当前已验证可用：

- Lithium
- Copper
- Nickel

说明：

- 当前“最新价格”是真实网页抓取
- 当前“价格趋势”是根据公开网页摘要重建的近似结果，不是完整历史 API 序列

## 已验证命令

### 全本地 fixture

```powershell
uv run python scripts/smoke_test.py
```

### 真实价格 + 真实 PDF + fixture 新闻

```powershell
$env:APP_ENV='production'
$env:NEWS_DATA_MODE='fixture'
$env:PDF_DATA_MODE='live'
$env:PRICE_DATA_MODE='live'
$env:PRICE_PUBLIC_WEB_ENABLED='1'
uv --directory ./apps/daily_agent run python -m app.cli "给我生成一份关于 Pilbara 锂矿的今日简报"
```

### 半真实全链路

```powershell
$env:APP_ENV='production'
$env:NEWS_DATA_MODE='live'
$env:PDF_DATA_MODE='live'
$env:PRICE_DATA_MODE='live'
$env:PRICE_PUBLIC_WEB_ENABLED='1'
uv --directory ./apps/daily_agent run python -m app.cli "给我生成一份关于 Pilbara 锂矿的今日简报"
```

## 常见问题

| 问题 | 处理方式 |
| --- | --- |
| `uv` 不存在 | 安装 `uv`，例如 `winget install astral-sh.uv` |
| `smoke_test.py` 失败 | 先执行根目录和各子项目的 `uv sync` |
| Agent 连不上 MCP | 不要手动先起服务，Agent 会通过 stdio 自动拉起 |
| 新闻 live 没结果 | 先确认最近 1 天内是否真的有相关公开新闻，可调大 `news_days` |
| PDF live 没结果 | 先确认 URL 可访问，再检查目标文档是否包含资源量表 |
| 价格 live 报不可用 | 先确认 `PRICE_PUBLIC_WEB_ENABLED=1` 或补齐私有价格 API 配置 |
| 报告里价格趋势带“近似结果” | 这是当前公开网页抓取模式的正常行为，不是报错 |

## 当前已知限制

- 价格趋势不是完整历史 API，只是公开网页摘要重建
- PDF 抽取目前已适配 Pilbara 年报版式，但还不是通用多公司版式引擎
- `fixture` 仍然保留，用于无外部依赖时的稳定演示

## 建议演示顺序

1. 先跑 `smoke_test.py`
2. 再跑 Agent CLI
3. 最后打开 FastAPI `/docs`
4. 如果需要，再用 Claude Desktop / Cursor 挂载 `mcp-config.json`
