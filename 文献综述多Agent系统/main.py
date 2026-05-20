#!/usr/bin/env python3
"""文献综述自动梳理多Agent系统 - 主入口"""

import argparse
import json
import logging
import os
import sys

from llm.client import LLMClient
from agents.coordinator import CoordinatorAgent
from agents.searcher import SearcherAgent
from agents.analyzer import AnalyzerAgent
from agents.organizer import OrganizerAgent
from agents.writer import WriterAgent
from agents.reviewer import ReviewerAgent

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
    parser = argparse.ArgumentParser(description="文献综述自动梳理系统")
    parser.add_argument("--topic", "-t", required=True, help="综述主题")
    parser.add_argument("--extra", "-e", default="", help="额外约束或关注点")
    parser.add_argument("--api-key", default=None, help="DeepSeek API Key（也可设 DEEPSEEK_API_KEY 环境变量）")
    return parser.parse_args()


def main():
    args = parse_args()

    print("=" * 60)
    print("  文献综述自动梳理系统")
    print("=" * 60)

    # 配置
    api_key = args.api_key or os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        print("错误：需要 API Key。用 --api-key 传入或设置 DEEPSEEK_API_KEY 环境变量。")
        sys.exit(1)

    topic = args.topic
    extra = args.extra

    print(f"\n{'='*60}")
    print(f"  开始处理: {topic}")
    print(f"{'='*60}\n")

    # 初始化
    llm = LLMClient(api_key=api_key)
    output_dir = ensure_output_dir()

    # ---- Stage 1: 制定计划 ----
    print("[1/6] 📋 协调员制定调研计划...")
    coordinator = CoordinatorAgent(llm)
    plan = coordinator.run(topic, extra)
    write_intermediate(plan, "01_plan.json", output_dir)

    sub_directions = plan.get("sub_directions", [])
    survey_structure = plan.get("survey_structure", [])
    print(f"     计划完成：{len(sub_directions)} 个子方向，{len(survey_structure)} 个章节\n")

    # ---- Stage 2: 检索论文 ----
    print("[2/6] 🔍 搜索员检索论文...")
    searcher = SearcherAgent(llm)
    raw_papers = searcher.run(sub_directions)

    print(f"     筛选相关论文...")
    papers = searcher.filter_relevant(raw_papers, topic)
    write_intermediate(papers, "02_papers.json", output_dir)
    print(f"     最终保留 {len(papers)} 篇\n")

    if not papers:
        print("警告：未找到相关论文，请尝试换一组关键词。")
        sys.exit(1)

    # ---- Stage 3: 分析论文 ----
    print("[3/6] 📖 分析员深度分析论文...")
    analyzer = AnalyzerAgent(llm)
    analyses = analyzer.run(papers)
    write_intermediate(analyses, "03_analyses.json", output_dir)
    print(f"     分析完成：{len(analyses)} 篇\n")

    # ---- Stage 4: 聚类组织 ----
    print("[4/6] 🗂️  组织员聚类分类...")
    organizer = OrganizerAgent(llm)
    organized = organizer.run(analyses, survey_structure)
    write_intermediate(organized, "04_organized.json", output_dir)

    clusters = organized.get("clusters", [])
    research_gaps = organized.get("research_gaps", [])
    timeline = organized.get("timeline", [])
    print(f"     聚类完成：{len(clusters)} 个类别\n")

    # ---- Stage 5: 撰写综述 ----
    print("[5/6] ✍️  撰稿人撰写综述...")
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
    print(f"     初稿完成：{draft_path}\n")

    # ---- Stage 6: 审校 ----
    print("[6/6] ✅ 审校员质量检查...")
    reviewer = ReviewerAgent(llm)
    review = reviewer.run(survey)
    write_intermediate(review, "06_review.json", output_dir)

    print(f"\n     评分: {review.get('score', 'N/A')}/10")
    for issue in review.get("major_issues", [])[:3]:
        print(f"     - {issue}")

    # 如果需要改进
    score = review.get("score")
    if score is None:
        log.warning("审校结果解析失败，跳过评分")
    elif score < 7:
        print(f"\n     评分 {score} 低于7分，正在根据审稿意见修改...")
        survey = reviewer.refine(survey, review)

    # 保存最终版
    final_path = os.path.join(output_dir, "07_final_survey.md")
    with open(final_path, "w", encoding="utf-8") as f:
        f.write(survey)
    print(f"\n     最终版已保存: {final_path}")

    # ---- 完成 ----
    print(f"\n{'='*60}")
    print("  综述生成完成！")
    print(f"{'='*60}")
    print(f"\n输出文件:")
    print(f"  📄 综述全文: {final_path}")
    print(f"  📊 论文分析: {os.path.join(output_dir, '03_analyses.json')}")
    print(f"  🗂️  聚类结果: {os.path.join(output_dir, '04_organized.json')}")
    print(f"\n共检索 {len(raw_papers)} 篇论文，分析 {len(analyses)} 篇，")
    print(f"聚类 {len(clusters)} 个类别，识别 {len(research_gaps)} 个研究空白。\n")


if __name__ == "__main__":
    main()
