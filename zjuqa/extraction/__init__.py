"""信息提取层：膜名称识别与膜参数提取。"""
from .prompts import IDENTIFY_SYSTEM, mem_extract_template, refit_prompt_template
from .membrane_identifier import (
    identify_membranes,
    set_meta_info,
    is_membrane_ids_got,
    set_membrane_ids,
    clean_meta_json,
    read_membrane_ids,
)
from .membrane_extractor import (
    build_multimodal_messages,
    load_images,
    get_membrane_params,
    extract_and_save,
)
