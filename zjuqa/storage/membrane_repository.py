"""
membrane_repository.py —— 膜参数的版本化持久化与均值聚合。

核心功能（需求2：文章-膜两级分离 + 需求3：版本化保存）：
  1. 每个膜独立保存为一个目录，内含 versions/（历史版本）和 aggregated.json（均值）。
  2. 每次提取结果以时间戳文件名保存，永不覆写历史版本。
  3. 支持单膜聚合和整篇论文聚合。
  4. 提供"是否已提取"的检查接口，支持断点续跑。

目录结构：
    data/extracted/<paper_name>/
    ├── <membrane_id>/
    │   ├── versions/
    │   │   ├── 20260822_213045.json   # 该膜的一次提取结果
    │   │   └── 20260822_220010.json
    │   └── aggregated.json            # 该膜的多版本均值
    └── _paper_aggregated.json         # 整篇论文所有膜的聚合

使用说明：
    from zjuqa.storage.membrane_repository import (
        save_membrane_version, is_membrane_extracted,
        aggregate_membrane, aggregate_paper, load_membrane_versions,
    )
    # 保存单个膜的一次提取
    save_membrane_version("Test_1", "TFC-s-O", membrane_data)
    # 检查是否已提取
    is_membrane_extracted("Test_1", "TFC-s-O")
    # 聚合单个膜
    aggregate_membrane("Test_1", "TFC-s-O")
    # 聚合整篇论文
    aggregate_paper("Test_1")
"""

from datetime import datetime
from pathlib import Path
from typing import List, Optional#, Dict, Union

from ..config.paths import (
    get_membrane_aggregated_path,
    get_membrane_versions_dir,
    get_paper_aggregated_path,
)
from ..schemas.membrane import MembraneData, ValueUnit
from ..utils.aggregation import (
    average_value_units,
    first_non_none,
    merge_rejections,
)
from ..utils.io import load_json_safe, save_json
from ..utils.scanner import scan_extracted_membranes


# ====================================================================
#region 需要聚合字段
# ====================================================================

# ValueUnit 数值字段：取均值（校验单位一致性）
_VALUEUNIT_FIELDS = [
    "Substrate_pore_size",
    "Substrate_MWCO",
    "Substrate_Water_contact_angle",
    "Substrate_zeta",
    "Substrate_Ra",
    "PIP_Concentration",
    "TMC_Concentration",
    "Degree_of_crosslinking",
    "Thickness",
    "Effective_pore_size",
    "Zeta_potential",
    "Membrane_Ra",
    "pure_water_flux",
]

# 字符串/类别字段：取第一个非空值
_STRING_FIELDS = ["membrane_id", "substrate"]


# ====================================================================
# 单膜版本化保存（需求2：细化到单个膜）
# ====================================================================

def save_membrane_version(paper_name: str,membrane_id: str,membrane: MembraneData) -> Path:
    """
    将单个膜的一次提取结果以时间戳文件名保存，不覆写历史版本。

    保存位置：data/extracted/<paper_name>/<membrane_id>/versions/YYYYMMDD_HHMMSS.json

    Args:
        paper_name: 论文名称（目录名）
        membrane_id: 膜名称
        membrane:    本次提取的膜参数

    Returns:
        本次保存的文件路径
    """
    versions_dir = get_membrane_versions_dir(paper_name, membrane_id)
    versions_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    save_path = versions_dir / f"{timestamp}.json"

    save_json(save_path, membrane.model_dump())
    print(f"  [存储] 已保存 {paper_name}/{membrane_id} 版本: {timestamp}.json")
    return save_path


def is_membrane_extracted(paper_name: str, membrane_id: str) -> bool:
    """
    检查某个膜是否已有提取结果（至少一个版本文件）。

    Args:
        paper_name: 论文名称
        membrane_id: 膜名称

    Returns:
        True 表示已有提取版本，False 表示未提取
    """
    versions_dir = get_membrane_versions_dir(paper_name, membrane_id)
    if not versions_dir.exists():
        return False
    return any(versions_dir.glob("*.json"))


