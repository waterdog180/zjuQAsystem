from pathlib import Path
import api_keys
from pydantic import BaseModel, Field
from typing import List, Optional, Union


ROOT_DIR = Path(__file__).parent
RAW_PDF_DIR = ROOT_DIR / "data" / "raw_pdfs"
PRE_PDF_DIR = ROOT_DIR / "data" / "pre_pdfs"#由于改用mineru，此文件夹暂时弃用，改用mineru_out
MINERU_OUT_DIR = ROOT_DIR / "data" /"mineru_out"
MEMBRANCE_DATA_DIR = ROOT_DIR / "data" / "membranes"


if False:
# 程序启动时确保目录存在
    RAW_PDF_DIR.mkdir(parents=True, exist_ok=True)
    PRE_PDF_DIR.mkdir(parents=True, exist_ok=True)
    MINERU_OUT_DIR.mkdir(parents=True, exist_ok=True)
    MEMBRANCE_DATA_DIR.mkdir(parents=True, exist_ok=True)

PAGE_DPI   = 200   # PDF 转图片分辨率（150=快/省token，200=均衡，300=高精度）
MAX_IMAGES = 40    # 单篇论文最多传入图片页数（超长文章截断，避免 token 超限）?


#LLM设置

class LLMParas:
    model_name ="glm-4.6v-flash"#"glm-4.6v-flash"
    base_url="https://open.bigmodel.cn/api/paas/v4/"
    api_key=api_keys.GLM_key


# ② 数据结构定义

class MembraneData(BaseModel):
    """单种膜的完整参数"""
    membrane_id: Optional[str] = Field(None, description="膜编号/名称，如 TFC-s-O、PA-1")
    substrate: Optional[str] = Field(None, description="支撑层类型，如 PES、PVDF、PSF、PAN")
    Substrate_pore_size: Optional[Union[float, str]] = Field(None, description="支撑层孔径 (nm)")
    Substrate_MWCO: Optional[Union[float, str]] = Field(None, description="支撑层截留分子量 (kDa)")
    Substrate_Water_contact_angle: Optional[Union[float, str]] = Field(None, description="支撑层水接触角 (°)")
    Substrate_zeta: Optional[Union[float, str]] = Field(None, description="支撑层 zeta 电位 (mV)")
    Substrate_Ra: Optional[Union[float, str]] = Field(None, description="支撑层粗糙度 (nm)")
    PIP_Concentration: Optional[Union[float, str, dict]] = Field(None, description="PIP 浓度，保留原始单位")
    TMC_Concentration: Optional[Union[float, str, dict]] = Field(None, description="TMC 浓度，保留原始单位")
    Degree_of_crosslinking: Optional[Union[float, str]] = Field(None, description="O/N 交联度")
    Thickness: Optional[Union[float, str]] = Field(None, description="皮层厚度 (nm)")
    Effective_pore_size: Optional[Union[float, str]] = Field(None, description="有效孔径 (nm)")
    Zeta_potential: Optional[Union[float, str]] = Field(None, description="皮层 zeta 电位 (mV)")
    Membrane_Ra: Optional[Union[float, str]] = Field(None, description="分离层粗糙度 (nm)")
    pure_water_flux: Optional[Union[float, str]] = Field(None, description="纯水通量 (LMH/bar)")
    Na2SO4_rejection: Optional[Union[float, str]] = Field(None, description="Na₂SO₄ 截留率 (%)")
    NaCl_rejection: Optional[Union[float, str]] = Field(None, description="NaCl 截留率 (%)")
    data_sources: Optional[List[str]] = Field(default_factory=list, description="数据来源（表格/图号）")
    notes: Optional[str] = Field(None, description="特殊说明，如 estimated_from_figure")

    def __str__(self):
        """print(instance) 时自动调用，美化输出"""
        lines = [f"===== Membrane [{self.membrane_id}] ====="]
        lines.append(f"支撑层类型substrate: {self.substrate}")
        lines.append(f"支撑层孔径Substrate_pore_size: {self.Substrate_pore_size} nm")
        lines.append(f"支撑层截留分子量Substrate_MWCO: {self.Substrate_MWCO} kDa")
        lines.append(f"支撑层水接触角Substrate_Water_contact_angle: {self.Substrate_Water_contact_angle} °")
        lines.append(f"支撑层 zeta 电位Substrate_zeta: {self.Substrate_zeta} mV")
        lines.append(f"支撑层粗糙度Substrate_Ra: {self.Substrate_Ra} nm")
        lines.append(f"PIP浓度PIP_Concentration: {self.PIP_Concentration} nm")
        lines.append(f"TMC浓度TMC_Concentration: {self.TMC_Concentration} nm")
        lines.append(f"O/N 交联度Degree_of_crosslinking: {self.Degree_of_crosslinking}")
        lines.append(f"皮层厚度: {self.Thickness} nm")
        lines.append(f"有效孔径: {self.Effective_pore_size} nm")
        lines.append(f"皮层 zeta 电位: {self.Zeta_potential} mV")
        lines.append(f"分离层粗糙度: {self.Membrane_Ra} nm")
        lines.append(f"纯水通量: {self.pure_water_flux} LMH/bar")
        lines.append(f"Na₂SO₄截留: {self.Na2SO4_rejection} %")
        lines.append(f"NaCl截留: {self.NaCl_rejection} %")
        lines.append(f"数据来源: {', '.join(self.data_sources)}")
        lines.append(f"特殊说明: {self.notes}")
        '''
        # 处理浓度字典格式化
        pip = self.PIP_Concentration
        tmc = self.TMC_Concentration
        if isinstance(pip, dict):
            lines.append(f"PIP浓度: {pip['value']} {pip['unit']}")
        else:
            lines.append(f"PIP浓度: {pip}")
        if isinstance(tmc, dict):
            lines.append(f"TMC浓度: {tmc['value']} {tmc['unit']}")
        else:
            lines.append(f"TMC浓度: {tmc}")
        '''
        if self.notes:
            lines.append(f"备注: {self.notes}")
        return "\n".join(lines)

class PaperData(BaseModel):
    """整篇论文的提取结果"""
    title: str = Field(description="论文标题")
    membranes: List[MembraneData] = Field(description="所有膜的参数列表")



if __name__=="__main__":
    print(__file__)
    print(type(__file__))
    print(ROOT_DIR)