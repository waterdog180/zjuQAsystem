#llm_pdf_extractor.py
#调用llm引擎对预处理pdf数据进行膜参数识别：遍历文件获得膜名称；文件中遍历膜名称得到膜参数。
#数据分步骤
from llm import get_llm
from pydantic import BaseModel, Field
from typing import List, Optional, Union
from paras import *
import prompts
from langchain_core.prompts import ChatPromptTemplate
import json
from pathlib import Path
import base64

#region S1识别膜名称

def identify_membranes(text: str,text_len:int=12000) -> List[str]:
    """
    调用纯文本 LLM 识别所有膜名称。
    传入论文文本，返回膜名称列表
    """
    llm = get_llm()
    truncated = text[:text_len]   # 膜名通常在 Experimental 节前半段
    #region!此处text_len的截断有待商榷，截取12000字符识别率大幅下降，建议传入-1取消截断
    prompt = ChatPromptTemplate.from_messages([
        ("system", prompts.IDENTIFY_SYSTEM),
        ("human", "论文文本如下：\n\n{text}\n\n请输出所有膜名称（逗号分隔）："),
    ])
    chain = prompt | llm
    response = chain.invoke({"text": truncated})
    raw = response.content.strip()
    membranes = [m.strip() for m in raw.split(",") if m.strip()]
    print(f"  [Step2] 识别到 {len(membranes)} 种膜: {membranes}")
    return membranes

def set_meta_infm(dir_path):
    "检测目标文件夹下有无文件meta.json，无则新建，并写入None；有则返回True，新建返回False"
    meta_path = dir_path / "meta.json"
    if meta_path.exists():
        return True
    meta={
        "article_Title":None,
        "article_Author":None,
        "article_Year":None,
        "membrane_names":[]
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=4, ensure_ascii=False)
    return False

def is_membrane_names_got(dir_path):
    "检测目标文件夹下meta.json是否已写入membrane_names；数组非空则返回True，无则返回False"
    if set_meta_infm(dir_path):
        #读取meta.json
        with open(dir_path / "meta.json", "r", encoding="utf-8") as f:
            meta = json.load(f)
        if meta["membrane_names"]:#检测meta["membrane_names"]是否为空数组
            return True
    return False

def set_menbrane_names(dir_path_list,text_path_list,mode="n"):
    for dir_path in dir_path_list:
        set_meta_infm(dir_path)
    """传入目标文件夹列表，检测每个文件夹下meta.json是否已写入membrane_names，对没写入的文件夹根据传入的文本地址列表，读取对应文本文件，调用identify_membranes，写入membrane_names"
    "新增mode参数：输入n时不重复检测，只要membrane_names不为空就跳过；输入a时使用增量方法，所有文件都检测，写入检测前与新检测的膜名称并集，并在控制台打印检测前与新检测的膜名称差异"""
    if mode=="a":
        for dir_path,text_path in zip(dir_path_list,text_path_list):
            #print(f"检测文件夹：{dir_path}")
            with open(text_path, "r", encoding="utf-8") as f:
                text = f.read()
            membranes = identify_membranes(text,text_len=-1)#"a"模式下传入-1取消文本截断
            with open(dir_path / "meta.json", "r", encoding="utf-8") as f:
                meta = json.load(f)
            print(f"检测前膜名称：{meta['membrane_names']}")
            print(f"新检测膜名称：{membranes}")
            meta["membrane_names"] = list(set(meta["membrane_names"] + membranes))
            with open(dir_path / "meta.json", "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=4, ensure_ascii=False)
    elif mode=="n":
        for dir_path,text_path in zip(dir_path_list,text_path_list):
            if not is_membrane_names_got(dir_path):
                with open(text_path, "r", encoding="utf-8") as f:
                    text = f.read()
                membranes = identify_membranes(text)
                meta_path = dir_path / "meta.json"
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                meta["membrane_names"] = membranes
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(meta, f, indent=4, ensure_ascii=False)


def _clean_meta_json(dir_path_list):
    "传入目标文件夹列表，删除全部meta.json文件"
    for dir_path in dir_path_list:
        meta_path = dir_path / "meta.json"
        if meta_path.exists():
            meta_path.unlink()
            print("已删除",meta_path)


#region S2:识别膜参数
def build_multimodal_messages(membrane_id: str,text: str,images: List[dict]) -> List:
    """
    构建多模态消息列表：
    - system：提取指令
    - human：文本内容 + 所有页面图片（base64）
    """
    system_content = prompts.mem_extract_template.substitute(membrane_id=membrane_id)
    human_parts = []# --- 构建 human 消息的 content（多模态列表）---
    # 1. 文字部分
    human_parts.append({
        "type": "text",
        "text": f"目标膜：{membrane_id}\n\n【论文全文（文字层）】\n{text}\n\n【以下为论文各页图片，请结合文字综合判断】\n"
    })
    # 2. 图片部分（每页一张，按页码顺序）
    for img in images:
        human_parts.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{img['base64']}",
                "detail": "high",   # 高精度模式，保证图表数字可读
            }
        })
    # 3. 末尾再次强调任务
    human_parts.append({
        "type": "text",
        "text": f"\n请严格只提取 \"{membrane_id}\" 的参数，综合文字和图片信息，输出纯 JSON："
    })
    return [SystemMessage(content=system_content),HumanMessage(content=human_parts)]


def load_images_to_base64(image_dir: Path | str) -> List[dict]:
    """
    读取文件夹下所有jpg/jpeg图片，返回字典列表
    :param image_dir: 图片文件夹路径
    :return:
    [
        {"name": "demo.jpg", "base64": "xxxx"},
        {"name": "photo.jpeg", "base64": "xxxx"},
        ...
    ]
    """
    image_dir = Path(image_dir)
    if not image_dir.is_dir():
        raise NotADirectoryError(f"路径不存在或不是文件夹：{image_dir}")
    results = []
    suffix_allow = {".jpg", ".jpeg", ".JPG", ".JPEG"}
    for file_path in image_dir.iterdir():
        # 跳过文件夹，筛选后缀
        if not file_path.is_file():
            continue
        if file_path.suffix not in suffix_allow:
            continue
        with open(file_path, "rb") as f:# 读取二进制并编码base64
            img_bytes = f.read()
            b64_str = base64.b64encode(img_bytes).decode("utf-8")
        results.append({"name": file_path.name,"base64": b64_str})
    return results


def get_mem_paras():
    pass



if __name__ == "__main__" and False:
    with open("./mineru_out/Test_1/auto/Test_1.md", "r", encoding="utf-8") as f:
        text = f.read()
    membranes = identify_membranes(text)
    print(membranes)


if __name__=="__main__" and False:
    _dir_list=[Path(f"./mineru_out/Test_{i}/auto") for i in range(1,11)]
    _text_list=[Path(f"./mineru_out/Test_{i}/auto/Test_{i}.md") for i in range(1,11)]
    _clean_meta_json(_dir_list)
    set_menbrane_names(_dir_list,_text_list,mode="a")
