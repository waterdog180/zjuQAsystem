"""
membrane_repository.py —— 膜参数的版本化持久化与均值聚合。

核心功能（对应项目需求 3）：
  1. 每次膜参数提取结果以时间戳文件名保存，永不覆写历史版本。
  2. 支持读取全部历史版本。
  3. 对多个版本按 membrane_id 分组聚合：数值字段取均值，
     截留率字典按物质名分组取均值，字符串字段取首个非空值。

设计动机：
  LLM 识图存在随机性，同一论文多次提取结果可能略有差异。
  保留全部版本并取均值，可降低随机误差，提高数据可靠性。

目录结构：
    paper_dir/auto/
    ├── mem_paras_versions/
    │   ├── mem_paras_20260822_213045.json   # 第 1 次提取
    │   └── mem_paras_20260822_220010.json   # 第 2 次提取
    └── mem_paras_aggregated.json             # 聚合后的均值结果

使用说明：
    from zjuqa.storage.membrane_repository import (
        save_membrane_params_version, aggregate_membrane_params,
    )
    # 保存一次提取结果
    path = save_membrane_params_version(paper_dir, membrane_list)
    # 聚合所有版本取均值
    aggregated = aggregate_membrane_params(paper_dir)
"""

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union

from ..models.membrane import MembraneData


# ====================================================================
# 路径工具
# ====================================================================

def get_versions_dir(paper_dir: Path) -> Path:
    """
    获取某篇论文的膜参数历史版本目录。

    Args:
        paper_dir: 论文根目录，如 data/mineru_out/Test_1

    Returns:
        版本目录路径 paper_dir/auto/mem_paras_versions
    """
    return paper_dir / "auto" / "mem_paras_versions"


def get_aggregated_path(paper_dir: Path) -> Path:
    """
    获取某篇论文的膜参数聚合结果文件路径。

    Args:
        paper_dir: 论文根目录

    Returns:
        聚合文件路径 paper_dir/auto/mem_paras_aggregated.json
    """
    return paper_dir / "auto" / "mem_paras_aggregated.json"


# ====================================================================
# 版本化保存
# ====================================================================

def save_membrane_params_version(
    paper_dir: Path,
    membranes: List[MembraneData],
) -> Path:
    """
    将一次膜参数提取结果以时间戳文件名保存，不覆写历史版本。

    文件名格式：mem_paras_YYYYMMDD_HHMMSS.json
    保存位置：paper_dir/auto/mem_paras_versions/

    Args:
        paper_dir: 论文根目录
        membranes: 本次提取的膜参数列表

    Returns:
        本次保存的文件路径
    """
    versions_dir = get_versions_dir(paper_dir)
    versions_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = versions_dir / f"mem_paras_{timestamp}.json"

    # Pydantic v2: model_dump() 序列化为 dict
    data = [m.model_dump() for m in membranes]
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    print(f"  [存储] 已保存版本: {save_path.name}（{len(membranes)} 种膜）")
    return save_path


# ====================================================================
# 版本读取
# ====================================================================

def load_all_versions(paper_dir: Path) -> List[List[MembraneData]]:
    """
    读取某篇论文的所有历史版本提取结果，按时间升序排列。

    Args:
        paper_dir: 论文根目录

    Returns:
        版本列表，每个元素是一次提取的膜参数列表。
        若版本目录不存在或为空，返回空列表。
    """
    versions_dir = get_versions_dir(paper_dir)
    if not versions_dir.exists():
        return []

    versions: List[List[MembraneData]] = []
    # glob 匹配 mem_paras_*.json，sorted 保证时间升序
    for fp in sorted(versions_dir.glob("mem_paras_*.json")):
        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f)
        try:
            membranes = [MembraneData(**d) for d in data]
            versions.append(membranes)
        except Exception as e:
            print(f"  [存储][警告] 跳过损坏的版本文件 {fp.name}: {e}")
            continue

    return versions


# ====================================================================
# 均值聚合
# ====================================================================

# 需要取均值的数值字段名（值可能是 float / int / 可转 float 的字符串）
_NUMERIC_FIELDS = [
    "Substrate_pore_size",
    "Substrate_MWCO",
    "Substrate_Water_contact_angle",
    "Substrate_zeta",
    "Substrate_Ra",
    "Degree_of_crosslinking",
    "Thickness",
    "Effective_pore_size",
    "Zeta_potential",
    "Membrane_Ra",
    "pure_water_flux",
]

# 字符串/类别字段：取第一个非空值（不宜平均）
_STRING_FIELDS = [
    "membrane_id",
    "substrate",
]

# 浓度字段：可能是 dict 或数值，取第一个非空值
_CONC_FIELDS = [
    "PIP_Concentration",
    "TMC_Concentration",
]


