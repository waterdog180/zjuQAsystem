"""
membrane.py —— 膜参数数据模型定义。

本文件定义了从论文中提取的膜参数的结构化数据模型。
两个核心修改（对应项目需求）：
  1. 所有数值字段只保留均值，不保留误差/标准差/范围。
  2. 截留率从固定字段（Na2SO4_rejection、NaCl_rejection）改为字典，
     以化学物质名称为键、截留率为值，支持智能识别与动态匹配。

使用说明：
    from zjuqa.models.membrane import MembraneData
    data = MembraneData(membrane_id="TFC-s-O", rejections={"Na2SO4": 95.2})
    print(data)  # 美化输出
    json_str = data.model_dump_json(indent=2)  # 序列化为 JSON
"""

from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field, model_validator


class MembraneData(BaseModel):
    """
    单种膜的完整参数。

    所有数值型字段仅保留均值（论文中的 ±误差、range 等均在提取阶段丢弃）。
    截留率使用 rejections 字典动态存储，不预设固定盐种类。
    """

    # —— 基本标识 ——
    membrane_id: Optional[str] = Field(None, description="膜编号/名称，如 TFC-s-O、PA-1")
    # —— 支撑层属性 ——
    substrate: Optional[str] = Field(None, description="支撑层类型，如 PES、PVDF、PSF、PAN")
    Substrate_pore_size: Optional[Union[float, str]] = Field(None, description="支撑层孔径均值 (nm)，仅保留均值，不含误差")
    Substrate_MWCO: Optional[Union[float, str]] = Field(None, description="支撑层截留分子量均值 (kDa)，仅保留均值")
    Substrate_Water_contact_angle: Optional[Union[float, str]] = Field(None, description="支撑层水接触角均值 (°)，仅保留均值")
    Substrate_zeta: Optional[Union[float, str]] = Field(None, description="支撑层 zeta 电位均值 (mV)，仅保留均值")
    Substrate_Ra: Optional[Union[float, str]] = Field(None, description="支撑层粗糙度均值 (nm)，仅保留均值")
    # —— 制备参数 ——
    PIP_Concentration: Optional[Union[float, str, dict]] = Field(
        None,
        description="PIP 浓度均值，保留原始单位。格式可为数值或 "
                    '{"value": 均值, "unit": "原始单位"}',
    )
    TMC_Concentration: Optional[Union[float, str, dict]] = Field(
        None,
        description="TMC 浓度均值，保留原始单位。格式可为数值或 "
                    '{"value": 均值, "unit": "原始单位"}',
    )
    Degree_of_crosslinking: Optional[Union[float, str]] = Field(None, description="O/N 交联度均值（无量纲），仅保留均值")
    Thickness: Optional[Union[float, str]] = Field(None, description="皮层厚度均值 (nm)，仅保留均值")
    Effective_pore_size: Optional[Union[float, str]] = Field(None, description="有效孔径均值 (nm)，仅保留均值")
    Zeta_potential: Optional[Union[float, str]] = Field(None, description="皮层 zeta 电位均值 (mV)，仅保留均值")
    Membrane_Ra: Optional[Union[float, str]] = Field(None, description="分离层粗糙度均值 (nm)，仅保留均值")

    # —— 性能指标 ——
    pure_water_flux: Optional[Union[float, str]] = Field(
        None, description="纯水通量均值 (LMH/bar)，仅保留均值"
    )

    # ★ 需求 2：截留率改为字典，键为化学物质名称，值为截留率均值(%)
    rejections: Dict[str, Optional[Union[float, str]]] = Field(
        default_factory=dict,
        description=(
            "各物质截留率均值字典。键为化学物质标准名称（如 Na2SO4、NaCl、MgCl2），"
            "值为该物质截留率均值(%)。由 LLM 智能识别论文中所有截留对象，动态填充，"
            "不预设固定种类。仅保留均值，不含误差。"
        ),
    )

    # —— 元信息 ——
    data_sources: List[str] = Field(
        default_factory=list, description="数据来源列表，如 ['Table 2', 'Fig. 3a']"
    )
    notes: Optional[str] = Field(
        None, description="特殊说明，如 estimated_from_figure、存疑数据等"
    )

    # —— 数据校验（轻量：静默修正明显异常值，不中断流水线）——
    @model_validator(mode="after")
    def _validate_ranges(self) -> "MembraneData":
        """
        模型构建后校验数值范围，静默修正明显异常值。

        修正规则：
          - 截留率 rejections：数值 >100 截断为 100，<0 修正为 0
          - 非负物理量（通量、厚度、孔径、粗糙度、MWCO）：数值 <0 修正为 0
          - 字符串类型值不处理（LLM 可能返回带单位的字符串）
          - 所有修正追加到 notes 字段

        设计原则：不拒绝数据，只修正明显异常，保持流水线不中断。
        """
        corrections: List[str] = []

        # 截留率范围校验（0-100%）
        if self.rejections:
            for substance, val in list(self.rejections.items()):
                if isinstance(val, (int, float)):
                    if val > 100:
                        self.rejections[substance] = 100.0
                        corrections.append(f"{substance}截留率={val}→截断为100")
                    elif val < 0:
                        self.rejections[substance] = 0.0
                        corrections.append(f"{substance}截留率={val}→修正为0")

        # 非负物理量校验
        non_negative_fields = [
            "pure_water_flux", "Thickness", "Effective_pore_size",
            "Substrate_pore_size", "Substrate_Ra", "Membrane_Ra",
            "Substrate_MWCO",
        ]
        for field_name in non_negative_fields:
            val = getattr(self, field_name)
            if isinstance(val, (int, float)) and val < 0:
                setattr(self, field_name, 0.0)
                corrections.append(f"{field_name}={val}→修正为0")

        # 水接触角范围校验（0-180°）
        ca = self.Substrate_Water_contact_angle
        if isinstance(ca, (int, float)):
            if ca > 180:
                self.Substrate_Water_contact_angle = 180.0
                corrections.append(f"接触角={ca}→截断为180")
            elif ca < 0:
                self.Substrate_Water_contact_angle = 0.0
                corrections.append(f"接触角={ca}→修正为0")

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
        截留率字典遍历打印，浓度字段若为 dict 则展开 value+unit。
        """
        lines = [f"===== Membrane [{self.membrane_id}] ====="]

        # 支撑层
        lines.append(f"支撑层类型 substrate: {self.substrate}")
        lines.append(f"支撑层孔径 Substrate_pore_size: {self.Substrate_pore_size} nm")
        lines.append(f"支撑层截留分子量 Substrate_MWCO: {self.Substrate_MWCO} kDa")
        lines.append(
            f"支撑层水接触角 Substrate_Water_contact_angle: "
            f"{self.Substrate_Water_contact_angle} °"
        )
        lines.append(f"支撑层 zeta 电位 Substrate_zeta: {self.Substrate_zeta} mV")
        lines.append(f"支撑层粗糙度 Substrate_Ra: {self.Substrate_Ra} nm")

        # 制备参数（浓度可能为 dict）
        lines.append(f"PIP 浓度 PIP_Concentration: {self._fmt_conc(self.PIP_Concentration)}")
        lines.append(f"TMC 浓度 TMC_Concentration: {self._fmt_conc(self.TMC_Concentration)}")
        lines.append(f"O/N 交联度 Degree_of_crosslinking: {self.Degree_of_crosslinking}")
        lines.append(f"皮层厚度 Thickness: {self.Thickness} nm")
        lines.append(f"有效孔径 Effective_pore_size: {self.Effective_pore_size} nm")
        lines.append(f"皮层 zeta 电位 Zeta_potential: {self.Zeta_potential} mV")
        lines.append(f"分离层粗糙度 Membrane_Ra: {self.Membrane_Ra} nm")

        # 性能
        lines.append(f"纯水通量 pure_water_flux: {self.pure_water_flux} LMH/bar")

        # ★ 截留率字典遍历
        if self.rejections:
            lines.append("截留率 rejections:")
            for substance, value in self.rejections.items():
                lines.append(f"  - {substance}: {value} %")
        else:
            lines.append("截留率 rejections: (无数据)")

        # 元信息
        lines.append(f"数据来源 data_sources: {', '.join(self.data_sources)}")
        if self.notes:
            lines.append(f"备注 notes: {self.notes}")

        return "\n".join(lines)

    @staticmethod
    def _fmt_conc(conc) -> str:
        """格式化浓度字段：若为 dict 则展开 value+unit，否则直接转字符串。"""
        if isinstance(conc, dict):
            return f"{conc.get('value', '?')} {conc.get('unit', '')}".strip()
        return str(conc)


#PaperData暂无使用场景，弃用
'''
class PaperData(BaseModel):
    """
    整篇论文的提取结果，包含论文标题与所有膜的参数列表。

    Attributes:
        title:     论文标题。
        membranes: 该论文中所有膜的参数列表。
    """
    title: str = Field(description="论文标题")
    membranes: List[MembraneData] = Field(description="所有膜的参数列表")
'''