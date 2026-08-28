"""
unit_normalizer.py —— 基于枚举的膜参数单位归一化工具。

为每个参数定义标准单位和已知单位的换算函数，将不同单位的数据统一到标准单位。
不修改原始提取数据，返回归一化后的新值。

设计原则：
  1. 基于枚举：每个参数的标准单位由 StandardUnit 枚举定义
  2. 换算函数：每个已知单位对应一个 lambda 换算函数，接收原始值返回标准单位值
  3. 通量与比通量分列：pure_water_flux（通量，LMH）与 pure_water_permeance（比通量，LMH/bar）
     是两个不同物理量（J = A × ΔP），各自独立归一化，不交叉换算
  4. 近似换算标记：wt% → w/v% 等物理意义不同但常近似等价的换算，标记 is_approximate=True

使用说明：
    from zjuqa.data_processing.unit_normalizer import normalize_value, classify_flux_unit
    # 归一化单个值
    result = normalize_value("pure_water_flux", 80.0, "LMH")  # 通量→LMH
    result = normalize_value("pure_water_permeance", 15.0, "L/(m²·h·bar)")  # 比通量→LMH/bar
    # 判断通量单位类型
    flux_type = classify_flux_unit("LMH/bar")  # → "permeance"
"""

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, Optional, Tuple

from ..schemas.membrane import MembraneData, ValueUnit


# ====================================================================
# 标准单位枚举
# ====================================================================

class StandardUnit(Enum):
    """各参数的标准单位枚举。"""
    Substrate_pore_size = "nm"
    Substrate_MWCO = "kDa"
    Substrate_Water_contact_angle = "°"
    Substrate_zeta = "mV"
    Substrate_Ra = "nm"
    PIP_Concentration = "w/v%"
    TMC_Concentration = "w/v%"
    Degree_of_crosslinking = "ratio"
    Thickness = "nm"
    Effective_pore_size = "nm"
    Zeta_potential = "mV"
    Membrane_Ra = "nm"
    pure_water_flux = "LMH"               # 通量（flux, J），单位时间单位面积体积
    pure_water_permeance = "LMH/bar"      # 比通量（permeance, A），通量/压力


# ====================================================================
# 归一化结果数据类
# ====================================================================

@dataclass
class NormalizedValue:
    """
    单位归一化结果。

    Attributes:
        value:         归一化后的数值
        unit:          标准单位
        original_unit: 原始单位
        is_approximate: 是否为近似换算（物理意义不同但常近似等价）
        needs_more_info: 是否需要更多信息才能换算
        note:          额外说明
    """
    value: Optional[float]
    unit: str
    original_unit: str
    is_approximate: bool = False
    needs_more_info: bool = False
    note: str = ""


# ====================================================================
# 通量单位分类
# ====================================================================
# 通量（flux）与比通量（permeance）是不同物理量：
#   通量 J: 单位时间通过单位面积的体积，单位 LMH = L/(m²·h)
#   比通量 A: 通量除以操作压力，单位 LMH/bar = L/(m²·h·bar)
#   关系: J = A × ΔP（在一定压力范围内近似线性）
# 因此两者各自独立归一化，不交叉换算。
# ====================================================================

# 比通量单位（含 bar / pressure）
_PERMEANCE_UNITS = {
    "LMH/bar", "LMH/bar*",
    "L/(m²·h·bar)", "L/(m2·h·bar)", "L/(m2/h/bar)",
    "L·m⁻²·h⁻¹·bar⁻¹", "L·m^-2·h^-1·bar^-1",
    "L m⁻² h⁻¹ bar⁻¹", "L m^-2 h^-1 bar^-1", "L m-2 h-1 bar-1",
    "LMH/MPa", "L/(m²·h·MPa)",
}

# 通量单位（不含压力）
_FLUX_UNITS = {
    "LMH",
    "L·m⁻²·h⁻¹", "L·m^-2·h^-1",
    "L m⁻² h⁻¹", "L m^-2 h^-1", "L m-2 h-1",
    "L/m²·h", "L/m2·h", "L/m2/h", "L/m²/h",
    "mL/(cm²·h)", "mL/cm²/h",
    "m³/(m²·d)", "m3/m2/d",
}


