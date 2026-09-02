"""
配置层：路径常量与 LLM 参数。

注意：
  - 本包不自动导入 LLMParas，避免 import config 时触发 api_keys 强依赖。
  - Path 实例生成函数已移至 zjuqa.utils.path_utils。
  - 目录自动扫描函数已移至 zjuqa.utils.scanner。
"""
from .paths import (
    ROOT_DIR,
    RAW_PDF_DIR,
    PARSED_DIR,
    IDENTIFIED_DIR,
    EXTRACTED_DIR,
    LOG_DIR,
    PAGE_DPI,
    MAX_IMAGES,
)
