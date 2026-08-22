import asyncio
from pathlib import Path
from datetime import datetime

# 正确导入路径：两个函数都在 mineru.cli.common 下
from mineru.cli.common import aio_do_parse, read_fn

# 保留你原有的常量
from paras import *


def get_raw_pdf_list(raw_pdf_dir: str) -> list[str]:
    pdf_list = []
    raw_dir = Path(raw_pdf_dir)
    for file in raw_dir.iterdir():
        if file.is_file() and file.suffix.lower() == ".pdf":
            pdf_list.append(file.name)
    return pdf_list


async def parse_single_pdf(pdf_path: Path, out_dir: str=MINERU_OUT_DIR):
    # read_fn 用法和旧版完全一致，兼容图片/PDF输入
    pdf_bytes = read_fn(pdf_path)

    # 3.4 参数名和旧版 do_parse 基本保持一致，无需 ParseOptions 对象
    # 注意：p_lang_list 参数在 pipeline 后端已静默失效，传了也不会切换独立语种模型
    result = await aio_do_parse(
        output_dir=out_dir,
        pdf_file_names=[pdf_path.stem],
        pdf_bytes_list=[pdf_bytes],
        p_lang_list=["en"],  # 保留写法不报错，但pipeline下不再生效
        backend="pipeline",
        parse_method="auto",
        formula_enable=True,
        table_enable=True,
        start_page_id=0,
        end_page_id=None
    )
    return result

#region 图片清洗
#识别长高过小的错误识别图片，删除


if __name__ == "__main__":
    print("循环前:", datetime.now(), "\n")

    pdf_path = Path(f"./data/raw_pdfs/Test_{1}.pdf")
    # 同步脚本用 asyncio.run 包裹异步调用即可
    asyncio.run(parse_single_pdf(pdf_path))
    print(f"完成：", datetime.now(), "\n")
