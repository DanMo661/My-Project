#!/usr/bin/env python3
"""文献综述自动梳理多Agent系统 - 主入口（并行优化版）"""

import argparse
import json
import logging
import os
import sys

from config import AppConfig, ConfigError, MAX_WORKERS, FILTER_BATCH_SIZE, ANALYZER_BATCH_SIZE, ORGANIZER_MAX_ANALYSES, PROVIDER_PRESETS
from llm.client import LLMClient
from agents.coordinator import CoordinatorAgent
from agents.searcher import SearcherAgent
from agents.analyzer import AnalyzerAgent
from agents.organizer import OrganizerAgent
from agents.writer import WriterAgent
from agents.reviewer import ReviewerAgent
from pipeline import PipelineExecutor
from errors import (
    SurveyError, LLMError, LLMAuthError, LLMRateLimitError,
    LLMTimeoutError, LLMNetworkError, ValidationError,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("main")


def ensure_output_dir():
    """确保输出目录存在"""
    base = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(base, "output")
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def write_intermediate(data: dict, filename: str, output_dir: str):
    """保存中间结果"""
    path = os.path.join(output_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log.info(f"已保存: {path}")


def parse_args():
    provider_choices = list(PROVIDER_PRESETS.keys())
    parser = argparse.ArgumentParser(description="文献综述自动梳理系统")
    # 必填
    parser.add_argument("--topic", "-t", required=True, help="综述主题")
    # 可选
    parser.add_argument("--extra", "-e", default="", help="额外约束或关注点")
    parser.add_argument("--api-key", default=None,
                        help="API Key（也可用环境变量：<PROVIDER>_API_KEY 或 LLM_API_KEY）")
    parser.add_argument("--provider", "-p", default=None, choices=provider_choices,
                        help=f"LLM 提供商（也可设 LLM_PROVIDER 环境变量，默认 deepseek）")
    parser.add_argument("--model", "-m", default=None,
                        help="模型名称（也可用环境变量：<PROVIDER>_MODEL）")
    parser.add_argument("--base-url", default=None,
                        help="API Base URL（也可用环境变量：<PROVIDER>_BASE_URL）")
    parser.add_argument("--config-file", "-c", default=None,
                        help="配置文件路径（支持 YAML/JSON）")
    # 并行
    parser.add_argument("--workers", "-w", type=int, default=MAX_WORKERS, help="并行线程数（默认 4）")
    parser.add_argument("--sequential", "-s", action="store_true", help="强制顺序执行（禁用并行）")
    return parser.parse_args()


# ── 阶段索引常量 ──
STAGE_COORDINATE = 0
STAGE_SEARCH = 1
STAGE_FILTER = 2
STAGE_ANALYZE = 3
STAGE_ORGANIZE = 4
STAGE_WRITE = 5
STAGE_REVIEW = 6

STAGE_NAMES = [
    "协调员制定调研计划",
    "搜索员检索论文",
    "筛选相关论文",
    "分析员深度分析论文",
    "组织员聚类分类",
    "撰稿人撰写综述",
    "审校员质量检查",
]


def main():
    args = parse_args()

    print("=" * 60)
    print("  文献综述自动梳理系统（并行优化版）")
    print("=" * 60)

    # 从 CLI 参数构建配置
    try:
        app_config = AppConfig.from_sources({
            "provider": args.provider,
            "api_key": args.api_key,
            "model": args.model,
            "base_url": args.base_url,
            "config_file": args.config_file,
        })
        errors = app_config.validate()
        if errors:
            for e in errors:
                print(f"  配置警告: {e}")
            # Ollama 无 key 也允许通过
            fatal = [e for e in errors if "缺少 API Key" not in e]
            if fatal:
                raise ConfigError("\n".join(fatal))
    except ConfigError as e:
        print(f"\n配置错误:\n{e}")
        sys.exit(1)

    topic = args.topic
    extra = args.extra
    use_parallel = not args.sequential
    max_workers = max(1, args.workers)

    print(f"\n{'='*60}")
    print(f"  开始处理: {topic}")
    print(f"  并行模式: {'开启' if use_parallel else '关闭'}（{max_workers} 线程）")
    print(app_config.summary())
    print(f"{'='*60}\n")

    # 初始化 LLM 客户端
    llm = LLMClient(config=app_config)
    output_dir = ensure_output_dir()

    # 创建管道执行器
    pipeline = PipelineExecutor(max_workers=max_workers, stages=STAGE_NAMES)
    pipeline.install_signal_handler()

    try:
        # ---- Stage 1: 制定计划 ----
        pipeline.progress.start_stage(STAGE_COORDINATE, STAGE_NAMES[STAGE_COORDINATE])
        coordinator = CoordinatorAgent(llm)
        plan = coordinator.run(topic, extra)
        write_intermediate(plan, "01_plan.json", output_dir)
        sub_directions = plan.get("sub_directions", [])
        survey_structure = plan.get("survey_structure", [])
        pipeline.progress.finish_stage(
            STAGE_COORDINATE,
            f"{len(sub_directions)} 个子方向，{len(survey_structure)} 个章节",
        )

        if pipeline.cancelled:
            return

        # ---- Stage 2: 检索论文 ----
        pipeline.progress.start_stage(STAGE_SEARCH, STAGE_NAMES[STAGE_SEARCH])
        searcher = SearcherAgent(llm)
        raw_papers = searcher.run(sub_directions)
        pipeline.progress.finish_stage(STAGE_SEARCH, f"共 {len(raw_papers)} 篇")

        if not raw_papers:
            print("警告：未找到论文，请尝试换一组关键词。")
            return

        # ---- Stage 3: 筛选相关论文（可并行） ----
        if use_parallel and len(raw_papers) > FILTER_BATCH_SIZE:
            papers = searcher.filter_parallel(raw_papers, topic, pipeline, STAGE_FILTER)
        else:
            pipeline.progress.start_stage(STAGE_FILTER, STAGE_NAMES[STAGE_FILTER])
            papers = searcher.filter_relevant(raw_papers, topic)
            pipeline.progress.advance(STAGE_FILTER, 1)
            pipeline.progress.finish_stage(STAGE_FILTER)
        write_intermediate(papers, "02_papers.json", output_dir)

        if not papers:
            print("警告：筛选后无相关论文，请尝试换关键词。")
            return

        if pipeline.cancelled:
            return

        # ---- Stage 4: 分析论文（可并行） ----
        analyzer = AnalyzerAgent(llm)
        if use_parallel and len(papers) > ANALYZER_BATCH_SIZE:
            analyses = analyzer.analyze_parallel(papers, pipeline, STAGE_ANALYZE)
        else:
            pipeline.progress.start_stage(STAGE_ANALYZE, STAGE_NAMES[STAGE_ANALYZE], len(papers))
            analyses = analyzer.run(papers)
            pipeline.progress.finish_stage(STAGE_ANALYZE, f"{len(analyses)} 篇")
        write_intermediate(analyses, "03_analyses.json", output_dir)

        if pipeline.cancelled:
            return

        # ---- Stage 5: 聚类组织（可并行） ----
        organizer = OrganizerAgent(llm)
        if use_parallel and len(analyses) > ORGANIZER_MAX_ANALYSES:
            organized = organizer.organize_parallel(analyses, survey_structure, pipeline, STAGE_ORGANIZE)
        else:
            pipeline.progress.start_stage(STAGE_ORGANIZE, STAGE_NAMES[STAGE_ORGANIZE])
            organized = organizer.run(analyses, survey_structure)
            pipeline.progress.finish_stage(STAGE_ORGANIZE)
        write_intermediate(organized, "04_organized.json", output_dir)

        clusters = organized.get("clusters", [])
        research_gaps = organized.get("research_gaps", [])
        timeline = organized.get("timeline", [])

        if pipeline.cancelled:
            return

        # ---- Stage 6: 撰写综述 ----
        pipeline.progress.start_stage(STAGE_WRITE, STAGE_NAMES[STAGE_WRITE])
        writer = WriterAgent(llm)
        survey = writer.run(
            topic=topic,
            survey_structure=survey_structure,
            clusters=clusters,
            analyses=analyses,
            timeline=timeline,
            research_gaps=research_gaps,
        )
        draft_path = os.path.join(output_dir, "05_draft.md")
        with open(draft_path, "w", encoding="utf-8") as f:
            f.write(survey)
        pipeline.progress.finish_stage(STAGE_WRITE)

        if pipeline.cancelled:
            return

        # ---- Stage 7: 审校 ----
        pipeline.progress.start_stage(STAGE_REVIEW, STAGE_NAMES[STAGE_REVIEW])
        reviewer = ReviewerAgent(llm)
        review = reviewer.run(survey)
        write_intermediate(review, "06_review.json", output_dir)

        score = review.get("score")
        if score is not None:
            pipeline.progress.advance(STAGE_REVIEW, 1, f"评分 {score}/10")
        else:
            log.warning("审校结果解析失败，跳过评分")

        # 如果需要改进
        if score is not None and score < 7:
            pipeline.progress.advance(STAGE_REVIEW, 1, f"评分 {score} < 7，修改中...")
            survey = reviewer.refine(survey, review)

        pipeline.progress.finish_stage(STAGE_REVIEW)

        # 保存最终版
        final_path = os.path.join(output_dir, "07_final_survey.md")
        with open(final_path, "w", encoding="utf-8") as f:
            f.write(survey)

        # ---- 完成 ----
        pipeline.progress.summary()

        print(f"\n{'='*60}")
        print("  综述生成完成！")
        print(f"{'='*60}")
        print(f"\n输出文件:")
        print(f"  综述全文: {final_path}")
        print(f"  论文分析: {os.path.join(output_dir, '03_analyses.json')}")
        print(f"  聚类结果: {os.path.join(output_dir, '04_organized.json')}")
        print(f"\n共检索 {len(raw_papers)} 篇论文，分析 {len(analyses)} 篇，")
        print(f"聚类 {len(clusters)} 个类别，识别 {len(research_gaps)} 个研究空白。\n")

        # 成本摘要
        print(llm.cost_tracker.summary())

    except KeyboardInterrupt:
        print("\n\n用户中断，已停止。")
    except LLMAuthError as e:
        print(f"\n认证失败，请检查 API Key: {e}")
        log.error("LLM 认证错误", exc_info=True)
        sys.exit(2)
    except LLMRateLimitError as e:
        print(f"\nAPI 限流，请稍后重试: {e}")
        log.error("LLM 限流", exc_info=True)
        sys.exit(3)
    except LLMTimeoutError as e:
        print(f"\n请求超时，请检查网络: {e}")
        log.error("LLM 超时", exc_info=True)
        sys.exit(4)
    except LLMNetworkError as e:
        print(f"\n网络连接失败: {e}")
        log.error("LLM 网络错误", exc_info=True)
        sys.exit(4)
    except LLMError as e:
        print(f"\nLLM 调用失败: {e}")
        log.error("LLM 错误", exc_info=True)
        sys.exit(5)
    except ValidationError as e:
        print(f"\n输入数据验证失败: {e}")
        log.error("验证错误", exc_info=True)
        sys.exit(6)
    except SurveyError as e:
        print(f"\n系统错误: {e}")
        log.error("系统错误", exc_info=True)
        sys.exit(10)
    finally:
        pipeline.uninstall_signal_handler()
        # 即使中断也打印成本摘要
        if hasattr(llm, 'cost_tracker') and llm.cost_tracker.call_count > 0:
            print(llm.cost_tracker.summary())


if __name__ == "__main__":
    main()
