# zjuQAsystem — 化工膜领域科研问答系统

基于大语言模型（LLM）的化工膜领域科研问答系统。当前处于 **M1 文献提取阶段**，实现从论文 PDF 中自动提取膜参数并结构化存储，同时提供数据清洗整理工具，为后续 M2 机器学习预测和 M3 知识库问答奠定数据基础。

## 项目目标

1. **文献参数提取**：利用多模态 LLM 读取论文 PDF（文本+图片），逐个提取不同膜的参数与性能数据
2. **数据清洗整理**：单位归一化、截留物名称映射、表格格式化、数据缺失分析，为 ML 训练准备干净数据集
3. **机器学习预测**（M2，开发中）：基于提取的膜参数数据，训练预测膜性能的 ML 模型
4. **科研问答接口**（M3，开发中）：搭建 QA 接口，研究者用自然语言提问，LLM 解析问题并提供科研辅助回答

## 项目架构

```
zjuQAsystem/
├── main.py                  # CLI 统一入口（parse/identify/extract/all/clean）
├── api_keys.py              # LLM API 密钥配置（需自行创建）
├── requirements.txt         # Python 依赖
├── data/                    # 数据目录（按处理阶段分离）
│   ├── raw/                 # 原始 PDF（不可变输入）
│   ├── parsed/              # 阶段1：MinerU 解析输出
│   ├── identified/          # 阶段2：膜名称识别结果
│   └── extracted/           # 阶段3：膜参数提取结果（文章-膜两级）
└── zjuqa/                   # 核心代码包
    ├── config/              # 配置层（路径常量、LLM 参数）
    ├── schemas/             # 数据模型层（Pydantic schema）
    ├── utils/               # 通用工具层（扫描、图片、聚合、IO、日志、清理、分析）
    ├── llm_client/          # LLM 客户端封装
    ├── pdf_processing/      # PDF 预处理（MinerU 解析）
    ├── extraction/          # 信息提取（膜名称识别 + 膜参数提取）
    ├── storage/             # 数据持久化（单膜版本化保存 + 均值聚合）
    ├── data_processing/     # 数据清洗整理（单位归一化、截留物映射、表格格式化）
    ├── ml/                  # 机器学习模块（预留）
    ├── knowledge_base/      # 知识库模块（预留）
    ├── qa_interface/        # 问答接口模块（预留）
    └── pandas_agent/        # PandasAgent 模块（预留）
```

### 包说明

| 包 | 功能 | 关键文件 |
|---|---|---|
| `config/` | 路径常量、LLM 参数等手动调整配置 | `paths.py`, `llm_config.py` |
| `schemas/` | Pydantic 数据模型定义（`MembraneData`, `ValueUnit`） | `membrane.py` |
| `utils/` | 通用工具：目录扫描、图片编码、数值聚合、JSON IO、日志、清理、数据分析 | `scanner.py`, `image.py`, `aggregation.py`, `io.py`, `logging.py`, `cleanup.py`, `analytics.py` |
| `pdf_processing/` | MinerU PDF 解析，输出结构化文本+页面图片 | `mineru_parser.py` |
| `extraction/` | 膜名称识别（S1）+ 膜参数提取（S2） | `membrane_identifier.py`, `membrane_extractor.py`, `prompts.py` |
| `storage/` | 单膜版本化保存、多版本均值聚合 | `membrane_repository.py` |
| `data_processing/` | 数据清洗整理：单位归一化、截留物映射、表格格式化、通量缺口扫描 | `unit_normalizer.py`, `substance_mapper.py`, `formatter.py`, `substance_aliases.json` |

> **命名说明**：原 `models/` 包已重命名为 `schemas/`，避免与 M2 阶段的机器学习模型命名冲突。

## 环境配置

### Python 版本
- **Python 3.11**（MinerU 依赖限制，不支持 3.12+）

### 安装依赖
```bash
pip install -r requirements.txt
```

核心依赖：
- `mineru==3.4.4` — PDF 文档解析
- `langchain-openai`, `langchain-core` — LLM 调用框架
- `pydantic>=2` — 数据模型校验
- `openai` — OpenAI 兼容 API 客户端
- `pandas` — 数据表格处理（data_processing 模块依赖）

