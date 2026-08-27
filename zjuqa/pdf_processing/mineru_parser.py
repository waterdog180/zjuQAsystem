"""
mineru_parser.py —— 基于 MinerU 的 PDF 预处理。

使用 MinerU 3.4 的 Python API（mineru.cli.common.do_parse）对 PDF 进行结构化解析，
输出结构化 Markdown 文本和页面图片，供后续膜名称识别和参数提取使用。

本次重写（修复 _mineru_parse_single 的多处 bug）：
  - 修正导入路径：mineru.cli.api → mineru.cli.common
  - 修正参数签名：Task 对象 → pdf_file_names + pdf_bytes_list + p_lang_list
  - 新增 read_fn 读取 PDF 为 bytes（API 要求传入字节流而非路径）
  - 设备通过环境变量 MINERU_DEVICE_MODE 设置，而非函数参数
  - 精简输出文件：只保留 .md 和 images/，关闭 middle_json/model_output 等
  - 默认模型源 modelscope（国内可访问），设备 cpu

输出目录结构（与 paths.py 中的 get_parsed_text / get_parsed_images 匹配）：
    data/parsed/<paper_name>/auto/
    ├── <paper_name>.md       # 结构化 Markdown 全文
    └── images/               # 页面图片
        └── *.jpg

使用说明：
    from zjuqa.pdf_processing.mineru_parser import parse_pdf, parse_all
    # 单篇解析
    parse_pdf("data/raw/Test_1.pdf")
    # 批量解析（自动扫描 data/raw/，跳过已完成的）
    parse_all(mode="skip")
"""

import os
from pathlib import Path
from typing import List, Optional

from ..config.paths import PARSED_DIR, RAW_PDF_DIR, get_parsed_text
from ..utils.scanner import scan_parsed_papers, scan_raw_pdfs

# ====================================================================
# MinerU 环境配置（必须在导入 mineru 之前设置）
# ====================================================================

# 模型下载源：modelscope（国内可访问），避免 HuggingFace 网络问题
os.environ.setdefault("MINERU_MODEL_SOURCE", "modelscope")
# 推理设备：默认 cpu（用户环境为 Windows Conda CPU）
os.environ.setdefault("MINERU_DEVICE_MODE", "cpu")


# ====================================================================
# MinerU 解析核心
# ====================================================================

def _mineru_parse_single(pdf_path: Path, output_dir: Path) -> None:
    """
    调用 MinerU 同步 API 解析单个 PDF。

    使用 mineru.cli.common.do_parse（pipeline backend 内部同步运行，
    无需 asyncio，比 aio_do_parse 更简洁可靠）。

    Args:
        pdf_path:   PDF 文件路径
        output_dir: 输出根目录（MinerU 会在其下创建 <stem>/auto/）

    输出：
        <output_dir>/<stem>/auto/<stem>.md
        <output_dir>/<stem>/auto/images/*.jpg
    """
    # 延迟导入：避免 import 本模块时就加载 MinerU（重依赖）
    from mineru.cli.common import do_parse, read_fn

    output_dir.mkdir(parents=True, exist_ok=True)

    # 步骤1：读取 PDF 为字节流（MinerU API 要求传入 bytes，而非文件路径）
    pdf_bytes = read_fn(pdf_path)

    # 步骤2：调用 do_parse
    # 参数说明（MinerU 3.4 官方签名）：
    #   output_dir        输出根目录
    #   pdf_file_names    文件名列表（不含扩展名），用于创建子目录
    #   pdf_bytes_list    PDF 字节流列表，与 pdf_file_names 一一对应
    #   p_lang_list       每篇文档的 OCR 语言列表（化工论文通常为英文）
    #   backend           处理后端：pipeline（传统多模型流水线）
    #   parse_method      解析方式：auto（自动判断文本/扫描）
    #   formula_enable    公式识别（化工论文含公式，开启）
    #   table_enable      表格识别（膜参数多在表格中，必须开启）
    #   f_dump_*          输出文件控制：只保留 .md，关闭其他冗余文件
    do_parse(
        output_dir=str(output_dir),
        pdf_file_names=[pdf_path.stem],
        pdf_bytes_list=[pdf_bytes],
        p_lang_list=["en"],
        backend="pipeline",
        parse_method="auto",
        formula_enable=True,
        table_enable=True,
        #region 精简输出：只保留 Markdown 和图片,额外需求在此开启
        f_dump_md=True,
        f_dump_middle_json=False,
        f_dump_model_output=False,
        f_dump_content_list=False,
        f_dump_orig_pdf=False,
        f_draw_layout_bbox=False,
        f_draw_span_bbox=False,
    )