def classify_flux_unit(unit: str) -> str:
    """
    判断通量类单位属于通量（flux）还是比通量（permeance）。

    Args:
        unit: 单位字符串

    Returns:
        "permeance"（含压力）、"flux"（不含压力）、或 "unknown"
    """
    u = unit.strip()
    if u in _PERMEANCE_UNITS:
        return "permeance"
    if u in _FLUX_UNITS:
        return "flux"
    # 启发式：含 bar 或 MPa 则为比通量
    lower = u.lower()
    if "bar" in lower or "mpa" in lower or "pa" in lower and "m" in lower:
        return "permeance"
    return "unknown"


# ====================================================================
# 单位换算表
# ====================================================================
# 每个参数对应一个字典：{原始单位: (换算函数, 是否近似, 说明)}
# ====================================================================

# 通量（flux）：标准单位 LMH
_FLUX_CONVERSIONS: Dict[str, Tuple[Callable, bool, str]] = {
    "LMH": (lambda v: v, False, ""),
    "L·m⁻²·h⁻¹": (lambda v: v, False, ""),
    "L·m^-2·h^-1": (lambda v: v, False, ""),
    "L m⁻² h⁻¹": (lambda v: v, False, ""),
    "L m^-2 h^-1": (lambda v: v, False, ""),
    "L m-2 h-1": (lambda v: v, False, ""),
    "L/m²·h": (lambda v: v, False, ""),
    "L/m2·h": (lambda v: v, False, ""),
    "L/m2/h": (lambda v: v, False, ""),
    "L/m²/h": (lambda v: v, False, ""),
    "mL/(cm²·h)": (lambda v: v * 10, False, "1 mL/(cm²·h) = 10 LMH"),
    "mL/cm²/h": (lambda v: v * 10, False, "1 mL/(cm²·h) = 10 LMH"),
    "m³/(m²·d)": (lambda v: v * 1000 / 24, False, "1 m³/(m²·d) = 41.67 LMH"),
    "m3/m2/d": (lambda v: v * 1000 / 24, False, "1 m³/(m²·d) = 41.67 LMH"),
}

# 比通量（permeance）：标准单位 LMH/bar
_PERMEANCE_CONVERSIONS: Dict[str, Tuple[Callable, bool, str]] = {
    "LMH/bar": (lambda v: v, False, ""),
    "LMH/bar*": (lambda v: v, False, "聚合时单位冲突标记，按LMH/bar处理"),
    "L/(m²·h·bar)": (lambda v: v, False, ""),
    "L/(m2·h·bar)": (lambda v: v, False, ""),
    "L/(m2/h/bar)": (lambda v: v, False, ""),
    "L·m⁻²·h⁻¹·bar⁻¹": (lambda v: v, False, ""),
    "L·m^-2·h^-1·bar^-1": (lambda v: v, False, ""),
    "L m⁻² h⁻¹ bar⁻¹": (lambda v: v, False, ""),
    "L m^-2 h^-1 bar^-1": (lambda v: v, False, ""),
    "L m-2 h-1 bar-1": (lambda v: v, False, ""),
    "LMH/MPa": (lambda v: v / 10, False, "1 MPa = 10 bar, LMH/MPa → LMH/bar 需除以10"),
    "L/(m²·h·MPa)": (lambda v: v / 10, False, "1 MPa = 10 bar"),
}

# 有效孔径：标准单位 nm
_PORESIZE_CONVERSIONS: Dict[str, Tuple[Callable, bool, str]] = {
    "nm": (lambda v: v, False, ""),
    "Å": (lambda v: v * 0.1, False, "1埃 = 0.1纳米"),
    "A": (lambda v: v * 0.1, False, "1埃 = 0.1纳米"),
    "μm": (lambda v: v * 1000, False, "1μm = 1000nm"),
}

# MWCO：标准单位 kDa
_MWCO_CONVERSIONS: Dict[str, Tuple[Callable, bool, str]] = {
    "kDa": (lambda v: v, False, ""),
    "Da": (lambda v: v / 1000, False, "1kDa = 1000Da"),
    "KD": (lambda v: v, False, ""),
}

# 交联度：标准单位 ratio（0-1）
_CROSSLINK_CONVERSIONS: Dict[str, Tuple[Callable, bool, str]] = {
    "ratio": (lambda v: v, False, ""),
    "%": (lambda v: v / 100, False, "百分比转比率"),
    "percent": (lambda v: v / 100, False, "百分比转比率"),
}