def load_membrane_versions(paper_name: str,membrane_id: str) -> List[MembraneData]:
    """
    读取某个膜的所有历史版本，按时间升序排列。

    Args:
        paper_name: 论文名称
        membrane_id: 膜名称

    Returns:
        该膜的所有历史版本列表，无版本时返回空列表
    """
    versions_dir = get_membrane_versions_dir(paper_name, membrane_id)
    if not versions_dir.exists():
        return []

    versions: List[MembraneData] = []
    for fp in sorted(versions_dir.glob("*.json")):
        data = load_json_safe(fp, default=None)
        if data is None:
            print(f"  [存储][警告] 跳过损坏版本 {fp.name}")
            continue
        try:
            versions.append(MembraneData(**data))
        except Exception as e:
            print(f"  [存储][警告] 跳过版本 {fp.name}: {e}")
            continue
    return versions


# ====================================================================
#region 均值聚合
# ====================================================================

def _average_membranes(membrane_list: List[MembraneData]) -> MembraneData:
    """
    对同一膜的多个版本实例取均值聚合。

    聚合规则：
      - ValueUnit 字段 → 取 value 均值，校验单位一致性（单位冲突标注 *）
      - 字符串/类别字段 → 第一个非空值
      - rejections 字典 → 按物质名分组取均值
      - data_sources → 并集去重（保持顺序）
      - notes → 合并为一条字符串

    Args:
        membrane_list: 同一膜的多个版本

    Returns:
        聚合后的 MembraneData
    """
    if not membrane_list:
        raise ValueError("membrane_list 不能为空")
    if len(membrane_list) == 1:
        return membrane_list[0]

    def collect(field: str) -> list:
        return [getattr(m, field) for m in membrane_list]

    # ValueUnit 字段聚合（校验单位一致性）
    vu_kwargs = {
        f: average_value_units(collect(f))
        for f in _VALUEUNIT_FIELDS
    }
    # 字符串字段聚合
    str_kwargs = {f: first_non_none(collect(f)) for f in _STRING_FIELDS}
    # 截留率字典聚合
    rejections_merged = merge_rejections(collect("rejections"))

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
        **vu_kwargs,
        **str_kwargs,
        rejections=rejections_merged,
        data_sources=all_sources,
        notes=merged_notes,
    )


def aggregate_membrane(
    paper_name: str,
    membrane_id: str,
    save: bool = True,
) -> Optional[MembraneData]:
    """
    聚合单个膜的所有历史版本，取均值。

    Args:
        paper_name: 论文名称
        membrane_id: 膜名称
        save: 是否将聚合结果写入 aggregated.json

    Returns:
        聚合后的 MembraneData，无版本时返回 None
    """
    versions = load_membrane_versions(paper_name, membrane_id)
    if not versions:
        return None

    aggregated = _average_membranes(versions)

    if save:
        agg_path = get_membrane_aggregated_path(paper_name, membrane_id)
        save_json(agg_path, aggregated.model_dump())
        print(
            f"  [存储] 已聚合 {paper_name}/{membrane_id}: "
            f"{len(versions)} 个版本 → 均值"
        )

    return aggregated


def aggregate_paper(
    paper_name: str,
    save: bool = True,
) -> List[MembraneData]:
    """
    聚合整篇论文的所有膜：逐个膜聚合后合并。

    Args:
        paper_name: 论文名称
        save: 是否将整篇论文的聚合结果写入 _paper_aggregated.json

    Returns:
        该论文所有膜的聚合结果列表
    """
    membrane_ids = scan_extracted_membranes(paper_name)
    if not membrane_ids:
        print(f"  [存储] {paper_name} 无已提取膜，跳过聚合")
        return []

    aggregated: List[MembraneData] = []
    for mid in membrane_ids:
        result = aggregate_membrane(paper_name, mid, save=save)
        if result:
            aggregated.append(result)

    if save and aggregated:
        paper_agg_path = get_paper_aggregated_path(paper_name)
        save_json(
            paper_agg_path,
            [m.model_dump() for m in aggregated],
        )
        print(
            f"  [存储] 已聚合论文 {paper_name}: "
            f"{len(aggregated)} 种膜 → {paper_agg_path.name}"
        )

    return aggregated