### MinerU 环境变量
```bash
# 国内网络使用 ModelScope 模型源（默认）
export MINERU_MODEL_SOURCE=modelscope
# CPU 模式（无 GPU 时）
export MINERU_DEVICE_MODE=cpu
```

### API 密钥配置
在项目根目录创建 `api_keys.py`：
```python
# api_keys.py
API_KEY = "your-api-key-here"
BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"  # 智谱 API
```

## 快速开始

### 1. 放置 PDF
将论文 PDF 放入 `data/raw/` 目录（文件名任意，不依赖 `Test_X` 格式）：
```
data/raw/
├── paper1.pdf
├── paper2.pdf
└── ...
```

### 2. 一键全流程运行
```bash
python main.py all
```
这将依次执行：MinerU 解析 → 膜名称识别 → 膜参数提取 → 均值聚合。

### 3. 分阶段运行
```bash
# 阶段1：MinerU PDF 解析
python main.py parse
# 阶段2：膜名称识别
python main.py identify
# 阶段3：膜参数提取
python main.py extract
```

### 4. 数据清洗与导出（提取完成后）
```python
from zjuqa.data_processing import build_dataframe, export_csv, scan_flux_gaps

# 构建归一化后的表格（通量/比通量自动分列）
df = build_dataframe(normalize_units=True, map_substances_names=True)

# 导出 CSV（Excel 兼容编码）
export_csv(df, "membrane_dataset.csv")

# 扫描通量数据缺口（哪些膜可通过补充操作压力ΔP补全）
scan_flux_gaps()
```

## CLI 详细用法

```bash
python main.py <command> [--mode MODE] [--papers PAPER1 PAPER2 ...]
```

### 命令

| 命令 | 功能 | 输入 | 输出 |
|---|---|---|---|
| `parse` | MinerU 解析 PDF | `data/raw/*.pdf` | `data/parsed/<paper>/auto/` |
| `identify` | 识别论文中所有膜名称 | `data/parsed/<paper>/auto/*.md` | `data/identified/<paper>/meta.json` |
| `extract` | 提取每种膜的参数 | `data/identified/<paper>/meta.json` + 文本+图片 | `data/extracted/<paper>/<membrane>/` |
| `all` | 依次执行 parse → identify → extract | 同上 | 同上 |
| `clean` | 清理各阶段中间数据 | — | 删除指定阶段目录内容 |

### clean 命令
```bash
# 清理所有中间数据（保留 data/raw/ 原始 PDF）
python main.py clean --stage all
# 清理指定阶段
python main.py clean --stage parsed       # 清理解析输出
python main.py clean --stage identified   # 清理膜名称识别结果
python main.py clean --stage extracted    # 清理膜参数提取结果
# 清理指定论文的中间数据
python main.py clean --paper Test_1 --stage extracted
python main.py clean --paper Test_1 --stage all
```

| --stage | 清理内容 |
|---|---|
| `parsed` | `data/parsed/` 下所有 MinerU 解析输出 |
| `identified` | `data/identified/` 下所有膜名称识别结果 |
| `extracted` | `data/extracted/` 下所有膜参数提取结果 |
| `all`（默认） | 以上三个阶段全部清理，**保留** `data/raw/` 原始 PDF |

> 清理操作不可恢复，建议确认后再执行。`--paper` 可缩小清理范围到单篇论文。

### --mode 参数

| mode | 行为 | 适用场景 |
|---|---|---|
| `skip`（默认） | 跳过已完成的论文/膜，只处理未完成的 | 增量处理、断点续跑 |
| `force` | 全部重新处理，**不覆盖历史版本**，新增时间戳版本 | 重新提取、数据校对 |

**关键行为：多次提取不覆盖**
- `--mode force` 不会删除或覆盖已有的提取结果，而是以**时间戳文件名**新增一个版本
- 每个膜的所有历史版本保存在 `versions/` 目录下
- 聚合时自动对所有版本取均值，便于多次重复识别校对和模糊识图数据取均值
- `--mode skip` 则完全跳过已有提取结果的膜，避免重复计算

### --papers 参数
指定处理的论文名称列表（不含 `.pdf` 扩展名）。不指定时自动扫描对应阶段的数据目录。
```bash
# 只处理 paper1 和 paper2
python main.py extract --papers paper1 paper2
```

## 数据目录结构

