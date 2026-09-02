"""
analytics.py —— 膜参数提取数据的分析统计工具。

提供两个核心统计功能，供人工介入观察与数据聚合前期调研：
  1. report_missing_data()  — 统计不同论文/膜的参数缺失情况，计算各参数缺失率
  2. report_unit_distribution() — 统计各参数使用的单位分布，为单位归一化提供依据

数据来源：data/extracted/<paper>/_paper_aggregated.json（整篇论文聚合结果）
         或 data/extracted/<paper>/<membrane>/aggregated.json（单膜聚合结果）

使用说明：
    from zjuqa.utils.analytics import report_missing_data, report_unit_distribution

    # 数据缺失统计（输出到控制台）
    report_missing_data()

    # 单位分布统计（输出到控制台）
    report_unit_distribution()

    # 保存为 JSON 文件
    missing_report = report_missing_data(output_json="data/missing_report.json")
    unit_report = report_unit_distribution(output_json="data/unit_report.json")
"""

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..config.paths import EXTRACTED_DIR
from ..schemas.membrane import MembraneData, ValueUnit
from ..utils.io import load_json_safe, save_json
from ..utils.path_utils import get_paper_aggregated_path
from ..utils.scanner import scan_extracted_papers


# ====================================================================
# 参数分类定义（用于统计报告）
# ====================================================================

# 所有 ValueUnit 数值字段（按类别分组）
PARAM_CATEGORIES: Dict[str, List[str]] = {
    "支撑层属性": [
        "Substrate_pore_size",
        "Substrate_MWCO",
        "Substrate_Water_contact_angle",
        "Substrate_zeta",
        "Substrate_Ra",
    ],
    "制备参数": [
        "PIP_Concentration",
        "TMC_Concentration",
        "Degree_of_crosslinking",
    ],
    "结构参数": [
        "Thickness",
        "Effective_pore_size",
        "Zeta_potential",
        "Membrane_Ra",
    ],
    "性能参数": [
        "pure_water_flux",
    ],
}

# 所有 ValueUnit 字段的扁平列表
ALL_VALUE_FIELDS: List[str] = [
    field for fields in PARAM_CATEGORIES.values() for field in fields
]

# 字段中文名映射
FIELD_NAMES_CN: Dict[str, str] = {
    "membrane_id": "膜名称",
    "substrate": "支撑层材料",
    "Substrate_pore_size": "支撑层孔径",
    "Substrate_MWCO": "支撑层MWCO",
    "Substrate_Water_contact_angle": "支撑层接触角",
    "Substrate_zeta": "支撑层zeta电位",
    "Substrate_Ra": "支撑层粗糙度",
    "PIP_Concentration": "PIP浓度",
    "TMC_Concentration": "TMC浓度",
    "Degree_of_crosslinking": "交联度(O/N)",
    "Thickness": "皮层厚度",
    "Effective_pore_size": "有效孔径",
    "Zeta_potential": "皮层zeta电位",
    "Membrane_Ra": "皮层粗糙度",
    "pure_water_flux": "纯水通量",
    "rejections": "截留率",
}


# ====================================================================
# 数据加载
# ====================================================================

def _load_all_membranes(verbose: bool = True) -> List[Tuple[str, MembraneData]]:
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
    skipped_membranes = 0
    parse_failures = 0

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

        # 回退条件：整篇聚合不存在、为空、或解析后 0 个膜
        if len(paper_membranes) == 0:
            paper_dir = EXTRACTED_DIR / paper_name
            if paper_dir.exists():
                for membrane_dir in sorted(paper_dir.iterdir()):
                    if not membrane_dir.is_dir() or membrane_dir.name.startswith("_"):
                        continue
                    agg_path = membrane_dir / "aggregated.json"
                    if agg_path.exists():
                        data = load_json_safe(agg_path, default=None)
                        if data:
                            try:
                                paper_membranes.append(MembraneData(**data))
                            except Exception as e:
                                parse_failures += 1
                                if verbose:
                                    print(f"  [加载][警告] {paper_name}/{membrane_dir.name} 解析失败: {e}")
                        else:
                            skipped_membranes += 1
                            if verbose:
                                print(f"  [加载][警告] {paper_name}/{membrane_dir.name}/aggregated.json 为空")
                    else:
                        skipped_membranes += 1
                        if verbose:
                            print(f"  [加载][警告] {paper_name}/{membrane_dir.name}/aggregated.json 不存在")

        for mem in paper_membranes:
            all_membranes.append((paper_name, mem))

    if verbose:
        print(f"[加载] 扫描到 {len(papers)} 篇论文，成功加载 {len(all_membranes)} 种膜"
              f"（解析失败 {parse_failures}，跳过无聚合 {skipped_membranes}）")

    return all_membranes


