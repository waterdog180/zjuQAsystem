"""配置层：路径常量与 LLM 参数。

注意：本包不自动导入 LLMParas，避免 import config 时触发 api_keys 强依赖。
需要 LLM 配置时请显式 from zjuqa.config.llm_config import LLMParas。
"""
from .paths import (
    ROOT_DIR,
    RAW_PDF_DIR,
    PARSED_DIR,
    IDENTIFIED_DIR,
    EXTRACTED_DIR,
    PRE_PDF_DIR,
    PAGE_DPI,
    MAX_IMAGES,
    ensure_data_dirs,
    scan_raw_pdfs,
    scan_parsed_papers,
    scan_identified_papers,
    scan_extracted_papers,
)
