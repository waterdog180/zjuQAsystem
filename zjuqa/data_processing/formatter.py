"""
formatter.py —— 膜提取数据格式化工具（表格输出）。

读取所有已识别、提取完成的膜数据，应用单位归一化和截留物名称映射，
整理为表格形式（pandas DataFrame），支持导出 CSV。

设计原则：
  1. 只读 extracted/ 文件夹，不修改原始提取数据
  2. 应用单位归一化（unit_normalizer）和截留物映射（substance_mapper）
  3. 通量与比通量分列：pure_water_flux（LMH）与 pure_water_permeance（LMH/bar）
     是不同物理量（J = A × ΔP），各自独立成列，不交叉换算
  4. 输出为 pandas DataFrame，每行一个膜，每列一个参数
  5. 截留率展开为多列（如 rejection_Na2SO4, rejection_NaCl）
  6. 自动扫描通量/比通量数据缺口，输出缺口报告

使用说明：
    from zjuqa.data_processing.formatter import build_dataframe, export_csv, scan_flux_gaps
    # 构建表格（通量与比通量自动分列）
    df = build_dataframe()
    # 扫描通量数据缺口
    gaps = scan_flux_gaps()
    # 导出 CSV
    export_csv(df, "membrane_dataset.csv")
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from ..config.paths import get_membrane_aggregated_path, get_paper_aggregated_path
from ..schemas.membrane import MembraneData, ValueUnit
from ..utils.io import load_json_safe
from ..utils.scanner import scan_extracted_membranes, scan_extracted_papers
from .substance_mapper import map_substances
from .unit_normalizer import (
    NormalizedValue,
    classify_flux_unit,
    normalize_flux_value,
    normalize_membrane,
    normalize_value,
)


# ====================================================================
# 数据加载（只读 extracted/）
# ====================================================================

def load_all_membranes(verbose: bool = True) -> List[Tuple[str, MembraneData]]:
    """
    加载所有论文的所有膜聚合数据。

    优先读取 _paper_aggregated.json（整篇论文聚合），
    若该文件不存在、为空列表、或解析后膜数量为 0，则回退到逐个读取单膜 aggregated.json。

    Args:
        verbose: 是否打印加载诊断信息

    Returns:
        列表，每项为 (paper_name, membrane_data) 元组
    """
    papers = scan_extracted_papers()
    all_membranes: List[Tuple[str, MembraneData]] = []
    parse_failures = 0
    skipped = 0

    for paper_name in papers:
        paper_membranes: List[MembraneData] = []
        paper_agg_path = get_paper_aggregated_path(paper_name)

        # 优先读取整篇论文聚合
        if paper_agg_path.exists():
            data = load_json_safe(paper_agg_path, default=None)
            if isinstance(data, list) and len(data) > 0:
                for idx, item in enumerate(data):
                    try:
                        paper_membranes.append(MembraneData(**item))
                    except Exception as e:
                        parse_failures += 1
                        if verbose:
                            mid = item.get("membrane_id", f"#{idx}") if isinstance(item, dict) else f"#{idx}"
                            print(f"  [加载][警告] {paper_name}/{mid} 解析失败: {e}")

        # 回退：整篇聚合不存在、为空、或解析后 0 个膜
        if len(paper_membranes) == 0:
            membrane_ids = scan_extracted_membranes(paper_name)
            for mid in membrane_ids:
                agg_path = get_membrane_aggregated_path(paper_name, mid)
                if agg_path.exists():
                    data = load_json_safe(agg_path, default=None)
                    if data:
                        try:
                            paper_membranes.append(MembraneData(**data))
                        except Exception as e:
                            parse_failures += 1
                            if verbose:
                                print(f"  [加载][警告] {paper_name}/{mid} 解析失败: {e}")
                    else:
                        skipped += 1
                        if verbose:
                            print(f"  [加载][警告] {paper_name}/{mid}/aggregated.json 为空")
                else:
                    skipped += 1

        for mem in paper_membranes:
            all_membranes.append((paper_name, mem))

    if verbose:
        print(f"[加载] 扫描到 {len(papers)} 篇论文，成功加载 {len(all_membranes)} 种膜"
              f"（解析失败 {parse_failures}，跳过 {skipped}）")

    return all_membranes


# ====================================================================
# 表格构建
# ====================================================================

# 非通量的 ValueUnit 字段（12个，通量单独处理）
_NON_FLUX_FIELDS = [
    "Substrate_pore_size", "Substrate_MWCO", "Substrate_Water_contact_angle",
    "Substrate_zeta", "Substrate_Ra", "PIP_Concentration", "TMC_Concentration",
    "Degree_of_crosslinking", "Thickness", "Effective_pore_size",
    "Zeta_potential", "Membrane_Ra",
]

# 输出表格中的通量相关列（分列）
_FLUX_OUTPUT_FIELDS = ["pure_water_flux", "pure_water_permeance"]

# 所有数值输出字段
_VALUE_FIELDS = _NON_FLUX_FIELDS + _FLUX_OUTPUT_FIELDS


def build_dataframe(
    normalize_units: bool = True,
    map_substances_names: bool = True,
    include_notes: bool = False,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    构建膜参数表格（pandas DataFrame）。

    每行一个膜，列包括：
      - 基础信息: paper_name, membrane_id, substrate
      - 12个非通量数值参数 + 通量/比通量分列（共14个数值列）
      - 截留率: rejection_<物质名> 展开为多列
      - 元信息: data_sources, notes（可选）

    通量分列逻辑：
      - 原始 pure_water_flux 字段的单位若含 bar（如 LMH/bar）→ 放入 pure_water_permeance 列
      - 若不含 bar（如 LMH）→ 放入 pure_water_flux 列
      - 两列各自归一化到标准单位（LMH / LMH/bar）

    Args:
        normalize_units:     是否应用单位归一化（默认 True）
        map_substances_names: 是否应用截留物名称映射（默认 True）
        include_notes:       是否包含 notes 和 data_sources 列（默认 False）
        verbose:             是否打印进度信息

    Returns:
        pandas DataFrame
    """
    all_membranes = load_all_membranes(verbose=verbose)

    if not all_membranes:
        if verbose:
            print("[格式化] 未找到任何膜数据")
        return pd.DataFrame()

    rows: List[dict] = []
    all_rejection_substances: set = set()
    normalization_issues: List[dict] = []

    for paper_name, mem in all_membranes:
        row: dict = {
            "paper_name": paper_name,
            "membrane_id": mem.membrane_id,
            "substrate": mem.substrate,
        }

        # --- 单位归一化（非通量字段） ---
        if normalize_units:
            normalized_mem, norm_report = normalize_membrane(mem)
            for field, result in norm_report.items():
                if result.needs_more_info or result.value is None:
                    normalization_issues.append({
                        "paper": paper_name,
                        "membrane": mem.membrane_id,
                        "field": field,
                        "original_unit": result.original_unit,
                        "note": result.note,
                    })
            source_mem = normalized_mem
        else:
            source_mem = mem

        # --- 12个非通量数值字段 ---
        for field in _NON_FLUX_FIELDS:
            vu = getattr(source_mem, field)
            if vu is not None and isinstance(vu, ValueUnit):
                row[field] = vu.value
                row[f"{field}__unit"] = vu.unit
            else:
                row[field] = None
                row[f"{field}__unit"] = None

        # --- 通量/比通量分列 ---
        # 初始化两列为空
        row["pure_water_flux"] = None
        row["pure_water_flux__unit"] = None
        row["pure_water_permeance"] = None
        row["pure_water_permeance__unit"] = None

        original_flux = mem.pure_water_flux
        if original_flux is not None and isinstance(original_flux, ValueUnit):
            if normalize_units:
                target_field, result = normalize_flux_value(
                    original_flux.value, original_flux.unit
                )
                if result.value is not None:
                    row[target_field] = result.value
                    row[f"{target_field}__unit"] = result.unit
                else:
                    # 归一化失败，保留原始值到对应列
                    flux_type = classify_flux_unit(original_flux.unit)
                    target = "pure_water_permeance" if flux_type == "permeance" else "pure_water_flux"
                    row[target] = original_flux.value
                    row[f"{target}__unit"] = original_flux.unit
                    normalization_issues.append({
                        "paper": paper_name,
                        "membrane": mem.membrane_id,
                        "field": target,
                        "original_unit": original_flux.unit,
                        "note": result.note,
                    })
            else:
                # 不归一化，按单位分类放入对应列
                flux_type = classify_flux_unit(original_flux.unit)
                target = "pure_water_permeance" if flux_type == "permeance" else "pure_water_flux"
                row[target] = original_flux.value
                row[f"{target}__unit"] = original_flux.unit

        # --- 截留率映射与展开 ---
        rejections = mem.rejections or {}
        if map_substances_names and rejections:
            rejections, _ = map_substances(rejections)

        for substance, vu in rejections.items():
            col = f"rejection_{substance}"
            if vu is not None and isinstance(vu, ValueUnit):
                row[col] = vu.value
                all_rejection_substances.add(substance)
            else:
                row[col] = None

        # --- 可选元信息 ---
        if include_notes:
            row["data_sources"] = json.dumps(mem.data_sources, ensure_ascii=False) if mem.data_sources else None
            row["notes"] = mem.notes

        rows.append(row)

    df = pd.DataFrame(rows)

    # 确保所有截留率列都存在（即使某些膜没有该物质）
    for substance in sorted(all_rejection_substances):
        col = f"rejection_{substance}"
        if col not in df.columns:
            df[col] = None

    if verbose:
        print(f"[格式化] 构建完成: {len(df)} 行 × {len(df.columns)} 列")
        print(f"  非通量参数: {len(_NON_FLUX_FIELDS)} 个")
        print(f"  通量分列: pure_water_flux (LMH) + pure_water_permeance (LMH/bar)")
        print(f"  截留率物质: {len(all_rejection_substances)} 种")
        if normalization_issues:
            print(f"  单位归一化问题: {len(normalization_issues)} 项")

    return df


