"""进度追踪器"""

import sys
import threading
import time


class ProgressTracker:
    """线程安全的进度追踪器，支持阶段管理和批次进度"""

    def __init__(self, stages: list[str]):
        self._lock = threading.Lock()
        self._stages = stages
        self._total_stages = len(stages)
        self._current_stage = -1
        self._stage_totals: dict[int, int] = {}
        self._stage_dones: dict[int, int] = {}
        self._stage_names: dict[int, str] = {}
        self._start_time = time.time()
        self._cancelled = False
        self._last_line_len = 0
        self._stage_start_times: dict[int, float] = {}
        self._stage_durations: dict[int, float] = {}

    def cancel(self):
        with self._lock:
            self._cancelled = True

    @property
    def cancelled(self) -> bool:
        with self._lock:
            return self._cancelled

    @property
    def stage_timings(self) -> dict[int, float]:
        with self._lock:
            return dict(self._stage_durations)

    def start_stage(self, stage_idx: int, name: str, total: int = 0):
        """开始一个新阶段"""
        with self._lock:
            self._current_stage = stage_idx
            self._stage_totals[stage_idx] = total
            self._stage_dones[stage_idx] = 0
            self._stage_names[stage_idx] = name
            self._stage_start_times[stage_idx] = time.time()
        self._print_stage_header(stage_idx, name, total)

    def advance(self, stage_idx: int, count: int = 1, detail: str = ""):
        """推进当前阶段进度"""
        with self._lock:
            if self._cancelled:
                return
            self._stage_dones[stage_idx] = self._stage_dones.get(stage_idx, 0) + count
            done = self._stage_dones[stage_idx]
            total = self._stage_totals.get(stage_idx, 0)
        self._print_progress(stage_idx, done, total, detail)

    def finish_stage(self, stage_idx: int, detail: str = ""):
        """标记阶段完成"""
        with self._lock:
            total = self._stage_totals.get(stage_idx, 0)
            if total > 0:
                self._stage_dones[stage_idx] = total
            if stage_idx in self._stage_start_times:
                self._stage_durations[stage_idx] = time.time() - self._stage_start_times[stage_idx]
        self._clear_line()
        elapsed = time.time() - self._start_time
        suffix = f" ({detail})" if detail else ""
        print(f"  阶段 {stage_idx + 1}/{self._total_stages} 完成{suffix}  [累计 {elapsed:.1f}s]")

    def summary(self):
        """打印最终汇总"""
        elapsed = time.time() - self._start_time
        if self._stage_durations:
            print("\n  阶段耗时:")
            for idx in sorted(self._stage_durations):
                dur = self._stage_durations[idx]
                name = self._stage_names.get(idx, f"阶段{idx + 1}")
                pct = dur / elapsed * 100 if elapsed > 0 else 0
                print(f"    {idx + 1}. {name}    {dur:.1f}s ({pct:.0f}%)")
        print(f"\n  总耗时: {elapsed:.1f}s")

    def _print_stage_header(self, stage_idx: int, name: str, total: int):
        total_str = f"（共 {total} 项）" if total > 0 else ""
        print(f"\n  [{stage_idx + 1}/{self._total_stages}] {name}{total_str}")

    @staticmethod
    def _make_bar(pct: float, width: int = 30) -> str:
        filled = int(width * pct)
        return "#" * filled + "-" * (width - filled)

    def _print_progress(self, stage_idx: int, done: int, total: int, detail: str = ""):
        if total > 0:
            pct = min(done / total, 1.0)
            bar = self._make_bar(pct)
            line = f"    [{bar}] {done}/{total} ({pct:.0%})"
        else:
            line = f"    已处理 {done} 项"

        if detail:
            line += f"  {detail}"

        self._write_line(line)

    def _write_line(self, line: str):
        """覆写当前行（控制台动画效果）"""
        pad = max(0, self._last_line_len - len(line))
        sys.stdout.write(f"\r{line}{' ' * pad}")
        sys.stdout.flush()
        self._last_line_len = len(line)

    def _clear_line(self):
        if self._last_line_len > 0:
            sys.stdout.write(f"\r{' ' * (self._last_line_len + 2)}\r")
            sys.stdout.flush()
            self._last_line_len = 0
