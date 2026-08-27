"""
schemas —— 数据模型层（Pydantic schema 定义）。

原 models/ 包重命名为 schemas/，避免与 M2 机器学习模型（models）命名冲突。
本层只定义数据结构，不包含业务逻辑。

使用说明：
    from zjuqa.schemas import MembraneData, ValueUnit
"""
from .membrane import MembraneData, ValueUnit

__all__ = ["MembraneData", "ValueUnit"]