### 阶段1：MinerU 解析输出
```
data/parsed/<paper_name>/
└── auto/
    ├── <paper_name>.md      # 结构化文本（含表格、公式）
    └── images/              # 页面图片（用于多模态 LLM）
        ├── page_1.jpg
        ├── page_2.jpg
        └── ...
```

### 阶段2：膜名称识别结果
```
data/identified/<paper_name>/
└── meta.json                # 膜名称列表 + 论文元信息
```
`meta.json` 格式：
```json
{
  "article_Title": null,
  "article_Author": null,
  "article_Year": null,
  "membrane_ids": ["TFC-s-O", "TFC-m-O", "PA-1"]
}
```

### 阶段3：膜参数提取结果（文章-膜两级分离）
```
data/extracted/<paper_name>/
├── <membrane_id>/           # 每种膜一个独立目录
│   ├── versions/            # 历史版本（时间戳命名，永不覆盖）
│   │   ├── 20260822_213045.json
│   │   ├── 20260822_220010.json
│   │   └── ...
│   └── aggregated.json      # 该膜的多版本均值聚合
└── _paper_aggregated.json   # 整篇论文所有膜的聚合结果
```

**单膜粒度 checkpoint**：每个膜提取后立即保存，异常中断时已完成的膜不丢失，重启后 `--mode skip` 自动跳过。

## 数据格式说明

### ValueUnit 格式
所有数值字段统一采用 `{"value": 数值, "unit": "原始单位"}` 字典格式，保留论文原始单位：
```json
{
  "membrane_id": "TFC-s-O",
  "substrate": "PES",
  "pure_water_flux": {"value": 15.2, "unit": "LMH/bar"},
  "Thickness": {"value": 100, "unit": "nm"},
  "Substrate_Water_contact_angle": {"value": 92.6, "unit": "°"},
  "rejections": {
    "Na2SO4": {"value": 95.2, "unit": "%"},
    "NaCl": {"value": 30.5, "unit": "%"}
  }
}
```

**设计原则**：
- `value`：仅保留均值，去除误差/标准差/置信区间/范围
- `unit`：论文中使用的原始单位字符串（如 `nm`, `μm`, `LMH/bar`, `mV`, `°`, `%`, `w/v%`）
- 无量纲参数（如交联度 O/N 比）的 `unit` 填 `"ratio"`
- 无数据的字段填 `null`

### 聚合时的单位处理
- 同一字段多个版本**单位一致**：取 `value` 均值，保留该单位
- 同一字段多个版本**单位不一致**：取第一个版本的单位，`value` 取所有版本均值，单位后标注 `*` 表示冲突（如 `"nm*"`）
- 建议在 M2 ML 训练前使用 `data_processing` 模块进行单位标准化

### MembraneData 字段一览

| 字段 | 类型 | 说明 |
|---|---|---|
| `membrane_id` | str | 膜名称/编号 |
| `substrate` | str | 支撑层材料（PES/PVDF/PSF/PAN） |
| `Substrate_pore_size` | ValueUnit | 支撑层孔径 |
| `Substrate_MWCO` | ValueUnit | 支撑层截留分子量 |
| `Substrate_Water_contact_angle` | ValueUnit | 支撑层水接触角 |
| `Substrate_zeta` | ValueUnit | 支撑层 zeta 电位 |
| `Substrate_Ra` | ValueUnit | 支撑层粗糙度 |
| `PIP_Concentration` | ValueUnit | PIP 浓度 |
| `TMC_Concentration` | ValueUnit | TMC 浓度 |
| `Degree_of_crosslinking` | ValueUnit | O/N 交联度 |
| `Thickness` | ValueUnit | 皮层厚度 |
| `Effective_pore_size` | ValueUnit | 有效孔径 |
| `Zeta_potential` | ValueUnit | 皮层 zeta 电位 |
| `Membrane_Ra` | ValueUnit | 分离层粗糙度 |
| `pure_water_flux` | ValueUnit | 纯水通量（单位可能是 LMH 或 LMH/bar，见数据清洗说明） |
| `rejections` | Dict[str, ValueUnit] | 截留率字典（键=化学物质名，值=截留率） |
| `data_sources` | List[str] | 数据来源（如 Table 2, Fig. 3a） |
| `notes` | str | 特殊说明（估算来源、存疑数据、单位冲突） |

## 数据清洗整理（data_processing 模块）

`data_processing` 模块为 M2 机器学习训练准备干净的数据集，**只读 `data/extracted/`，不修改原始提取数据**。

