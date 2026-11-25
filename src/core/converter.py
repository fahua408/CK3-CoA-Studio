"""Wrapper and async runner for coaConverter_windows.exe."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QProcess, QElapsedTimer, Signal


COLOR_MODES = ("Reduced", "Full", "Vanilla")


@dataclass
class ConvertParams:
    """Parameters passed to coaConverter_windows.exe."""

    source_path: Path
    destination_path: Optional[Path] = None
    resolution: int = 150
    color_mode: str = "Reduced"
    color_limit: int = 20
    landed_title: bool = False

    def resolve_destination(self) -> Path:
        if self.destination_path is not None:
            return self.destination_path
        return self.source_path.with_suffix(".txt")

    def build_args(self) -> list[str]:
        dest = self.resolve_destination()
        args = [
            "-s",
            str(self.source_path),
            "-d",
            str(dest),
            "-r",
            str(self.resolution),
            "-c",
            self.color_mode,
        ]
        if self.color_mode == "Reduced":
            args.extend(["-k", str(self.color_limit)])
        if self.landed_title:
            args.append("-t")
        return args

    def format_command(self, exe_path: str) -> str:
        parts = [f'"{exe_path}"']
        for arg in self.build_args():
            if " " in arg or "\\" in arg or "/" in arg:
                parts.append(f'"{arg}"')
            else:
                parts.append(arg)
        return " ".join(parts)


class ConverterRunner(QObject):
    """Runs coaConverter_windows.exe asynchronously without blocking the UI."""

    started_job = Signal(str, str)  # source_path, command_line
    output_received = Signal(str)
    finished_job = Signal(bool, str, str, float)  # ok, source_path, dest_path, elapsed_sec

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._process: Optional[QProcess] = None
        self._timer = QElapsedTimer()
        self._current_source = ""
        self._current_dest = ""
        self._stdout_buf: list[str] = []

    @property
    def is_running(self) -> bool:
        return (
            self._process is not None
            and self._process.state() != QProcess.ProcessState.NotRunning
        )

    def start(self, exe_path: str, params: ConvertParams) -> None:
        if self.is_running:
            raise RuntimeError("已有转换任务正在运行，请稍候。")

        exe = Path(exe_path)
        if not exe.is_file():
            raise FileNotFoundError(f"未找到转换工具: {exe_path}")
        if not params.source_path.is_file():
            raise FileNotFoundError(f"未找到源图片: {params.source_path}")

        dest = params.resolve_destination()
        dest.parent.mkdir(parents=True, exist_ok=True)

        self._current_source = str(params.source_path)
        self._current_dest = str(dest)
        self._stdout_buf.clear()

        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        proc.setWorkingDirectory(str(dest.parent))
        proc.readyReadStandardOutput.connect(self._on_ready_read)
        proc.finished.connect(self._on_finished)
        proc.errorOccurred.connect(self._on_error)

        self._process = proc
        self._timer.start()
        args = params.build_args()
        cmd_str = params.format_command(str(exe))
        self.started_job.emit(self._current_source, cmd_str)
        proc.start(str(exe), args)

    def cancel(self) -> None:
        if self._process and self.is_running:
            self._process.kill()

    def _on_ready_read(self) -> None:
        if not self._process:
            return
        raw = bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if raw:
            self._stdout_buf.append(raw)
            self.output_received.emit(raw)

    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        elapsed = self._timer.elapsed() / 1000.0
        ok = (
            exit_status == QProcess.ExitStatus.NormalExit
            and exit_code == 0
            and Path(self._current_dest).is_file()
        )
        if not ok and self._stdout_buf:
            self.output_received.emit(f"\n[退出码: {exit_code}]")
        self._cleanup()
        self.finished_job.emit(ok, self._current_source, self._current_dest, elapsed)

    def _on_error(self, error: QProcess.ProcessError) -> None:
        elapsed = self._timer.elapsed() / 1000.0
        self.output_received.emit(f"\n进程启动失败: {error.name}")
        self._cleanup()
        self.finished_job.emit(False, self._current_source, self._current_dest, elapsed)

    def _cleanup(self) -> None:
        if self._process:
            self._process.deleteLater()
            self._process = None
