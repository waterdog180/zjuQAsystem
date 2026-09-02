"""
image_cleaner.py —— MinerU 解析图片清洗工具。

根据 markdown 文档中图片链接出现的顺序，清洗像素尺寸太小的图片，
将保留的图片复制到独立的 images_cleaned/ 目录并按顺序重编号，
同时更新 markdown 中的图片链接。

设计原则：
  1. 原始 images/ 目录保持不变（MinerU 输出可追溯）
  2. 清洗后的图片单独保存到 images_cleaned/，下游优先加载此目录
  3. 图片加载顺序与文中出现顺序一致（page_1, page_2, ...）
  4. 去除无意义的小图片（分隔线、图标、装饰元素），节约 LLM token

本工具在 MinerU 解析完成后自动调用（见 mineru_parser.parse_pdf），
也可直接运行本文件单独清理指定论文。

直接运行：
    python -m zjuqa.pdf_processing.image_cleaner --paper Test_1
    python -m zjuqa.pdf_processing.image_cleaner --paper Test_1 --min-width 300 --dry-run
"""

import argparse
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image

from ..utils.logging import get_logger
from ..utils.path_utils import get_parsed_images, get_parsed_images_cleaned, get_parsed_text

logger = get_logger(__name__)


# ====================================================================
# 数据结构
# ====================================================================

@dataclass
class ImageEntry:
    """
    markdown 中引用的一张图片的信息。

    Attributes:
        order:        在 markdown 中出现的顺序（从 1 开始）
        original_path: 图片原始文件路径（相对于 markdown 所在目录）
        full_path:    图片文件的绝对路径
        width:        图片宽度（像素）
        height:       图片高度（像素）
        file_size:    文件大小（字节）
        kept:         是否保留
        new_name:     清洗后的文件名（如 page_1.jpg），删除的为 None
    """
    order: int
    original_path: str
    full_path: Path
    width: int = -1
    height: int = -1
    file_size: int = 0
    kept: bool = True
    new_name: Optional[str] = None


@dataclass
class CleanReport:
    """图片清洗结果报告。"""
    paper_name: str
    md_path: Path
    images_dir: Path
    cleaned_dir: Path
    total_found: int = 0
    kept: int = 0
    removed: int = 0
    missing: int = 0
    renamed: int = 0
    entries: List[ImageEntry] = field(default_factory=list)
    backup_md: Optional[Path] = None


# ====================================================================
# markdown 图片链接提取
# ====================================================================

_IMAGE_LINK_PATTERN = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')


def _extract_image_links(md_content: str) -> List[Tuple[str, str]]:
    """从 markdown 内容中按出现顺序提取所有图片链接。"""
    return [(alt.strip(), path.strip()) for alt, path in _IMAGE_LINK_PATTERN.findall(md_content)]


# ====================================================================
# 核心清洗函数
# ====================================================================