### 1. 单位归一化

对 13 个数值参数定义标准单位和换算函数，将不同单位的数据统一到标准单位。

```python
from zjuqa.data_processing import normalize_value, normalize_membrane

# 单个值归一化
result = normalize_value("Effective_pore_size", 10.0, "Å")
print(result.value, result.unit)  # 1.0 nm

# 整个膜数据归一化
normalized_mem, report = normalize_membrane(membrane_data)
```

**各参数标准单位**：

| 参数 | 标准单位 | 可换算单位 |
|---|---|---|
| 支撑层孔径 | nm | Å, μm |
| 支撑层 MWCO | kDa | Da |
| 接触角 | ° | deg |
| zeta 电位 | mV | V |
| PIP/TMC 浓度 | w/v% | wt%, wt.%, g/L（近似） |
| 交联度 | ratio | % |
| 厚度/孔径/粗糙度 | nm | Å, μm, mm |
| 纯水通量 | LMH | L/m²/h, mL/(cm²·h), m³/(m²·d) |
| 纯水比通量 | LMH/bar | L/(m²·h·bar), LMH/MPa |

**近似换算标记**：`wt%` → `w/v%` 物理意义不同（质量分数 vs 质量体积比），但膜领域常近似等价，归一化结果标记 `is_approximate=True`。

### 2. 通量与比通量分列

通量（flux, J，单位 LMH）与比通量（permeance, A，单位 LMH/bar）是**两个不同物理量**，关系为 `J = A × ΔP`。`data_processing` 在表格输出时自动分列：

```python
from zjuqa.data_processing import classify_flux_unit, normalize_flux_value

# 判断单位类型
print(classify_flux_unit("LMH/bar"))   # "permeance"
print(classify_flux_unit("LMH"))       # "flux"

# 自动分类并归一化
field, result = normalize_flux_value(80.0, "L/(m²·h·bar)")
print(field)   # "pure_water_permeance"
print(result.value, result.unit)  # 80.0 LMH/bar
```

### 3. 通量数据缺口扫描

扫描哪些膜有比通量无通量、哪些有通量无比通量，补充操作压力 ΔP 后可自动补全：

```python
from zjuqa.data_processing import scan_flux_gaps

gaps = scan_flux_gaps()
# 输出示例：
# 有比通量(LMH/bar)、无通量(LMH): 35 个 → 补充ΔP后可计算通量
# 有通量(LMH)、无比通量(LMH/bar): 6 个 → 补充ΔP后可计算比通量
# 两者皆无: 5 个
# 可通过ΔP补全: 41 个
```

> 当前 `MembraneData` schema 无 `operating_pressure` 字段，缺口扫描只报告不计算。未来添加操作压力字段后可实现 `J = A × ΔP` 自动补全。

### 4. 截留物名称映射

LLM 可能将同一物质识别为不同名称（如 `TC`、`Tetracycline`、`tetracycline`），通过配置文件 `substance_aliases.json` 建立纠正映射：

```python
from zjuqa.data_processing import get_standard_name, map_substances

# 单个名称映射
print(get_standard_name("TC"))  # ("tetracycline", True)

# 整个截留率字典映射
mapped_rej, log = map_substances({"TC": {"value": 90, "unit": "%"}, "NaCl": {"value": 50, "unit": "%"}})
# → {"tetracycline": {...}, "NaCl": {...}}
```

**映射规则**：
- 大小写不敏感匹配
- 盐与离子不合并（`Na2SO4` ≠ `SO4^2-`）
- 配置文件可扩展，新增别称直接编辑 `substance_aliases.json`

当前配置覆盖 21 种标准物质，包括：四环素类、磺胺类抗生素、PFAS 全氟化合物、对羟基苯甲酸酯类、常见离子等。

### 5. 表格格式化与 CSV 导出

将所有提取完成的膜整理为 pandas DataFrame，每行一个膜，截留率展开为多列：

```python
from zjuqa.data_processing import build_dataframe, export_csv, print_summary

# 构建表格（默认应用单位归一化和截留物映射）
df = build_dataframe(normalize_units=True, map_substances_names=True)

# 打印摘要
print_summary(df)

# 导出 CSV（utf-8-sig 编码，Excel 直接打开不乱码）
export_csv(df, "membrane_dataset.csv")
```

