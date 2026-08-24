"""
zjuqa —— 化工膜领域科研问答系统核心包。

包结构：
    config/          配置层（路径、LLM 参数）
    models/          数据模型层（MembraneData 等 Pydantic 模型）
    llm_client/      LLM 客户端封装
    pdf_processing/  PDF 预处理（MinerU 解析 + 旧版 fitz 兼容）
    extraction/      信息提取（膜名称识别 + 膜参数提取）
    storage/         数据持久化（版本化保存 + 均值聚合）
    ml/              机器学习模块（预留）
    knowledge_base/  知识库模块（预留）
    qa_interface/    问答接口模块（预留）
    pandas_agent/    PandasAgent 模块（预留）
"""

# 常用类与函数的包级导出，方便外部 from zjuqa import MembraneData
from .models.membrane import MembraneData, PaperData
from .config.paths import (
    ROOT_DIR, RAW_PDF_DIR, PRE_PDF_DIR, MINERU_OUT_DIR,
    MEMBRANE_DATA_DIR, PAGE_DPI, MAX_IMAGES,
)
from .config.llm_config import LLMParas
