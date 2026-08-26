"""
prompts.py —— LLM 提示词模板集中管理。

将较长的系统提示词与提取模板独立存放，便于维护和 A/B 测试。
本次修改（对应项目需求）：
  1. 膜参数提取模板新增"只保留均值、去除误差"规则。
  2. 截留率从固定字段改为字典输出，要求智能识别所有截留物质。

使用说明：
    from zjuqa.extraction.prompts import IDENTIFY_SYSTEM, mem_extract_template
    system_prompt = mem_extract_template.substitute(membrane_id="TFC-s-O")
"""

from string import Template

# ====================================================================
# S1：膜名称识别 —— 系统提示词
# ====================================================================
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


# ====================================================================
# S2：膜参数提取 —— 系统提示词模板
# 用 $membrane_id 占位符，调用时 substitute 替换为具体膜名。
# ====================================================================
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

【均值提取规则（重要）】
1. 所有数值只保留均值，严禁保留误差/标准差/置信区间/范围。
   - 若原文为 "95.2 ± 0.3"，只提取 95.2
   - 若原文为 "range 94-96"，只提取均值 95
   - 若原文为 "(95.0, 95.4)"，只提取均值 95.2
   - 若表格分列 "mean" 和 "std"，只取 mean 列
2. 浓度字段同样只取均值，保留原始单位。

【截留率智能识别规则（重要）】
- 截留率使用字典输出，键为被截留物质的标准化学式（用普通字符，不用下标特殊符号），
  如 "Na2SO4"、"NaCl"、"MgCl2"、"CaCl2"、"Na2HPO4"、"RhB"（染料）等。
- 扫描全文所有截留率数据，包括表格和图表，动态识别所有被截留的物质，不要遗漏。
- 若同一物质在多处出现，取均值（按上述均值规则）。
- 盐截留率图中注意区分不同物质。

【提取规则】
1. 只提取与膜 "$membrane_id" 直接相关的数据，严格忽略其他膜。
2. 若数值估算自图表，在 notes 字段标注来源图号，如 "Membrane_Ra estimated from Fig.3b"。
3. 若某参数文中和图中均无数据，填 null。
4. 浓度单位保留原文单位（w/v%、g/L、mol/L 等），格式 {"value": 均值, "unit": "原始单位"}。
5. 数值型字段必须是 float/int；无法确定时可保留字符串但需在 notes 说明。

【需要提取的参数】
- membrane_id        : 膜名称/编号
- substrate          : 支撑层材料（PES/PVDF/PSF/PAN）
- Substrate_pore_size: 支撑层孔径均值 (nm)
- Substrate_MWCO     : 支撑层截留分子量均值 (kDa)
- Substrate_Water_contact_angle: 支撑层水接触角均值 (°)
- Substrate_zeta     : 支撑层 zeta 电位均值 (mV)
- Substrate_Ra       : 支撑层粗糙度均值 (nm)
- PIP_Concentration  : PIP 浓度均值，格式 {"value": 数值, "unit": "原始单位"}
- TMC_Concentration  : TMC 浓度均值，格式 {"value": 数值, "unit": "原始单位"}
- Degree_of_crosslinking: O/N 交联度均值（无量纲）
- Thickness          : 皮层厚度均值 (nm)
- Effective_pore_size: 有效孔径均值 (nm)
- Zeta_potential     : 皮层 zeta 电位均值 (mV)
- Membrane_Ra        : 分离层粗糙度均值 (nm)
- pure_water_flux    : 纯水通量均值 (LMH/bar)
- rejections         : 截留率字典，键为物质名(如"Na2SO4")，值为截留率均值(%)
                       示例 {"Na2SO4": 95.2, "NaCl": 30.5, "MgCl2": 45.0}
- data_sources       : 数据来源列表，如 ["Table 2", "Fig. 3a"]
- notes              : 特殊说明（估算来源、存疑数据等）
【重要】直接输出标准JSON，不要任何解释，不要 markdown 代码块。
"""

# Template 实例，调用时 .substitute(membrane_id="...")
mem_extract_template = Template(RAW_MEMBRANE_EXTRACT)
REFIT_SYSTEM="""请将文字重写成符合json数据格式要求的字段。
所要求的数据格式：
1. 所有数值只保留均值，严禁保留误差/标准差/置信区间/范围。
   - 若原文为 "95.2 ± 0.3"，只提取 95.2
   - 若原文为 "range 94-96"，只提取均值 95
   - 若原文为 "(95.0, 95.4)"，只提取均值 95.2
   - 若表格分列 "mean" 和 "std"，只取 mean 列
2. 浓度字段同样只取均值，浓度单位保留原文单位（w/v%、g/L、mol/L 等），格式 {"value": 均值, "unit": "原始单位"}。
3. 截留率使用字典输出，键为被截留物质的标准化学式（用普通字符，不用下标特殊符号），
  如 "Na2SO4"、"NaCl"、"MgCl2"、"CaCl2"、"Na2HPO4"、"RhB"（染料）等。
4. 数值型字段必须是 float/int；无法确定时可保留字符串但需在 notes 说明。
【需要提取的参数】
- membrane_id        : 膜名称/编号
- substrate          : 支撑层材料（PES/PVDF/PSF/PAN）
- Substrate_pore_size: 支撑层孔径均值 (nm)
- Substrate_MWCO     : 支撑层截留分子量均值 (kDa)
- Substrate_Water_contact_angle: 支撑层水接触角均值，返回纯数字，不保留单位 (°)
- Substrate_zeta     : 支撑层 zeta 电位均值 (mV)
- Substrate_Ra       : 支撑层粗糙度均值 (nm)
- PIP_Concentration  : PIP 浓度均值，格式 {"value": 数值, "unit": "原始单位"}
- TMC_Concentration  : TMC 浓度均值，格式 {"value": 数值, "unit": "原始单位"}
- Degree_of_crosslinking: O/N 交联度均值（无量纲）
- Thickness          : 皮层厚度均值 (nm)
- Effective_pore_size: 有效孔径均值 (nm)
- Zeta_potential     : 皮层 zeta 电位均值 (mV)
- Membrane_Ra        : 分离层粗糙度均值 (nm)
- pure_water_flux    : 纯水通量均值 (LMH/bar)
- rejections         : 截留率字典，键为物质名(如"Na2SO4")，值为截留率均值(%)，
                       示例 {"Na2SO4": 95.2, "NaCl": 30.5, "MgCl2": 45.0}
- data_sources       : 数据来源列表，如 ["Table 2", "Fig. 3a"]
- notes              : 特殊说明（估算来源、存疑数据等）
【重要】直接输出标准JSON，不要任何解释，不要 markdown 代码块。
请将文字重写成符合json数据格式要求的字段，直接输出标准JSON，不要任何解释，不要 markdown 代码块。
"""


if __name__ == "__main__":
    # 快速预览模板替换效果
    print(mem_extract_template.substitute(membrane_id="Test_name"))