def clean_paper_images(
    paper_name: str,
    min_width: int = 200,
    min_height: int = 200,
    dry_run: bool = False,
    backup: bool = True,
    verbose: bool = True,
) -> CleanReport:
    """
    清洗某篇论文的 MinerU 解析图片。

    流程：
      1. 读取 markdown，按出现顺序提取所有图片链接
      2. 检查每张图片的像素尺寸，标记小于阈值的图片为删除
      3. 保留的图片复制到 images_cleaned/ 目录，按顺序命名为 page_1.jpg, page_2.png, ...
      4. 更新 markdown 中的图片链接为 images_cleaned/ 路径，删除小图链接
      5. 原始 images/ 目录和原始图片保持不变

    Args:
        paper_name:  论文名称
        min_width:   最小宽度阈值（像素），默认 200
        min_height:  最小高度阈值（像素），默认 200
        dry_run:     试运行模式，只报告不修改任何文件
        backup:      修改前备份原 markdown
        verbose:     是否打印详细日志

    Returns:
        CleanReport 清洗结果报告
    """
    md_path = get_parsed_text(paper_name)
    images_dir = get_parsed_images(paper_name)
    cleaned_dir = get_parsed_images_cleaned(paper_name)
    md_dir = md_path.parent

    report = CleanReport(
        paper_name=paper_name,
        md_path=md_path,
        images_dir=images_dir,
        cleaned_dir=cleaned_dir,
    )

    if not md_path.exists():
        if verbose:
            logger.debug(f"{paper_name}: markdown 不存在，跳过")
        return report

    if verbose:
        logger.debug(f"{paper_name}: 阈值≥{min_width}×≥{min_height}px" + (" [dry-run]" if dry_run else ""))

    # 1. 读取 markdown
    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    # 2. 按出现顺序提取图片链接
    links = _extract_image_links(md_content)
    report.total_found = len(links)

    # 3. 检查每张图片（去重：同一张图多次引用只处理一次）
    entries: List[ImageEntry] = []
    seen_paths: Dict[str, ImageEntry] = {}

    for order, (alt, img_path) in enumerate(links, start=1):
        full_path = (md_dir / img_path).resolve()

        if img_path in seen_paths:
            entries.append(seen_paths[img_path])
            continue

        entry = ImageEntry(order=order, original_path=img_path, full_path=full_path)

        if full_path.exists():
            entry.file_size = full_path.stat().st_size
            with Image.open(full_path) as img:
                entry.width, entry.height = img.width, img.height
            entry.kept = not (entry.width < min_width or entry.height < min_height)
            if entry.kept:
                report.kept += 1
            else:
                report.removed += 1
        else:
            entry.kept = False
            report.missing += 1

        entries.append(entry)
        seen_paths[img_path] = entry

    report.entries = entries

    # 4. 为保留的图片分配新编号（按第一次出现顺序，去重）
    seen_kept: Dict[str, str] = {}
    kept_counter = 0
    for entry in entries:
        if entry.kept and entry.original_path not in seen_kept:
            kept_counter += 1
            ext = entry.full_path.suffix.lower() or ".jpg"
            seen_kept[entry.original_path] = f"page_{kept_counter}{ext}"
            report.renamed += 1
        if entry.kept:
            entry.new_name = seen_kept[entry.original_path]

    # 5. 执行修改（非 dry-run）
    if not dry_run:
        # 备份 markdown
        if backup:
            backup_path = md_path.with_suffix(".md.bak")
            shutil.copy2(md_path, backup_path)
            report.backup_md = backup_path

        # 清空并重建 cleaned 目录（避免旧文件残留）
        if cleaned_dir.exists():
            shutil.rmtree(cleaned_dir)
        cleaned_dir.mkdir(parents=True, exist_ok=True)

        # 复制保留的图片到 cleaned 目录，按新名称命名
        for entry in entries:
            if entry.kept and entry.new_name and entry.full_path.exists():
                dest = cleaned_dir / entry.new_name
                shutil.copy2(entry.full_path, dest)

        # 更新 markdown 链接
        new_md_content = md_content
        for entry in entries:
            if entry.kept and entry.new_name:
                new_link = f"images_cleaned/{entry.new_name}"
                new_md_content = new_md_content.replace(
                    f"]({entry.original_path})",
                    f"]({new_link})",
                )
            elif not entry.kept:
                pattern = re.compile(
                    r'!\[[^\]]*\]\(' + re.escape(entry.original_path) + r'\)\s*\n?'
                )
                new_md_content = pattern.sub("", new_md_content)

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(new_md_content)

    # 6. 打印报告
    if verbose:
        logger.debug(
            f"{paper_name}: 找到 {report.total_found} 引用，"
            f"保留 {report.kept}，删除 {report.removed}，缺失 {report.missing}"
        )
        if not dry_run:
            logger.debug(f"清洗后图片 → {cleaned_dir.name}/ ({report.kept} 张)")
            for entry in entries:
                if not entry.kept and entry.width > 0:
                    logger.debug(
                        f"删除: {Path(entry.original_path).name} "
                        f"({entry.width}×{entry.height})"
                    )

    return report


# ====================================================================
# 直接运行入口
# ====================================================================

def main():
    """直接运行本文件时的入口。"""
    parser = argparse.ArgumentParser(
        description="MinerU 解析图片清洗工具（删除小图+按文中顺序重编号，输出到 images_cleaned/）",
    )
    parser.add_argument("--paper", required=True, help="论文名称")
    parser.add_argument("--min-width", type=int, default=200, help="最小宽度阈值（像素），默认200")
    parser.add_argument("--min-height", type=int, default=200, help="最小高度阈值（像素），默认200")
    parser.add_argument("--dry-run", action="store_true", help="试运行，只报告不修改")
    parser.add_argument("--no-backup", action="store_true", help="不备份原 markdown")
    args = parser.parse_args()

    report = clean_paper_images(
        paper_name=args.paper,
        min_width=args.min_width,
        min_height=args.min_height,
        dry_run=args.dry_run,
        backup=not args.no_backup,
        verbose=True,
    )

    if args.dry_run:
        print("\n[dry-run] 未修改任何文件")
    else:
        print(f"\n完成，备份: {report.backup_md.name if report.backup_md else '无'}")


if __name__ == "__main__":
    main()
