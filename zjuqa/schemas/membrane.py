"""
membrane.py —— 膜参数数据模型定义（schemas 层）。

本文件定义从论文中提取的膜参数的结构化数据模型。
所有数值字段统一采用 {"value": 数值, "unit": "原始单位"} 格式，
保留论文原始单位，避免单位混淆导致后续 ML 训练数据混乱。

核心设计：
  1. ValueUnit：数值+单位的复合类型，所有物理量统一使用
  2. MembraneData：单种膜的完整参数，所有数值字段均为 Optional[ValueUnit]
  3. rejections：截留率字典，键为化学物质名，值为 ValueUnit（单位通常为 %）
  4. 内置范围校验：截留率 0-100%、物理量非负，异常值静默修正并记录 notes

使用说明：
    from zjuqa.schemas.membrane import MembraneData, ValueUnit
    data = MembraneData(
        membrane_id="TFC-s-O",
        pure_water_flux=ValueUnit(value=15.2, unit="LMH/bar"),
        rejections={"Na2SO4": ValueUnit(value=95.2, unit="%")},
    )
    print(data)
    json_str = data.model_dump_json(indent=2)
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class ValueUnit(BaseModel):
    """
    数值+单位的复合类型。

    所有物理量统一使用此格式，保留论文原始单位。
    聚合时需校验单位一致性，单位不同时取第一个非空单位并记录警告。

    Attributes:
        value: 数值（仅保留均值，去除误差/标准差/范围）
        unit:  原始单位字符串（如 "nm"、"LMH/bar"、"%"、"°"）
    """
    value: float = Field(description="数值（均值）")
    unit: str = Field(description="原始单位字符串")

    def __str__(self) -> str:
        return f"{self.value} {self.unit}".strip()


class MembraneData(BaseModel):
    """
    单种膜的完整参数。

    所有数值型字段仅保留均值（论文中的 ±误差、range 等均在提取阶段丢弃），
    统一采用 ValueUnit（数值+单位）格式。
    截留率使用 rejections 字典动态存储，不预设固定盐种类。
    """

    # —— 基本标识 ——
    membrane_id: Optional[str] = Field(
        None, description="膜编号/名称，如 TFC-s-O、PA-1"
    )

    # —— 支撑层属性 ——
    substrate: Optional[str] = Field(
        None, description="支撑层类型，如 PES、PVDF、PSF、PAN"
    )
    Substrate_pore_size: Optional[ValueUnit] = Field(
        None, description="支撑层孔径均值，单位通常为 nm"
    )
    Substrate_MWCO: Optional[ValueUnit] = Field(
        None, description="支撑层截留分子量均值，单位通常为 kDa"
    )
    Substrate_Water_contact_angle: Optional[ValueUnit] = Field(
        None, description="支撑层水接触角均值，单位通常为 °"
    )
    Substrate_zeta: Optional[ValueUnit] = Field(
        None, description="支撑层 zeta 电位均值，单位通常为 mV"
    )
    Substrate_Ra: Optional[ValueUnit] = Field(
        None, description="支撑层粗糙度均值，单位通常为 nm"
    )

    # —— 制备参数 ——
    PIP_Concentration: Optional[ValueUnit] = Field(
        None, description="PIP 浓度均值，单位如 w/v%、g/L、mol/L"
    )
    TMC_Concentration: Optional[ValueUnit] = Field(
        None, description="TMC 浓度均值，单位如 w/v%、g/L、mol/L"
    )
    Degree_of_crosslinking: Optional[ValueUnit] = Field(
        None, description="O/N 交联度均值，无量纲时 unit 为空字符串或 'ratio'"
    )
    Thickness: Optional[ValueUnit] = Field(
        None, description="皮层厚度均值，单位通常为 nm 或 μm"
    )
    Effective_pore_size: Optional[ValueUnit] = Field(
        None, description="有效孔径均值，单位通常为 nm"
    )
    Zeta_potential: Optional[ValueUnit] = Field(
        None, description="皮层 zeta 电位均值，单位通常为 mV"
    )
    Membrane_Ra: Optional[ValueUnit] = Field(
        None, description="分离层粗糙度均值，单位通常为 nm"
    )

    # —— 性能指标 ——
    pure_water_flux: Optional[ValueUnit] = Field(
        None, description="纯水通量均值，单位如 LMH、LMH/bar、L/m²/h"
    )

    # ★ 截留率字典：键为化学物质名，值为 ValueUnit（单位通常为 %）
    rejections: Dict[str, Optional[ValueUnit]] = Field(
        default_factory=dict,
        description=(
            "各物质截留率均值字典。键为化学物质标准名称（如 Na2SO4、NaCl、MgCl2），"
            "值为 ValueUnit（value=截留率均值, unit 通常为 %）。"
            "由 LLM 智能识别论文中所有截留对象，动态填充，不预设固定种类。"
        ),
    )

    # —— 元信息 ——
    data_sources: List[str] = Field(
        default_factory=list, description="数据来源列表，如 ['Table 2', 'Fig. 3a']"
    )
    notes: Optional[str] = Field(
        None, description="特殊说明，如 estimated_from_figure、存疑数据、单位冲突等"
    )

    # ====================================================================
    # 数据校验（轻量：静默修正明显异常值，不中断流水线）
    # ====================================================================
    @model_validator(mode="after")
    def _validate_ranges(self) -> "MembraneData":
        """
        模型构建后校验数值范围，静默修正明显异常值。

        修正规则：
          - 截留率 rejections：value >100 截断为 100，<0 修正为 0
          - 非负物理量（通量、厚度、孔径、粗糙度、MWCO、浓度）：value <0 修正为 0
          - 水接触角：value >180 截断为 180，<0 修正为 0
          - 所有修正追加到 notes 字段

        设计原则：不拒绝数据，只修正明显异常，保持流水线不中断。
        """
        corrections: List[str] = []

        # 截留率范围校验（0-100%）
        if self.rejections:
            for substance, vu in list(self.rejections.items()):
                if vu is not None and isinstance(vu.value, (int, float)):
                    if vu.value > 100:
                        self.rejections[substance] = ValueUnit(
                            value=100.0, unit=vu.unit
                        )
                        corrections.append(
                            f"{substance}截留率={vu.value}{vu.unit}→截断为100%"
                        )
                    elif vu.value < 0:
                        self.rejections[substance] = ValueUnit(
                            value=0.0, unit=vu.unit
                        )
                        corrections.append(
                            f"{substance}截留率={vu.value}{vu.unit}→修正为0"
                        )

        # 非负物理量校验
        non_negative_fields = [
            "pure_water_flux", "Thickness", "Effective_pore_size",
            "Substrate_pore_size", "Substrate_Ra", "Membrane_Ra",
            "Substrate_MWCO", "PIP_Concentration", "TMC_Concentration",
        ]
        for field_name in non_negative_fields:
            vu = getattr(self, field_name)
            if vu is not None and isinstance(vu.value, (int, float)) and vu.value < 0:
                setattr(self, field_name, ValueUnit(value=0.0, unit=vu.unit))
                corrections.append(f"{field_name}={vu.value}{vu.unit}→修正为0")

        # 水接触角范围校验（0-180°）
        ca = self.Substrate_Water_contact_angle
        if ca is not None and isinstance(ca.value, (int, float)):
            if ca.value > 180:
                self.Substrate_Water_contact_angle = ValueUnit(
                    value=180.0, unit=ca.unit
                )
                corrections.append(f"接触角={ca.value}{ca.unit}→截断为180")
            elif ca.value < 0:
                self.Substrate_Water_contact_angle = ValueUnit(
                    value=0.0, unit=ca.unit
                )
                corrections.append(f"接触角={ca.value}{ca.unit}→修正为0")

        # 修正记录追加到 notes
        if corrections:
            correction_str = "数据校验修正: " + "; ".join(corrections)
            if self.notes:
                self.notes = f"{self.notes} | {correction_str}"
            else:
                self.notes = correction_str

        return self

    def __str__(self) -> str:
        """
        print(instance) 时自动调用，美化输出所有参数。
        ValueUnit 字段展开为 "数值 单位" 格式。
        """
        lines = [f"===== Membrane [{self.membrane_id}] ====="]

        # 支撑层
        lines.append(f"支撑层类型 substrate: {self.substrate}")
        lines.append(f"支撑层孔径 Substrate_pore_size: {self.Substrate_pore_size}")
        lines.append(f"支撑层截留分子量 Substrate_MWCO: {self.Substrate_MWCO}")
        lines.append(
            f"支撑层水接触角 Substrate_Water_contact_angle: "
            f"{self.Substrate_Water_contact_angle}"
        )
        lines.append(f"支撑层 zeta 电位 Substrate_zeta: {self.Substrate_zeta}")
        lines.append(f"支撑层粗糙度 Substrate_Ra: {self.Substrate_Ra}")

        # 制备参数
        lines.append(f"PIP 浓度 PIP_Concentration: {self.PIP_Concentration}")
        lines.append(f"TMC 浓度 TMC_Concentration: {self.TMC_Concentration}")
        lines.append(f"O/N 交联度 Degree_of_crosslinking: {self.Degree_of_crosslinking}")
        lines.append(f"皮层厚度 Thickness: {self.Thickness}")
        lines.append(f"有效孔径 Effective_pore_size: {self.Effective_pore_size}")
        lines.append(f"皮层 zeta 电位 Zeta_potential: {self.Zeta_potential}")
        lines.append(f"分离层粗糙度 Membrane_Ra: {self.Membrane_Ra}")

        # 性能
        lines.append(f"纯水通量 pure_water_flux: {self.pure_water_flux}")

        # 截留率字典遍历
        if self.rejections:
            lines.append("截留率 rejections:")
            for substance, vu in self.rejections.items():
                lines.append(f"  - {substance}: {vu}")
        else:
            lines.append("截留率 rejections: (无数据)")

        # 元信息
        lines.append(f"数据来源 data_sources: {', '.join(self.data_sources)}")
        if self.notes:
            lines.append(f"备注 notes: {self.notes}")

        return "\n".join(lines)
