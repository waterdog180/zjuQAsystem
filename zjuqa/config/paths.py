"""
paths.py —— 项目全局路径配置。

数据目录按处理阶段分离，三阶段成果互不干扰：
    data/raw/        原始 PDF（不可变输入）
    data/parsed/     阶段1：MinerU 解析输出（结构化文本 + 图片）
    data/identified/ 阶段2：膜名称识别结果（meta.json）
    data/extracted/  阶段3：膜参数提取结果（文章-膜两级分离）

所有路径均以项目根目录为基准，避免硬编码绝对路径。

注意：目录自动扫描函数已移至 zjuqa.utils.scanner，
本文件只保留路径常量和路径辅助函数。

使用说明：
    from zjuqa.config.paths import (
        RAW_PDF_DIR, PARSED_DIR, IDENTIFIED_DIR, EXTRACTED_DIR,
        get_parsed_text, get_meta_path, get_membrane_dir,
        ensure_data_dirs,
    )
"""

from pathlib import Path
#region 路径常量
# 项目根目录：zjuqa/config/paths.py 的上两级
ROOT_DIR = Path(__file__).resolve().parent.parent.parent


RAW_PDF_DIR = ROOT_DIR / "data" / "raw"
"""原始 PDF 存放目录。"""

PARSED_DIR = ROOT_DIR / "data" / "parsed"
"""阶段1：MinerU 解析输出目录。每篇论文一个子文件夹。"""

IDENTIFIED_DIR = ROOT_DIR / "data" / "identified"
"""阶段2：膜名称识别结果目录。每篇论文一个子文件夹，内含 meta.json。"""

EXTRACTED_DIR = ROOT_DIR / "data" / "extracted"
"""阶段3：膜参数提取结果目录。文章-膜两级分离。"""

# 旧版目录（保留兼容，已弃用）
PRE_PDF_DIR = ROOT_DIR / "data" / "pre_pdfs"
"""旧版预处理输出目录（已弃用）。"""

MEMBRANE_DATA_DIR = EXTRACTED_DIR
"""兼容旧引用：膜参数目录即 extracted/。"""

# ====================================================================
# 处理参数（少量手动调整参数，留在 config 层）
# ====================================================================

PAGE_DPI = 200#未使用
"""PDF 转图片分辨率：150=快/省token，200=均衡，300=高精度。"""

MAX_IMAGES = 60#不建议一刀切，应增加筛选机制，后续处理
"""单篇论文最多传入 LLM 的图片页数，超长文章截断避免 token 超限。"""

# ====================================================================
# 路径辅助函数（需求2：文章-膜两级分离）
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
    """获取某篇论文的页面图片目录路径。"""
    return get_parsed_dir(paper_name) / "images"


def get_identified_dir(paper_name: str) -> Path:
    """获取某篇论文的膜名称识别结果目录。"""
    return IDENTIFIED_DIR / paper_name


def get_meta_path(paper_name: str) -> Path:
    """获取某篇论文的 meta.json 路径（膜名称列表）。"""
    return get_identified_dir(paper_name) / "meta.json"


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
    for d in (RAW_PDF_DIR, PARSED_DIR, IDENTIFIED_DIR, EXTRACTED_DIR, PRE_PDF_DIR):
        d.mkdir(parents=True, exist_ok=True)
