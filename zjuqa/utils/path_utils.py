"""
path_utils.py —— Path 实例生成工具（utils 层）。

从 config.paths 导入目录常量，提供各阶段数据文件/目录的 Path 实例生成函数。
与 config.paths 分离：config 层只定义"在哪里"，utils 层负责"怎么拼路径"。

使用说明：
    from zjuqa.utils.path_utils import (
        get_parsed_text, get_parsed_images, get_meta_path,
        get_extracted_dir, get_membrane_dir, ensure_data_dirs,
        get_raw_pdf_path,
    )
"""

from pathlib import Path
from typing import Optional

from ..config.paths import (
    EXTRACTED_DIR,
    IDENTIFIED_DIR,
    LOG_DIR,
    PARSED_DIR,
    RAW_PDF_DIR,
)


# ====================================================================
# 原始 PDF 路径（不修改原始文件名，读取时自动纠正）
# ====================================================================

def get_raw_pdf_path(safe_paper_name: str) -> Optional[Path]:
    """
    根据合规后的论文名称，反查 data/raw/ 中的原始 PDF 文件路径。

    原始 PDF 文件名可能包含空格等不合规字符，程序内部使用合规名称，
    但不修改原始文件。本函数通过比对 sanitize 后的文件名找到原始文件。

    Args:
        safe_paper_name: 合规后的论文名称（不含扩展名）

    Returns:
        原始 PDF 文件路径；未找到时返回 None
    """
    from .scanner import sanitize_paper_name

    if not RAW_PDF_DIR.exists():
        return None

    for pdf_file in RAW_PDF_DIR.iterdir():
        if pdf_file.is_file() and pdf_file.suffix.lower() == ".pdf":
            if sanitize_paper_name(pdf_file.stem) == safe_paper_name:
                return pdf_file
    return None


# ====================================================================
# 阶段1：MinerU 解析输出
# ====================================================================

def get_parsed_dir(paper_name: str) -> Path:
    """
    获取某篇论文的 MinerU 解析输出目录。
    MinerU 输出结构为 <parsed_dir>/<paper_name>/auto/
    """
    return PARSED_DIR / paper_name / "auto"


def get_parsed_text(paper_name: str) -> Path:
    """获取某篇论文的结构化文本文件路径。"""
    return get_parsed_dir(paper_name) / f"{paper_name}.md"


def get_parsed_images(paper_name: str) -> Path:
    """获取某篇论文的页面图片目录路径（MinerU 原始输出）。"""
    return get_parsed_dir(paper_name) / "images"


def get_parsed_images_cleaned(paper_name: str) -> Path:
    """获取某篇论文清洗后的图片目录路径（image_cleaner 输出，按文中顺序重编号，小图已删除）。"""
    return get_parsed_dir(paper_name) / "images_cleaned"


# ====================================================================
# 阶段2：膜名称识别
# ====================================================================

def get_identified_dir(paper_name: str) -> Path:
    """获取某篇论文的膜名称识别结果目录。"""
    return IDENTIFIED_DIR / paper_name


def get_meta_path(paper_name: str) -> Path:
    """获取某篇论文的 meta.json 路径（膜名称列表）。"""
    return get_identified_dir(paper_name) / "meta.json"


# ====================================================================
# 阶段3：膜参数提取（文章-膜两级分离）
# ====================================================================

def get_extracted_dir(paper_name: str) -> Path:
    """获取某篇论文的膜参数提取根目录（文章级）。"""
    return EXTRACTED_DIR / paper_name


def get_membrane_dir(paper_name: str, membrane_id: str) -> Path:
    """
    获取某个膜的参数目录（膜级，文章-膜两级分离）。
    结构：<extracted_dir>/<paper_name>/<membrane_id>/
    膜名中的特殊字符（/ \\ 空格）会被替换为下划线。
    """
    safe_id = membrane_id.replace("/", "_").replace("\\", "_").replace(" ", "_")
    return get_extracted_dir(paper_name) / safe_id


def get_membrane_versions_dir(paper_name: str, membrane_id: str) -> Path:
    """获取某个膜的历史版本目录。"""
    return get_membrane_dir(paper_name, membrane_id) / "versions"


def get_membrane_aggregated_path(paper_name: str, membrane_id: str) -> Path:
    """获取某个膜的聚合结果文件路径。"""
    return get_membrane_dir(paper_name, membrane_id) / "aggregated.json"


def get_paper_aggregated_path(paper_name: str) -> Path:
    """获取整篇论文所有膜的聚合结果文件路径。"""
    return get_extracted_dir(paper_name) / "_paper_aggregated.json"


# ====================================================================
# 目录初始化
# ====================================================================

def ensure_data_dirs() -> None:
    """
    确保所有数据目录存在。在程序启动时调用一次即可。
    不放在模块顶层自动执行，避免导入时产生副作用。
    """
    for d in (RAW_PDF_DIR, PARSED_DIR, IDENTIFIED_DIR, EXTRACTED_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)
