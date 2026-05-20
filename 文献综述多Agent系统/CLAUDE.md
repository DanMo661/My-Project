# 文献综述自动梳理多Agent系统

基于多 Agent 协作的科研领域综述自动生成系统。

## 架构

6 个 Agent 顺序执行（全部继承 `agents/base.py:BaseAgent`）：
1. **Coordinator** — 制定调研计划，拆解子方向
2. **Searcher** — 检索论文（Semantic Scholar + ArXiv），LLM 过滤相关性
3. **Analyzer** — 逐篇深度分析
4. **Organizer** — 聚类分类 + 识别研究空白（>30 篇自动分批）
5. **Writer** — 撰写综述初稿（>40 篇按 cluster 采样）
6. **Reviewer** — 质量审查 + 改进（审阅前 20000 字）

## 关键模块

- `config.py` — 全局配置常量（batch size、token 上限、超时等）
- `llm/client.py` — DeepSeek API 封装 + `check_structured()` 错误检查工具
- `tools/paper_search.py` — Semantic Scholar + ArXiv 检索

## 运行

```bash
pip install -r requirements.txt
python main.py --topic "研究主题" --api-key YOUR_KEY
# 或 set DEEPSEEK_API_KEY=YOUR_KEY && python main.py -t "主题"
```

CLI 参数：`--topic/-t`（必填）、`--extra/-e`（可选约束）、`--api-key`（可选）

## 输出

output/ 目录下生成：
- 01_plan.json — 调研计划
- 02_papers.json — 论文列表
- 03_analyses.json — 分析结果
- 04_organized.json — 聚类与研究空白
- 05_draft.md — 初稿
- 06_review.json — 审校意见
- 07_final_survey.md — 终稿

## 注意事项

- LLM 返回解析失败时各 Agent 有容错（不会静默吞错误）
- OrganizerAgent 和 WriterAgent 有上下文溢出保护
- 所有硬编码参数集中在 `config.py`，修改参数不需改 Agent 代码
