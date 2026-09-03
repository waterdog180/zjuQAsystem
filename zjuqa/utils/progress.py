"""
progress.py —— 基于 tqdm 的单行进度条工具。

封装 tqdm 为 ProgressBar 类，保持与旧版自定义进度条相同的接口
（update(current, item, action) + 上下文管理器），调用方无需修改。
tqdm 自动处理单行刷新、速率估算、剩余时间等。

使用说明：
    from zjuqa.utils.progress import ProgressBar

    with ProgressBar(total=10, prefix="解析") as bar:
        for i, paper in enumerate(papers, 1):
            bar.update(i, item=paper, action="解析中")
            # ... 处理 paper ...
"""

import sys
import time
from typing import Optional

from tqdm import tqdm


class ProgressBar:
    """
    基于 tqdm 的单行进度条，支持上下文管理器。

    输出格式（tqdm 自动渲染）：
      解析:  50%|███████████████               | 5/10 [00:12<00:12, 解析中: Test_1]

    每次 update 设置当前进度并刷新后缀（操作: 文献/膜名称），不产生新行。
    完成后自动关闭并换行。
    """

    def __init__(
        self,
        total: int,
        prefix: str = "处理",
        bar_width: int = 30,
        stream=None,
    ):
        """
        Args:
            total:     总任务数
            prefix:    进度条前缀（如"解析"、"提取"）
            bar_width: 保留参数（兼容旧接口），tqdm 自动适配终端宽度
            stream:    输出流，默认 stdout
        """
        self.total = max(total, 1)
        self.prefix = prefix
        self._tqdm = tqdm(
            total=self.total,
            desc=prefix,
            unit="项",
            file=stream or sys.stdout,
            leave=True,
            ncols=None,  # 自适应终端宽度
        )
        self._start_time = time.time()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 异常时不强制设为 100%，正常结束时设为完成
        if exc_type is None:
            self._tqdm.n = self.total
            self._tqdm.set_postfix_str("完成", refresh=False)
            self._tqdm.refresh()
        self._tqdm.close()
        return False

    def update(self, current: int, item: str = "", action: str = "") -> None:
        """
        更新进度条显示。

        Args:
            current: 当前完成的任务数（从 1 开始，绝对值而非增量）
            item:    当前处理的文献/膜名称
            action:  当前操作描述（如"解析中"、"提取中"）
        """
        # tqdm.update() 是增量，这里设置绝对值
        self._tqdm.n = min(current, self.total)

        # 构建后缀：操作: 名称
        postfix_parts = []
        if action:
            postfix_parts.append(action)
        if item:
            postfix_parts.append(item)
        postfix = ": ".join(postfix_parts) if postfix_parts else ""

        # set_postfix_str(refresh=False) 只更新内部状态，最后统一 refresh 一次
        self._tqdm.set_postfix_str(postfix, refresh=False)
        self._tqdm.refresh()

    def close(self) -> None:
        """手动关闭进度条。"""
        self._tqdm.close()


def progress_iter(iterable, total: Optional[int] = None, prefix: str = "处理"):
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
            bar.update(i, item=str(item))
            yield i, item, bar
