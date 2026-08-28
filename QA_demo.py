"""
qa_demo.py —— 极简科研问答 Demo

基于已提取的膜参数 CSV 数据集，用 LLM 回答科研问题。
这是 M3 知识库问答接口的极简原型：将表格数据直接注入 prompt，LLM 基于数据回答。

使用前准备：
  1. 完成膜参数提取（python main.py all）
  2. 导出 CSV 数据集：
     from zjuqa.data_processing import build_dataframe, export_csv
     df = build_dataframe()
     export_csv(df, "membrane_dataset.csv")
  3. 配置 api_keys.py（API_KEY, BASE_URL）

运行：
  python qa_demo.py
  python qa_demo.py "哪种膜的纯水通量最高？"
  python qa_demo.py --csv membrane_dataset.csv "PES 支撑层的膜有哪些？"
  ctrl+c 退出
"""

import argparse
import sys
from pathlib import Path

import pandas as pd
from langchain_core.messages import HumanMessage, SystemMessage

from zjuqa.llm_client import get_llm


# ====================================================================
# 配置
# ====================================================================

DEFAULT_CSV = "data/membrane_dataset.csv"

# System Prompt：设定角色与回答规则
SYSTEM_PROMPT = """你是一个化工膜领域的科研助手，基于用户提供的膜参数数据集回答问题。

回答规则：
1. 只基于提供的表格数据回答，不要编造数据中不存在的信息
2. 引用数据时注明来源（论文名称 / 膜名称）
3. 如果数据中没有相关信息，如实说明"数据集中未找到相关信息"
4. 涉及数值比较时，列出具体数值和单位
5. 回答简洁准确，优先用表格或列表呈现对比信息
6. 注意：pure_water_flux 是通量（单位 LMH），pure_water_permeance 是比通量（单位 LMH/bar），两者是不同物理量，不要混淆
"""


# ====================================================================
# 核心函数
# ====================================================================

def load_csv_data(csv_path: str, max_rows: int = 100) -> str:
    """
    读取 CSV 文件并转换为 Markdown 表格字符串，注入 LLM prompt。

    Args:
        csv_path: CSV 文件路径
        max_rows: 最大读取行数（防止超出 token 限制）

    Returns:
        Markdown 格式的表格字符串
    """
    path = Path(csv_path)
    if not path.exists():
        print(f"[错误] CSV 文件不存在: {path.resolve()}")
        print(f"请先运行数据导出：")
        print(f"  from zjuqa.data_processing import build_dataframe, export_csv")
        print(f"  df = build_dataframe()")
        print(f'  export_csv(df, "{csv_path}")')
        sys.exit(1)

    df = pd.read_csv(path)
    print(f"[加载] 数据集: {len(df)} 行 × {len(df.columns)} 列")

    if len(df) > max_rows:
        print(f"[警告] 数据超过 {max_rows} 行，仅使用前 {max_rows} 行（可通过 --max-rows 调整）")
        df = df.head(max_rows)

    # 转为 Markdown 表格（NaN 显示为空）
    md_table = df.to_markdown(index=False)#, na_rep="—"
    return md_table


def ask_question(question: str, csv_data: str, llm=None) -> str:
    """
    基于 CSV 数据向 LLM 提问。

    Args:
        question: 用户问题
        csv_data: Markdown 格式的表格数据
        llm: LLM 客户端实例（None 则自动创建）

    Returns:
        LLM 回答文本
    """
    if llm is None:
        llm = get_llm(llm_type="QA", temperature=0.3)

    # 构建消息：System（角色规则）+ Human（数据 + 问题）
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"以下是膜参数数据集：\n\n{csv_data}\n\n"
                            f"请基于以上数据回答问题：{question}"),
    ]

    print(f"[提问] {question}")
    print("[思考中...]")
    response = llm.invoke(messages)
    return response.content


# ====================================================================
# 交互模式
# ====================================================================

def interactive_mode(csv_data: str):
    """交互式问答：循环接收用户输入，直到输入 exit/quit。"""
    llm = get_llm(llm_type="QA", temperature=0.3)

    print("\n" + "=" * 60)
    print("  化工膜科研问答 Demo（输入 exit 退出）")
    print("=" * 60)
    print("示例问题：")
    print("  - 哪种膜的比通量最高？数值是多少？")
    print("  - PES 支撑层的膜有哪些？")
    print("  - 对比 TFC-l-A 和 TFC-s-O 的各项参数")
    print("  - 截留率数据中最常见的测试物质是什么？")
    print()

    while True:
        try:
            question = input("\n请输入问题 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not question:
            continue
        if question.lower() in ("exit", "quit", "q"):
            print("再见！")
            break

        try:
            answer = ask_question(question, csv_data, llm=llm)
            print(f"\n[回答]\n{answer}\n")
        except Exception as e:
            print(f"\n[错误] LLM 调用失败: {e}\n")


# ====================================================================
# 入口
# ====================================================================

def main():
    parser = argparse.ArgumentParser(description="化工膜科研问答 Demo")
    parser.add_argument("question", nargs="?", help="单次提问的问题（不指定则进入交互模式）")
    parser.add_argument("--csv", default=DEFAULT_CSV, help=f"CSV 数据集路径（默认: {DEFAULT_CSV}）")
    parser.add_argument("--max-rows", type=int, default=100, help="最大读取行数（默认: 100）")
    args = parser.parse_args()

    # 加载数据
    csv_data = load_csv_data(args.csv, max_rows=args.max_rows)

    if args.question:
        # 单次提问模式
        answer = ask_question(args.question, csv_data)
        print(f"\n[回答]\n{answer}")
    else:
        # 交互模式
        interactive_mode(csv_data)


if __name__ == "__main__":
    main()
