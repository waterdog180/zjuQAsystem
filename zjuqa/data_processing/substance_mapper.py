"""
substance_mapper.py —— 基于枚举的截留物名称纠正映射工具。

读取 substance_aliases.json 配置文件，将 LLM 可能误识别的别称/错称统一为标准名称。
不修改原始提取数据，返回映射后的新字典。

设计原则：
  1. 配置驱动：别称映射存储在 substance_aliases.json，便于扩展
  2. 反向映射：运行时构建 别称→标准名 的查找字典，O(1) 查询
  3. 大小写不敏感：匹配时忽略大小写，但保留标准名的原始大小写
  4. 不修改原始数据：返回新的 rejections 字典

使用说明：
    from zjuqa.data_processing.substance_mapper import map_substances, get_standard_name
    # 单个名称映射
    standard = get_standard_name("TC")  # → "tetracycline"
    # 整个 rejections 字典映射
    mapped = map_substances({"TC": {"value": 90, "unit": "%"}, "NaCl": {"value": 50, "unit": "%"}})
    # → {"tetracycline": {...}, "NaCl": {...}}
"""

import json
from pathlib import Path
from typing import Dict, Optional, Tuple

from ..schemas.membrane import ValueUnit


# ====================================================================
# 配置加载与反向映射构建
# ====================================================================

_ALIASES_FILE = Path(__file__).parent / "substance_aliases.json"


def _load_aliases() -> Tuple[Dict[str, str], Dict[str, list]]:
    """
    加载 substance_aliases.json 并构建反向映射。

    Returns:
        (reverse_map, forward_map)
        - reverse_map: {别称(小写): 标准名}，用于快速查找
        - forward_map: {标准名: [别称列表]}，原始配置
    """
    with open(_ALIASES_FILE, "r", encoding="utf-8") as f:
        forward_map = json.load(f)

    # 移除注释键
    forward_map = {k: v for k, v in forward_map.items() if not k.startswith("_")}

    reverse_map: Dict[str, str] = {}
    for standard, aliases in forward_map.items():
        # 标准名自身也加入映射（大小写不敏感匹配）
        reverse_map[standard.lower()] = standard
        for alias in aliases:
            reverse_map[alias.lower()] = standard

    return reverse_map, forward_map


# 模块加载时构建一次
_REVERSE_MAP, _FORWARD_MAP = _load_aliases()


# ====================================================================
# 核心映射函数
# ====================================================================

def get_standard_name(name: str) -> Tuple[str, bool]:
    """
    将截留物名称映射为标准名称。

    Args:
        name: 原始名称（可能是别称或错称）

    Returns:
        (standard_name, was_mapped)
        - standard_name: 标准名称（若未找到映射，返回原始名称）
        - was_mapped: 是否发生了映射（True=从别称纠正为标准名，False=本身就是标准名或未知）
    """
    key = name.strip().lower()
    if key in _REVERSE_MAP:
        standard = _REVERSE_MAP[key]
        return standard, standard != name
    return name, False


def map_substances(
    rejections: Dict[str, ValueUnit],
) -> Tuple[Dict[str, ValueUnit], Dict[str, str]]:
    """
    对整个 rejections 字典进行截留物名称纠正映射。

    不修改原始字典，返回新的映射后字典和映射记录。

    Args:
        rejections: 原始 rejections 字典 {物质名: ValueUnit}

    Returns:
        (mapped_rejections, mapping_log)
        - mapped_rejections: 映射后的新字典 {标准名: ValueUnit}
        - mapping_log: {原始名: 标准名}，仅记录发生了映射的条目
    """
    mapped: Dict[str, ValueUnit] = {}
    mapping_log: Dict[str, str] = {}

    for name, value in rejections.items():
        standard, was_mapped = get_standard_name(name)
        if was_mapped:
            mapping_log[name] = standard
        # 若映射后出现重复键（如 TC 和 tetracycline 都映射到 tetracycline），保留第一个
        if standard not in mapped:
            mapped[standard] = value
        # 重复键的第二个值被丢弃（实际数据中同一膜不会同时出现 TC 和 tetracycline）

    return mapped, mapping_log


def list_standard_substances() -> list:
    """返回所有标准截留物名称列表。"""
    return list(_FORWARD_MAP.keys())


def list_all_aliases() -> Dict[str, list]:
    """返回完整的 标准名→别称列表 映射。"""
    return dict(_FORWARD_MAP)


def reload_aliases() -> None:
    """重新加载 substance_aliases.json（配置文件被修改后调用）。"""
    global _REVERSE_MAP, _FORWARD_MAP
    _REVERSE_MAP, _FORWARD_MAP = _load_aliases()
