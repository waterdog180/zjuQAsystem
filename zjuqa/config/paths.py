"""
paths.py —— 项目全局路径与参数配置（config 层）。

只保留目录路径常量和少量手动调整参数。
Path 实例生成函数已移至 zjuqa.utils.path_utils。

数据目录按处理阶段分离，三阶段成果互不干扰：
    data/raw/        原始 PDF（不可变输入，文件名不修改）
    data/parsed/     阶段1：MinerU 解析输出（结构化文本 + 图片）
    data/identified/ 阶段2：膜名称识别结果（meta.json）
    data/extracted/  阶段3：膜参数提取结果（文章-膜两级分离）

使用说明：
    from zjuqa.config.paths import (
        ROOT_DIR, RAW_PDF_DIR, PARSED_DIR, IDENTIFIED_DIR, EXTRACTED_DIR,
        LOG_DIR, PAGE_DPI, MAX_IMAGES,
    )
"""

from pathlib import Path

# ====================================================================
# 目录路径常量
# ====================================================================

# 项目根目录：zjuqa/config/paths.py 的上两级
ROOT_DIR = Path(__file__).resolve().parent.parent.parent

RAW_PDF_DIR = ROOT_DIR / "data" / "raw_4"
"""原始 PDF 存放目录（不可变输入，程序不修改原始文件名）。"""

PARSED_DIR = ROOT_DIR / "data" / "parsed"
"""阶段1：MinerU 解析输出目录。每篇论文一个子文件夹。"""

IDENTIFIED_DIR = ROOT_DIR / "data" / "identified"
"""阶段2：膜名称识别结果目录。每篇论文一个子文件夹，内含 meta.json。"""

EXTRACTED_DIR = ROOT_DIR / "data" / "extracted"
"""阶段3：膜参数提取结果目录。文章-膜两级分离。"""

LOG_DIR = ROOT_DIR / "logs"
"""运行日志目录（带时间戳的详细日志文件）。"""

# ====================================================================
# 处理参数（少量手动调整参数，留在 config 层）
# ====================================================================

PAGE_DPI = 200#未使用
"""PDF 转图片分辨率：150=快/省token，200=均衡，300=高精度。"""

MAX_IMAGES = 60
"""单篇论文最多传入 LLM 的图片页数，超长文章截断避免 token 超限。"""
