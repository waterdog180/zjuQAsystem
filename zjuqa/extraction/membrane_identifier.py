"""
membrane_identifier.py —— 膜名称识别（S1 阶段）。

调用纯文本 LLM 从论文全文中识别所有 TFC 膜的名称，
结果保存到 data/identified/<paper_name>/meta.json。

使用说明：
    from zjuqa.extraction.membrane_identifier import identify_paper, identify_all
    # 单篇识别
    identify_paper("Test_1")
    # 批量识别（自动扫描 data/parsed/，跳过已完成的）
    identify_all(mode="skip")
"""

from typing import List, Optional

from langchain_core.prompts import ChatPromptTemplate

from ..llm_client.client import get_llm
from ..utils.io import ensure_json_file, load_json_safe, save_json
from ..utils.logging import get_logger
from ..utils.path_utils import get_meta_path, get_parsed_text
from ..utils.progress import ProgressBar
from ..utils.scanner import scan_identified_papers, scan_parsed_papers
from . import prompts

logger = get_logger(__name__)


# ====================================================================
# meta.json 读写工具
# ====================================================================

DEFAULT_META = {
    "article_Title": None,
    "article_Author": None,
    "article_Year": None,
    "membrane_ids": [],
}


def read_membrane_ids(paper_name: str, mode: str = "a") -> List[str]:
    """
    从 meta.json 读取膜名称列表。

    Args:
        paper_name: 论文名称
        mode:       "c" (clear) 清除 "Unnamed_Membrane"；其他模式保留全部

    Returns:
        膜名称列表，meta.json 不存在时返回空列表
    """
    data = load_json_safe(get_meta_path(paper_name), default={"membrane_ids": []})
    if mode == "c":
        return [m for m in data.get("membrane_ids", []) if m != "Unnamed_Membrane"]
    return data.get("membrane_ids", [])


def is_membrane_ids_got(paper_name: str) -> bool:
    """
    检测某篇论文是否已写入非空的 membrane_ids。

    Args:
        paper_name: 论文名称

    Returns:
        True 表示已有膜名称；False 表示无或为空
    """
    data = load_json_safe(get_meta_path(paper_name), default=None)
    if data is None:
        return False
    return bool(data.get("membrane_ids"))


# ====================================================================
# LLM 膜名识别
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
    llm = get_llm(llm_type="identify")
    truncated = text[:text_len] if text_len > 0 else text
    prompt = ChatPromptTemplate.from_messages([
        ("system", prompts.IDENTIFY_SYSTEM),
        ("human", "论文文本如下：\n\n{text}\n\n请输出所有膜名称（逗号分隔）："),
    ])
    chain = prompt | llm
    try:
        response = chain.invoke({"text": truncated})
    except Exception as e:
        logger.error(f"识别调用失败: {e}", exc_info=True)
        return []
    raw = response.content.strip()
    membranes = [m.strip() for m in raw.split(",") if m.strip()]
    logger.info(f"识别到 {len(membranes)} 种膜: {membranes}")
    return membranes


# ====================================================================
# 单篇 / 批量处理
# ====================================================================

def identify_paper(
    paper_name: str,
    mode: str = "n",
    text_len: int = -1,
) -> Optional[List[str]]:
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
        logger.warning(f"跳过 {paper_name}: 解析文本不存在 ({text_path})")
        return None

    # mode="n"：已有则跳过
    if mode == "n" and is_membrane_ids_got(paper_name):
        logger.info(f"跳过 {paper_name}: 已有膜名称")
        return read_membrane_ids(paper_name)

    with open(text_path, "r", encoding="utf-8") as f:
        text = f.read()

    membranes = identify_membranes(text, text_len=text_len)
    meta = ensure_json_file(get_meta_path(paper_name), default=DEFAULT_META)

    if mode == "a":
        # 增量：取并集
        logger.info(f"{paper_name} 增量合并: 旧={meta['membrane_ids']} + 新={membranes}")
        meta["membrane_ids"] = list(set(meta["membrane_ids"] + membranes))
    else:
        # n(无旧值时) / c / f：覆盖
        meta["membrane_ids"] = membranes

    save_json(get_meta_path(paper_name), meta)
    logger.info(f"{paper_name} 完成，共 {len(meta['membrane_ids'])} 种膜")
    return meta["membrane_ids"]


def identify_all(
    mode: str = "skip",
    papers: Optional[List[str]] = None,
) -> dict:
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
    # 自动扫描
    if papers is None:
        papers = scan_parsed_papers()

    if not papers:
        print("[识别] 未找到已解析的论文，请先运行 MinerU 解析")
        return {"total": 0, "processed": 0, "skipped": 0}

    print(f"[识别] 发现 {len(papers)} 篇已解析论文，mode={mode}")

    processed = 0
    skipped = 0
    internal_mode = {"skip": "n", "force": "f", "append": "a"}.get(mode, "n")

    with ProgressBar(total=len(papers), prefix="识别") as bar:
        for i, paper_name in enumerate(papers, start=1):
            bar.update(i, item=paper_name, action="识别膜名称")

            if mode == "skip" and is_membrane_ids_got(paper_name):
                logger.info(f"跳过 {paper_name}（已识别）")
                skipped += 1
                continue

            result = identify_paper(paper_name, mode=internal_mode)
            if result is not None:
                processed += 1
            else:
                skipped += 1

    stats = {"total": len(papers), "processed": processed, "skipped": skipped}
    print(f"[识别] 完成: 总计 {stats['total']}, 处理 {stats['processed']}, 跳过 {stats['skipped']}")
    logger.info(f"批量识别完成: {stats}")
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
            logger.info(f"已删除 {meta_path}")


# ====================================================================
# 命令行入口
# ====================================================================

if __name__ == "__main__":
    # 默认批量识别所有已解析论文，跳过已完成的
    identify_all(mode="skip")
