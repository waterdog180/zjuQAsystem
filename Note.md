# zjuQAsystem 项目规划与架构设计

> 版本：v0.2（重构版）  
> 日期：2026-08-22  
> 性质：半工程化、半科研实践项目

---

## 一、项目总目标

开发一个**基于大语言模型技术的化工膜领域科研问答系统**，覆盖三大核心能力：

| 模块 | 功能 | 当前状态 |
|------|------|----------|
| **M1 文献信息提取** | LLM 读取论文 PDF，逐个提取不同膜的制备参数与性能指标 | ✅ 核心链路已跑通，本次重构优化 |
| **M2 性能预测建模** | 基于提取的膜参数数据，训练预测膜性能的机器学习模型 | ⏳ 预留结构，待数据量充足后启动 |
| **M3 科研问答接口** | 研究者用自然语言提问，LLM 解析意图，结合知识库给出科研辅助回答 | ⏳ 预留结构，依赖 M1 数据与 M2 模型 |

三者关系：M1 是数据基座，M2 是分析引擎，M3 是用户交互层。M1 的数据质量直接决定 M2 和 M3 的上限。

---

## 二、当前阶段（M1）的处理流水线

```
PDF 论文
  │
  ▼  [pdf_processing/mineru_parser.py]  MinerU 机器学习解析
结构化 Markdown 全文 + 页面图片（auto/ 目录）
  │
  ▼  [extraction/membrane_identifier.py]  纯文本 LLM 识别膜名称
膜名称列表 → meta.json
  │
  ▼  [extraction/membrane_extractor.py]  多模态 LLM 逐膜提取参数
文本 + 全部页面图片 → 21 项参数 → 时间戳版本化 JSON
  │
  ▼  [storage/membrane_repository.py]  版本管理 + 均值聚合
历史版本并列保存 + 多版本取均值 → mem_paras_aggregated.json
```

### 设计决策说明

1. **硬盘暂存（Checkpoint）**：每阶段结果独立落盘，支持断点续跑。MinerU 单篇 CPU 处理 3-10 分钟，重复计算代价高，暂存是必要的容错设计。
2. **两阶段提取**：先识别膜名称（纯文本、低成本），再逐膜提取参数（多模态、高成本）。避免在一篇论文只有 1 种膜时浪费多模态调用。
3. **多模态输入**：膜参数大量存在于图表（截留率曲线、柱状图）中，纯文本提取必然丢失信息，必须传入页面图片。

---

## 三、本次重构的四项具体需求与实现方案

### 需求 1：MembraneData 只保留均值，去除误差

**问题**：论文中数据常以 `95.2 ± 0.3` 或 `(94.8, 95.6)` 形式呈现，LLM 可能将误差一并提取，污染后续机器学习训练。

**方案**：
- `models/membrane.py` 中所有数值字段的 description 明确标注"仅保留均值"。
- `extraction/prompts.py` 提取规则新增："若数据带有误差范围/标准差/置信区间（如 95.2±0.3、range 94-96），只提取均值 95.2，忽略误差部分。"
- 浓度字段若为 dict，`value` 同样只取均值。
- 聚合时（需求 3）对多次识别的均值再取均值，进一步降低识图误差。

**可行性**：高。仅需修改提示词和字段描述，不涉及算法变更。LLM 对"只取均值"的指令遵循度较好。

---

### 需求 2：截留率改为字典，智能识别与动态匹配

**问题**：原模型硬编码 `Na2SO4_rejection` 和 `NaCl_rejection` 两个字段，但论文中可能出现 MgCl₂、CaCl₂、Na₂HPO₄、染料分子等多种截留对象，固定字段无法覆盖。

**方案**：
- 删除 `Na2SO4_rejection`、`NaCl_rejection` 两个固定字段。
- 新增 `rejections: Dict[str, Optional[Union[float, str]]]`，键为化学物质标准名称（如 `"Na2SO4"`、`"NaCl"`、`"MgCl2"`），值为截留率（%）。
- 提示词中要求 LLM 扫描全文所有截留率数据，动态识别被截留物质，以字典输出。常见盐名给出示例但不限制。
- `__str__` 方法遍历字典逐项打印。
- 聚合时按物质名分组取均值，不同版本识别出的新物质自动并入。

**数据结构示例**：
```json
{
  "membrane_id": "TFC-s-O",
  "rejections": {
    "Na2SO4": 95.2,
    "NaCl": 30.5,
    "MgCl2": 45.0
  }
}
```

**可行性**：高。字典结构比固定字段更灵活，LLM 输出 JSON 字典的稳定性已在浓度字段验证。唯一风险是 LLM 对同一物质使用不同命名（如 `"Na₂SO₄"` vs `"Na2SO4"`），需在提示词中要求使用标准化学式（无下标特殊字符）。

---

### 需求 3：时间戳版本化保存 + 均值聚合

**问题**：原 `get_mem_paras_from_paper` 直接覆写 `mem_paras.json`，多次运行的结果无法对比，识图数据的随机误差无法通过多次取样平均。

