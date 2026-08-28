"""
zjuqa.data_processing —— 膜提取数据清洗整理工具包。

为后续机器学习模块开发提供数据预处理能力：
  1. unit_normalizer: 基于枚举的单位归一化
  2. substance_mapper: 基于枚举的截留物名称纠正映射
  3. formatter: 数据格式化工具（表格输出、CSV导出）

所有工具只读 data/extracted/ 文件夹，不修改原始提取数据。
"""

from .substance_mapper import (
    get_standard_name,
    list_all_aliases,
    list_standard_substances,
    map_substances,
    reload_aliases,
)
from .unit_normalizer import (
    NormalizedValue,
    StandardUnit,
    classify_flux_unit,
    get_standard_unit,
    list_normalizable_fields,
    normalize_flux_value,
    normalize_membrane,
    normalize_value,
    normalize_value_unit,
)
from .formatter import (
    build_dataframe,
    export_csv,
    get_normalization_report,
    load_all_membranes,
    print_summary,
    scan_flux_gaps,
)

__all__ = [
    # unit_normalizer
    "StandardUnit",
    "NormalizedValue",
    "normalize_value",
    "normalize_value_unit",
    "normalize_membrane",
    "normalize_flux_value",
    "classify_flux_unit",
    "get_standard_unit",
    "list_normalizable_fields",
    # substance_mapper
    "get_standard_name",
    "map_substances",
    "list_standard_substances",
    "list_all_aliases",
    "reload_aliases",
    # formatter
    "load_all_membranes",
    "build_dataframe",
    "export_csv",
    "print_summary",
    "get_normalization_report",
    "scan_flux_gaps",
]
