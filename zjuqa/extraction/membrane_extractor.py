"""
membrane_extractor.py —— 膜参数提取（S2 阶段）。

对每个已识别的膜名称，构建多模态消息（文本 + 全部页面图片），
调用多模态 LLM 提取该膜的 21 项参数。

本次修改（对应项目需求 3）：
  提取结果不再覆写 mem_paras.json，而是通过 storage 层以时间戳
  版本化保存，并自动触发多版本均值聚合。

本模块由原 llm_pdf_extractor.py 的 S2 部分迁移而来。

使用说明：
    from zjuqa.extraction.membrane_extractor import extract_and_save
    extract_and_save(Path("./data/mineru_out/Test_1"))
"""

import base64
import json
from datetime import datetime
from pathlib import Path
from typing import List

from langchain_core.messages import HumanMessage, SystemMessage

from ..llm_client.client import get_llm
from ..models.membrane import MembraneData
from ..storage.membrane_repository import (
    save_membrane_params_version,
    aggregate_membrane_params,
)
from . import prompts
from .membrane_identifier import read_membrane_ids
from ..config import MINERU_OUT_DIR, MEMBRANE_DATA_DIR
from pydantic.error_wrappers import ValidationError


# ====================================================================
# 多模态消息构建
# ====================================================================

def build_multimodal_messages(membrane_id: str,text: str,images: List[dict],) -> List:
    """
    构建多模态消息列表：
      - system：膜参数提取指令（含目标膜名）
      - human：论文全文文本 + 所有页面图片（base64）+ 末尾任务强调

    Args:
        membrane_id: 目标膜名称
        text:        论文全文文本
        images:      页面图片列表，每项 {"name": ..., "base64": ...}

    Returns:
        LangChain 消息列表 [SystemMessage, HumanMessage]
    """
    system_content = prompts.mem_extract_template.substitute(membrane_id=membrane_id)

    human_parts = []

    # 1. 文字部分
    human_parts.append({
        "type": "text",
        "text": (
            f"目标膜：{membrane_id}\n"
            f"【论文全文（文字层）】\n{text}\n\n"
            f"【以下为论文各页图片，请结合文字综合判断】\n"
        ),
    })

    # 2. 图片部分（每页一张，按页码顺序）
    for img in images:
        human_parts.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{img['base64']}",
                "detail": "high",  # 高精度模式，保证图表数字可读
            },
        })

    # 3. 末尾再次强调任务
    human_parts.append({
        "type": "text",
        "text": (
            f'\n请严格只提取 "{membrane_id}" 的参数，'
            f"综合文字和图片信息，输出纯 JSON："
        ),
    })

    return [SystemMessage(content=system_content), HumanMessage(content=human_parts)]


# ====================================================================
# 图片加载
# ====================================================================

def load_images(image_dir: Path | str) -> List[dict]:
    """
    读取文件夹下所有 jpg/jpeg 图片，返回 base64 编码的字典列表。

    Args:
        image_dir: 图片文件夹路径

    Returns:    
        [{"name": "demo.jpg", "base64": "xxxx"}, ...]

    Raises:
        NotADirectoryError: 路径不存在或不是文件夹
    """
    image_dir = Path(image_dir)
    if not image_dir.is_dir():
        raise NotADirectoryError(f"路径不存在或不是文件夹：{image_dir}")

    results = []
    suffix_allow = {".jpg", ".jpeg", ".JPG", ".JPEG"}
    for file_path in image_dir.iterdir():
        if not file_path.is_file() or file_path.suffix not in suffix_allow:
            continue
        img_bytes = file_path.read_bytes()
        b64_str = base64.b64encode(img_bytes).decode("utf-8")
        results.append({"name": file_path.name, "base64": b64_str})
    return results

def membrane_paras_refit(raw_text: str) -> str:
    """
    接收无法格式化的LLM参数返回字符串，重新格式化,仍然返回字符串
    """
    llm=get_llm(llm_type="data_fit", max_retries=1)
    mesasage=HumanMessage(content=prompts.refit_prompt_template.substitute(raw_text=raw_text))
    response=llm.invoke(mesasage)
    return response.content

# 单膜参数提取

def get_membrane_params(text: str,img: List[dict],membrane_id: str,) -> MembraneData:
    """
    提取单个膜的参数。
    构建多模态消息 → 调用 LLM → 解析 JSON → 校验为 MembraneData。

    Args:
        text:        论文全文文本
        img:         页面图片列表
        membrane_id: 目标膜名称
    Returns:
        MembraneData 实例
    Raises:
        json.JSONDecodeError: LLM 输出不是合法 JSON 时抛出，
                              原始响应会打印到控制台供排查
    """
    llm = get_llm(llm_type="membrace_get")
    messages = build_multimodal_messages(membrane_id, text, img)
    response = llm.invoke(messages)
    try:
        raw_dict = json.loads(response.content)
        membrane = MembraneData(**raw_dict)
    except (json.JSONDecodeError,ValidationError):
        print("不是合法 JSON或 MembraneData:", response.content)
        print("启动再适配")
        refit_text=membrane_paras_refit(response.content)
        try:
            raw_dict = json.loads(refit_text)
            membrane = MembraneData(**raw_dict)
        except (json.JSONDecodeError,ValidationError):
            print("再适配失败：\n", refit_text)
            raise
    return membrane


# ====================================================================
# 单篇论文全量提取 + 版本化保存
# ====================================================================

def extract_and_save(text_path: Path,meta_path: Path, image_dir: Path,save_dir: Path) -> None:
    """
    对单篇论文执行全量膜参数提取，并以时间戳版本化保存。

    流程：
      1. 读取 meta.json 中的膜名称列表（清除 Unnamed_Membrane）
      2. 读取论文文本与页面图片
      3. 逐膜调用多模态 LLM 提取参数
      4. 调用 save_membrane_params_version 保存本次结果（不覆写）
      5. 调用 aggregate_membrane_params 聚合所有历史版本取均值

    Args:
        text_path: 论文文本文件路径
        meta_path: 论文 meta.json 文件路径
        image_dir: 论文图片文件夹路径
        save_dir: 保存文件夹路径
    """
    paper_name=text_path.stem
    # 读取膜名称（清除占位符）
    membrane_ids = read_membrane_ids(meta_path, mode="c")
    # 跳过空数组
    if len(membrane_ids) == 0:
        print(f"  [提取] {paper_name} 无膜名称，跳过")
        return
    # 读取文本与图片
    text = text_path.read_text(encoding="utf-8")
    img = load_images(image_dir)

    # 逐膜提取
    mem_paras: List[MembraneData] = []
    for membrane_id in membrane_ids:
        print(f"[{datetime.now()}][提取] 正在提取: {paper_name} | {membrane_id}")
        mem_paras.append(get_membrane_params(text, img, membrane_id))

    # ★ 需求 3：版本化保存（不覆写）+ 自动聚合均值
    save_membrane_params_version(save_dir, mem_paras)
    aggregate_membrane_params(save_dir)

    print(f"已完成 {text_path.name} 膜参数提取")

# ====================================================================
# 命令行测试入口
# ====================================================================

if __name__ == "__main__":
    # 快速测试：对 Test_1 执行提取
    for i in range(5):
        num=i+6
        extract_and_save(MINERU_OUT_DIR/f"Test_{num}"/"auto"/f"Test_{num}.md",MINERU_OUT_DIR/f"Test_{num}"/"auto"/"meta.json",MINERU_OUT_DIR/f"Test_{num}"/"auto"/"images",MEMBRANE_DATA_DIR/f"Test_{num}")
