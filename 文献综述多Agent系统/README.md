# 文献综述多Agent系统

基于多 Agent 协作的科研综述自动生成系统。给定研究主题，自动完成：制定调研计划 → 检索论文 → 深度分析 → 聚类分类 → 撰写综述 → 质量审查。

## 快速开始

```bash
pip install -r requirements.txt
python main.py --topic "你的研究主题" --api-key YOUR_KEY
```

也可通过环境变量传入 API Key：`export DEEPSEEK_API_KEY=your_key`

## CLI 参数

| 参数 | 缩写 | 必填 | 说明 |
|------|------|------|------|
| `--topic` | `-t` | 是 | 综述研究主题 |
| `--extra` | `-e` | 否 | 额外约束或关注点 |
| `--api-key` | | 否 | DeepSeek API Key（优先级高于环境变量） |

## 架构

6 个 Agent 顺序执行：

| 阶段 | Agent | 功能 |
|------|-------|------|
| 1 | Coordinator | 拆解主题为子方向 + 规划章节结构 |
| 2 | Searcher | 检索 Semantic Scholar + ArXiv，LLM 过滤相关性 |
| 3 | Analyzer | 逐篇分析方法、贡献、局限性 |
| 4 | Organizer | 聚类分类 + 时间线 + 识别研究空白 |
| 5 | Writer | 撰写中文综述（带编号引用） |
| 6 | Reviewer | 6 维度评分，低于 7 分自动修改 |

所有 Agent 继承 `agents/base.py` 中的 `BaseAgent` 基类。

## 配置

硬编码参数集中在 `config.py`，包括 batch size、token 上限、API 超时等。修改参数不需改 Agent 代码。

## 依赖

仅 `requests` 一个外部依赖（LLM 和论文搜索均为 HTTP API）。

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

## 项目结构

```
文献综述多Agent系统/
├── main.py              ← 主入口
├── config.py            ← 全局配置
├── requirements.txt     ← 依赖列表
├── agents/              ← Agent 实现
│   ├── base.py          ← 基类
│   ├── coordinator.py   ← 协调器
│   ├── searcher.py      ← 搜索器
│   ├── analyzer.py      ← 分析器
│   ├── organizer.py     ← 组织器
│   ├── writer.py        ← 撰写器
│   └── reviewer.py      ← 审阅器
├── llm/                 ← LLM 客户端
│   └── client.py
└── tools/               ← 工具集
    └── paper_search.py  ← 论文检索
```

## 技术栈

- **Python**: 核心实现
- **DeepSeek API**: LLM 服务
- **Semantic Scholar**: 论文数据库
- **ArXiv**: 预印本检索

---

## 许可证

MIT License
