from PyQt5.QtCore import QThread, pyqtSignal
from clay_gcode_generator_definitive import ClayPrintSettings, ClayGCodeGenerator

# Alias para compatibilidade
DefinitiveClayGCodeGenerator = ClayGCodeGenerator

class GCodeGenerationThread(QThread):
    """Thread simples para gerar G-code sem travar a UI"""
    progress = pyqtSignal(int)
    finished_generation = pyqtSignal(str, list, dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, polydata, settings: ClayPrintSettings, parent=None):
        super().__init__(parent)
        self.polydata = polydata
        self.settings = settings

    def run(self):
        try:
            self.progress.emit(10)
            generator = DefinitiveClayGCodeGenerator(self.settings)
            gcode_data = generator.generate_gcode_data(self.polydata, for_visualization=True)
            self.progress.emit(100)
            metadata = getattr(generator, 'last_generation_metadata', {})
            self.finished_generation.emit("OK", gcode_data, metadata)
        except Exception as e:
            self.error_occurred.emit(str(e))
