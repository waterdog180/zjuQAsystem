"""
scanner.py —— 目录自动扫描工具。

扫描各阶段数据目录，返回论文/膜名称列表。
从 config.paths 导入目录常量，不依赖 Test_X 命名格式。

使用说明：
    from zjuqa.utils.scanner import (
        scan_raw_pdfs, scan_parsed_papers,
        scan_identified_papers, scan_extracted_papers,
        scan_extracted_membranes,
    )
    papers = scan_raw_pdfs()  # 自动发现 data/raw/ 下所有 PDF
"""

import json
from pathlib import Path
from typing import List

from ..config.paths import (
    EXTRACTED_DIR,
    IDENTIFIED_DIR,
    PARSED_DIR,
    RAW_PDF_DIR,
    get_extracted_dir,
)


def scan_raw_pdfs() -> List[str]:
    """
    扫描 data/raw/ 目录，返回所有 PDF 文件名（不含扩展名）。
    不依赖 Test_X 命名格式，任意 PDF 文件名均可识别。
    """
    if not RAW_PDF_DIR.exists():
        return []
    return sorted([
        f.stem for f in RAW_PDF_DIR.iterdir()
        if f.is_file() and f.suffix.lower() == ".pdf"
    ])


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