# ====================================================================
# 通量数据缺口扫描
# ====================================================================

def scan_flux_gaps(
    verbose: bool = True,
) -> Dict[str, list]:
    """
    扫描通量/比通量数据缺口。

    通量（flux, LMH）与比通量（permeance, LMH/bar）关系为 J = A × ΔP。
    若已知其中一个量和操作压力 ΔP，可计算另一个量。
    当前 schema 无 operating_pressure 字段，因此仅扫描缺口，不自动计算。

    Args:
        verbose: 是否打印缺口报告

    Returns:
        字典，包含：
        - "has_permeance_no_flux": 有比通量但无通量的膜列表（可通过 ΔP 计算通量）
        - "has_flux_no_permeance": 有通量但无比通量的膜列表（可通过 ΔP 计算比通量）
        - "has_neither": 两者都没有的膜列表
        - "has_both": 两者都有的膜列表
        - "summary": 统计摘要
    """
    all_membranes = load_all_membranes(verbose=False)

    has_perm_no_flux: List[dict] = []
    has_flux_no_perm: List[dict] = []
    has_neither: List[dict] = []
    has_both: List[dict] = []

    for paper_name, mem in all_membranes:
        vu = mem.pure_water_flux
        info = {"paper": paper_name, "membrane": mem.membrane_id}

        if vu is None:
            has_neither.append(info)
            continue

        flux_type = classify_flux_unit(vu.unit)
        info["value"] = vu.value
        info["unit"] = vu.unit

        if flux_type == "permeance":
            has_perm_no_flux.append(info)
        elif flux_type == "flux":
            has_flux_no_perm.append(info)
        else:
            # 未知单位，归入 has_neither 并标记
            info["note"] = f"未知通量单位 '{vu.unit}'"
            has_neither.append(info)

    result = {
        "has_permeance_no_flux": has_perm_no_flux,
        "has_flux_no_permeance": has_flux_no_perm,
        "has_neither": has_neither,
        "has_both": has_both,  # 当前 schema 单字段，不可能两者都有，预留
        "summary": {
            "total": len(all_membranes),
            "has_permeance": len(has_perm_no_flux),
            "has_flux": len(has_flux_no_perm),
            "has_neither": len(has_neither),
            "has_both": len(has_both),
            "calculable_with_pressure": len(has_perm_no_flux) + len(has_flux_no_perm),
        },
    }

    if verbose:
        s = result["summary"]
        print(f"=== 通量数据缺口扫描 ===")
        print(f"  总膜数: {s['total']}")
        print(f"  有比通量(LMH/bar)、无通量(LMH): {s['has_permeance']} 个 → 补充ΔP后可计算通量")
        print(f"  有通量(LMH)、无比通量(LMH/bar): {s['has_flux']} 个 → 补充ΔP后可计算比通量")
        print(f"  两者皆无: {s['has_neither']} 个")
        print(f"  可通过ΔP补全: {s['calculable_with_pressure']} 个")
        print()
        if has_perm_no_flux:
            print(f"  有比通量无通量（需ΔP计算J=A×ΔP）:")
            for item in has_perm_no_flux:
                print(f"    {item['paper']}/{item['membrane']}: {item['value']} {item['unit']}")
        if has_flux_no_perm:
            print(f"  有通量无比通量（需ΔP计算A=J/ΔP）:")
            for item in has_flux_no_perm:
                print(f"    {item['paper']}/{item['membrane']}: {item['value']} {item['unit']}")
        if has_neither:
            print(f"  无通量数据:")
            for item in has_neither:
                note = f" ({item.get('note', '')})" if 'note' in item else ""
                print(f"    {item['paper']}/{item['membrane']}{note}")

    return result


