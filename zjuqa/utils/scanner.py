"""
scanner.py —— 目录自动扫描工具。

扫描各阶段数据目录，返回论文/膜名称列表。
从 config.paths 导入目录常量，不依赖 Test_X 命名格式。

原始 PDF 文件名可能包含空格等不合规字符，scan_raw_pdfs() 返回
sanitize 后的合规名称，但不修改原始文件。通过 path_utils.get_raw_pdf_path()
反查原始文件路径。

使用说明：
    from zjuqa.utils.scanner import (
        scan_raw_pdfs, scan_parsed_papers,
        scan_identified_papers, scan_extracted_papers,
        scan_extracted_membranes, sanitize_paper_name,
    )
    papers = scan_raw_pdfs()  # 自动发现 data/raw/ 下所有 PDF（返回合规名称）
"""

import hashlib
import json
import re
from pathlib import Path
from typing import List

from ..config.paths import (
    EXTRACTED_DIR,
    IDENTIFIED_DIR,
    PARSED_DIR,
    RAW_PDF_DIR,
)
from .path_utils import get_extracted_dir


# ====================================================================
# 文件名校验（不修改原始文件，仅用于内部名称规范化）
# ====================================================================

# 只保留 ASCII 字母、数字、下划线、连字符、点号
# 其他字符（空格、中文、特殊Unicode如 ‐ U+2010、Windows非法字符等）全部替换为下划线
_SAFE_CHARS_PATTERN = re.compile(r'[^a-zA-Z0-9_.\-]+')
# 连续下划线合并
_MULTI_UNDERSCORE_PATTERN = re.compile(r'_+')
# 默认最大名称长度（避免 Windows MAX_PATH 260 字符限制）
_DEFAULT_MAX_NAME_LENGTH = 80


def sanitize_paper_name(name: str, max_length: int = _DEFAULT_MAX_NAME_LENGTH) -> str:
    """
    将论文名称转换为合规的文件/目录名（不修改原始文件，仅内部使用）。

    规则：
      - 只保留 ASCII 字母、数字、下划线、连字符、点号
      - 其他字符（空格、中文、特殊Unicode如 ‐、Windows非法字符等）替换为下划线
      - 连续下划线合并为一个
      - 去除首尾下划线和点号
      - 长度超过 max_length 时截断并附加 6 位哈希避免冲突
      - 空名称返回 "untitled"

    Args:
        name:       原始论文名称（PDF 文件名不含扩展名）
        max_length: 最大名称长度，默认 80（避免 Windows MAX_PATH 限制）

    Returns:
        合规后的名称
    """
    if not name or not name.strip():
        return "untitled"

    # 非安全字符 → 下划线
    cleaned = _SAFE_CHARS_PATTERN.sub("_", name)
    # 连续下划线合并
    cleaned = _MULTI_UNDERSCORE_PATTERN.sub("_", cleaned)
    # 去除首尾下划线和点号
    cleaned = cleaned.strip("_.")

    if not cleaned:
        return "untitled"

    # 长度限制：超长时截断并附加短哈希
    if len(cleaned) > max_length:
        short_hash = hashlib.md5(name.encode("utf-8")).hexdigest()[:6]
        # 保留前 max_length - 7 个字符 + "_" + 6位哈希
        cleaned = cleaned[:max_length - 7] + "_" + short_hash

    return cleaned


# ====================================================================
# 目录扫描
# ====================================================================

def scan_raw_pdfs() -> List[str]:
    """
    扫描 data/raw/ 目录，返回所有 PDF 的合规名称列表（不含扩展名）。

    不修改原始 PDF 文件，仅返回 sanitize 后的名称。
    通过 path_utils.get_raw_pdf_path(safe_name) 可反查原始文件路径。

    Returns:
        合规后的论文名称列表（去重、排序）
    """
    if not RAW_PDF_DIR.exists():
        return []
    # 使用 set 去重（不同原始文件名 sanitize 后可能相同）
    safe_names = set()
    for f in RAW_PDF_DIR.iterdir():
        if f.is_file() and f.suffix.lower() == ".pdf":
            safe_names.add(sanitize_paper_name(f.stem))
    return sorted(safe_names)


def scan_parsed_papers() -> List[str]:
    """
    扫描 data/parsed/ 目录，返回已完成 MinerU 解析的论文名列表。
    判断依据：存在 <paper_name>/auto/<paper_name>.md 文件。
    """
    if not PARSED_DIR.exists():
        return []
    result = []
    for d in PARSED_DIR.iterdir():
        if d.is_dir() and (d / "auto" / f"{d.name}.md").exists():
            result.append(d.name)
    return sorted(result)


def scan_identified_papers() -> List[str]:
    """
    扫描 data/identified/ 目录，返回已完成膜名称识别的论文名列表。
    判断依据：存在 <paper_name>/meta.json 且 membrane_ids 非空。
    """
    if not IDENTIFIED_DIR.exists():
        return []
    result = []
    for d in IDENTIFIED_DIR.iterdir():
        meta_path = d / "meta.json"
        if d.is_dir() and meta_path.exists():
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                if meta.get("membrane_ids"):
                    result.append(d.name)
            except (json.JSONDecodeError, OSError):
                continue
    return sorted(result)


def scan_extracted_papers() -> List[str]:
    """
    扫描 data/extracted/ 目录，返回已有膜参数提取结果的论文名列表。
    判断依据：论文目录下至少有一个膜子目录。
    """
    if not EXTRACTED_DIR.exists():
        return []
    result = []
    for d in EXTRACTED_DIR.iterdir():
        if d.is_dir():
            membrane_dirs = [
                sub for sub in d.iterdir()
                if sub.is_dir() and not sub.name.startswith("_")
            ]
            if membrane_dirs:
                result.append(d.name)
    return sorted(result)


def scan_extracted_membranes(paper_name: str) -> List[str]:
    """
    扫描某篇论文下已提取的膜名称列表（目录名）。
    """
    paper_dir = get_extracted_dir(paper_name)
    if not paper_dir.exists():
        return []
    return sorted([
        d.name for d in paper_dir.iterdir()
        if d.is_dir() and not d.name.startswith("_")
    ])
