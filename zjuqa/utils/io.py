"""
io.py —— JSON 文件读写工具。

提供安全的 JSON 读写函数，处理编码和异常。
供各模块复用，减少重复的文件操作代码。

使用说明：
    from zjuqa.utils.io import load_json_safe, save_json
    data = load_json_safe("/path/to/file.json", default={})
    save_json("/path/to/file.json", data)
"""

import json
from pathlib import Path
from typing import Any, Optional


def load_json_safe(
    file_path: Path | str,
    default: Any = None,
) -> Any:
    """
    安全读取 JSON 文件。

    文件不存在或解析失败时返回 default，不抛出异常。

    Args:
        file_path: JSON 文件路径
        default:   读取失败时的默认返回值

    Returns:
        解析后的 JSON 数据，失败时返回 default
    """
    file_path = Path(file_path)
    if not file_path.exists():
        return default
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"  [IO] 警告: 读取 {file_path} 失败: {e}")
        return default


def save_json(
    file_path: Path | str,
    data: Any,
    indent: int = 4,
) -> Path:
    """
    保存数据为 JSON 文件。

    自动创建父目录，使用 UTF-8 编码和 ensure_ascii=False。

    Args:
        file_path: 目标文件路径
        data:      要保存的数据（可 JSON 序列化）
        indent:    缩进空格数

    Returns:
        保存的文件路径
    """
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)
    return file_path


def ensure_json_file(
    file_path: Path | str,
    default: dict,
) -> dict:
    """
    确保 JSON 文件存在，不存在则创建并写入 default。

    Args:
        file_path: JSON 文件路径
        default:   默认内容

    Returns:
        文件内容（已存在则读取，不存在则返回 default 并写入）
    """
    file_path = Path(file_path)
    if file_path.exists():
        data = load_json_safe(file_path, default=default)
        return data if data is not None else default
    save_json(file_path, default)
    return default