# ====================================================================
# 导出与打印
# ====================================================================

def export_csv(
    df: pd.DataFrame,
    output_path: str,
    encoding: str = "utf-8-sig",
) -> str:
    """
    将 DataFrame 导出为 CSV 文件。

    Args:
        df:          要导出的 DataFrame
        output_path: 输出文件路径
        encoding:    文件编码（默认 utf-8-sig，Excel 兼容）

    Returns:
        输出文件的绝对路径
    """
    out = Path(output_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False, encoding=encoding)
    print(f"[导出] 已保存: {out} ({len(df)} 行 × {len(df.columns)} 列)")
    return str(out)


def print_summary(df: pd.DataFrame) -> None:
    """
    打印 DataFrame 的摘要信息（行数、列数、各列非空率）。

    Args:
        df: 要摘要的 DataFrame
    """
    if df.empty:
        print("[摘要] 空 DataFrame")
        return

    print(f"=== 膜参数数据集摘要 ===")
    print(f"  总膜数: {len(df)}")
    print(f"  论文数: {df['paper_name'].nunique()}")
    print(f"  总列数: {len(df.columns)}")
    print()

    # 非通量参数非空率
    print("  非通量参数非空率:")
    for field in _NON_FLUX_FIELDS:
        if field in df.columns:
            non_null = df[field].notna().sum()
            pct = non_null / len(df) * 100
            print(f"    {field:30s} {non_null:3d}/{len(df)} ({pct:5.1f}%)")

    # 通量分列非空率
    print()
    print("  通量/比通量非空率:")
    for field in _FLUX_OUTPUT_FIELDS:
        if field in df.columns:
            non_null = df[field].notna().sum()
            pct = non_null / len(df) * 100
            unit = df[f"{field}__unit"].dropna().unique()
            unit_str = unit[0] if len(unit) == 1 else f"{list(unit)}"
            print(f"    {field:30s} {non_null:3d}/{len(df)} ({pct:5.1f}%)  [{unit_str}]")

    # 截留率列
    rej_cols = [c for c in df.columns if c.startswith("rejection_")]
    if rej_cols:
        print(f"\n  截留率物质 ({len(rej_cols)} 种):")
        for col in sorted(rej_cols):
            non_null = df[col].notna().sum()
            pct = non_null / len(df) * 100
            print(f"    {col:35s} {non_null:3d}/{len(df)} ({pct:5.1f}%)")


def get_normalization_report(
    verbose: bool = True,
) -> List[dict]:
    """
    获取所有膜的单位归一化问题报告。

    Returns:
        归一化问题列表，每项包含 paper, membrane, field, original_unit, note
    """
    all_membranes = load_all_membranes(verbose=False)
    issues: List[dict] = []

    for paper_name, mem in all_membranes:
        _, norm_report = normalize_membrane(mem)
        for field, result in norm_report.items():
            if result.needs_more_info or result.value is None:
                issues.append({
                    "paper": paper_name,
                    "membrane": mem.membrane_id,
                    "field": field,
                    "original_unit": result.original_unit,
                    "is_approximate": result.is_approximate,
                    "note": result.note,
                })

    if verbose and issues:
        print(f"[归一化报告] 发现 {len(issues)} 项问题:")
        for issue in issues:
            print(f"  {issue['paper']}/{issue['membrane']} - {issue['field']}: "
                  f"{issue['original_unit']} → {issue['note']}")
    elif verbose:
        print("[归一化报告] 无单位归一化问题")

    return issues
