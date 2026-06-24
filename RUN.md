# Mining Daily Brief Agent — 运行指南

## 项目简介

矿业每日简报自动生成系统。输入一句自然语言查询，自动汇总新闻、储量、价格数据，输出结构化 Markdown 简报。

```text
给我生成一份关于 Pilbara 锂矿的今日简报
```

输出包含 6 个章节：结论摘要、新闻摘要、储量数据、价格走势、风险提示、引用源链接。

技术架构详见 [docs/architecture.md](docs/architecture.md)。

## 环境要求

| 依赖 | 用途 | 安装 |
|------|------|------|
| Docker Desktop | Docker 方式运行（推荐） | `winget install Docker.DockerDesktop` |
| Python 3.11+ | 本地方式运行 | — |
| uv | 本地方式的包管理 | `winget install astral-sh.uv` |
| Node.js 18+ | 仅 MCP Inspector 调试时需要 | — |

## 数据模式

通过 `.env` 统一控制三个数据源的模式：

```env
NEWS_DATA_MODE=fixture|live
PDF_DATA_MODE=fixture|live
PRICE_DATA_MODE=fixture|live
```

| 模式 | 新闻 | 储量 | 价格 | 需要网络 |
|------|------|------|------|---------|
| fixture | `data/fixtures/news.json` | `data/fixtures/resources.json` | `data/fixtures/prices.csv` | 否 |
| live | MINING.COM + Mining Technology RSS | 真实 PDF 下载 + 解析 | TradingEconomics 网页抓取 | 是 |

当前 `.env.example` 默认为 **live 模式**，不需要私有 API。

## 网络要求

live 模式依赖公开网站抓取。如果需要代理：

**本地运行**：

```powershell
$env:HTTP_PROXY='http://127.0.0.1:7897'
$env:HTTPS_PROXY='http://127.0.0.1:7897'
```

**Docker 运行**：在 `.env` 中添加：

```env
HTTP_PROXY=http://host.docker.internal:7897
HTTPS_PROXY=http://host.docker.internal:7897
```

`httpx` 会自动读取这两个环境变量。

---

## 快速启动

### 方式 1：Docker（推荐）

```powershell
cd D:\mineral-daily-agent
copy .env.example .env          # 按需编辑代理等配置
docker compose up -d            # 首次构建约 3-5 分钟
```

启动后：

| 地址 | 说明 |
|------|------|
| http://127.0.0.1:8000/docs | Swagger API 文档 |
| http://127.0.0.1:8000/api/v1/health | 健康检查 |

生成简报：

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/briefs ^
  -H "Content-Type: application/json" ^
  -d "{\"query\":\"给我生成一份关于 Pilbara 锂矿的今日简报\",\"news_days\":1,\"price_days\":30}"
```

报告持久化到宿主机 `data/reports/` 目录（通过 volume 挂载）。

停止：

```powershell
docker compose down
```

重新构建（代码有改动后）：

```powershell
docker compose up -d --build
```

### 方式 2：本地直接运行

#### 1. 准备配置

```powershell
cd D:\mineral-daily-agent
copy .env.example .env
```

#### 2. 安装依赖

```powershell
uv sync
uv --directory ./mcp_servers/mining_news sync
uv --directory ./mcp_servers/mineral_pdf sync
uv --directory ./mcp_servers/lme_price sync
uv --directory ./apps/daily_agent sync
```

#### 3. 冒烟测试

```powershell
uv run python scripts/smoke_test.py
```

预期输出：发现 3 个 MCP Server、完成 3 次 `tools/call`、`Overall: ALL PASSED`。

#### 4. 跑 Agent CLI

```powershell
uv --directory ./apps/daily_agent run python -m app.cli "给我生成一份关于 Pilbara 锂矿的今日简报"
```

终端输出 Markdown 简报，同时保存到 `data/reports/`。

#### 5. 跑 Agent API

```powershell
uv --directory ./apps/daily_agent run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Swagger 文档：http://127.0.0.1:8000/docs

---

## 单独验证 MCP Server

每个 MCP Server 可独立启动（stdio 模式）：