# ====================================================================
# 工具1：数据缺失统计
# ====================================================================

def report_missing_data(
    output_json: Optional[str] = None,
    verbose: bool = True,
    substances: Optional[List[str]] = None,
    min_substance_freq: int = 50,
) -> dict:
    """
    统计不同论文提取数据的缺失情况。

    统计维度：
      1. 每篇论文的参数缺失情况（哪些参数有值，哪些缺失）
      2. 每个参数在所有膜中的缺失率（百分比）
      3. 截留率物质覆盖统计（哪些物质被提取过，频率如何）
      4. 按类别的整体缺失率

    Args:
        output_json: 保存报告为 JSON 文件的路径，None 则不保存
        verbose:     是否打印到控制台

    Returns:
        统计报告字典
    """
    all_membranes = _load_all_membranes()
    total_membranes = len(all_membranes)

    if total_membranes == 0:
        if verbose:
            print("[分析] 未找到任何已提取的膜数据，请先运行提取流程。")
        return {"total_membranes": 0, "note": "无数据"}

    # --- 截留率物质筛选 ---
    # 先统计所有物质的出现次数
    all_substance_counter: Counter = Counter()
    for _, mem in all_membranes:
        if mem.rejections:
            valid_rej = {k: v for k, v in mem.rejections.items() if v is not None}
            for substance in valid_rej:
                all_substance_counter[substance] += 1

    # 确定筛选物质列表
    if substances is None:
        # 自动选取出现次数 > min_substance_freq 的物质
        substances = [
            sub for sub, cnt in all_substance_counter.most_common()
            if cnt > min_substance_freq
        ]
        if substances and verbose:
            print(f"[分析] 自动筛选出现次数>{min_substance_freq}的截留物质: {substances}")

    # 筛选膜：rejections 中包含列表中任一物质（并集）
    filtered_membranes: List[Tuple[str, MembraneData]] = []
    if substances:
        substance_set = set(substances)
        for paper_name, mem in all_membranes:
            if mem.rejections:
                valid_rej = {k: v for k, v in mem.rejections.items() if v is not None}
                if substance_set & set(valid_rej.keys()):
                    filtered_membranes.append((paper_name, mem))
        if verbose:
            print(f"[分析] 截留物质筛选: {len(filtered_membranes)}/{total_membranes} 种膜包含指定物质")
    else:
        filtered_membranes = all_membranes

    total_membranes = len(filtered_membranes)
    if total_membranes == 0:
        if verbose:
            print("[分析] 筛选后无符合条件的膜数据。")
        return {"total_membranes": 0, "note": "筛选后无数据", "filter_substances": substances}

    # 按论文分组
    papers_membranes: Dict[str, List[MembraneData]] = defaultdict(list)
    for paper_name, mem in filtered_membranes:
        papers_membranes[paper_name].append(mem)

    # --- 维度1：每个参数的整体缺失率 ---
    field_missing_count: Dict[str, int] = {f: 0 for f in ALL_VALUE_FIELDS}
    field_present_count: Dict[str, int] = {f: 0 for f in ALL_VALUE_FIELDS}

    for _, mem in filtered_membranes:
        for field in ALL_VALUE_FIELDS:
            if getattr(mem, field) is not None:
                field_present_count[field] += 1
            else:
                field_missing_count[field] += 1

    # substrate 和 membrane_id 单独统计
    substrate_present = sum(1 for _, m in filtered_membranes if m.substrate)

    # --- 维度2：截留率物质覆盖统计 ---
    substance_counter: Counter = Counter()
    membranes_with_rejections = 0
    for _, mem in filtered_membranes:
        if mem.rejections:
            # 只统计有实际值（非 None）的截留率，排除 {"NaCl": None} 这种空值
            valid_rej = {k: v for k, v in mem.rejections.items() if v is not None}
            if valid_rej:
                membranes_with_rejections += 1
                for substance in valid_rej:
                    substance_counter[substance] += 1

    # --- 维度3：数据全部完整的膜数量 ---
    # 定义：所有 ALL_VALUE_FIELDS 字段非 None + substrate 非空
    fully_complete_membranes = 0
    fully_complete_list: List[str] = []
    for paper_name, mem in filtered_membranes:
        all_fields_present = all(
            getattr(mem, field) is not None for field in ALL_VALUE_FIELDS
        )
        if all_fields_present and mem.substrate:
            fully_complete_membranes += 1
            fully_complete_list.append(f"{paper_name}/{mem.membrane_id}")

    # --- 维度4：每篇论文的缺失情况 ---
    paper_reports: Dict[str, dict] = {}
    for paper_name, membranes in papers_membranes.items():
        n_membranes = len(membranes)
        # 该论文中每个参数的有值膜数
        paper_field_present: Dict[str, int] = {f: 0 for f in ALL_VALUE_FIELDS}
        paper_substances: set = set()
        for mem in membranes:
            for field in ALL_VALUE_FIELDS:
                if getattr(mem, field) is not None:
                    paper_field_present[field] += 1
            if mem.rejections:
                valid_rej = {k: v for k, v in mem.rejections.items() if v is not None}
                paper_substances.update(valid_rej.keys())

        paper_reports[paper_name] = {
            "membrane_count": n_membranes,
            "field_present": paper_field_present,
            "rejection_substances": sorted(paper_substances),
        }

    # --- 维度4：按类别缺失率 ---
    category_missing: Dict[str, dict] = {}
    for category, fields in PARAM_CATEGORIES.items():
        total_possible = total_membranes * len(fields)
        total_present = sum(field_present_count[f] for f in fields)
        missing_rate = (1 - total_present / total_possible) * 100 if total_possible else 0
        category_missing[category] = {
            "fields": fields,
            "present": total_present,
            "total": total_possible,
            "missing_rate_pct": round(missing_rate, 1),
        }

    # --- 组装报告 ---
    report = {
        "filter": {
            "substances": substances,
            "min_substance_freq": min_substance_freq if not substances else None,
            "filtered_from_total": len(all_membranes),
        },
        "summary": {
            "total_papers": len(papers_membranes),
            "total_membranes": total_membranes,
            "substrate_present": substrate_present,
            "substrate_missing_rate_pct": round(
                (1 - substrate_present / total_membranes) * 100, 1
            ),
            "membranes_with_rejections": membranes_with_rejections,
            "rejections_coverage_pct": round(
                membranes_with_rejections / total_membranes * 100, 1
            ),
            "fully_complete_membranes": fully_complete_membranes,
            "fully_complete_rate_pct": round(
                fully_complete_membranes / total_membranes * 100, 1
            ),
        },
        "field_missing_rate": {
            field: {
                "present": field_present_count[field],
                "missing": field_missing_count[field],
                "missing_rate_pct": round(
                    field_missing_count[field] / total_membranes * 100, 1
                ),
            }
            for field in ALL_VALUE_FIELDS
        },
        "category_missing_rate": category_missing,
        "rejection_substances": dict(substance_counter.most_common()),
        "fully_complete_list": fully_complete_list,
        "per_paper": paper_reports,
    }

    # --- 打印报告 ---
    if verbose:
        _print_missing_report(report)

    # --- 保存 JSON ---
    if output_json:
        save_json(output_json, report)
        if verbose:
            print(f"\n[分析] 报告已保存至: {output_json}")

    return report