**输出表格列结构**：
- 基础信息：`paper_name`, `membrane_id`, `substrate`
- 12 个非通量数值参数（各带 `__unit` 后缀列）
- 通量分列：`pure_water_flux`（LMH）+ `pure_water_permeance`（LMH/bar）
- 截留率：`rejection_<物质名>` 展开为多列
- 可选：`data_sources`, `notes`

### 6. 单位归一化问题报告

查看哪些数据无法归一化（未知单位、需补充信息等）：

```python
from zjuqa.data_processing import get_normalization_report

issues = get_normalization_report()
# 输出每项问题：论文/膜/字段/原始单位/原因
```

## 数据分析工具（utils/analytics）

提取完成后，可使用 `analytics` 模块进行数据质量评估：

### 数据缺失统计
```python
from zjuqa.utils.analytics import report_missing_data

report = report_missing_data()
# 输出：各参数缺失率、截留率物质覆盖、各论文详情
```

### 单位分布统计
```python
from zjuqa.utils.analytics import report_unit_distribution

report = report_unit_distribution()
# 输出：各参数使用的单位及出现次数，标记存在单位冲突的字段
# 为 ML 训练前的单位归一化提供前期调研
```

## 处理流程详解

### 阶段1：MinerU 解析
- 调用 `mineru.cli.common.do_parse` API（MinerU 3.4.4）
- 输出结构化 Markdown 文本（含表格、公式）和页面图片
- 页面图片 DPI 默认 200（可在 `config/paths.py` 调整 `PAGE_DPI`）

### 阶段2：膜名称识别
- 调用纯文本 LLM，从论文前 12000 字符中识别所有膜名称
- 结果保存到 `meta.json`
- `--mode force` 会覆盖已有膜名称列表

### 阶段3：膜参数提取
- 对每个膜构建多模态消息：
  - **SystemMessage**：通用规则（单位格式、均值规则、JSON 约束、截留率智能识别）
  - **HumanMessage**：膜名称 + 论文全文文本 + 页面图片（最多 40 张）
- 调用多模态 LLM（glm-4.6v）提取参数
- JSON 解析失败时自动调用 refit 二次格式化
- Pydantic 校验失败时同样尝试 refit
- 每个膜提取后立即版本化保存

## 常见问题

### Q: 提取中断后如何续跑？
A: 直接运行 `python main.py extract --mode skip`，已提取的膜会自动跳过，只处理未完成的膜。

### Q: 想重新提取某篇论文但保留旧结果对比？
A: 使用 `python main.py extract --mode force --papers paper1`。旧版本保留在 `versions/` 目录，新版本以新时间戳保存，`aggregated.json` 会自动对所有版本取均值。

### Q: 如何查看某个膜的所有历史版本？
A: 查看 `data/extracted/<paper>/<membrane>/versions/` 目录，每个 JSON 文件是一次提取结果。

### Q: MinerU 模型下载失败？
A: 确保设置了 `MINERU_MODEL_SOURCE=modelscope`（国内网络）。HuggingFace 源在国内可能不可达。

### Q: LLM 返回的 JSON 解析失败？
A: 系统会自动调用 refit 二次格式化。如果仍失败，该膜会被跳过并打印日志，不影响其他膜的提取。

### Q: 通量数据单位不一致怎么办？
A: 使用 `data_processing` 模块的 `build_dataframe()`，它会自动将通量（LMH）和比通量（LMH/bar）分列，并各自归一化到标准单位。用 `scan_flux_gaps()` 查看哪些膜可通过补充操作压力补全。

### Q: 截留率物质名大小写不一致（如 TC vs Tetracycline）？
A: `build_dataframe()` 默认应用截留物名称映射，自动合并为标准名。映射规则在 `substance_aliases.json` 中配置。

## 开发路线

- [x] **M1**：文献参数提取（MinerU 解析 + 膜名称识别 + 膜参数提取 + 版本化存储）
- [x] **M1.5**：数据清洗整理（单位归一化 + 截留物映射 + 表格格式化 + 数据分析工具）
- [ ] **M2**：机器学习膜性能预测（基于提取数据训练回归模型）
- [ ] **M3**：知识库问答接口（自然语言提问 + LLM 解析 + 科研辅助回答）
- [ ] **M4**：PandasAgent 数据交互（自然语言查询膜参数数据库）
