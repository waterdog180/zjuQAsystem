"""
mineru_parser.py —— 基于 MinerU 的 PDF 预处理。

使用 MinerU 3.4 的 Python API（mineru.cli.common.do_parse）对 PDF 进行结构化解析，
输出结构化 Markdown 文本和页面图片，供后续膜名称识别和参数提取使用。

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

from ..config.paths import PARSED_DIR, RAW_PDF_DIR
from ..utils.logging import get_logger
from ..utils.path_utils import get_parsed_text
from ..utils.progress import ProgressBar
from ..utils.scanner import scan_parsed_papers, sanitize_paper_name

logger = get_logger(__name__)

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

def _mineru_parse_single(pdf_path: Path, output_dir: Path, paper_name: str) -> None:
    """
    调用 MinerU 同步 API 解析单个 PDF。

    使用 mineru.cli.common.do_parse（pipeline backend 内部同步运行，
    无需 asyncio，比 aio_do_parse 更简洁可靠）。

    Args:
        pdf_path:   PDF 文件路径（原始文件，含空格等不影响读取）
        output_dir: 输出根目录（MinerU 会在其下创建 <paper_name>/auto/）
        paper_name: 合规后的论文名称，用作 MinerU 输出子目录名和 markdown 文件名

    输出：
        <output_dir>/<paper_name>/auto/<paper_name>.md
        <output_dir>/<paper_name>/auto/images/*.jpg
    """
    # 延迟导入：避免 import 本模块时就加载 MinerU（重依赖）
    from mineru.cli.common import do_parse, read_fn

    output_dir.mkdir(parents=True, exist_ok=True)

    # 步骤1：读取 PDF 为字节流（MinerU API 要求传入 bytes，而非文件路径）
    pdf_bytes = read_fn(pdf_path)

    # 步骤2：调用 do_parse
    # pdf_file_names 使用合规名称，确保输出目录与后续路径一致
    do_parse(
        output_dir=str(output_dir),
        pdf_file_names=[paper_name],
        pdf_bytes_list=[pdf_bytes],
        p_lang_list=["en"],
        backend="pipeline",
        parse_method="auto",
        formula_enable=True,
        table_enable=True,
        # 精简输出：只保留 Markdown 和图片
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
        logger.warning(f"文件不存在: {pdf_path}")
        return None

    # 内部使用合规名称（不修改原始文件）
    paper_name = sanitize_paper_name(pdf_path.stem)
    text_path = get_parsed_text(paper_name)

    # 跳过已解析的
    if not force and text_path.exists():
        logger.info(f"跳过 {paper_name}（已解析）")
        return text_path

    logger.info(f"正在解析: {paper_name} (原始文件: {pdf_path.name})")
    try:
        _mineru_parse_single(pdf_path, PARSED_DIR, paper_name)
    except Exception as e:
        logger.error(f"{paper_name} 解析失败: {e}", exc_info=True)
        return None

    if text_path.exists():
        logger.info(f"完成: {paper_name} → {text_path}")
        # 解析成功后自动清洗图片（删除小图+按文中顺序重编号）
        try:
            from .image_cleaner import clean_paper_images
            clean_paper_images(paper_name, verbose=False)
        except Exception as e:
            logger.warning(f"{paper_name} 图片清洗失败（不影响解析结果）: {e}")
        return text_path
    else:
        logger.warning(f"解析后未找到输出文件 {text_path}")
        return None


# ====================================================================
# 批量处理（自动扫描 + mode 开关 + 进度条）
# ====================================================================

def parse_all(mode: str = "skip", pdf_files: Optional[List[str | Path]] = None) -> dict:
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
    # 自动扫描：直接遍历 RAW_PDF_DIR，避免 scan→反查的间接层
    if pdf_files is None:
        if RAW_PDF_DIR.exists():
            pdf_files = sorted([
                f for f in RAW_PDF_DIR.iterdir()
                if f.is_file() and f.suffix.lower() == ".pdf"
            ])
        else:
            pdf_files = []

    if not pdf_files:
        print("[解析] 未找到 PDF 文件，请将论文放入 data/raw/")
        return {"total": 0, "parsed": 0, "skipped": 0, "failed": 0}

    force = (mode == "force")
    print(f"[解析] 发现 {len(pdf_files)} 个 PDF，mode={mode}")

    parsed = 0
    skipped = 0
    failed = 0

    with ProgressBar(total=len(pdf_files), prefix="解析") as bar:
        for i, pdf_path in enumerate(pdf_files, start=1):
            paper_name = sanitize_paper_name(Path(pdf_path).stem)
            bar.update(i, item=paper_name, action="解析中")

            result = parse_pdf(pdf_path, force=force)
            if result is not None:
                parsed += 1
            else:
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
    logger.info(f"批量解析完成: {stats}")
    return stats


# ====================================================================
# 命令行入口
# ====================================================================

if __name__ == "__main__":
    # 默认批量解析 data/raw/ 下所有 PDF，跳过已完成的
    parse_all(mode="skip")
