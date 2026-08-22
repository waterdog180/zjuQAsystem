#转用MinerU，整体弃用

from paras import RAW_PDF_DIR, PRE_PDF_DIR, PAGE_DPI, MAX_IMAGES
import fitz
import re
import base64
from typing import List
from pathlib import Path


def get_raw_pdf_list(rawPdfDir=RAW_PDF_DIR):
    pdf_list = []
    raw_dir = Path(rawPdfDir)
    for file in raw_dir.iterdir():
        if file.is_file() and file.suffix.lower() == ".pdf":
            pdf_list.append(file.name)
    return pdf_list


def pdf2txt(pdf_name: str, rawPdfDir=RAW_PDF_DIR, prePdfDir=PRE_PDF_DIR):
    """提取 PDF 全文写入本地txt文件，带页码标记。只执行写入，不返回文本内容。
    返回：成功True；失败None
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
    # 去除空白行开关
    if True:
        full_text = re.sub(r'^\s*$', '', full_text, flags=re.MULTILINE)
        full_text = re.sub(r'\n+', '\n', full_text)
        full_text = full_text.strip('\n')
    # 去除参考文献开关
    if True:
        pat = re.compile(r'references[.:\s]*', re.IGNORECASE)
        ms = list(pat.finditer(full_text))
        if ms:
            full_text = full_text[:ms[-1].start()].rstrip()

    txt_subdir.mkdir(parents=True, exist_ok=True)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(full_text)

    print(f"文件 {pdf_name} 提取完成：{len(full_text)} 字符，共 {page_count} 页，输出：{txt_path}")
    return True


def pdf_to_images_base64(pdf_name: str, dpi: int = PAGE_DPI, rawPdfDir=RAW_PDF_DIR, prePdfDir=PRE_PDF_DIR):
    """
    提取PDF文件中的图片并保存为base64字符串，写入对应文件夹
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
    results = []

    print(f"  [Step1-图片] 渲染 {pages_to_render}/{total} 页（DPI={dpi}）...")

    mat = fitz.Matrix(dpi / 72, dpi / 72)
    for i in range(pages_to_render):
        pix = doc[i].get_pixmap(matrix=mat, alpha=False)
        img_path = img_dir / f"page_{i+1:03d}.png"
        pix.save(img_path)

        with open(img_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        results.append({"page": i + 1, "path": str(img_path), "base64": b64})

    doc.close()
    print(f"  [Step1-图片] 完成，保存至: {img_dir}")
    return True


if __name__ == "__main__":
    print("pdf_controller.py单元测试:")
    print(get_raw_pdf_list())
    print(pdf2txt("Test_1.pdf"))
    print(pdf_to_images_base64("Test_1.pdf"))