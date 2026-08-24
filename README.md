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
├── main.py                  # 统一入口（预留）
├── requirements.txt         # 依赖清单
├── api_key_example.py       # API 密钥模板（复制为 api_keys.py）
│
└── zjuqa/                   # 核心包
    ├── config/              # 配置层（路径、LLM 参数）
    ├── models/              # 数据模型（MembraneData 等）
    ├── llm_client/          # LLM 客户端封装
    ├── pdf_processing/      # PDF 预处理（MinerU + 旧版 fitz）
    ├── extraction/          # 信息提取（膜名称识别 + 膜参数提取）
    ├── storage/             # 持久化（版本化保存 + 均值聚合）
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

将 PDF 论文放入 `data/raw_pdfs/` 目录。

### 3. 运行流水线

```bash
# Step 1: MinerU 解析 PDF（输出结构化 Markdown + 图片）
python -m zjuqa.pdf_processing.mineru_parser

# Step 2: 识别膜名称（写入 meta.json）
python -m zjuqa.extraction.membrane_identifier

# Step 3: 提取膜参数（版本化保存 + 均值聚合）
python -m zjuqa.extraction.membrane_extractor
```

## 本次重构要点（v0.2）

1. **MembraneData 只保留均值**：所有数值字段去除误差/标准差/范围。
2. **截留率改为字典**：`rejections: Dict[str, float]`，智能识别所有截留物质。
3. **时间戳版本化保存**：每次提取结果独立保存，不覆写；支持多版本取均值。
4. **代码结构优化**：按功能分包子包，为 ML/知识库/QA/PandasAgent 预留结构。

详见 [Note.md](./Note.md)。

## 处理流水线

```
PDF → MinerU 解析 → 膜名称识别(纯文本LLM) → 膜参数提取(多模态LLM)
    → 版本化保存 → 均值聚合 → 结构化 JSON
```

## 后续开发

- [ ] M2：膜性能预测机器学习模型
- [ ] 知识库构建与向量检索
- [ ] M3：自然语言问答接口
- [ ] PandasAgent 自动数据分析
