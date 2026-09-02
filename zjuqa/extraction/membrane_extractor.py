"""
membrane_extractor.py —— 膜参数提取（S2 阶段）。

对每个已识别的膜名称，构建多模态消息（文本 + 页面图片），
调用多模态 LLM 提取该膜的所有参数，以单膜粒度版本化保存。

使用说明：
    from zjuqa.extraction.membrane_extractor import extract_paper, extract_all
    # 单篇提取（自动跳过已提取的膜）
    extract_paper("Test_1")
    # 批量提取（自动扫描所有已识别膜名的论文）
    extract_all(mode="skip")
"""

import json
from typing import List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from ..utils.path_utils import get_meta_path, get_parsed_text
from ..llm_client.client import get_llm
from ..schemas.membrane import MembraneData
from ..utils.storage.membrane_repository import (
    aggregate_paper,
    is_membrane_extracted,
    save_membrane_version,
)
from ..utils.image import load_images_for_paper
from ..utils.logging import get_logger
from ..utils.progress import ProgressBar
from ..utils.scanner import scan_identified_papers
from . import prompts
from .membrane_identifier import read_membrane_ids

logger = get_logger(__name__)


# ====================================================================
# LLM 提取核心
# ====================================================================

def membrane_paras_refit(raw_text: str) -> str:
    """
    当 LLM 首次输出非标准 JSON 时，调用纯文本 LLM 进行二次格式化。

    Args:
        raw_text: LLM 首次返回的非标准文本

    Returns:
        格式化后的 JSON 字符串；失败时返回空字符串
    """
    llm = get_llm(llm_type="refit")
    messages = [
        SystemMessage(content=prompts.REFIT_SYSTEM),
        HumanMessage(content=f"需要格式化的原始输出：\n{raw_text}"),
    ]
    try:
        response = llm.invoke(messages)
        return response.content.strip()
    except Exception as e:
        logger.warning(f"refit 格式化调用失败: {e}")
        return ""


def get_membrane_params(
    membrane_id: str,
    paper_text: str,
    image_contents: List[dict],
) -> Optional[MembraneData]:
    """
    对单个膜调用多模态 LLM 提取参数。

    流程：构建多模态消息 → 调用 LLM → 解析 JSON → 失败时 refit 重试。

    Args:
        membrane_id:    膜名称
        paper_text:     论文全文文本
        image_contents: 页面图片的多模态内容列表

    Returns:
        提取成功返回 MembraneData，失败返回 None
    """
    llm = get_llm(llm_type="extractor")
    system_msg = SystemMessage(content=prompts.EXTRACT_SYSTEM)
    human_msg = HumanMessage(
        content=prompts.build_extract_human(membrane_id, paper_text, image_contents)
    )

    try:
        response = llm.invoke([system_msg, human_msg])
        raw = response.content.strip()

        # 尝试直接解析 JSON
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.info(f"{membrane_id}: JSON 解析失败，尝试 refit 格式化...")
            refitted = membrane_paras_refit(raw)
            try:
                data = json.loads(refitted)
            except json.JSONDecodeError:
                logger.warning(f"{membrane_id}: refit 后仍无法解析，跳过")
                return None

        # 用 Pydantic 校验（ValueUnit 格式自动解析）
        try:
            membrane = MembraneData(**data)
            return membrane
        except ValidationError as e:
            logger.info(f"{membrane_id}: 数据校验失败，尝试 refit: {e}")
            refitted = membrane_paras_refit(raw)
            try:
                data = json.loads(refitted)
                membrane = MembraneData(**data)
                return membrane
            except (json.JSONDecodeError, ValidationError):
                logger.warning(f"{membrane_id}: refit 后校验仍失败，跳过")
                return None
    except Exception as e:
        logger.error(f"{membrane_id}: LLM 调用异常: {e}", exc_info=True)
        return None


# ====================================================================
# 单篇/批量处理
# ====================================================================

