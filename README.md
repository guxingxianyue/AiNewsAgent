# AiNewsAgent

AiNewsAgent 是一个本地运行的每日 AI 前沿情报 agent。它会读取 arXiv 上最新的 AI/CS 论文，完成去重、排序和筛选后，调用兼容 OpenAI 接口的 Mimo 大模型生成中文简报，并写入 `reports/YYYY-MM-DD.md`。

## 安装

```bash
python -m pip install -e ".[dev]"
cp examples/config.example.yaml config.yaml
cp examples/.env.example .env
```

也可以直接运行初始化向导：

```bash
ainewsagent init
```

它会创建或补全 `config.yaml`、`.env`，并准备 `reports/`、`data/` 目录。

配置 Mimo API。你可以编辑 `.env`：

```dotenv
MIMO_API_KEY=your-mimo-api-key
MIMO_BASE_URL=https://your-mimo-compatible-endpoint
MIMO_MODEL=your-model-name
```

也可以继续使用系统环境变量。AiNewsAgent 启动时会自动读取项目根目录下的 `.env`，但不会覆盖已经存在的系统环境变量。

## 使用

```bash
ainewsagent init
ainewsagent doctor
ainewsagent preview
ainewsagent run-once
ainewsagent web
ainewsagent install-schedule
```

`run-once` 会立即抓取 arXiv 内容，并生成当天的中文 Markdown 简报。

`doctor` 会检查配置、Mimo 环境变量和 arXiv API 连通性。

`preview` 会只抓取和排序候选内容，不调用 Mimo，也不会生成报告，适合调试每天会选中哪些内容。

`web` 会启动本地 Web 页面，默认访问地址是 `http://127.0.0.1:8000`，可以查看今日简报、历史简报、候选内容和运行历史。

`install-schedule` 会创建一个 macOS LaunchAgent，使用当前项目目录作为工作目录，每天 Asia/Shanghai 时间 08:00 自动运行。

## 配置

编辑 `config.yaml`：

```yaml
arxiv_categories:
  - cs.AI
  - cs.LG
  - cs.CL
  - cs.CV
  - cs.RO
  - cs.HC
  - cs.SE
max_items: 15
timezone: Asia/Shanghai
output_dir: reports
data_dir: data
arxiv_max_results: 80
interests:
  - AI Agent
  - LLM 推理
  - 多模态
  - AI 编程
  - 开源模型
avoid_topics:
  - 纯营销
  - 金融炒作
reading_level: technical
```

字段说明：

- `arxiv_categories`：要抓取的 arXiv 分类。
- `max_items`：每天最终精选条数，默认 15。
- `timezone`：定时和报告日期使用的时区。
- `output_dir`：简报输出目录。
- `data_dir`：SQLite 数据库和已读状态文件目录。
- `arxiv_max_results`：每次从 arXiv 拉取的最大候选数量。
- `interests`：你最关心的 AI 方向，会影响模型评分和入选排序。
- `avoid_topics`：你想降低权重的主题。
- `reading_level`：阅读深度，推荐 `technical`，也可以使用 `product` 或 `executive`。

## 项目结构

```text
examples/         # 示例配置文件
ainewsagent/
  application/      # 应用编排流程，例如 run-once pipeline
  domain/           # 核心领域模型，例如 Item、Source
  infrastructure/   # 配置、状态文件、系统定时任务
  interfaces/       # CLI 和 Web 入口
  services/         # LLM、排序去重、报告生成等业务服务
  sources/          # 外部信息源读取，例如 arXiv
```

入口：

```bash
ainewsagent run-once
python -m ainewsagent run-once
```

## 调试命令

初始化项目：

```bash
ainewsagent init
```

检查当前环境：

```bash
ainewsagent doctor
```

预览候选内容：

```bash
ainewsagent preview
```

预览时包含已经读过的内容：

```bash
ainewsagent preview --include-seen
```

指定其他 `.env` 文件：

```bash
ainewsagent --env-file .env.local run-once
```

## Web 页面

启动本地 Web 服务：

```bash
ainewsagent web
```

然后访问：

```text
http://127.0.0.1:8000
```

页面包含：

- 今日/最新简报
- 历史日期切换
- 候选内容列表，支持关键词、来源、主题、重要性和读者类型过滤
- 运行历史和失败原因
- “立即更新”按钮
- Markdown 简报 HTML 渲染
- 每条入选内容的规则分、模型分、主题和入选理由

如果需要换端口：

```bash
ainewsagent web --port 8080
```

## 输出

每天生成一篇 Markdown 简报：

```text
reports/YYYY-MM-DD.md
```

同时会写入 SQLite 数据库：

```text
data/ainewsagent.db
```

SQLite 会保存：

- 每次运行的状态、时间、报告路径和失败原因
- 每日简报内容
- 入选候选内容
- 每条内容的规则分、模型分、总分、主题和入选理由
- 每条内容的重要性等级、适合读者和标签

简报包含：

- 今日重点
- arXiv 论文精选
- 交叉趋势/观察
- 原始链接列表

已读论文 ID 会保存在 `data/seen.json`，用于减少重复内容。

## 筛选流程

AiNewsAgent 使用两阶段筛选：

1. 本地规则先按来源、新鲜度、关键词和分类打分，筛出较大的候选池。
2. Mimo 再结合 `interests`、`avoid_topics` 和 `reading_level` 做重要性评分、主题归类、读者类型、标签和入选理由生成。
3. 最终简报使用带评分和理由的候选内容生成，Web 页面也会展示这些解释信息。

## 趋势追踪

Web 页面会基于 SQLite 中最近 7 天的入选内容统计高频主题，显示在页面顶部：

```text
近 7 天趋势：智能体 · 6，多模态 · 4，AI 编程 · 3
```

这个趋势来自每天入选内容的主题标签，能帮助你快速看到连续热点。