**方案**：
- 每次提取结果保存为 `auto/mem_paras_versions/mem_paras_YYYYMMDD_HHMMSS.json`，永不覆写。
- 提供 `load_all_versions()` 读取全部历史版本。
- 提供 `aggregate_membrane_paras()` 对所有版本按 `membrane_id` 分组聚合：
  - **数值字段**：取所有非空值的算术均值。
  - **字符串字段**（substrate 等）：取第一个非空值（类别变量不宜平均）。
  - **浓度 dict**：取第一个非空值。
  - **rejections 字典**：按物质名分组，每种物质取均值。
  - **data_sources**：取并集去重。
  - **notes**：合并为一条字符串。
- 聚合结果保存为 `auto/mem_paras_aggregated.json`。
- 提取主函数 `extract_and_save()` 每次运行后自动触发聚合。

**目录结构**：
```
paper_dir/auto/
├── Test_1.md              # MinerU 输出文本
├── meta.json              # 膜名称元数据
├── images/                # 页面图片
├── mem_paras_versions/    # 历史版本（新增）
│   ├── mem_paras_20260822_213045.json
│   └── mem_paras_20260822_220010.json
└── mem_paras_aggregated.json  # 聚合均值（新增）
```

**可行性**：高。文件操作逻辑简单，均值聚合是标准统计操作。注意数值字段可能是字符串（LLM 偶尔返回带单位的字符串），聚合时需尝试 `float()` 转换，失败则跳过该值。

---

### 需求 4：代码结构优化，子包分离

**问题**：原项目 8 个 .py 文件平铺在根目录，`paras.py` 混杂了路径、配置、数据模型三类职责，`llm_pdf_extractor.py` 超过 200 行混杂膜名识别和参数提取。随着 ML、知识库、QA 模块加入，文件将急剧膨胀。

**方案**：按功能分层为 Python 包：

```
zjuqa/
├── __init__.py
├── config/              # 配置层：路径、LLM 参数
│   ├── __init__.py
│   ├── paths.py         # 原 paras.py 路径部分
│   └── llm_config.py    # 原 paras.py LLMParas + api_keys 导入
├── models/              # 数据模型层
│   ├── __init__.py
│   └── membrane.py      # MembraneData（需求1、2 修改）
├── llm_client/          # LLM 客户端层
│   ├── __init__.py
│   └── client.py        # 原 llm.py
├── pdf_processing/      # PDF 预处理层
│   ├── __init__.py
│   ├── mineru_parser.py # 原 MinerUpdf.py
│   └── legacy_controller.py  # 原 pdf_controller.py（弃用保留）
├── extraction/          # 信息提取层（核心）
│   ├── __init__.py
│   ├── prompts.py       # 原 prompts.py（需求1、2 修改）
│   ├── membrane_identifier.py  # 原 S1 膜名称识别
│   └── membrane_extractor.py   # 原 S2 膜参数提取（需求3 修改）
├── storage/             # 持久化层
│   ├── __init__.py
│   └── membrane_repository.py  # 需求3 新增：版本管理+聚合
├── ml/                  # M2 机器学习（预留）
│   └── __init__.py
├── knowledge_base/      # 知识库（预留）
│   └── __init__.py
├── qa_interface/        # M3 问答接口（预留）
│   └── __init__.py
└── pandas_agent/        # PandasAgent（预留）
    └── __init__.py
```

**预留模块的设计意图**：
- `ml/`：后续存放特征工程、模型训练、预测推理代码。输入为 `mem_paras_aggregated.json`，输出为训练好的模型文件。
- `knowledge_base/`：后续存放向量数据库构建、检索逻辑。将论文文本片段与结构化膜参数关联。
- `qa_interface/`：后续存放意图解析、答案生成、API 端点。是用户直接交互的层。
- `pandas_agent/`：后续存放 LLM 生成数据分析代码的自动处理逻辑，数据量充足后启用。

**导入策略**：各模块通过相对导入（`from ..config.paths import ...`）引用，包根 `zjuqa/__init__.py` 导出常用类和函数，外部可 `from zjuqa import MembraneData, extract_membranes`。

**可行性**：高。纯结构重构，不改变算法逻辑。风险点是原代码使用 `from paras import *` 通配符导入，重构后需显式导入，需仔细核对每个文件的依赖。

---

## 四、约束与边界

本次重构**严格不修改**以下未提及的实现：
- MinerU 解析参数（backend、parse_method、formula_enable 等）
- LLM 客户端的模型选择、temperature、timeout 等参数
- 膜名称识别的提示词与截断逻辑（`text_len=12000` 等保持原样）
- 多模态消息构建方式（文本+全部图片）
- 图片加载逻辑（jpg/jpeg 过滤、base64 编码）
- `pdf_controller.py`（弃用文件，原样移入 legacy）

---

## 五、后续路线图

| 阶段 | 内容 | 前置条件 |
|------|------|----------|
| v0.3 | M1 稳定化：批量处理、错误重试、提取准确率评估 | 本次重构完成 |
| v0.4 | M2 启动：特征工程 + 基线模型（通量/截留率预测） | ≥50 篇论文结构化数据 |
| v0.5 | 知识库构建：向量检索 + 结构化数据混合查询 | M1 数据量充足 |
| v1.0 | M3 QA 接口：自然语言提问 + 意图路由 + 答案生成 | M2 + 知识库就绪 |
