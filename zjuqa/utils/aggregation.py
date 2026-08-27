"""
aggregation.py —— 数值聚合工具（支持 ValueUnit 格式）。

提供多版本膜参数的均值聚合函数，处理单位一致性检查。
从 storage 层提取，供 storage 和未来 ML 层复用。

使用说明：
    from zjuqa.utils.aggregation import average_value_units, merge_rejections
    avg = average_value_units([vu1, vu2, vu3])
"""

from collections import defaultdict
from typing import Dict, List, Optional

from ..schemas.membrane import ValueUnit


def _to_float(value) -> Optional[float]:
    """
    尝试将值转为 float，失败返回 None。
    支持 int、float、str（可解析的数字字符串）。
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except (ValueError, AttributeError):
            return None
    return None


def average_value_units(
    values: List[Optional[ValueUnit]],
) -> Optional[ValueUnit]:
    """
    对一组 ValueUnit 取均值聚合。

    聚合规则：
      1. 过滤 None 值
      2. 检查单位一致性：
         - 全部单位相同 → 取 value 均值，保留该单位
         - 单位不同 → 取第一个非空单位，value 取所有值均值（不做单位转换），
           并在返回值的 unit 后标注 "*" 表示单位冲突
      3. 全部为 None → 返回 None

    Args:
        values: ValueUnit 列表（可能含 None）

    Returns:
        聚合后的 ValueUnit，无有效值时返回 None
    """
    valid = [v for v in values if v is not None]
    if not valid:
        return None
    if len(valid) == 1:
        return valid[0]

    # 检查单位一致性
    units = {v.unit for v in valid}
    nums = [v.value for v in valid]
    avg_value = sum(nums) / len(nums)

    if len(units) == 1:
        # 单位一致
        return ValueUnit(value=avg_value, unit=valid[0].unit)
    else:
        # 单位冲突：取第一个单位，标注 *
        first_unit = valid[0].unit
        return ValueUnit(value=avg_value, unit=f"{first_unit}*")


def merge_rejections(
    rejection_dicts: List[Dict[str, Optional[ValueUnit]]],
) -> Dict[str, Optional[ValueUnit]]:
    """
    合并多个版本的截留率字典：按物质名分组，对每组取均值聚合。

    Args:
        rejection_dicts: 多个版本的 rejections 字典列表

    Returns:
        合并后的截留率字典
    """
    substance_values: Dict[str, list] = defaultdict(list)
    for rd in rejection_dicts:
        if not rd:
            continue
        for substance, vu in rd.items():
            substance_values[substance].append(vu)

    merged: Dict[str, Optional[ValueUnit]] = {}
    for substance, vals in substance_values.items():
        merged[substance] = average_value_units(vals)
    return merged


def first_non_none(values: list):
    """
    返回列表中第一个非 None 值。
    用于字符串/类别字段的聚合（取第一个非空值）。
    """
    for v in values:
        if v is not None:
            return v
    return None
