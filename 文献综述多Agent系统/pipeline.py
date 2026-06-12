"""并行执行管道"""

import signal
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from typing import Callable, Any, Optional

from progress import ProgressTracker


class PipelineExecutor:
    """支持并行批次执行和优雅终止的管道"""

    def __init__(self, max_workers: int = 4, stages: Optional[list[str]] = None):
        self.max_workers = max_workers
        self._stages = stages or []
        self._progress = ProgressTracker(self._stages)
        self._abort_event = threading.Event()
        self._executor: Optional[ThreadPoolExecutor] = None
        self._original_sigint = None
        self._installed = False

    @property
    def progress(self) -> ProgressTracker:
        return self._progress

    @property
    def cancelled(self) -> bool:
        return self._abort_event.is_set() or self._progress.cancelled

    def install_signal_handler(self):
        """安装 Ctrl+C 信号处理器（仅主线程）"""
        if self._installed:
            return
        try:
            self._original_sigint = signal.getsignal(signal.SIGINT)
            signal.signal(signal.SIGINT, self._handle_sigint)
            self._installed = True
        except ValueError:
            pass  # 非主线程无法安装

    def uninstall_signal_handler(self):
        """恢复原始信号处理器"""
        if not self._installed:
            return
        try:
            sig = self._original_sigint or signal.SIGINT
            signal.signal(signal.SIGINT, sig)
        except ValueError:
            pass
        self._installed = False

    def _handle_sigint(self, signum, frame):
        """Ctrl+C -> 优雅终止"""
        self._abort_event.set()
        self._progress.cancel()
        print("\n\n  [!] 收到中断信号，正在等待进行中的任务完成...")
        print("      再按一次 Ctrl+C 强制退出")
        # 第二次按 Ctrl+C -> 强制退出
        signal.signal(signal.SIGINT, lambda s, f: sys.exit(1))

    def run_parallel_batches(
        self,
        items: list[Any],
        worker_fn: Callable[[Any], Any],
        stage_idx: int,
        stage_name: str,
        preserve_order: bool = True,
    ) -> list[Any]:
        """将 items 拆分成批次并行执行 worker_fn

        Args:
            items: 待处理的项目列表
            worker_fn: 单项处理函数 (item) -> result
            stage_idx: 当前阶段编号
            stage_name: 阶段名称
            preserve_order: 是否保持结果顺序与输入一致

        Returns:
            处理结果列表
        """
        if not items:
            return []

        total = len(items)
        self._progress.start_stage(stage_idx, stage_name, total)

        if self.cancelled:
            print("  [!] 已取消，跳过此阶段")
            return []

        # 只有 1 项时不需要线程池
        if total == 1:
            result = worker_fn(items[0])
            self._progress.advance(stage_idx, 1)
            self._progress.finish_stage(stage_idx)
            return [result]

        results: dict[int, Any] = {}
        futures: dict[Future, int] = {}

        with ThreadPoolExecutor(max_workers=min(self.max_workers, total)) as executor:
            self._executor = executor
            try:
                for i, item in enumerate(items):
                    if self.cancelled:
                        break
                    future = executor.submit(self._safe_worker, worker_fn, item, i)
                    futures[future] = i

                for future in as_completed(futures):
                    if self.cancelled and not future.running():
                        continue
                    idx = futures[future]
                    try:
                        results[idx] = future.result()
                    except Exception as e:
                        results[idx] = None
                        print(f"\n  [!] 批次 {idx + 1} 异常: {e}")
                    self._progress.advance(stage_idx, 1, f"批次 {idx + 1}/{total}")
            finally:
                self._executor = None

        self._progress.finish_stage(stage_idx)

        if preserve_order:
            return [results.get(i) for i in range(total) if i in results]
        return list(results.values())

    def _safe_worker(self, fn, item, idx):
        """带异常捕获和取消检查的 worker 包装"""
        if self.cancelled:
            return None
        return fn(item)

    def abort(self):
        """外部主动触发终止"""
        self._abort_event.set()
        self._progress.cancel()
        if self._executor:
            # 不等待，让 with 块自然清理
            pass
