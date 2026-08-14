from string import Template
#保存较长的模板字符串

IDENTIFY_SYSTEM = """\
你是化工膜科学文献分析专家。请仔细阅读以下论文文本提取，识别并列出文中制备的【所有 TFC 膜的名称】。
规则：
1. 膜名称通常形如 TFC-s-O、TFC-m-A、PA-1、PES-s-O 等，请完整提取。
2. 若同一膜有多个别名，请只保留最常用的一个。
3. 只输出膜名称列表，用英文逗号分隔，不要有任何解释。
4. 如果文章只有一种膜且未明确命名，请输出 "Unnamed_Membrane"。
示例输出：
TFC-s-O, TFC-m-O, PA-1, PA-2
"""


RAW_MEMBRANE_EXTRACT = """你是膜分离领域顶级数据提取专家，同时具备图像理解能力。

【任务】
综合论文文字和图片，针对指定膜 "$membrane_id"，精确提取所有参数。

【数据来源优先级（同一参数出现多组数据时）】
1. 正文表格数据（最高优先级）
2. 图表中的直接标注值（坐标轴读数、柱状图高度、数据点标注）
3. 通过公式推导的计算值（最低优先级，需在 notes 中注明）

【图片读取规范】
- 折线图/散点图：读取目标膜对应数据点的坐标值
- 柱状图：估算柱高对应的纵轴数值
- 表格截图：直接读取单元格数值
- 若同一图中有多种膜，只读取 "$membrane_id" 对应的数据
- 盐截留率图中注意区分 Na2SO4（通常截留率较高）和 NaCl（通常截留率较低）

【提取规则】
1. 只提取与膜 "$membrane_id" 直接相关的数据，严格忽略其他膜。
2. 若数值估算自图表，在 notes 字段标注来源图号，如 "Membrane_Ra estimated from Fig.3b"。
3. 若某参数文中和图中均无数据，填 null。
4. 浓度单位保留原文单位（w/v%、g/L、mol/L 等）。
5. 数值型字段必须是 float/int；浓度用嵌套格式。

【需要提取的参数】
- membrane_id        : 膜名称/编号
- substrate          : 支撑层材料（PES/PVDF/PSF/PAN）
- Substrate_pore_size: 支撑层孔径 (nm)
- Substrate_MWCO     : 支撑层截留分子量 (kDa)
- Substrate_Water_contact_angle: 支撑层水接触角 (°)
- Substrate_zeta     : 支撑层 zeta 电位 (mV)
- Substrate_Ra       : 支撑层粗糙度 (nm)
- PIP_Concentration  : PIP 浓度，格式 {"value": 数值, "unit": "原始单位"}
- TMC_Concentration  : TMC 浓度，格式 {"value": 数值, "unit": "原始单位"}
- Degree_of_crosslinking: O/N 交联度（无量纲）
- Thickness          : 皮层厚度 (nm)
- Effective_pore_size: 有效孔径 (nm)
- Zeta_potential     : 皮层 zeta 电位 (mV)
- Membrane_Ra        : 分离层粗糙度 (nm)
- pure_water_flux    : 纯水通量 (LMH/bar)
- Na2SO4_rejection   : Na2SO4 截留率 (%)
- NaCl_rejection     : NaCl 截留率 (%)
- data_sources       : 数据来源列表，如 ["Table 2", "Fig. 3a"]
- notes              : 特殊说明（估算来源、存疑数据等）

【重要】直接输出 JSON，不要任何解释，不要 markdown 代码块。
"""

mem_extract_template = Template(RAW_MEMBRANE_EXTRACT)

if __name__ == "__main__":
    print(mem_extract_template.substitute(membrane_id="Test_name"))