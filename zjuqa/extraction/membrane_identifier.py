"""
membrane_identifier.py —— 膜名称识别（S1 阶段）。

调用纯文本 LLM 从论文全文中识别所有 TFC 膜的名称，
结果保存到 data/identified/<paper_name>/meta.json。

本次修改：
  - 适配新的阶段化数据目录（data/identified/）
  - 新增单篇处理函数 identify_paper()
  - 新增批量自动扫描函数 identify_all()，脱离 Test_X 依赖
  - 支持 mode 开关控制是否跳过已识别的论文

使用说明：
    from zjuqa.extraction.membrane_identifier import identify_paper, identify_all
    # 单篇识别
    identify_paper("Test_1")
    # 批量识别（自动扫描 data/parsed/，跳过已完成的）
    identify_all(mode="skip")
"""

import json
from pathlib import Path
from typing import List, Optional

from langchain_core.prompts import ChatPromptTemplate

from ..config.paths import (
    get_meta_path,
    get_parsed_text,
    scan_identified_papers,
    scan_parsed_papers,
)
from ..llm_client.client import get_llm
from . import prompts


# ====================================================================
# meta.json 读写工具
# ====================================================================

def read_membrane_ids(paper_name: str, mode: str = "a") -> List[str]:
    """
    从 meta.json 读取膜名称列表。

    Args:
        paper_name: 论文名称
        mode:       "c" (clear) 清除 "Unnamed_Membrane"；其他模式保留全部

    Returns:
        膜名称列表，meta.json 不存在时返回空列表
    """
    meta_path = get_meta_path(paper_name)
    if not meta_path.exists():
        return []
    with open(meta_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if mode == "c":
        return [m for m in data["membrane_ids"] if m != "Unnamed_Membrane"]
    return data["membrane_ids"]


def _ensure_meta(paper_name: str) -> dict:
    """确保 meta.json 存在，返回其内容。不存在则创建默认空结构。"""
    meta_path = get_meta_path(paper_name)
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    if meta_path.exists():
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)
    meta = {
        "article_Title": None,
        "article_Author": None,
        "article_Year": None,
        "membrane_ids": [],
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=4, ensure_ascii=False)
    return meta


def _write_meta(paper_name: str, meta: dict) -> None:
    """写入 meta.json。"""
    meta_path = get_meta_path(paper_name)
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=4, ensure_ascii=False)


def is_membrane_ids_got(paper_name: str) -> bool:
    """
    检测某篇论文是否已写入非空的 membrane_ids。

    Args:
        paper_name: 论文名称

    Returns:
        True 表示已有膜名称；False 表示无或为空
    """
    meta_path = get_meta_path(paper_name)
    if not meta_path.exists():
        return False
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    return bool(meta.get("membrane_ids"))


# ====================================================================
# LLM 膜名称识别
# ====================================================================

def identify_membranes(text: str, text_len: int = 12000) -> List[str]:
    """
    调用纯文本 LLM 识别论文中所有膜名称。

    膜名通常出现在 Experimental 节前半段，默认截断前 12000 字符。
    text_len=-1 时不截断。

    Args:
        text:     论文全文文本
        text_len: 截断字符数，-1 表示不截断

    Returns:
        识别到的膜名称列表
    """
    llm = get_llm()
    truncated = text[:text_len] if text_len > 0 else text

    prompt = ChatPromptTemplate.from_messages([
        ("system", prompts.IDENTIFY_SYSTEM),
        ("human", "论文文本如下：\n\n{text}\n\n请输出所有膜名称（逗号分隔）："),
    ])
    chain = prompt | llm
    response = chain.invoke({"text": truncated})
    raw = response.content.strip()
    membranes = [m.strip() for m in raw.split(",") if m.strip()]
    print(f"  [识别] 识别到 {len(membranes)} 种膜: {membranes}")
    return membranes


# ====================================================================
# 单篇 / 批量处理（需求3：自动扫描 + 需求4：mode 开关）
# ====================================================================

