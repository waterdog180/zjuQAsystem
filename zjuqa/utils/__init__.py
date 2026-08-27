"""
utils —— 通用工具包。

储存稳定的、无业务逻辑的基础工具代码，供各子包复用。

模块清单：
    scanner.py     目录自动扫描工具
    image.py       图片编码与加载工具
    aggregation.py 数值聚合工具（支持 ValueUnit 格式）
    io.py          JSON 文件读写工具
    logging.py     统一日志配置
    cleanup.py     各阶段中间数据一键清理工具

使用说明：
    from zjuqa.utils import (
        scan_raw_pdfs, scan_parsed_papers, scan_identified_papers,
        scan_extracted_papers, scan_extracted_membranes,
        encode_image, load_images_for_paper,
        average_value_units, merge_rejections, first_non_none,
        load_json_safe, save_json, ensure_json_file,
        get_logger,
        clean_stage, clean_paper, STAGES,
    )
"""

from .scanner import (
    scan_raw_pdfs,
    scan_parsed_papers,
    scan_identified_papers,
    scan_extracted_papers,
    scan_extracted_membranes,
)
from .image import encode_image, load_images_for_paper
from .aggregation import (
    average_value_units,
    merge_rejections,
    first_non_none,
)
from .io import load_json_safe, save_json, ensure_json_file
from .logging import get_logger
from .cleanup import clean_stage, clean_paper, STAGES

__all__ = [
    "scan_raw_pdfs", "scan_parsed_papers", "scan_identified_papers",
    "scan_extracted_papers", "scan_extracted_membranes",
    "encode_image", "load_images_for_paper",
    "average_value_units", "merge_rejections", "first_non_none",
    "load_json_safe", "save_json", "ensure_json_file",
    "get_logger",
    "clean_stage", "clean_paper", "STAGES",
]
