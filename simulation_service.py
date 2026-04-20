from typing import Optional

from PyQt5.QtCore import QObject, pyqtSignal

from clay_simulation_thread import GCodeGenerationThread
from clay_gcode_generator_definitive import ClayPrintSettings


class SimulationService(QObject):
    """Gerencia ciclo de vida da thread de geração de G-code."""

    progress = pyqtSignal(int)
    finished = pyqtSignal(str, list, dict)
    error = pyqtSignal(str)
    running_changed = pyqtSignal(bool)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._thread: Optional[GCodeGenerationThread] = None

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.isRunning())

    def start(self, polydata, settings: ClayPrintSettings) -> None:
        if self.is_running():
            return
        self._thread = GCodeGenerationThread(polydata, settings)
        self._thread.progress.connect(self.progress.emit)
        self._thread.finished_generation.connect(self._handle_finished)
        self._thread.error_occurred.connect(self._handle_error)
        self._thread.start()
        self.running_changed.emit(True)

    def stop(self) -> None:
        if self._thread and self._thread.isRunning():
            self._thread.requestInterruption()
            self._thread.wait()
        self._thread = None
        self.running_changed.emit(False)

    def _handle_finished(self, message: str, gcode_data: list, metadata: dict) -> None:
        self.running_changed.emit(False)
        self.finished.emit(message, gcode_data, metadata or {})
        self._thread = None

    def _handle_error(self, error_message: str) -> None:
        self.running_changed.emit(False)
        self.error.emit(error_message)
        self._thread = None
