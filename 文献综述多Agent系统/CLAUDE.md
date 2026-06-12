# 文献综述自动梳理多Agent系统

基于多 Agent 协作的科研领域综述自动生成系统。

## 架构

7 个阶段按依赖关系执行（全部继承 `agents/base.py:BaseAgent`）：
1. **Coordinator** — 制定调研计划，拆解子方向
2. **Searcher** — 检索论文（Semantic Scholar + ArXiv），串行（受 API 限流）
3. **Searcher.filter** — LLM 过滤相关性（可并行：多批次并发）
4. **Analyzer** — 逐篇深度分析（可并行：多批次并发）
5. **Organizer** — 聚类分类 + 识别研究空白（可并行：分批聚类并发，>30 篇自动分批）
6. **Writer** — 撰写综述初稿（>40 篇按 cluster 采样）
7. **Reviewer** — 质量审查 + 改进（审阅前 20000 字）

### 并行化策略

- 阶段 1→2→3→4→5→6→7 严格顺序（数据依赖）
- 阶段 3/4/5 内部的 LLM 批次互相独立，通过 `ThreadPoolExecutor` 并行执行
- I/O 密集型（HTTP → LLM API），线程池比进程池更合适
- 单项数据时自动退化为顺序执行，无线程开销

### 依赖关系图

```
Coordinator → Searcher.run → filter_parallel → Analyzer.analyze_parallel
                                                    ↓
                          Organizer.organize_parallel → Writer → Reviewer
```

## 关键模块

- `config.py` — 灵活配置系统（多 LLM 提供商预设、环境变量、YAML/JSON 配置文件、CLI 参数）
- `errors.py` — 标准化错误类型层次结构
- `progress.py` — 线程安全进度追踪器（进度条 + 阶段计时）
- `pipeline.py` — 并行管道执行器（线程池 + Ctrl+C 优雅终止 + 取消传播）
- `llm/client.py` — 多提供商 LLM 封装（OpenAI 兼容 / Anthropic / Ollama）
- `llm/rate_limiter.py` — 令牌桶限流器（RPM/RPD/TPM 多维限流）
- `llm/cost_tracker.py` — 会话级成本追踪器（Token 统计 + 费用估算）
- `tools/paper_search.py` — Semantic Scholar + ArXiv 检索

## 运行

```bash
pip install -r requirements.txt

# 最简用法（默认 DeepSeek）
python main.py --topic "研究主题" --api-key YOUR_KEY
# 或 set DEEPSEEK_API_KEY=YOUR_KEY && python main.py -t "主题"

# 指定其他提供商
python main.py -t "主题" --provider openai --api-key YOUR_KEY
python main.py -t "主题" --provider moonshot --model moonshot-v1-128k
python main.py -t "主题" --provider ollama  # 本地模型，无需 key

# 使用配置文件
python main.py -t "主题" -c litreview.yml
```

### LLM 提供商

预设提供商（`--provider`）：`deepseek`(默认)、`openai`、`moonshot`、`zhipu`、`qwen`、`siliconflow`、`ollama`、`anthropic`、`custom`

环境变量命名规则（以 `deepseek` 为例）：
- `DEEPSEEK_API_KEY` — API Key
- `DEEPSEEK_BASE_URL` — Base URL
- `DEEPSEEK_MODEL` — 模型名

通用环境变量（覆盖所有提供商）：
- `LLM_API_KEY`、`LLM_MODEL`、`LLM_PROVIDER`
- `LLM_TIMEOUT`、`LLM_MAX_TOKENS`、`LLM_MAX_RETRIES`

### 配置文件格式（YAML 示例）

```yaml
provider: deepseek
app:
  search_max_results: 8
  cost_tracking: true
  cost_alert_threshold_usd: 5.0
```

CLI 参数：`--topic/-t`（必填）、`--extra/-e`（可选约束）、`--api-key`（可选）、`--provider/-p`（可选）、`--model/-m`（可选）、`--base-url`（可选）、`--config-file/-c`（可选）、`--workers/-w`（可选，默认 4）、`--sequential/-s`（可选）

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
- Ctrl+C 信号：第一次优雅终止（等待进行中的线程），第二次强制退出
- 并行线程数受 LLM API 并发限制，建议不超过 4
