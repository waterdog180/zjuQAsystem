"""数据持久化层：膜参数的单膜版本化保存与均值聚合。"""
from .membrane_repository import (
    save_membrane_version,
    load_membrane_versions,
    is_membrane_extracted,
    aggregate_membrane,
    aggregate_paper,
    # 兼容旧接口
    #save_membrane_params_version,
    #aggregate_membrane_params,
)