def _print_missing_report(report: dict) -> None:
    """格式化打印数据缺失报告。"""
    s = report["summary"]
    print("=" * 70)
    print("膜参数提取数据 — 缺失情况统计报告")
    print("=" * 70)

    print(f"\n【总览】")
    # 筛选信息
    if report.get("filter", {}).get("substances"):
        print(f"  筛选截留物质: {', '.join(report['filter']['substances'])}")
        print(f"  筛选范围: {s['total_membranes']}/{report['filter']['filtered_from_total']} 种膜")
    print(f"  论文数: {s['total_papers']}")
    print(f"  膜总数: {s['total_membranes']}")
    print(f"  支撑层材料有值: {s['substrate_present']}/{s['total_membranes']} "
          f"(缺失率 {s['substrate_missing_rate_pct']}%)")
    print(f"  有截留率数据的膜: {s['membranes_with_rejections']}/{s['total_membranes']} "
          f"(覆盖率 {s['rejections_coverage_pct']}%)")
    print(f"  数据全部完整的膜: {s['fully_complete_membranes']}/{s['total_membranes']} "
          f"(完整率 {s['fully_complete_rate_pct']}%)")

    print(f"\n【按类别缺失率】")
    for category, info in report["category_missing_rate"].items():
        print(f"  {category}: 缺失率 {info['missing_rate_pct']}% "
              f"({info['present']}/{info['total']} 有值)")

    print(f"\n【各参数缺失率（按缺失率降序）】")
    sorted_fields = sorted(
        report["field_missing_rate"].items(),
        key=lambda x: x[1]["missing_rate_pct"],
        reverse=True,
    )
    for field, info in sorted_fields:
        name_cn = FIELD_NAMES_CN.get(field, field)
        bar = "█" * int(info["missing_rate_pct"] / 5) + "░" * (20 - int(info["missing_rate_pct"] / 5))
        print(f"  {name_cn:<14} {bar} {info['missing_rate_pct']:>5.1f}%  "
              f"({info['present']}/{s['total_membranes']} 有值)")

    print(f"\n【截留率物质覆盖（共 {len(report['rejection_substances'])} 种）】")
    for substance, count in report["rejection_substances"].items():
        print(f"  {substance:<16}: {count} 篇膜")

    print(f"\n【各论文详情】")
    for paper_name, info in report["per_paper"].items():
        print(f"\n  ── {paper_name} ({info['membrane_count']} 种膜) ──")
        # 该论文缺失率最高的5个参数
        paper_fields = sorted(
            info["field_present"].items(),
            key=lambda x: x[1],
        )
        missing_fields = [(f, c) for f, c in paper_fields if c == 0]
        partial_fields = [(f, c) for f, c in paper_fields if 0 < c < info["membrane_count"]]
        if missing_fields:
            names = ", ".join(FIELD_NAMES_CN.get(f, f) for f, _ in missing_fields)
            print(f"    完全缺失: {names}")
        if partial_fields:
            parts = ", ".join(
                f"{FIELD_NAMES_CN.get(f, f)}({c}/{info['membrane_count']})"
                for f, c in partial_fields
            )
            print(f"    部分缺失: {parts}")
        print(f"    截留率物质: {', '.join(info['rejection_substances']) or '无'}")

    print("\n" + "=" * 70)


