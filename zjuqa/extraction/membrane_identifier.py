"""
membrane_identifier.py —— 膜名称识别（S1 阶段）。

调用纯文本 LLM 从论文全文中识别所有 TFC 膜的名称，
结果写入论文目录下的 meta.json。

本模块由原 llm_pdf_extractor.py 的 S1 部分迁移而来，
修复了原函数名的拼写错误（mambrane→membrane, menbrane→membrane, infm→info），
功能逻辑保持不变。

使用说明：
    from zjuqa.extraction.membrane_identifier import (
        identify_membranes, set_membrane_ids, read_membrane_ids,
    )
    membranes = identify_membranes(paper_text)
    set_membrane_ids([dir1, dir2], [text1, text2], mode="n")
"""

import json
from pathlib import Path
from typing import List

from langchain_core.prompts import ChatPromptTemplate

from ..llm_client.client import get_llm
from . import prompts
from ..config import MINERU_OUT_DIR


# ====================================================================
#region meta.json读写工具
# ====================================================================

def read_membrane_ids(file_path: Path, mode: str = "a") -> List[str]:
    """
    从 meta.json 读取膜名称列表。

    Args:
        file_path: meta.json 文件路径
        mode:      "c" (clear) 清除 "Unnamed_Membrane"；其他模式保留全部

    Returns:
        膜名称列表
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if mode == "c":
        # 清除占位符 "Unnamed_Membrane"
        membranes = [m for m in data["membrane_ids"] if m != "Unnamed_Membrane"]
    else:
        membranes = data["membrane_ids"]
    return membranes


def set_meta_info(dir_path: Path) -> bool:
    """
    检测目标文件夹下有无 meta.json，无则新建并写入默认空值。

    Args:
        dir_path: 论文 auto/ 目录路径

    Returns:
        True 表示文件已存在；False 表示新建
    """
    meta_path = dir_path / "meta.json"
    if meta_path.exists():
        return True
    meta = {
        "article_Title": None,
        "article_Author": None,
        "article_Year": None,
        "membrane_ids": [],
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=4, ensure_ascii=False)
    return False


def is_membrane_ids_got(dir_path: Path) -> bool:
    """
    检测 meta.json 是否已写入非空的 membrane_ids。

    Args:
        dir_path: 论文 auto/ 目录路径

    Returns:
        True 表示已有膜名称；False 表示无或为空
    """
    if set_meta_info(dir_path):
        with open(dir_path / "meta.json", "r", encoding="utf-8") as f:
            meta = json.load(f)
        if meta["membrane_ids"]:
            return True
    return False


# ====================================================================
# LLM 膜名称识别
# ====================================================================

def identify_membranes(text: str, text_len: int = 12000) -> List[str]:
    """
    调用纯文本 LLM 识别论文中所有膜名称。

    膜名通常出现在 Experimental 节前半段，默认截断前 12000 字符。
    注意：截断可能降低识别率，增量模式下传入 -1 可取消截断。

    Args:
        text:     论文全文文本
        text_len: 截断字符数，-1 表示不截断

    Returns:
        识别到的膜名称列表
    """
    llm = get_llm()
    # text_len=-1 时不截断
    truncated = text[:text_len] if text_len > 0 else text

    prompt = ChatPromptTemplate.from_messages([
        ("system", prompts.IDENTIFY_SYSTEM),
        ("human", "论文文本如下：\n\n{text}\n\n请输出所有膜名称（逗号分隔）："),
    ])
    chain = prompt | llm
    response = chain.invoke({"text": truncated})
    raw = response.content.strip()
    membranes = [m.strip() for m in raw.split(",") if m.strip()]
    print(f"识别到 {len(membranes)} 种膜: {membranes}")
    return membranes


# ====================================================================
# 批量膜名称写入
# ====================================================================

def set_membrane_ids(dir_path_list: List[Path],text_path_list: List[Path],mode: str = "n",) -> None:
    """
    批量为多篇论文识别并写入膜名称到 meta.json。

    Args:
        dir_path_list:  论文 auto/ 目录列表
        text_path_list: 对应论文的文本文件路径列表（与 dir_path_list 一一对应）
        mode:
            "n" (normal)：跳过已有膜名称的论文，只处理空的
            "a" (append)：增量模式，所有论文重新识别，与已有结果取并集
            "c" (clear)：清除已有膜名称，重新识别

    注意：mode="a" 下传入 text_len=-1 取消文本截断，以提高识别率。
    """
    # 先确保所有目录都有 meta.json
    for dir_path in dir_path_list:
        set_meta_info(dir_path)

    if mode == "a":
        # 增量模式：全部重新识别，取并集
        for dir_path, text_path in zip(dir_path_list, text_path_list):
            with open(text_path, "r", encoding="utf-8") as f:
                text = f.read()
            membranes = identify_membranes(text, text_len=-1)
            with open(dir_path / "meta.json", "r", encoding="utf-8") as f:
                meta = json.load(f)
            print(f"检测前膜名称：{meta['membrane_ids']}")
            #print(f"新检测膜名称：{membranes}")
            meta["membrane_ids"] = list(set(meta["membrane_ids"] + membranes))
            with open(dir_path / "meta.json", "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=4, ensure_ascii=False)
    elif mode=="c":
        # 清除已有膜名称，重新识别
        for dir_path, text_path in zip(dir_path_list, text_path_list):
            with open(text_path, "r", encoding="utf-8") as f:
                text = f.read()
            membranes = identify_membranes(text, text_len=-1)
            with open(dir_path / "meta.json", "r", encoding="utf-8") as f:
                meta = json.load(f)
            print(f"检测前膜名称：{meta['membrane_ids']}")
            #print(f"重新检测膜名称：{membranes}")
            meta["membrane_ids"] = membranes
            with open(dir_path / "meta.json", "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=4, ensure_ascii=False)

    elif mode == "n":
        # 正常模式：只处理尚无膜名称的论文
        for dir_path, text_path in zip(dir_path_list, text_path_list):
            if not is_membrane_ids_got(dir_path):
                with open(text_path, "r", encoding="utf-8") as f:
                    text = f.read()
                membranes = identify_membranes(text, text_len=-1)
                with open(dir_path / "meta.json", "r", encoding="utf-8") as f:
                    meta = json.load(f)
                meta["membrane_ids"] = membranes
                with open(dir_path / "meta.json", "w", encoding="utf-8") as f:
                    json.dump(meta, f, indent=4, ensure_ascii=False)
    else:
        print("set_membrane_ids不支持的模式:", mode)


def clean_meta_json(dir_path_list: List[Path]) -> None:
    """
    删除目标文件夹列表下的全部 meta.json 文件。

    Args:
        dir_path_list: 论文 auto/ 目录列表
    """
    for dir_path in dir_path_list:
        meta_path = dir_path / "meta.json"
        if meta_path.exists():
            meta_path.unlink()
            print("已删除", meta_path)

if __name__=="__main__":
    dir_path_list=[MINERU_OUT_DIR /f"Test_{i+1}"/"auto" for i in range(10)]
    text_path_list=[dir_path_list[i]/f"Test_{i+1}.md" for i in range(10)]
    set_membrane_ids(dir_path_list, text_path_list, mode="c")



