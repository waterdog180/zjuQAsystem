"""
llm_config.py —— LLM 调用配置。

API 密钥从 api_keys.py 读取（该文件已加入 .gitignore，不提交到仓库）。
首次使用请复制 api_key_example.py 为 api_keys.py 并填入个人密钥。

使用说明：
    from zjuqa.config.llm_config import LLMParas
    print(LLMParas.model_name, LLMParas.base_url)
"""

import api_keys


class LLMParas:
    """
    LLM 调用参数集中管理。

    Attributes:
        model_name: 使用的模型名称（如 glm-4.6v-flash）。
        base_url:   API 端点地址。
        api_key:    API 密钥，从 api_keys.GLM_KEY 读取。
    """
    model_name = "glm-4.6v"
    """模型名称。"""

    base_url = "https://open.bigmodel.cn/api/paas/v4/"
    """智谱 API 兼容 OpenAI 格式的端点。"""

    api_key = api_keys.GLM_KEY
    """API 密钥（来自 api_keys.py）。"""