def identify_paper(paper_name: str,mode: str = "n",text_len: int = -1) -> Optional[List[str]]:
    """
    对单篇论文执行膜名称识别。

    Args:
        paper_name: 论文名称（对应 data/parsed/ 下的子目录名）
        mode:
            "n" (normal)：已有膜名称则跳过，无则识别
            "a" (append)：增量模式，重新识别后与已有结果取并集
            "c" (clear)：清除已有结果，重新识别
            "f" (force)：强制覆盖，重新识别
        text_len: LLM 文本截断长度，-1 表示不截断

    Returns:
        膜名称列表；论文文本不存在或跳过时返回 None
    """
    text_path = get_parsed_text(paper_name)
    if not text_path.exists():
        print(f"  [识别] 跳过 {paper_name}: 解析文本不存在 ({text_path})")
        return None

    # mode="n"：已有则跳过
    if mode == "n" and is_membrane_ids_got(paper_name):
        print(f"  [识别] 跳过 {paper_name}: 已有膜名称")
        return read_membrane_ids(paper_name)

    # 读取文本
    with open(text_path, "r", encoding="utf-8") as f:
        text = f.read()

    # 调用 LLM 识别
    membranes = identify_membranes(text, text_len=text_len)

    # 写入 meta.json
    meta = _ensure_meta(paper_name)

    if mode == "a":
        # 增量：取并集
        print(f"  [识别] {paper_name} 增量合并: 旧={meta['membrane_ids']} + 新={membranes}")
        meta["membrane_ids"] = list(set(meta["membrane_ids"] + membranes))
    else:
        # n(无旧值时) / c / f：覆盖
        meta["membrane_ids"] = membranes

    _write_meta(paper_name, meta)
    print(f"  [识别] {paper_name} 完成，共 {len(meta['membrane_ids'])} 种膜")
    return meta["membrane_ids"]


def identify_all(mode: str = "skip",papers: Optional[List[str]] = None) -> dict:
    """
    批量识别所有论文的膜名称。

    Args:
        mode:
            "skip" ：跳过已识别的论文（默认，避免重复计算）
            "force"：全部重新识别，覆盖已有结果
            "append"：全部重新识别，与已有结果取并集
        papers: 指定论文名列表，None 时自动扫描 data/parsed/

    Returns:
        统计字典 {"total": 总数, "processed": 处理数, "skipped": 跳过数}
    """
    # 自动扫描（需求3：脱离 Test_X 依赖）
    if papers is None:
        papers = scan_parsed_papers()

    if not papers:
        print("[识别] 未找到已解析的论文，请先运行 MinerU 解析")
        return {"total": 0, "processed": 0, "skipped": 0}

    print(f"[识别] 发现 {len(papers)} 篇已解析论文，mode={mode}")

    processed = 0
    skipped = 0
    internal_mode = {"skip": "n", "force": "f", "append": "a"}.get(mode, "n")

    for paper_name in papers:
        if mode == "skip" and is_membrane_ids_got(paper_name):
            print(f"[识别] 跳过 {paper_name}（已识别）")
            skipped += 1
            continue
        result = identify_paper(paper_name, mode=internal_mode)
        if result is not None:
            processed += 1
        else:
            skipped += 1

    stats = {"total": len(papers), "processed": processed, "skipped": skipped}
    print(f"[识别] 完成: 总计 {stats['total']}, 处理 {stats['processed']}, 跳过 {stats['skipped']}")
    return stats


def clean_meta_json(paper_names: List[str]) -> None:
    """
    删除指定论文的 meta.json 文件。

    Args:
        paper_names: 论文名称列表
    """
    for paper_name in paper_names:
        meta_path = get_meta_path(paper_name)
        if meta_path.exists():
            meta_path.unlink()
            print(f"已删除 {meta_path}")


# ====================================================================
# 命令行入口
# ====================================================================

if __name__ == "__main__":
    # 默认批量识别所有已解析论文，跳过已完成的
    identify_all(mode="skip")
