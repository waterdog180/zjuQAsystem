"""配置层：路径常量与 LLM 参数。"""
from .paths import (
    ROOT_DIR, RAW_PDF_DIR, PRE_PDF_DIR, MINERU_OUT_DIR,
    MEMBRANE_DATA_DIR, PAGE_DPI, MAX_IMAGES, ensure_data_dirs,
)
from .llm_config import LLMParas