# 接触角：标准单位 °
_ANGLE_CONVERSIONS: Dict[str, Tuple[Callable, bool, str]] = {
    "°": (lambda v: v, False, ""),
    "deg": (lambda v: v, False, ""),
    "degree": (lambda v: v, False, ""),
}

# 浓度：标准单位 w/v%
_CONCENTRATION_CONVERSIONS: Dict[str, Tuple[Callable, bool, str]] = {
    "w/v%": (lambda v: v, False, ""),
    "wt/v%": (lambda v: v, False, ""),
    "wt%": (lambda v: v, True, "wt%(质量分数)与w/v%(质量体积比)物理意义不同，膜领域常近似等价"),
    "wt.%": (lambda v: v, True, "wt.%(质量分数)与w/v%(质量体积比)物理意义不同，膜领域常近似等价"),
    "w.t.%": (lambda v: v, True, "近似换算"),
    "g/L": (lambda v: v / 10, False, "1g/L = 0.1w/v%（假设水溶液密度1g/mL）"),
    "mol/L": (lambda v: None, False, "摩尔浓度需分子量才能换算为w/v%"),
    "M": (lambda v: None, False, "摩尔浓度需分子量才能换算为w/v%"),
}

# zeta电位：标准单位 mV
_ZETA_CONVERSIONS: Dict[str, Tuple[Callable, bool, str]] = {
    "mV": (lambda v: v, False, ""),
    "V": (lambda v: v * 1000, False, "1V = 1000mV"),
}

# 粗糙度/厚度：标准单位 nm
_LENGTH_CONVERSIONS: Dict[str, Tuple[Callable, bool, str]] = {
    "nm": (lambda v: v, False, ""),
    "μm": (lambda v: v * 1000, False, "1μm = 1000nm"),
    "um": (lambda v: v * 1000, False, "1μm = 1000nm"),
    "mm": (lambda v: v * 1e6, False, "1mm = 1e6nm"),
    "Å": (lambda v: v * 0.1, False, "1埃 = 0.1nm"),
}

# 参数 → 换算表映射
_CONVERSION_TABLES: Dict[str, Dict[str, Tuple[Callable, bool, str]]] = {
    "pure_water_flux": _FLUX_CONVERSIONS,
    "pure_water_permeance": _PERMEANCE_CONVERSIONS,
    "Effective_pore_size": _PORESIZE_CONVERSIONS,
    "Substrate_pore_size": _LENGTH_CONVERSIONS,
    "Substrate_MWCO": _MWCO_CONVERSIONS,
    "Degree_of_crosslinking": _CROSSLINK_CONVERSIONS,
    "Substrate_Water_contact_angle": _ANGLE_CONVERSIONS,
    "PIP_Concentration": _CONCENTRATION_CONVERSIONS,
    "TMC_Concentration": _CONCENTRATION_CONVERSIONS,
    "Substrate_zeta": _ZETA_CONVERSIONS,
    "Zeta_potential": _ZETA_CONVERSIONS,
    "Substrate_Ra": _LENGTH_CONVERSIONS,
    "Membrane_Ra": _LENGTH_CONVERSIONS,
    "Thickness": _LENGTH_CONVERSIONS,
}

# 所有可归一化的 ValueUnit 字段（schema 中存在的字段）
# 注意：pure_water_permeance 不在 schema 中，是 formatter 层的虚拟分列
_NORMALIZABLE_FIELDS = [
    "Substrate_pore_size", "Substrate_MWCO", "Substrate_Water_contact_angle",
    "Substrate_zeta", "Substrate_Ra", "PIP_Concentration", "TMC_Concentration",
    "Degree_of_crosslinking", "Thickness", "Effective_pore_size",
    "Zeta_potential", "Membrane_Ra", "pure_water_flux",
]


# ====================================================================
# 通量专用归一化
# ====================================================================

