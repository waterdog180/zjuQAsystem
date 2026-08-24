"""
main.py —— zjuQAsystem 统一入口（预留）。

当前阶段（M1 文献提取）各模块可独立运行，本文件提供便捷的命令行入口。
后续 M2/M3 模块就绪后，将在此处编排完整流水线。

使用示例：
    # 方式一：直接运行模块
    python -m zjuqa.pdf_processing.mineru_parser
    python -m zjuqa.extraction.membrane_extractor

    # 方式二：通过本入口（待实现完整 CLI）
    python main.py --stage extract --paper Test_1
"""

from pathlib import Path

from zjuqa.config.paths import ensure_data_dirs


def main():
    """主入口：初始化目录，后续将添加 argparse 命令行解析。"""
    ensure_data_dirs()
    print("zjuQAsystem 已启动。当前阶段：M1 文献信息提取。")
    print("请通过子模块直接运行，或在此处扩展完整流水线。")
    # 后续实现：
    # parser = argparse.ArgumentParser(...)
    # args = parser.parse_args()
    # if args.stage == "parse": ...
    # elif args.stage == "identify": ...
    # elif args.stage == "extract": ...


if __name__ == "__main__":
    main()
