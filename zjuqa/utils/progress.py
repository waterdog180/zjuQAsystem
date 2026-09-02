"""
progress.py —— 单行进度条工具。

控制台只显示一行进度条，每次更新时用 \\r 覆盖原行，不占用多行。
进度条后附加当前操作和文献/膜名称，同样实时更新。

详细信息通过 logger 写入日志文件，控制台保持简洁。

使用说明：
    from zjuqa.utils.progress import ProgressBar

    with ProgressBar(total=10, prefix="解析") as bar:
        for i, paper in enumerate(papers):
            bar.update(i + 1, current=paper, action="解析中")
            # ... 处理 paper ...
            bar.update(i + 1, current=paper, action="完成")
"""

import sys
import time
from typing import Optional


class ProgressBar:
    """
    单行进度条，支持上下文管理器。

    输出格式：
      解析 [████████░░░░░░] 50% (5/10) | 解析中: Test_1

    每次 update 用 \\r 覆盖当前行，不产生新行。
    完成后自动换行。
    """

    def __init__(self,total: int,prefix: str = "处理",bar_width: int = 30,stream=sys.stdout):
        """
        Args:
            total:     总任务数
            prefix:    进度条前缀（如"解析"、"提取"）
            bar_width: 进度条字符宽度
            stream:    输出流，默认 stdout
        """
        self.total = max(total, 1)
        self.prefix = prefix
        self.bar_width = bar_width
        self.stream = stream
        self._start_time = time.time()
        self._last_line_len = 0

    def __enter__(self):
        self._start_time = time.time()
        self.update(0)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.update(self.total, action="完成")
        self._finish()
        return False

    def update(self,current: int,item: str = "",action: str = "") -> None:
        """
        更新进度条显示。

        Args:
            current: 当前完成的任务数（从 1 开始）
            item:    当前处理的文献/膜名称
            action:  当前操作描述（如"解析中"、"提取中"）
        """
        pct = min(current / self.total, 1.0)
        filled = int(self.bar_width * pct)
        bar = "█" * filled + "░" * (self.bar_width - filled)

        # 构建状态后缀
        suffix_parts = []
        if action:
            suffix_parts.append(action)
        if item:
            suffix_parts.append(item)
        suffix = " | " + ": ".join(suffix_parts) if suffix_parts else ""

        line = f"\r{self.prefix} [{bar}] {pct * 100:5.1f}% ({current}/{self.total}){suffix}"

        # 清除上次残留字符
        if len(line) < self._last_line_len:
            line = line + " " * (self._last_line_len - len(line))
        self._last_line_len = len(line)

        self.stream.write(line)
        self.stream.flush()

    def _finish(self) -> None:
        """进度条完成，换行。"""
        elapsed = time.time() - self._start_time
        self.stream.write(f"\n  耗时: {elapsed:.1f}s\n")
        self.stream.flush()


def progress_iter(iterable,total: Optional[int] = None,prefix: str = "处理"):
    """
    便捷迭代器包装，自动管理进度条。

    Args:
        iterable: 要迭代的对象
        total:    总任务数，None 时用 len(iterable)
        prefix:   进度条前缀

    Yields:
        (index, item, progress_bar) —— 可在循环中调用 progress_bar.update()
    """
    if total is None:
        try:
            total = len(iterable)
        except TypeError:
            total = 0

    with ProgressBar(total=total, prefix=prefix) as bar:
        for i, item in enumerate(iterable, start=1):
            bar.update(i, current=str(item))
            yield i, item, bar
