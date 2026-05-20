# 文献综述自动梳理多Agent系统

基于多 Agent 协作的科研领域综述自动生成系统。

## 架构

6个 Agent 顺序执行：
1. **Coordinator** — 制定调研计划，拆解子方向
2. **Searcher** — 检索论文（Semantic Scholar + ArXiv）
3. **Analyzer** — 逐篇深度分析
4. **Organizer** — 聚类分类 + 识别研究空白
5. **Writer** — 撰写综述初稿
6. **Reviewer** — 质量审查 + 改进

## 运行

```bash
set DEEPSEEK_API_KEY=你的key
python main.py
```

或运行后按提示输入 key。

## 依赖

- requests（仅此一个，LLM 和搜索全是 HTTP API）

## 输出

output/ 目录下生成：
- 01-04: 中间过程 JSON
- 05_draft.md: 初稿
- 06_review.json: 审校意见
- 07_final_survey.md: 终稿
