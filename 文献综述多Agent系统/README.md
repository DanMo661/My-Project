# 文献综述多Agent系统

基于多 Agent 协作的科研综述自动生成系统。给定研究主题，自动完成：制定调研计划 → 检索论文 → 深度分析 → 聚类分类 → 撰写综述 → 质量审查。

## 快速开始

```bash
pip install -r requirements.txt
python main.py --topic "你的研究主题" --api-key YOUR_KEY
```

也可通过环境变量传入 API Key：`export DEEPSEEK_API_KEY=your_key`

## Web 界面

```bash
python web/server.py
# 打开 http://localhost:8080
```

- 输入主题、点击开始 → 自动执行全流程，实时显示进度日志
- 执行完成后自动展示结果：综述全文、论文列表、聚类分析、审校报告
- 支持 SSE 实时进度推送

## CLI 参数

| 参数 | 缩写 | 必填 | 说明 |
|------|------|------|------|
| `--topic` | `-t` | 是 | 综述研究主题 |
| `--extra` | `-e` | 否 | 额外约束或关注点 |
| `--api-key` | | 否 | API Key（优先级高于环境变量） |
| `--provider` | `-p` | 否 | LLM 提供商（默认 deepseek） |
| `--model` | `-m` | 否 | 模型名称 |
| `--base-url` | | 否 | API Base URL |
| `--config-file` | `-c` | 否 | 配置文件路径（YAML/JSON） |
| `--workers` | `-w` | 否 | 并行线程数（默认 4） |
| `--sequential` | `-s` | 否 | 强制顺序执行 |
| `--resume` | `-r` | 否 | 从上次中断的断点恢复执行 |

## 架构

7 个 Agent 顺序执行，阶段 3/4/5 内部可并行：

| 阶段 | Agent | 功能 |
|------|-------|------|
| 1 | Coordinator | 拆解主题为子方向 + 规划章节结构 |
| 2 | Searcher | 检索 Semantic Scholar + ArXiv |
| 3 | Searcher.filter | LLM 过滤相关性（可并行） |
| 4 | Analyzer | 逐篇分析方法、贡献、局限性（可并行，失败单篇重试） |
| 5 | Organizer | 聚类分类 + 时间线 + 识别研究空白（可并行） |
| 6 | Writer | 撰写中文综述（带编号引用） |
| 7 | Reviewer | 6 维度评分，低于 7 分自动修改（长综述分段审阅） |

所有 Agent 继承 `agents/base.py` 中的 `BaseAgent` 基类，通过 `AppConfig` 获取配置。

## 配置

配置系统支持多来源（优先级：CLI > 环境变量 > 配置文件 > 默认值）：

- `config.py` — 全局配置，多 LLM 提供商预设
- 硬编码参数集中在 `config.py`，通过 `AppConfig` 穿透到各 Agent
- 配置文件支持 YAML/JSON 格式

## 依赖

仅 `requests`、`openai`、`pyyaml` 三个外部依赖。

## 输出

运行后在 `output/` 目录生成：

| 文件 | 内容 |
|------|------|
| `01_plan.json` | 调研计划 |
| `02_papers.json` | 检索到的论文 |
| `03_analyses.json` | 逐篇分析 |
| `04_organized.json` | 聚类与研究空白 |
| `05_draft.md` | 综述初稿 |
| `06_review.json` | 审校意见 |
| `07_final_survey.md` | 最终综述 |
| `checkpoint.json` | 断点文件（正常完成后自动清除） |

## 项目结构

```
文献综述多Agent系统/
├── main.py              ← 主入口（阶段函数 + 断点续跑）
├── config.py            ← 全局配置（AppConfig 数据类）
├── pipeline.py          ← 并行管道执行器
├── progress.py          ← 进度追踪器（阶段耗时统计）
├── errors.py            ← 错误类型层次
├── requirements.txt     ← 依赖列表
├── agents/              ← Agent 实现
│   ├── base.py          ← 基类（config 穿透）
│   ├── coordinator.py   ← 协调器
│   ├── searcher.py      ← 搜索器（统一并行/顺序）
│   ├── analyzer.py      ← 分析器（单篇重试）
│   ├── organizer.py     ← 组织器（统一并行/顺序）
│   ├── writer.py        ← 撰写器
│   └── reviewer.py      ← 审阅器（分段审阅）
├── llm/                 ← LLM 客户端
│   ├── client.py
│   ├── rate_limiter.py
│   └── cost_tracker.py
├── tools/               ← 工具集
│   └── paper_search.py  ← 论文检索（多维去重）
└── web/                 ← Web 界面
    ├── server.py        ← Flask 后端（SSE 实时进度）
    └── static/
        ├── index.html   ← 前端页面
        ├── style.css    ← 暗色主题样式
        └── app.js       ← 前端逻辑
```

## 核心特性

- **Web 界面**：暗色主题，实时进度日志，结果多标签浏览
- **断点续跑**：`--resume` 从 checkpoint 恢复，不浪费已完成的 API 调用
- **统一并行**：所有 Agent 的 `run()` 接受可选 `pipeline` 参数，传入即并行
- **单篇重试**：Analyzer 批次失败时自动重试单篇论文
- **分段审阅**：Reviewer 对长综述按 `##` 标题拆分审阅，合并评分
- **多维去重**：论文按 DOI + 标题 + URL 三维去重
- **阶段耗时**：自动统计每阶段耗时和占比，定位瓶颈
- **配置穿透**：AppConfig 统一管理，不再依赖模块级常量

---

## 许可证

MIT License
