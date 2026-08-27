"""
cleanup.py —— 各阶段中间数据一键清理工具。

提供按阶段或按论文清理中间数据的功能，便于重新运行或释放空间。
不会删除 data/raw/ 下的原始 PDF。

支持的清理阶段：
    parsed     — MinerU 解析输出（data/parsed/）
    identified — 膜名称识别结果（data/identified/）
    extracted  — 膜参数提取结果（data/extracted/）
    all        — 以上三个阶段全部清理（保留 raw/）

使用说明：
    from zjuqa.utils.cleanup import clean_stage, clean_paper, STAGES
    # 清理所有解析输出
    clean_stage("parsed")
    # 清理指定论文的识别和提取结果
    clean_paper("Test_1", stages=["identified", "extracted"])
    # 一键清理所有中间数据
    clean_stage("all")
"""

import shutil
from pathlib import Path
from typing import List, Optional

from ..config.paths import (
    EXTRACTED_DIR,
    IDENTIFIED_DIR,
    PARSED_DIR,
)

# 可清理的阶段及其对应目录（硬编码，本身安全）
STAGES = {
    "parsed": PARSED_DIR,
    "identified": IDENTIFIED_DIR,
    "extracted": EXTRACTED_DIR,
}


def _rmtree_contents(dir_path: Path, label: str) -> int:
    """
    删除目录内容（保留目录本身），返回删除的子项数量。

    Args:
        dir_path: 要清理的目录
        label:    阶段标签（用于日志）

    Returns:
        删除的子项数量
    """
    if not dir_path.exists():
        print(f"  [清理] {label}: 目录不存在，跳过")
        return 0

    count = 0
    for item in dir_path.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()
        count += 1

    print(f"  [清理] {label}: 已删除 {count} 项 ({dir_path})")
    return count


def clean_stage(stage: str) -> dict:
    """
    清理指定阶段的所有中间数据。

    STAGES 中的路径为硬编码配置，本身安全，无需额外路径校验。

    Args:
        stage: 阶段名称，可选 "parsed"、"identified"、"extracted"、"all"

    Returns:
        各阶段删除数量的字典

    Raises:
        ValueError: stage 不在允许列表中
    """
    if stage == "all":
        result = {}
        for name, dir_path in STAGES.items():
            result[name] = _rmtree_contents(dir_path, name)
        total = sum(result.values())
        print(f"[清理] 全部中间数据清理完成，共删除 {total} 项（raw/ 未动）")
        return result

    if stage not in STAGES:
        raise ValueError(
            f"未知阶段 '{stage}'，允许值: {list(STAGES.keys()) + ['all']}"
        )

    count = _rmtree_contents(STAGES[stage], stage)
    return {stage: count}


def clean_paper(
    paper_name: str,
    stages: Optional[List[str]] = None,
) -> dict:
    """
    清理指定论文的中间数据（按阶段）。

    安全检查：拼接后的路径必须在对应阶段目录内，防止路径逃逸（如 paper_name="../../etc"）。

    Args:
        paper_name: 论文名称
        stages:     要清理的阶段列表，None 时清理所有三个阶段

    Returns:
        各阶段删除结果的字典（True=已删除，False=不存在或被安全拒绝）
    """
    if stages is None:
        stages = list(STAGES.keys())

    result = {}
    for stage in stages:
        if stage not in STAGES:
            print(f"  [清理][警告] 未知阶段 '{stage}'，跳过")
            continue

        stage_dir = STAGES[stage]
        target = (stage_dir / paper_name).resolve()

        # 安全检查：目标路径必须在阶段目录内
        try:
            target.relative_to(stage_dir.resolve())
        except ValueError:
            print(f"  [清理][警告] 路径逃逸检测，拒绝删除: {target}")
            result[stage] = False
            continue

        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            print(f"  [清理] {stage}/{paper_name}: 已删除")
            result[stage] = True
        else:
            print(f"  [清理] {stage}/{paper_name}: 不存在，跳过")
            result[stage] = False
    return result
