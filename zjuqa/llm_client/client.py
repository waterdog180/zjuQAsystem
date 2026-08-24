"""
client.py —— LLM 客户端封装。

通过 LangChain 的 ChatOpenAI 兼容接口调用智谱 GLM 多模态模型。
配置参数（模型名、API Key、base_url）来自 zjuqa.config.llm_config。

使用说明：
    from zjuqa.llm_client.client import get_llm
    llm = get_llm(temperature=0.1)
    response = llm.invoke("你好")
    print(response.content)
"""

from langchain_openai import ChatOpenAI
from ..config.llm_config import LLMParas


def get_llm(
    llm_type: str = "normal",
    temperature: float = 0.1,
    max_retries: int = 3,
) -> ChatOpenAI:
    """
    创建并返回一个 ChatOpenAI 客户端实例。

    Args:
        llm_type:    预留参数，用于未来区分不同用途的模型配置
                     （如 normal / membrane_get），当前暂未使用。
        temperature: 生成温度，越低越确定。提取任务建议 0.1。
        max_retries: 最大重试次数。

    Returns:
        配置好的 ChatOpenAI 实例，可直接 .invoke() 调用。
    """
    return ChatOpenAI(
        model="glm-4.6v",  # LLMParas.model_name,
        openai_api_key=LLMParas.api_key,
        openai_api_base=LLMParas.base_url,
        temperature=temperature,
        top_p=0.8,
        timeout=180.0,
        max_retries=max_retries,
    )


if __name__ == "__main__":
    # 快速连通性测试
    llm = get_llm(temperature=0, max_retries=1)
    TEST_PROMPT = (
        "请回答你现在用的是什么模型？"
        "请具体到你的详细版本号与输入输出模态。"
    )
    response = llm.invoke(TEST_PROMPT)
    print(response.content)
