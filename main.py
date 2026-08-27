"""
main.py —— zjuQAsystem 统一命令行入口。

三阶段流水线：parse（MinerU解析）→ identify（膜名称识别）→ extract（膜参数提取）。
支持分功能运行、全量运行、指定单篇论文、精细参数透传、中间数据清理。

子命令：
    parse     MinerU PDF 结构化解析
    identify  膜名称识别（纯文本 LLM）
    extract   膜参数提取（多模态 LLM）
    all       全量运行 parse → identify → extract
    clean     清理各阶段中间数据（不删除 raw/ 原始 PDF）

使用示例：
    # 全量运行三阶段（自动扫描，跳过已完成）
    python main.py all

    # 只运行 MinerU 解析，强制重跑
    python main.py parse --mode force

    # 只运行膜参数提取，指定单篇论文
    python main.py extract --paper Test_1

    # 膜名称识别，指定文本截断长度
    python main.py identify --text-len 12000

    # 清理所有中间数据（保留 raw/ 原始 PDF）
    python main.py clean --stage all

    # 清理指定阶段
    python main.py clean --stage parsed

    # 清理指定论文的提取结果
    python main.py clean --paper Test_1 --stage extracted

    # 查看帮助
    python main.py --help
    python main.py clean --help
"""

import argparse
import sys
from typing import List, Optional

from zjuqa.config.paths import ensure_data_dirs


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    """为子命令添加通用参数。"""
    parser.add_argument(
        "--mode",
        choices=["skip", "force"],
        default="skip",
        help="skip=跳过已完成的（默认），force=全部重跑",
    )
    parser.add_argument(
        "--paper",
        type=str,
        default=None,
        help="指定单篇论文名称，默认自动扫描全部",
    )


def cmd_parse(args: argparse.Namespace) -> None:
    """处理 parse 子命令：MinerU PDF 解析。"""
    from zjuqa.pdf_processing.mineru_parser import parse_all, parse_pdf
    from zjuqa.config.paths import RAW_PDF_DIR

    if args.paper:
        pdf_path = RAW_PDF_DIR / f"{args.paper}.pdf"
        parse_pdf(pdf_path, force=(args.mode == "force"))
    else:
        parse_all(mode=args.mode)


def cmd_identify(args: argparse.Namespace) -> None:
    """处理 identify 子命令：膜名称识别。"""
    from zjuqa.extraction.membrane_identifier import identify_all, identify_paper

    text_len = getattr(args, "text_len", -1)
    if args.paper:
        internal_mode = "f" if args.mode == "force" else "n"
        identify_paper(args.paper, mode=internal_mode, text_len=text_len)
    else:
        identify_all(mode=args.mode)


def cmd_extract(args: argparse.Namespace) -> None:
    """处理 extract 子命令：膜参数提取。"""
    from zjuqa.extraction.membrane_extractor import extract_all, extract_paper

    max_images = getattr(args, "max_images", 40)
    if args.paper:
        extract_paper(args.paper, mode=args.mode, max_images=max_images)
    else:
        extract_all(mode=args.mode, max_images=max_images)


def cmd_all(args: argparse.Namespace) -> None:
    """处理 all 子命令：依次运行 parse → identify → extract。"""
    print("=" * 60)
    print("阶段 1/3: MinerU PDF 解析")
    print("=" * 60)
    cmd_parse(args)

    print("\n" + "=" * 60)
    print("阶段 2/3: 膜名称识别")
    print("=" * 60)
    cmd_identify(args)

    print("\n" + "=" * 60)
    print("阶段 3/3: 膜参数提取")
    print("=" * 60)
    cmd_extract(args)

    print("\n" + "=" * 60)
    print("全流程完成！")
    print("=" * 60)


def cmd_clean(args: argparse.Namespace) -> None:
    """
    处理 clean 子命令：清理各阶段中间数据。

    --stage 指定清理阶段：parsed / identified / extracted / all
    --paper 指定论文名称时，只清理该论文的对应阶段数据
    不会删除 data/raw/ 下的原始 PDF。
    """
    from zjuqa.utils.cleanup import clean_stage, clean_paper, STAGES

    stage = args.stage

    if args.paper:
        # 清理指定论文
        stages = None if stage == "all" else [stage]
        result = clean_paper(args.paper, stages=stages)
        deleted = sum(1 for v in result.values() if v)
        print(f"[清理] 论文 {args.paper} 清理完成，删除 {deleted} 个阶段数据")
    else:
        # 清理整个阶段
        result = clean_stage(stage)
        total = sum(result.values())
        print(f"[清理] 阶段 '{stage}' 清理完成，共删除 {total} 项")


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        prog="zjuqa",
        description="zjuQAsystem —— 化工膜领域 LLM 科研问答系统（M1 文献提取阶段）",
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # parse
    p_parse = subparsers.add_parser("parse", help="MinerU PDF 结构化解析")
    _add_common_args(p_parse)
    p_parse.set_defaults(func=cmd_parse)

    # identify
    p_identify = subparsers.add_parser("identify", help="膜名称识别（纯文本 LLM）")
    _add_common_args(p_identify)
    p_identify.add_argument(
        "--text-len",
        type=int,
        default=-1,
        help="LLM 文本截断字符数，-1 表示不截断（默认）",
    )
    p_identify.set_defaults(func=cmd_identify)

    # extract
    p_extract = subparsers.add_parser("extract", help="膜参数提取（多模态 LLM）")
    _add_common_args(p_extract)
    p_extract.add_argument(
        "--max-images",
        type=int,
        default=60,
        help="单篇论文最大传入图片数（默认60）",
    )
    p_extract.set_defaults(func=cmd_extract)

    # all
    p_all = subparsers.add_parser("all", help="全量运行 parse → identify → extract")
    _add_common_args(p_all)
    p_all.add_argument(
        "--max-images",
        type=int,
        default=60,
        help="单篇论文最大传入图片数（默认60）",
    )
    p_all.add_argument(
        "--text-len",
        type=int,
        default=-1,
        help="膜名称识别的文本截断字符数，-1 表示不截断（默认）",
    )
    p_all.set_defaults(func=cmd_all)

    # clean
    p_clean = subparsers.add_parser(
        "clean",
        help="清理各阶段中间数据（不删除 raw/ 原始 PDF）",
    )
    p_clean.add_argument(
        "--stage",
        choices=["parsed", "identified", "extracted", "all"],
        default="all",
        help="清理阶段：parsed/identified/extracted/all（默认 all）",
    )
    p_clean.add_argument(
        "--paper",
        type=str,
        default=None,
        help="指定论文名称时只清理该论文的数据，默认清理全部",
    )
    p_clean.set_defaults(func=cmd_clean)

    return parser


def main(argv: Optional[List[str]] = None) -> None:
    """主入口。"""
    ensure_data_dirs()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