# ====================================================================
# 工具2：单位分布统计
# ====================================================================

def report_unit_distribution(
    output_json: Optional[str] = None,
    verbose: bool = True,
) -> dict:
    """
    统计各个参数所使用的单位分布，为后续单位归一化提供前期调研。

    统计维度：
      1. 每个 ValueUnit 字段的单位分布（单位 → 出现次数）
      2. 单位冲突标记（同一参数出现多种单位）
      3. 截留率单位统计
      4. 推荐的标准单位（基于出现频率最高的单位）

    Args:
        output_json: 保存报告为 JSON 文件的路径，None 则不保存
        verbose:     是否打印到控制台

    Returns:
        统计报告字典
    """
    all_membranes = _load_all_membranes()
    total_membranes = len(all_membranes)

    if total_membranes == 0:
        if verbose:
            print("[分析] 未找到任何已提取的膜数据，请先运行提取流程。")
        return {"total_membranes": 0, "note": "无数据"}

    # 每个字段的单位计数器
    field_unit_counters: Dict[str, Counter] = {
        f: Counter() for f in ALL_VALUE_FIELDS
    }
    # 截留率单位计数器
    rejection_unit_counter: Counter = Counter()
    # 截留率物质-单位组合
    rejection_substance_units: Dict[str, Counter] = defaultdict(Counter)

    for _, mem in all_membranes:
        for field in ALL_VALUE_FIELDS:
            vu = getattr(mem, field)
            if vu is not None and isinstance(vu, ValueUnit):
                field_unit_counters[field][vu.unit] += 1
        if mem.rejections:
            for substance, vu in mem.rejections.items():
                if vu is not None and isinstance(vu, ValueUnit):
                    rejection_unit_counter[vu.unit] += 1
                    rejection_substance_units[substance][vu.unit] += 1

    # 组装每个字段的单位报告
    field_reports: Dict[str, dict] = {}
    for field in ALL_VALUE_FIELDS:
        counter = field_unit_counters[field]
        total_with_unit = sum(counter.values())
        units = dict(counter.most_common())
        has_conflict = len(units) > 1
        recommended = list(units.keys())[0] if units else None

        field_reports[field] = {
            "name_cn": FIELD_NAMES_CN.get(field, field),
            "total_with_value": total_with_unit,
            "units": units,
            "has_unit_conflict": has_conflict,
            "recommended_unit": recommended,
        }

    # 截留率单位报告
    rejection_report = {
        "total_with_value": sum(rejection_unit_counter.values()),
        "units": dict(rejection_unit_counter.most_common()),
        "has_unit_conflict": len(rejection_unit_counter) > 1,
        "recommended_unit": list(rejection_unit_counter.keys())[0] if rejection_unit_counter else None,
        "per_substance": {
            sub: dict(counter.most_common())
            for sub, counter in rejection_substance_units.items()
        },
    }

    # 汇总有单位冲突的字段
    conflict_fields = [
        f for f, r in field_reports.items() if r["has_unit_conflict"]
    ]

    report = {
        "summary": {
            "total_membranes": total_membranes,
            "fields_with_unit_conflict": conflict_fields,
            "conflict_count": len(conflict_fields),
        },
        "field_units": field_reports,
        "rejection_units": rejection_report,
    }

    # 打印报告
    if verbose:
        _print_unit_report(report)

    # 保存 JSON
    if output_json:
        save_json(output_json, report)
        if verbose:
            print(f"\n[分析] 报告已保存至: {output_json}")

    return report


