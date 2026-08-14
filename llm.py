from paras import LLMParas
from langchain_openai import ChatOpenAI

def get_llm( temperature: float = 0.1,max_retries: int = 3) -> ChatOpenAI:
    return ChatOpenAI(
        model="glm-4.6v",#LLMParas.model_name,
        openai_api_key=LLMParas.api_key,
        openai_api_base=LLMParas.base_url,
        temperature=temperature,
        top_p=0.8,
        timeout=180.0,
        max_retries=max_retries,
    )

if __name__=="__main__":
    llm=get_llm(temperature=0,max_retries=1)
    TEST_PROMPT="请回答你现在用的是什么模型？请具体到你的详细版本号与输入输出模态。"
    response=llm.invoke(TEST_PROMPT)
    print(response.content)