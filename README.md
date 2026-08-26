# zjuQAsystem

基于大语言模型技术的**化工膜领域科研问答系统**。

## 项目目标

三大核心模块：

1. **M1 文献信息提取**：LLM 读取论文 PDF，逐个提取不同膜的制备参数与性能指标 ✅
2. **M2 性能预测建模**：基于膜参数数据训练机器学习预测模型 ⏳（预留）
3. **M3 科研问答接口**：自然语言提问 → LLM 解析意图 → 科研辅助回答 ⏳（预留）

## 项目结构

```
zjuQAsystem/
├── Note.md                  # 项目规划与架构设计文档
├── main.py                  # 统一 CLI 入口（parse / identify / extract / all）
├── requirements.txt         # 依赖清单
├── api_key_example.py       # API 密钥模板（复制为 api_keys.py）
│
├── data/                    # 数据目录（按处理阶段分离）
│   ├── raw/                 #   原始 PDF（不可变输入）
│   ├── parsed/              #   阶段1：MinerU 解析输出
│   ├── identified/          #   阶段2：膜名称识别结果
│   └── extracted/           #   阶段3：膜参数提取结果（文章-膜两级）
│
└── zjuqa/                   # 核心包
    ├── config/              # 配置层（路径、LLM 参数）
    ├── models/              # 数据模型（MembraneData 等 Pydantic 模型）
    ├── llm_client/          # LLM 客户端封装
    ├── pdf_processing/      # PDF 预处理（MinerU 解析）
    ├── extraction/          # 信息提取（膜名称识别 + 膜参数提取）
    ├── storage/             # 持久化（单膜版本化保存 + 均值聚合）
    ├── ml/                  # 机器学习（预留）
    ├── knowledge_base/      # 知识库（预留）
    ├── qa_interface/        # 问答接口（预留）
    └── pandas_agent/        # PandasAgent（预留）
```

## 快速开始

### 1. 环境配置

```bash
# Python 3.11（MinerU 依赖限制）
conda create -n zjuqa python=3.11
conda activate zjuqa

# 安装依赖
pip install -r requirements.txt

# 配置 API 密钥
cp api_key_example.py api_keys.py
# 编辑 api_keys.py，填入你的 GLM_KEY
```

### 2. 数据准备

将 PDF 论文放入 `data/raw/` 目录。文件名（不含扩展名）将作为论文标识符，不要求 `Test_X` 格式。

### 3. 运行流水线

```bash
# 全量运行三阶段（自动扫描 data/raw/，跳过已完成的）
python main.py all

# 或分阶段运行
python main.py parse      # 阶段1：MinerU PDF 解析
python main.py identify   # 阶段2：膜名称识别
python main.py extract    # 阶段3：膜参数提取

# 常用参数
python main.py all --mode force        # 强制重跑（覆盖已有结果）
python main.py extract --paper Test_1  # 只处理指定论文
python main.py extract --max-images 20 # 限制传入图片数
```

## 数据目录结构

```
data/
├── raw/                          # 原始 PDF
│   └── *.pdf
├── parsed/                       # 阶段1：MinerU 输出
│   └── <paper>/auto/
│       ├── <paper>.md
│       └── images/
├── identified/                   # 阶段2：膜名称列表
│   └── <paper>/meta.json
└── extracted/                    # 阶段3：膜参数（文章-膜两级）
    └── <paper>/
        ├── <membrane>/
        │   ├── versions/         # 该膜的历史版本（时间戳命名）
        │   └── aggregated.json   # 该膜的多版本均值
        └── _paper_aggregated.json  # 整篇论文所有膜的聚合
```

详见 [data/README.md](./data/README.md)。

## 重构要点

### v0.3（当前）

1. **阶段化数据目录**：`raw/` → `parsed/` → `identified/` → `extracted/`，三阶段成果充分分离。
2. **文章-膜两级分离**：每个膜独立目录，含版本历史和聚合结果，支持异常中断后单膜重启。
3. **自动扫描**：脱离 `Test_X` 命名依赖，自动发现 `data/raw/` 下所有 PDF。
4. **统一 CLI 入口**：`main.py` 提供 `parse`/`identify`/`extract`/`all` 子命令，`--mode skip|force` 控制重复计算。
5. **Bug 修复**：修复 `membrane_paras_refit` 变量名错误、`import zjuqa` 触发 api_keys 强依赖、模型名硬编码等问题。

### v0.2

1. **MembraneData 只保留均值**：所有数值字段去除误差/标准差/范围。
2. **截留率改为字典**：`rejections: Dict[str, float]`，智能识别所有截留物质。
3. **时间戳版本化保存**：每次提取结果独立保存，不覆写；支持多版本取均值。
4. **代码结构优化**：按功能分包子包，为 ML/知识库/QA/PandasAgent 预留结构。

详见 [Note.md](./Note.md)。

## 处理流水线

```
PDF → MinerU 解析 → 膜名称识别(纯文本LLM) → 膜参数提取(多模态LLM)
    → 单膜版本化保存 → 均值聚合 → 结构化 JSON
```

## 后续开发

- [ ] M2：膜性能预测机器学习模型
- [ ] 知识库构建与向量检索
- [ ] M3：自然语言问答接口
- [ ] PandasAgent 自动数据分析
