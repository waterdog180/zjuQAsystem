"""
paths.py —— 项目全局路径配置。

所有数据目录均以项目根目录（本文件所在包的上两级）为基准，
避免硬编码绝对路径，保证跨机器可移植。

使用说明：
    from zjuqa.config.paths import RAW_PDF_DIR, MINERU_OUT_DIR
    # 或在程序启动时调用 ensure_data_dirs() 确保目录存在
"""

from pathlib import Path

# 项目根目录：zjuQAsystem_v2/（zjuqa/config/paths.py 的上两级）
ROOT_DIR = Path(__file__).resolve().parent.parent.parent

# —— 数据目录 ——
RAW_PDF_DIR = ROOT_DIR / "data" / "raw_pdfs"
"""原始 PDF 存放目录。"""

PRE_PDF_DIR = ROOT_DIR / "data" / "pre_pdfs"
"""旧版预处理输出目录（已弃用，改用 MINERU_OUT_DIR）。"""

MINERU_OUT_DIR = ROOT_DIR / "data" / "mineru_out_2"
"""MinerU 解析输出目录，每篇论文一个子文件夹。"""

MEMBRANE_DATA_DIR = ROOT_DIR / "data" / "membranes"
"""膜参数汇总数据目录（预留）。"""

# —— 处理参数 ——
PAGE_DPI = 200
"""PDF 转图片分辨率：150=快/省token，200=均衡，300=高精度。"""

MAX_IMAGES = 40
"""单篇论文最多传入 LLM 的图片页数，超长文章截断避免 token 超限。"""


def ensure_data_dirs() -> None:
    """
    确保所有数据目录存在。在程序启动时调用一次即可。
    不放在模块顶层自动执行，避免导入时产生副作用。
    """
    for d in (RAW_PDF_DIR, PRE_PDF_DIR, MINERU_OUT_DIR, MEMBRANE_DATA_DIR):
        d.mkdir(parents=True, exist_ok=True)