def normalize_flux_value(
    value: float,
    unit: str,
) -> Tuple[str, NormalizedValue]:
    """
    对通量类数据自动分类并归一化。

    根据单位判断是通量（flux）还是比通量（permeance），分别归一化到对应标准单位。

    Args:
        value: 原始数值
        unit:  原始单位

    Returns:
        (field_name, normalized_value)
        - field_name: "pure_water_flux" 或 "pure_water_permeance" 或 "pure_water_flux"（未知单位时）
        - normalized_value: NormalizedValue 归一化结果
    """
    flux_type = classify_flux_unit(unit)

    if flux_type == "permeance":
        result = normalize_value("pure_water_permeance", value, unit)
        return "pure_water_permeance", result
    elif flux_type == "flux":
        result = normalize_value("pure_water_flux", value, unit)
        return "pure_water_flux", result
    else:
        # 未知单位，尝试在两个换算表中查找
        if unit in _PERMEANCE_CONVERSIONS:
            result = normalize_value("pure_water_permeance", value, unit)
            return "pure_water_permeance", result
        if unit in _FLUX_CONVERSIONS:
            result = normalize_value("pure_water_flux", value, unit)
            return "pure_water_flux", result
        # 完全未知，保持原值
        result = NormalizedValue(
            value=value, unit=unit, original_unit=unit,
            note=f"未知通量单位 '{unit}'，无法分类",
        )
        return "pure_water_flux", result


# ====================================================================
# 核心归一化函数
# ====================================================================

def normalize_value(
    field_name: str,
    value: float,
    unit: str,
) -> NormalizedValue:
    """
    将单个参数值从原始单位归一化到标准单位。

    Args:
        field_name: 参数字段名（如 pure_water_flux）
        value:      原始数值
        unit:       原始单位字符串

    Returns:
        NormalizedValue 归一化结果。若单位未知或需要更多信息，value 可能为 None。
    """
    if field_name not in _CONVERSION_TABLES:
        return NormalizedValue(
            value=value, unit=unit, original_unit=unit,
            note=f"字段 {field_name} 无归一化规则，保持原值",
        )

    conversions = _CONVERSION_TABLES[field_name]
    standard_unit = StandardUnit[field_name].value

    if unit not in conversions:
        return NormalizedValue(
            value=None, unit=standard_unit, original_unit=unit,
            note=f"未知单位 '{unit}'，无法归一化",
        )

    func, is_approx, note = conversions[unit]
    normalized = func(value)

    if normalized is None:
        return NormalizedValue(
            value=None, unit=standard_unit, original_unit=unit,
            is_approximate=is_approx, needs_more_info=True, note=note,
        )

    return NormalizedValue(
        value=normalized, unit=standard_unit, original_unit=unit,
        is_approximate=is_approx, note=note,
    )


def normalize_value_unit(vu: ValueUnit, field_name: str) -> NormalizedValue:
    """
    对 ValueUnit 对象进行单位归一化。

    Args:
        vu:         ValueUnit 对象（value + unit）
        field_name: 参数字段名

    Returns:
        NormalizedValue 归一化结果
    """
    return normalize_value(field_name, vu.value, vu.unit)


def normalize_membrane(
    membrane: MembraneData,
) -> Tuple[MembraneData, Dict[str, NormalizedValue]]:
    """
    对单个 MembraneData 的所有 ValueUnit 字段进行单位归一化。

    不修改原始 membrane 对象，返回新的归一化后 MembraneData 和归一化详情。
    注意：pure_water_flux 字段保持原字段名，但单位会被归一化到对应标准（LMH 或 LMH/bar）。
    通量/比通量的分列由 formatter 层处理。

    Args:
        membrane: 原始 MembraneData 对象

    Returns:
        (normalized_membrane, normalization_report)
    """
    report: Dict[str, NormalizedValue] = {}
    new_data = membrane.model_dump()

    for field_name in _NORMALIZABLE_FIELDS:
        vu = getattr(membrane, field_name)
        if vu is None:
            continue

        if field_name == "pure_water_flux":
            # 通量字段：自动分类后归一化，但保持原字段名
            _, result = normalize_flux_value(vu.value, vu.unit)
        else:
            result = normalize_value(field_name, vu.value, vu.unit)

        report[field_name] = result

        if result.value is not None:
            new_data[field_name] = {"value": result.value, "unit": result.unit}
        # 无法归一化的保持原值

    normalized = MembraneData(**new_data)
    return normalized, report


def get_standard_unit(field_name: str) -> Optional[str]:
    """
    获取指定字段的标准单位。

    Args:
        field_name: 参数字段名

    Returns:
        标准单位字符串，未知字段返回 None
    """
    if field_name in StandardUnit.__members__:
        return StandardUnit[field_name].value
    return None


def list_normalizable_fields() -> list:
    """返回所有可归一化的字段名列表（schema 中存在的字段）。"""
    return list(_NORMALIZABLE_FIELDS)
