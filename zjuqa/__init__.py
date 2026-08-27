"""
zjuqa —— 化工膜领域科研问答系统核心包。

包结构：
    config/          配置层（路径常量、LLM 参数）
    schemas/         数据模型层（Pydantic schema，原 models/，避免与 ML 模型冲突）
    utils/           通用工具层（扫描、图片、聚合、IO、日志）
    llm_client/      LLM 客户端封装
    pdf_processing/  PDF 预处理（MinerU 解析）
    extraction/      信息提取（膜名称识别 + 膜参数提取）
    storage/         数据持久化（单膜版本化保存 + 均值聚合）
    ml/              机器学习模块（预留）
    knowledge_base/  知识库模块（预留）
    qa_interface/    问答接口模块（预留）
    pandas_agent/    PandasAgent 模块（预留）

注意：
  - 本包不导入 LLMParas，避免 import zjuqa 时触发 api_keys 强依赖。
"""
# 数据模型（从 schemas 导入，无外部依赖）
from .schemas.membrane import MembraneData, ValueUnit

# 路径配置（无外部依赖，可安全导入）
from .config.paths import (
    ROOT_DIR,
    RAW_PDF_DIR,
    PARSED_DIR,
    IDENTIFIED_DIR,
    EXTRACTED_DIR,
    PRE_PDF_DIR,
    PAGE_DPI,
    MAX_IMAGES,
    ensure_data_dirs,
)

__all__ = [
    "MembraneData", "ValueUnit",
    "ROOT_DIR", "RAW_PDF_DIR", "PARSED_DIR", "IDENTIFIED_DIR", "EXTRACTED_DIR",
    "PRE_PDF_DIR", "PAGE_DPI", "MAX_IMAGES", "ensure_data_dirs",
]
