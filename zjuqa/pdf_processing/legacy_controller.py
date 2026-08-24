"""
legacy_controller.py —— 旧版 PDF 预处理（基于 PyMuPDF/fitz）。

【已弃用】项目已转用 MinerU 进行 PDF 预处理，本文件保留仅作参考兼容。
原文件 pdf_controller.py 已加入 .gitignore。

功能：
  - get_raw_pdf_list: 列出原始 PDF
  - pdf2txt:          提取 PDF 全文为 txt（带页码标记，去除参考文献）
  - pdf_to_images_base64: 将 PDF 各页渲染为图片并 base64 编码

使用说明：
    from zjuqa.pdf_processing.legacy_controller import pdf2txt
    pdf2txt("Test_1.pdf")
"""

import base64
import re
from pathlib import Path
from typing import List

import fitz

from ..config.paths import MAX_IMAGES, PAGE_DPI, PRE_PDF_DIR, RAW_PDF_DIR


def get_raw_pdf_list(rawPdfDir=RAW_PDF_DIR) -> List[str]:
    """
    获取原始 PDF 目录下所有 PDF 文件名。

    Args:
        rawPdfDir: 原始 PDF 目录

    Returns:
        PDF 文件名列表
    """
    pdf_list = []
    raw_dir = Path(rawPdfDir)
    for file in raw_dir.iterdir():
        if file.is_file() and file.suffix.lower() == ".pdf":
            pdf_list.append(file.name)
    return pdf_list


def pdf2txt(
    pdf_name: str,
    rawPdfDir=RAW_PDF_DIR,
    prePdfDir=PRE_PDF_DIR,
) -> bool | None:
    """
    提取 PDF 全文写入本地 txt 文件，带页码标记。
    自动去除空白行和参考文献部分。只执行写入，不返回文本内容。

    Args:
        pdf_name:   PDF 文件名
        rawPdfDir:  原始 PDF 目录
        prePdfDir:  预处理输出目录

    Returns:
        成功返回 True，失败返回 None
    """
    raw_dir = Path(rawPdfDir)
    pre_dir = Path(prePdfDir)
    pdf_path = raw_dir / pdf_name
    name_no_suffix = pdf_path.stem
    txt_subdir = pre_dir / name_no_suffix
    txt_path = txt_subdir / f"{name_no_suffix}.txt"

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"文件 {pdf_name} 提取失败：{pdf_path}, error:{str(e)}")
        return None

    pages = []
    for i, page in enumerate(doc):
        txt = page.get_text()
        if txt.strip():
            pages.append(f"--- Page {i+1} ---\n{txt}")
    page_count = len(doc)
    doc.close()

    full_text = "\n".join(pages)

    # 去除空白行
    if True:
        full_text = re.sub(r'^\s*$', '', full_text, flags=re.MULTILINE)
        full_text = re.sub(r'\n+', '\n', full_text)
        full_text = full_text.strip('\n')

    # 去除参考文献部分
    if True:
        pat = re.compile(r'references[.:\s]*', re.IGNORECASE)
        ms = list(pat.finditer(full_text))
        if ms:
            full_text = full_text[:ms[-1].start()].rstrip()

    txt_subdir.mkdir(parents=True, exist_ok=True)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(full_text)
    print(
        f"文件 {pdf_name} 提取完成：{len(full_text)} 字符，"
        f"共 {page_count} 页，输出：{txt_path}"
    )
    return True


def pdf_to_images_base64(
    pdf_name: str,
    dpi: int = PAGE_DPI,
    rawPdfDir=RAW_PDF_DIR,
    prePdfDir=PRE_PDF_DIR,
) -> bool | None:
    """
    将 PDF 各页渲染为图片并保存为 base64 字符串，写入对应文件夹。

    Args:
        pdf_name:   PDF 文件名
        dpi:        渲染分辨率
        rawPdfDir:  原始 PDF 目录
        prePdfDir:  预处理输出目录

    Returns:
        成功返回 True，失败返回 None
    """
    raw_dir = Path(rawPdfDir)
    pre_dir = Path(prePdfDir)
    pdf_path = raw_dir / pdf_name
    name_no_suffix = pdf_path.stem
    output_dir = pre_dir / name_no_suffix
    img_dir = output_dir / "page_images" / pdf_path.stem
    img_dir.mkdir(parents=True, exist_ok=True)

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"文件 {pdf_name} 图片提取失败：{pdf_path}, error:{str(e)}")
        return None

    total = len(doc)
    pages_to_render = min(total, MAX_IMAGES)
    print(f"  [Step1-图片] 渲染 {pages_to_render}/{total} 页（DPI={dpi}）...")

    mat = fitz.Matrix(dpi / 72, dpi / 72)
    for i in range(pages_to_render):
        pix = doc[i].get_pixmap(matrix=mat, alpha=False)
        img_path = img_dir / f"page_{i+1:03d}.png"
        pix.save(img_path)
        with open(img_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        # results 变量保留原逻辑（当前未使用返回值）
        _ = {"page": i + 1, "path": str(img_path), "base64": b64}

    doc.close()
    print(f"  [Step1-图片] 完成，保存至: {img_dir}")
    return True


if __name__ == "__main__":
    print("legacy_controller.py 单元测试:")
    print(get_raw_pdf_list())
    print(pdf2txt("Test_1.pdf"))
    print(pdf_to_images_base64("Test_1.pdf"))
