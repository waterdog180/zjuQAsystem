"""
配置层：路径常量与 LLM 参数。

注意：
  - 本包不自动导入 LLMParas，避免 import config 时触发 api_keys 强依赖。
  - 目录自动扫描函数已移至 zjuqa.utils.scanner。
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
    get_parsed_dir,
    get_parsed_text,
    get_parsed_images,
    get_identified_dir,
    get_meta_path,
    get_extracted_dir,
    get_membrane_dir,
    get_membrane_versions_dir,
    get_membrane_aggregated_path,
    get_paper_aggregated_path,
)