def _to_float(value) -> Optional[float]:
    """
    尝试将值转为 float。失败返回 None。
    用于聚合时过滤无法数值化的字符串。
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


def _average_numeric(values: list) -> Optional[Union[float, str]]:
    """
    对一组数值取均值。所有值都无法转为 float 时返回 None。
    若原始值中有字符串且无法转换，跳过该值。
    """
    nums = [v for v in (_to_float(v) for v in values) if v is not None]
    if not nums:
        return None
    return sum(nums) / len(nums)


def _first_non_none(values: list):
    """返回列表中第一个非 None 值，全为 None 则返回 None。"""
    for v in values:
        if v is not None:
            return v
    return None


def _merge_rejections(
    rejection_dicts: List[Dict[str, Optional[Union[float, str]]]],
) -> Dict[str, Optional[Union[float, str]]]:
    """
    合并多个版本的截留率字典：按物质名分组，每种物质取均值。

    Args:
        rejection_dicts: 各版本的 rejections 字典列表

    Returns:
        合并后的截留率字典，值为各版本均值
    """
    # 按物质名收集所有版本的值
    substance_values: Dict[str, list] = defaultdict(list)
    for rd in rejection_dicts:
        if not rd:
            continue
        for substance, val in rd.items():
            substance_values[substance].append(val)

    # 每种物质取均值
    merged: Dict[str, Optional[Union[float, str]]] = {}
    for substance, vals in substance_values.items():
        avg = _average_numeric(vals)
        merged[substance] = avg
    return merged


def _average_membranes(membrane_list: List[MembraneData]) -> MembraneData:
    """
    对同一膜的多个版本实例取均值聚合。

    聚合规则：
      - 数值字段 → 算术均值
      - 字符串/类别字段 → 第一个非空值
      - 浓度字段 → 第一个非空值（dict 或数值）
      - rejections 字典 → 按物质名分组取均值
      - data_sources → 并集去重
      - notes → 合并为一条字符串

    Args:
        membrane_list: 同一膜的多个版本实例

    Returns:
        聚合后的 MembraneData 实例
    """
    if not membrane_list:
        raise ValueError("membrane_list 不能为空")

    if len(membrane_list) == 1:
        return membrane_list[0]

    # 收集各字段的所有版本值
    def collect(field: str) -> list:
        return [getattr(m, field) for m in membrane_list]

    # 数值字段取均值
    numeric_kwargs = {}
    for field in _NUMERIC_FIELDS:
        numeric_kwargs[field] = _average_numeric(collect(field))

    # 字符串字段取首个非空
    string_kwargs = {}
    for field in _STRING_FIELDS:
        string_kwargs[field] = _first_non_none(collect(field))

    # 浓度字段取首个非空
    conc_kwargs = {}
    for field in _CONC_FIELDS:
        conc_kwargs[field] = _first_non_none(collect(field))

    # 截留率字典合并取均值
    rejections_merged = _merge_rejections(collect("rejections"))

    # data_sources 并集去重（保持顺序）
    all_sources: List[str] = []
    seen = set()
    for m in membrane_list:
        for src in m.data_sources:
            if src not in seen:
                all_sources.append(src)
                seen.add(src)

    # notes 合并
    all_notes = [m.notes for m in membrane_list if m.notes]
    merged_notes = " | ".join(all_notes) if all_notes else None

    return MembraneData(
        **numeric_kwargs,
        **string_kwargs,
        **conc_kwargs,
        rejections=rejections_merged,
        data_sources=all_sources,
        notes=merged_notes,
    )


def aggregate_membrane_params(
    paper_dir: Path,
    save: bool = True,
) -> List[MembraneData]:
    """
    聚合某篇论文的所有历史版本，按膜名称分组取均值。

    流程：
      1. 读取所有历史版本
      2. 按 membrane_id 分组
      3. 每组调用 _average_membranes 取均值
      4. 可选：将聚合结果保存为 mem_paras_aggregated.json

    Args:
        paper_dir: 论文根目录
        save:      是否将聚合结果写入文件（默认 True）

    Returns:
        聚合后的膜参数列表。若无历史版本，返回空列表。
    """
    versions = load_all_versions(paper_dir)
    if not versions:
        print(f"  [存储] {paper_dir} 无历史版本，跳过聚合")
        return []

    # 按 membrane_id 分组
    groups: Dict[str, List[MembraneData]] = defaultdict(list)
    for version in versions:
        for m in version:
            key = m.membrane_id or "Unnamed_Membrane"
            groups[key].append(m)

    # 每组取均值
    aggregated = [_average_membranes(mlist) for mlist in groups.values()]

    # 保存聚合结果
    if save:
        agg_path = get_aggregated_path(paper_dir)
        agg_path.parent.mkdir(parents=True, exist_ok=True)
        with open(agg_path, "w", encoding="utf-8") as f:
            json.dump(
                [m.model_dump() for m in aggregated],
                f, indent=4, ensure_ascii=False,
            )
        print(
            f"  [存储] 已聚合 {len(versions)} 个版本 → "
            f"{len(aggregated)} 种膜，写入 {agg_path.name}"
        )

    return aggregated
