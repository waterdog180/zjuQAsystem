"""
mineru_parser.py —— 基于 MinerU 的 PDF 预处理。

使用 MinerU 3.4 的机器学习 pipeline 对 PDF 进行结构化解析，
输出 Markdown 全文 + 页面图片，供后续 LLM 提取使用。

依赖：mineru==3.4.x（要求 Python 3.11）
性能：纯 CPU pipeline 单 PDF 处理 3~10 分钟，GPU 可加速。

本模块由原 MinerUpdf.py 迁移而来，功能逻辑保持不变。

使用说明：
    import asyncio
    from pathlib import Path
    from zjuqa.pdf_processing.mineru_parser import parse_single_pdf
    asyncio.run(parse_single_pdf(Path("./data/raw_pdfs/Test_1.pdf")))
"""

import asyncio
from datetime import datetime
from pathlib import Path

# MinerU 3.4：两个函数都在 mineru.cli.common 下
from mineru.cli.common import aio_do_parse, read_fn

from ..config.paths import MINERU_OUT_DIR


def get_raw_pdf_list(raw_pdf_dir: str) -> list[str]:
    """
    获取指定目录下所有 PDF 文件名列表。

    Args:
        raw_pdf_dir: 原始 PDF 目录路径

    Returns:
        PDF 文件名列表（仅文件名，不含路径）
    """
    pdf_list = []
    raw_dir = Path(raw_pdf_dir)
    for file in raw_dir.iterdir():
        if file.is_file() and file.suffix.lower() == ".pdf":
            pdf_list.append(file.name)
    return pdf_list


async def parse_single_pdf(
    pdf_path: Path,
    out_dir: str = MINERU_OUT_DIR,
):
    """
    异步解析单个 PDF 文件，输出结构化结果到 out_dir。

    Args:
        pdf_path: PDF 文件路径
        out_dir:  输出根目录，默认 MINERU_OUT_DIR

    Returns:
        MinerU 解析结果

    注意：
        - p_lang_list 参数在 pipeline 后端已静默失效，传了也不会切换语种模型
        - formula_enable=True 启用公式识别，table_enable=True 启用表格识别
        - backend="pipeline" 使用机器学习 pipeline（更准确但更慢）
    """
    # read_fn 兼容图片/PDF 输入，返回字节流
    pdf_bytes = read_fn(pdf_path)

    # MinerU 3.4 参数名与旧版 do_parse 基本一致，无需 ParseOptions 对象
    result = await aio_do_parse(
        output_dir=out_dir,
        pdf_file_names=[pdf_path.stem],
        pdf_bytes_list=[pdf_bytes],
        p_lang_list=["en"],  # 保留写法不报错，但 pipeline 下不再生效
        backend="pipeline",
        parse_method="auto",
        formula_enable=True,
        table_enable=True,
        start_page_id=0,
        end_page_id=None,
    )
    return result


# region 图片清洗（预留）
# 识别长高过小的错误识别图片，删除
# endregion


if __name__ == "__main__":
    # 快速测试：解析 Test_1.pdf
    for i in range(10):
        print("循环前:", datetime.now(), "\n")
        pdf_path = Path(f"./data/raw_pdfs/Test_{i+1}.pdf")
        # 同步脚本用 asyncio.run 包裹异步调用
        asyncio.run(parse_single_pdf(pdf_path))
        print(f"完成：", datetime.now(), "\n")