def parse_pdf(pdf_path: str | Path, force: bool = False) -> Optional[Path]:
    """
    解析单个 PDF 文件。

    Args:
        pdf_path: PDF 文件路径（绝对或相对）
        force:    True 时强制重新解析，False 时已解析则跳过

    Returns:
        解析后的文本文件路径，跳过时返回 None
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        print(f"  [解析] 文件不存在: {pdf_path}")
        return None

    paper_name = pdf_path.stem
    text_path = get_parsed_text(paper_name)

    # 跳过已解析的
    if not force and text_path.exists():
        print(f"  [解析] 跳过 {paper_name}（已解析）")
        return text_path

    print(f"  [解析] 正在解析: {paper_name}")
    try:
        _mineru_parse_single(pdf_path, PARSED_DIR)
    except Exception as e:
        print(f"  [解析] {paper_name} 解析失败: {e}")
        return None

    if text_path.exists():
        print(f"  [解析] 完成: {paper_name} → {text_path}")
        return text_path
    else:
        print(f"  [解析] 警告: 解析后未找到输出文件 {text_path}")
        return None


# ====================================================================
# 批量处理（自动扫描 + mode 开关）
# ====================================================================

def parse_all(mode: str = "skip",pdf_files: Optional[List[str | Path]] = None) -> dict:
    """
    批量解析 data/raw/ 下的所有 PDF。

    Args:
        mode:
            "skip" ：跳过已解析的论文（默认，避免重复计算）
            "force"：全部重新解析
        pdf_files: 指定 PDF 文件列表，None 时自动扫描 data/raw/

    Returns:
        统计字典 {"total": 总数, "parsed": 解析数, "skipped": 跳过数, "failed": 失败数}
    """
    # 自动扫描（脱离 Test_X 依赖）
    if pdf_files is None:
        pdf_names = scan_raw_pdfs()
        pdf_files = [RAW_PDF_DIR / f"{name}.pdf" for name in pdf_names]

    if not pdf_files:
        print("[解析] 未找到 PDF 文件，请将论文放入 data/raw/")
        return {"total": 0, "parsed": 0, "skipped": 0, "failed": 0}

    force = (mode == "force")
    print(f"[解析] 发现 {len(pdf_files)} 个 PDF，mode={mode}")

    parsed = 0
    skipped = 0
    failed = 0

    for pdf_path in pdf_files:
        result = parse_pdf(pdf_path, force=force)
        if result is not None:
            parsed += 1
        else:
            paper_name = Path(pdf_path).stem
            if get_parsed_text(paper_name).exists():
                skipped += 1
            else:
                failed += 1

    stats = {
        "total": len(pdf_files),
        "parsed": parsed,
        "skipped": skipped,
        "failed": failed,
    }
    print(
        f"[解析] 完成: 总计 {stats['total']}, "
        f"解析 {stats['parsed']}, 跳过 {stats['skipped']}, 失败 {stats['failed']}"
    )
    return stats


# ====================================================================
# 命令行入口
# ====================================================================

if __name__ == "__main__":
    # 默认批量解析 data/raw/ 下所有 PDF，跳过已完成的
    parse_all(mode="skip")