def _print_unit_report(report: dict) -> None:
    """格式化打印单位分布报告。"""
    s = report["summary"]
    print("=" * 70)
    print("膜参数提取数据 — 单位分布统计报告")
    print("=" * 70)

    print(f"\n【总览】")
    print(f"  膜总数: {s['total_membranes']}")
    print(f"  存在单位冲突的字段数: {s['conflict_count']}")
    if s["fields_with_unit_conflict"]:
        names = ", ".join(
            FIELD_NAMES_CN.get(f, f) for f in s["fields_with_unit_conflict"]
        )
        print(f"  冲突字段: {names}")

    print(f"\n【各参数单位分布】")
    for field, info in report["field_units"].items():
        if info["total_with_value"] == 0:
            print(f"  {info['name_cn']:<14}: (无数据)")
            continue
        conflict_mark = " ⚠️ 单位冲突" if info["has_unit_conflict"] else ""
        print(f"  {info['name_cn']:<14} (推荐: {info['recommended_unit']}){conflict_mark}")
        for unit, count in info["units"].items():
            pct = round(count / info["total_with_value"] * 100, 1)
            print(f"    {unit:<16}: {count:>3} 次 ({pct}%)")

    print(f"\n【截留率单位分布】")
    rj = report["rejection_units"]
    if rj["total_with_value"] == 0:
        print("  (无截留率数据)")
    else:
        conflict_mark = " ⚠️ 单位冲突" if rj["has_unit_conflict"] else ""
        print(f"  截留率 (推荐: {rj['recommended_unit']}){conflict_mark}")
        for unit, count in rj["units"].items():
            pct = round(count / rj["total_with_value"] * 100, 1)
            print(f"    {unit:<16}: {count:>3} 次 ({pct}%)")
        print(f"\n  按物质细分:")
        for substance, units in rj["per_substance"].items():
            unit_str = ", ".join(f"{u}({c})" for u, c in units.items())
            print(f"    {substance:<16}: {unit_str}")

    print(f"\n【单位归一化建议】")
    print("  以下字段存在多种单位，ML 训练前需统一：")
    for field in s["fields_with_unit_conflict"]:
        info = report["field_units"][field]
        print(f"    - {info['name_cn']}: 建议统一为 '{info['recommended_unit']}' "
              f"(出现频率最高)")
    if not s["fields_with_unit_conflict"]:
        print("    (无单位冲突，所有字段单位一致)")

    print("\n" + "=" * 70)


# ====================================================================
# 综合报告入口
# ====================================================================

def run_all_reports(
    output_dir: Optional[str] = None,
    verbose: bool = True,
    substances: Optional[List[str]] = None,
) -> dict:
    """
    执行所有分析报告，一次性输出数据缺失统计和单位分布统计。

    Args:
        output_dir:  报告输出目录，None 时不保存文件
        verbose:     是否打印到控制台
        substances:  截留率物质筛选列表，传递给 report_missing_data

    Returns:
        {"missing": missing_report, "units": unit_report}
    """
    results = {}

    if verbose:
        print("\n" + "=" * 70)
        print("运行全部分析报告")
        print("=" * 70)

    # 报告1：数据缺失统计
    missing_output = f"{output_dir}/missing_report.json" if output_dir else None
    results["missing"] = report_missing_data(
        output_json=missing_output,
        verbose=verbose,
        substances=substances,
    )

    # 报告2：单位分布统计
    units_output = f"{output_dir}/unit_report.json" if output_dir else None
    results["units"] = report_unit_distribution(
        output_json=units_output,
        verbose=verbose,
    )

    if verbose and output_dir:
        print(f"\n[分析] 全部报告已保存至: {output_dir}/")

    return results


# ====================================================================
# 命令行入口
# ====================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "units":
        report_unit_distribution()
    elif len(sys.argv) > 1 and sys.argv[1] == "missing":
        report_missing_data()
    elif len(sys.argv) > 1 and sys.argv[1] == "all":
        run_all_reports()
    else:
        print("用法:")
        print("  python -m zjuqa.utils.analytics missing   # 数据缺失统计")
        print("  python -m zjuqa.utils.analytics units     # 单位分布统计")
        print("  python -m zjuqa.utils.analytics all       # 全部报告")