def extract_paper(
    paper_name: str,
    mode: str = "skip",
    max_images: int = 40,
    do_aggregate: bool = True,
    show_progress: bool = True,
) -> dict:
    """
    对单篇论文的所有膜执行参数提取。

    每个膜提取后立即保存（单膜粒度 checkpoint），异常中断时已完成的膜不丢失。
    mode="skip" 时跳过已有提取结果的膜。

    Args:
        paper_name:    论文名称
        mode:
            "skip" ：跳过已提取的膜（默认，避免重复计算）
            "force"：全部重新提取，覆盖已有版本
        max_images:    最大图片数量
        do_aggregate:  提取完成后是否执行均值聚合
        show_progress: 是否显示膜级别进度条（被 extract_all 调用时设为 False）

    Returns:
        统计字典 {"total": 膜总数, "extracted": 新提取数, "skipped": 跳过数, "failed": 失败数}
    """
    # 读取膜名称列表
    meta_path = get_meta_path(paper_name)
    if not meta_path.exists():
        logger.warning(f"跳过 {paper_name}: meta.json 不存在，请先运行膜名称识别")
        return {"total": 0, "extracted": 0, "skipped": 0, "failed": 0}

    membrane_ids = read_membrane_ids(paper_name, mode="c")
    if not membrane_ids:
        logger.warning(f"跳过 {paper_name}: 膜名称列表为空")
        return {"total": 0, "extracted": 0, "skipped": 0, "failed": 0}

    # 加载论文文本和图片（整篇论文共享，避免重复加载）
    text_path = get_parsed_text(paper_name)
    if not text_path.exists():
        logger.warning(f"跳过 {paper_name}: 解析文本不存在")
        return {"total": 0, "extracted": 0, "skipped": 0, "failed": 0}

    with open(text_path, "r", encoding="utf-8") as f:
        paper_text = f.read()

    image_contents = load_images_for_paper(paper_name, max_images=max_images)
    logger.info(f"{paper_name}: 共 {len(membrane_ids)} 种膜，mode={mode}")

    extracted = 0
    skipped = 0
    failed = 0

    # 膜级别进度条（单独调用 extract_paper 时显示）
    bar = ProgressBar(total=len(membrane_ids), prefix=f"提取[{paper_name}]") if show_progress else None
    if bar:
        bar.__enter__()

    try:
        for i, membrane_id in enumerate(membrane_ids, start=1):
            if bar:
                bar.update(i, item=membrane_id, action="提取中")

            # mode="skip"：已有提取结果则跳过
            if mode == "skip" and is_membrane_extracted(paper_name, membrane_id):
                logger.info(f"跳过 {membrane_id}（已提取）")
                skipped += 1
                continue

            logger.info(f"正在提取: {membrane_id}")
            result = get_membrane_params(membrane_id, paper_text, image_contents)
            if result is not None:
                save_membrane_version(paper_name, membrane_id, result)
                extracted += 1
            else:
                logger.warning(f"{membrane_id}: 提取失败")
                failed += 1
    finally:
        if bar:
            bar.__exit__(None, None, None)

    # 聚合
    if do_aggregate and (extracted > 0 or skipped > 0):
        aggregate_paper(paper_name, save=True)

    stats = {
        "total": len(membrane_ids),
        "extracted": extracted,
        "skipped": skipped,
        "failed": failed,
    }
    logger.info(
        f"{paper_name} 完成: 总计 {stats['total']}, "
        f"新提取 {stats['extracted']}, 跳过 {stats['skipped']}, 失败 {stats['failed']}"
    )
    return stats


def extract_all(
    mode: str = "skip",
    papers: Optional[List[str]] = None,
    max_images: int = 40,
) -> dict:
    """
    批量提取所有论文的膜参数。

    Args:
        mode:
            "skip" ：跳过已提取的膜（默认）
            "force"：全部重新提取
        papers:     指定论文名列表，None 时自动扫描 data/identified/
        max_images: 最大图片数量

    Returns:
        统计字典 {"total_papers": 论文数, "total_membranes": 膜总数, ...}
    """
    # 自动扫描
    if papers is None:
        papers = scan_identified_papers()

    if not papers:
        print("[提取] 未找到已识别膜名的论文，请先运行膜名称识别")
        return {"total_papers": 0, "total_membranes": 0}

    print(f"[提取] 发现 {len(papers)} 篇已识别论文，mode={mode}")

    total_membranes = 0
    total_extracted = 0
    total_skipped = 0
    total_failed = 0

    # 论文级别进度条
    with ProgressBar(total=len(papers), prefix="提取") as bar:
        for i, paper_name in enumerate(papers, start=1):
            bar.update(i, item=paper_name, action="提取膜参数")
            stats = extract_paper(
                paper_name, mode=mode, max_images=max_images, show_progress=False
            )
            total_membranes += stats["total"]
            total_extracted += stats["extracted"]
            total_skipped += stats["skipped"]
            total_failed += stats["failed"]

    summary = {
        "total_papers": len(papers),
        "total_membranes": total_membranes,
        "total_extracted": total_extracted,
        "total_skipped": total_skipped,
        "total_failed": total_failed,
    }
    print(
        f"[提取] 全部完成: 论文 {summary['total_papers']}, "
        f"膜 {summary['total_membranes']}, "
        f"新提取 {summary['total_extracted']}, "
        f"跳过 {summary['total_skipped']}, "
        f"失败 {summary['total_failed']}"
    )
    logger.info(f"批量提取完成: {summary}")
    return summary


# ====================================================================
# 命令行入口
# ====================================================================

if __name__ == "__main__":
    # 默认批量提取所有已识别论文，跳过已完成的膜
    extract_all(mode="skip")
