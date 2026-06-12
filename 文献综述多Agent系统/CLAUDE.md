# 文献综述自动梳理多Agent系统

基于多 Agent 协作的科研领域综述自动生成系统。

## 架构

7 个阶段按依赖关系执行（全部继承 `agents/base.py:BaseAgent`）：
1. **Coordinator** — 制定调研计划，拆解子方向
2. **Searcher** — 检索论文（Semantic Scholar + ArXiv），串行（受 API 限流）
3. **Searcher.filter** — LLM 过滤相关性（可并行：多批次并发）
4. **Analyzer** — 逐篇深度分析（可并行：多批次并发，失败单篇重试）
5. **Organizer** — 聚类分类 + 识别研究空白（可并行：分批聚类并发，>30 篇自动分批）
6. **Writer** — 撰写综述初稿（>40 篇按 cluster 采样）
7. **Reviewer** — 质量审查 + 改进（长综述自动分段审阅，按 ## 拆分）

### 并行化策略

- 阶段 1→2→3→4→5→6→7 严格顺序（数据依赖）
- 阶段 3/4/5 内部的 LLM 批次互相独立，通过 `ThreadPoolExecutor` 并行执行
- 统一接口：所有 Agent 的 `run()` 方法接受可选 `pipeline` 参数
  - 传入 pipeline → 自动并行
  - 不传 → 顺序执行
- I/O 密集型（HTTP → LLM API），线程池比进程池更合适
- 单项数据时自动退化为顺序执行，无线程开销

### 依赖关系图

```
Coordinator → Searcher.run → filter_papers → Analyzer.run(pipeline)
                                                    ↓
                          Organizer.run(pipeline) → Writer → Reviewer
```

### 断点续跑

每个阶段完成后自动写 checkpoint.json 到 output/ 目录。使用 `--resume` 参数可从上次中断处恢复：

```bash
python main.py --topic "主题" --api-key KEY --resume
```

### 阶段耗时统计

ProgressTracker 自动记录每阶段耗时，结束时打印耗时占比，便于定位性能瓶颈。

## 关键模块

- `config.py` — 灵活配置系统（多 LLM 提供商预设、环境变量、YAML/JSON 配置文件、CLI 参数）
- `errors.py` — 标准化错误类型层次结构
- `progress.py` — 线程安全进度追踪器（进度条 + 阶段计时 + 耗时占比）
- `pipeline.py` — 并行管道执行器（线程池 + Ctrl+C 优雅终止 + 取消传播）
- `llm/client.py` — 多提供商 LLM 封装（OpenAI 兼容 / Anthropic / Ollama）
- `llm/rate_limiter.py` — 令牌桶限流器（RPM/RPD/TPM 多维限流）
- `llm/cost_tracker.py` — 会话级成本追踪器（Token 统计 + 费用估算）
- `tools/paper_search.py` — Semantic Scholar + ArXiv 检索（DOI/title/URL 多维去重）

## 配置穿透

所有 Agent 接收 `AppConfig` 对象，通过 `self._cfg(key)` 访问配置，不再依赖模块级常量。

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

# 从断点恢复
python main.py -t "主题" --api-key KEY --resume

# 顺序执行（调试用）
python main.py -t "主题" --api-key KEY --sequential
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

CLI 参数：`--topic/-t`（必填）、`--extra/-e`（可选约束）、`--api-key`（可选）、`--provider/-p`（可选）、`--model/-m`（可选）、`--base-url`（可选）、`--config-file/-c`（可选）、`--workers/-w`（可选，默认 4）、`--sequential/-s`（可选）、`--resume/-r`（可选）

## Web 界面

启动 Web 服务后通过浏览器操作：

```bash
python web/server.py
# 打开 http://localhost:8080
```

- 输入主题、点击开始 → 自动执行全流程，实时显示进度日志
- 执行完成后自动展示结果：综述全文、论文列表、聚类分析、审校报告
- 支持 SSE 实时进度推送

## 输出

output/ 目录下生成：
- 01_plan.json — 调研计划
- 02_papers.json — 论文列表
- 03_analyses.json — 分析结果
- 04_organized.json — 聚类与研究空白
- 05_draft.md — 初稿
- 06_review.json — 审校意见
- 07_final_survey.md — 终稿
- checkpoint.json — 断点文件（正常完成后自动清除）

## 注意事项

- LLM 返回解析失败时各 Agent 有容错（不会静默吞错误）
- Analyzer 失败时自动重试单篇论文，不跳过整批
- Reviewer 对长综述自动分段审阅（按 ## 标题拆分），合并评分
- 论文去重支持 DOI + 标题 + URL 三维去重
- 所有硬编码参数集中在 `config.py`，通过 AppConfig 穿透到各 Agent
- Ctrl+C 信号：第一次优雅终止（等待进行中的线程），第二次强制退出
- 并行线程数受 LLM API 并发限制，建议不超过 4
- 断点续跑：使用 `--resume` 从 checkpoint.json 恢复
