#!/usr/bin/env python3
"""文献综述自动梳理多Agent系统 - 主入口（并行优化版）"""

import argparse
import json
import logging
import os
import sys

from config import AppConfig, ConfigError, PROVIDER_PRESETS
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

STAGE_NAMES = [
    "协调员制定调研计划",
    "搜索员检索论文",
    "筛选相关论文",
    "分析员深度分析论文",
    "组织员聚类分类",
    "撰稿人撰写综述",
    "审校员质量检查",
]

CHECKPOINT_FILE = "checkpoint.json"


def ensure_output_dir():
    base = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(base, "output")
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def write_json(data, filename, output_dir):
    path = os.path.join(output_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log.info(f"已保存: {path}")


def read_json(filename, output_dir):
    path = os.path.join(output_dir, filename)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_checkpoint(output_dir, stage, data):
    path = os.path.join(output_dir, CHECKPOINT_FILE)
    checkpoint = {"completed_stage": stage, "data": data}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, ensure_ascii=False, indent=2)
    log.info(f"断点已保存: 阶段 {stage}")


def load_checkpoint(output_dir):
    path = os.path.join(output_dir, CHECKPOINT_FILE)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def clear_checkpoint(output_dir):
    path = os.path.join(output_dir, CHECKPOINT_FILE)
    if os.path.exists(path):
        os.remove(path)


def parse_args():
    provider_choices = list(PROVIDER_PRESETS.keys())
    parser = argparse.ArgumentParser(description="文献综述自动梳理系统")
    parser.add_argument("--topic", "-t", required=True, help="综述主题")
    parser.add_argument("--extra", "-e", default="", help="额外约束或关注点")
    parser.add_argument("--api-key", default=None, help="API Key")
    parser.add_argument("--provider", "-p", default=None, choices=provider_choices,
                        help=f"LLM 提供商（默认 deepseek）")
    parser.add_argument("--model", "-m", default=None, help="模型名称")
    parser.add_argument("--base-url", default=None, help="API Base URL")
    parser.add_argument("--config-file", "-c", default=None, help="配置文件路径")
    parser.add_argument("--workers", "-w", type=int, default=4, help="并行线程数（默认 4）")
    parser.add_argument("--sequential", "-s", action="store_true", help="强制顺序执行")
    parser.add_argument("--resume", "-r", action="store_true",
                        help="从上次中断的断点恢复执行")
    return parser.parse_args()


def run_stage_coordinate(pipeline, llm, config, topic, extra, output_dir):
    STAGE = 0
    pipeline.progress.start_stage(STAGE, STAGE_NAMES[STAGE])
    coordinator = CoordinatorAgent(llm, config)
    plan = coordinator.run(topic, extra)
    write_json(plan, "01_plan.json", output_dir)
    sub_directions = plan.get("sub_directions", [])
    survey_structure = plan.get("survey_structure", [])
    pipeline.progress.finish_stage(
        STAGE, f"{len(sub_directions)} 个子方向，{len(survey_structure)} 个章节",
    )
    save_checkpoint(output_dir, STAGE, {
        "plan": plan,
        "sub_directions": sub_directions,
        "survey_structure": survey_structure,
    })
    return plan, sub_directions, survey_structure


def run_stage_search(pipeline, llm, config, sub_directions, output_dir):
    STAGE = 1
    pipeline.progress.start_stage(STAGE, STAGE_NAMES[STAGE])
    searcher = SearcherAgent(llm, config)
    raw_papers = searcher.run(sub_directions)
    pipeline.progress.finish_stage(STAGE, f"共 {len(raw_papers)} 篇")
    if not raw_papers:
        return None
    save_checkpoint(output_dir, STAGE, {"raw_papers": raw_papers})
    return raw_papers


def run_stage_filter(pipeline, llm, config, raw_papers, topic, use_parallel, output_dir):
    STAGE = 2
    searcher = SearcherAgent(llm, config)
    if use_parallel:
        papers = searcher.filter_papers(raw_papers, topic, pipeline, STAGE)
    else:
        pipeline.progress.start_stage(STAGE, STAGE_NAMES[STAGE])
        papers = searcher.filter_papers(raw_papers, topic)
        pipeline.progress.advance(STAGE, 1)
        pipeline.progress.finish_stage(STAGE)
    write_json(papers, "02_papers.json", output_dir)
    if not papers:
        return None
    save_checkpoint(output_dir, STAGE, {"papers": papers})
    return papers


def run_stage_analyze(pipeline, llm, config, papers, use_parallel, output_dir):
    STAGE = 3
    analyzer = AnalyzerAgent(llm, config)
    if use_parallel:
        analyses = analyzer.run(papers, pipeline, STAGE)
    else:
        pipeline.progress.start_stage(STAGE, STAGE_NAMES[STAGE], len(papers))
        analyses = analyzer.run(papers)
        pipeline.progress.finish_stage(STAGE, f"{len(analyses)} 篇")
    write_json(analyses, "03_analyses.json", output_dir)
    save_checkpoint(output_dir, STAGE, {"analyses": analyses})
    return analyses


def run_stage_organize(pipeline, llm, config, analyses, survey_structure, use_parallel, output_dir):
    STAGE = 4
    organizer = OrganizerAgent(llm, config)
    if use_parallel:
        organized = organizer.run(analyses, survey_structure, pipeline, STAGE)
    else:
        pipeline.progress.start_stage(STAGE, STAGE_NAMES[STAGE])
        organized = organizer.run(analyses, survey_structure)
        pipeline.progress.finish_stage(STAGE)
    write_json(organized, "04_organized.json", output_dir)
    save_checkpoint(output_dir, STAGE, {"organized": organized})
    return organized