```powershell
uv --directory ./mcp_servers/mining_news run python -m app.server    # 新闻
uv --directory ./mcp_servers/mineral_pdf run python -m app.server    # PDF
uv --directory ./mcp_servers/lme_price run python -m app.server      # 价格
```

用 MCP Inspector 调试（需要 Node.js）：

```powershell
npx @modelcontextprotocol/inspector uv --directory ./mcp_servers/lme_price run python -m app.server
```

## Claude Desktop / Cursor 接入

项目提供了 `mcp-config.json`，包含三个 MCP Server 的配置。

使用方式：

- **Claude Desktop**：复制内容到 `%APPDATA%\Claude\claude_desktop_config.json`
- **Cursor**：粘贴到 `Settings → MCP Servers`

注意：配置中的路径是 `D:/mineral-daily-agent/...`，克隆到其他目录时需替换。

---

## 已验证的 live 链路

### 新闻

当前 RSS 源：

- MINING.COM — `https://www.mining.com/feed/`
- Mining Technology — `https://www.mining-technology.com/feed/`

搜索后对命中文章用 trafilatura 抓取正文。

空结果自动回退：如果 `news_days=1` 无结果，自动扩展到 3 天，再无结果扩展到 7 天。

### PDF / 储量

Pilbara 已验证的公开 PDF：

```
https://pls.com/wp-content/uploads/2025/08/2025AnnualReportincorporatingAppendix4E.pdf
```

live 抽取结果：

- Indicated 349.0 Mt @ 1.29 % Li2O
- Inferred 70.0 Mt @ 1.25 % Li2O

提取流程：表格解析 → 正文正则 → LLM 结构化（三级降级）。

### 价格

公开网页源：`https://tradingeconomics.com/commodity/lithium`

可获取：最新价格快照 + 近 30 天趋势重建。趋势为基于网页摘要的近似值，非完整历史序列。

支持的矿种：copper、nickel、zinc、lithium_carbonate、iron_ore。

### 输出示例

报告中的引用带真实链接：

```markdown
- [R1] Technical Report p.32 — https://pls.com/.../2025AnnualReport...pdf
- [P1] 2026-06-23 lithium_carbonate, CNY/tonne — https://tradingeconomics.com/commodity/lithium
```

---

## 运行模式参考命令

### 全链路 live

```powershell
$env:NEWS_DATA_MODE='live'
$env:PDF_DATA_MODE='live'
$env:PRICE_DATA_MODE='live'
$env:PRICE_PUBLIC_WEB_ENABLED='1'
uv --directory ./apps/daily_agent run python -m app.cli "给我生成一份关于 Pilbara 锂矿的今日简报"
```

### 纯 fixture 快速演示

```powershell
$env:NEWS_DATA_MODE='fixture'
$env:PDF_DATA_MODE='fixture'
$env:PRICE_DATA_MODE='fixture'
uv --directory ./apps/daily_agent run python -m app.cli "给我生成一份关于 Pilbara 锂矿的今日简报"
```

---

## 已知限制

- 价格趋势来自公开网页摘要重建，不是交易所完整历史 API
- 新闻 live 受 RSS 更新频率影响，某些天可能为空（会自动扩展到 7 天）
- PDF 抽取对 Pilbara 年报版式效果最好，其他公司版式可能不稳定
- 外网受限时必须配置代理，否则 live 模式会失败

## 常见问题

| 问题 | 处理 |
|------|------|
| `uv` 不存在 | `winget install astral-sh.uv` |
| `docker` 不存在 | `winget install Docker.DockerDesktop`，安装后重启 |
| smoke test 失败 | 确认已执行所有 `uv sync` |
| live 没有新闻 | 确认代理生效 + 最近是否有相关新闻；可调大 `news_days` |
| live 没有价格 | 确认 `PRICE_DATA_MODE=live` + `PRICE_PUBLIC_WEB_ENABLED=1` + 代理可访问 tradingeconomics.com |
| live 没有储量 | 确认 PDF URL 可访问 + 代理正常 |
| Docker 构建慢 | 首次需下载依赖，后续构建有缓存；也可用 `docker compose up -d --build` 强制重建 |
| Docker 内无法访问外网 | 在 `.env` 中加 `HTTP_PROXY=http://host.docker.internal:端口` |