def run_stage_write(pipeline, llm, config, topic, survey_structure,
                    clusters, analyses, timeline, research_gaps, output_dir):
    STAGE = 5
    pipeline.progress.start_stage(STAGE, STAGE_NAMES[STAGE])
    writer = WriterAgent(llm, config)
    survey = writer.run(
        topic=topic, survey_structure=survey_structure,
        clusters=clusters, analyses=analyses,
        timeline=timeline, research_gaps=research_gaps,
    )
    draft_path = os.path.join(output_dir, "05_draft.md")
    with open(draft_path, "w", encoding="utf-8") as f:
        f.write(survey)
    pipeline.progress.finish_stage(STAGE)
    save_checkpoint(output_dir, STAGE, {"survey": survey})
    return survey


def run_stage_review(pipeline, llm, config, survey, output_dir):
    STAGE = 6
    pipeline.progress.start_stage(STAGE, STAGE_NAMES[STAGE])
    reviewer = ReviewerAgent(llm, config)
    review = reviewer.run(survey)
    write_json(review, "06_review.json", output_dir)

    score = review.get("score")
    if score is not None:
        pipeline.progress.advance(STAGE, 1, f"评分 {score}/10")
    else:
        log.warning("审校结果解析失败，跳过评分")

    if score is not None and score < 7:
        pipeline.progress.advance(STAGE, 1, f"评分 {score} < 7，修改中...")
        survey = reviewer.refine(survey, review)

    pipeline.progress.finish_stage(STAGE)
    return survey


def main():
    args = parse_args()

    print("=" * 60)
    print("  文献综述自动梳理系统（并行优化版）")
    print("=" * 60)

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
    print(f"  断点恢复: {'是' if args.resume else '否'}")
    print(app_config.summary())
    print(f"{'='*60}\n")

    llm = LLMClient(config=app_config)
    output_dir = ensure_output_dir()
    pipeline = PipelineExecutor(max_workers=max_workers, stages=STAGE_NAMES)
    pipeline.install_signal_handler()

    try:
        checkpoint = None
        start_stage = 0

        if args.resume:
            checkpoint = load_checkpoint(output_dir)
            if checkpoint:
                start_stage = checkpoint["completed_stage"] + 1
                print(f"\n  从阶段 {start_stage + 1} 恢复执行（上次完成到阶段 {checkpoint['completed_stage'] + 1}）")
            else:
                print("\n  未找到断点，从头开始执行")

        plan = sub_directions = survey_structure = None
        raw_papers = papers = analyses = None
        organized = survey = None

        if start_stage <= 0:
            plan, sub_directions, survey_structure = run_stage_coordinate(
                pipeline, llm, app_config, topic, extra, output_dir)
        elif checkpoint:
            data = checkpoint["data"]
            plan = data.get("plan")
            sub_directions = data.get("sub_directions", [])
            survey_structure = data.get("survey_structure", [])
            if not sub_directions:
                saved_plan = read_json("01_plan.json", output_dir)
                if saved_plan:
                    plan = saved_plan
                    sub_directions = saved_plan.get("sub_directions", [])
                    survey_structure = saved_plan.get("survey_structure", [])

        if pipeline.cancelled:
            return

        if start_stage <= 1:
            raw_papers = run_stage_search(pipeline, llm, app_config, sub_directions, output_dir)
            if raw_papers is None:
                print("警告：未找到论文，请尝试换一组关键词。")
                return
        elif checkpoint:
            data = checkpoint["data"]
            raw_papers = data.get("raw_papers", [])
            if not raw_papers:
                saved_papers = read_json("02_papers.json", output_dir)
                if saved_papers:
                    raw_papers = saved_papers

        if pipeline.cancelled:
            return

        if start_stage <= 2:
            papers = run_stage_filter(pipeline, llm, app_config, raw_papers, topic, use_parallel, output_dir)
            if papers is None:
                print("警告：筛选后无相关论文，请尝试换关键词。")
                return
        elif checkpoint:
            data = checkpoint["data"]
            papers = data.get("papers", [])
            if not papers:
                saved_papers = read_json("02_papers.json", output_dir)
                if saved_papers:
                    papers = saved_papers

        if pipeline.cancelled:
            return

        if start_stage <= 3:
            analyses = run_stage_analyze(pipeline, llm, app_config, papers, use_parallel, output_dir)
        elif checkpoint:
            data = checkpoint["data"]
            analyses = data.get("analyses", [])
            if not analyses:
                saved_analyses = read_json("03_analyses.json", output_dir)
                if saved_analyses:
                    analyses = saved_analyses

        if pipeline.cancelled:
            return

        if start_stage <= 4:
            organized = run_stage_organize(
                pipeline, llm, app_config, analyses, survey_structure, use_parallel, output_dir)
        elif checkpoint:
            data = checkpoint["data"]
            organized = data.get("organized", {})

        clusters = organized.get("clusters", [])
        research_gaps = organized.get("research_gaps", [])
        timeline = organized.get("timeline", [])

        if pipeline.cancelled:
            return

        if start_stage <= 5:
            survey = run_stage_write(
                pipeline, llm, app_config, topic, survey_structure,
                clusters, analyses, timeline, research_gaps, output_dir)
        elif checkpoint:
            data = checkpoint["data"]
            survey = data.get("survey", "")

        if pipeline.cancelled:
            return

        if start_stage <= 6:
            survey = run_stage_review(pipeline, llm, app_config, survey, output_dir)

        final_path = os.path.join(output_dir, "07_final_survey.md")
        with open(final_path, "w", encoding="utf-8") as f:
            f.write(survey)

        clear_checkpoint(output_dir)
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
        if hasattr(llm, 'cost_tracker') and llm.cost_tracker.call_count > 0:
            print(llm.cost_tracker.summary())


if __name__ == "__main__":
    main()
