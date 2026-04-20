import vtk
from PyQt5.QtCore import QTimer
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

from clay_view_cube import ViewCube3D


class ClayVTKViewport:
    """Empacota configuração do VTK (renderer + cubo de navegação)."""

    def __init__(self, parent=None) -> None:
        self.widget = QVTKRenderWindowInteractor(parent)
        self.renderer = vtk.vtkRenderer()
        self.renderer.SetBackground(0.1, 0.1, 0.2)
        self.widget.GetRenderWindow().AddRenderer(self.renderer)
        self.interactor = self.widget.GetRenderWindow().GetInteractor()

        camera = self.renderer.GetActiveCamera()
        camera.SetPosition(50, 50, 50)
        camera.SetFocalPoint(0, 0, 0)
        camera.SetViewUp(0, 0, 1)

        self.view_cube_3d = ViewCube3D(self.renderer, self.widget.GetRenderWindow())

        self.resize_timer = QTimer()
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.update_view_cube_size)

        self.widget.Initialize()
        self.widget.Start()

    def render(self) -> None:
        self.widget.GetRenderWindow().Render()

    def request_resize_update(self, delay_ms: int = 100) -> None:
        self.resize_timer.start(delay_ms)

    def update_view_cube_size(self) -> None:
        if self.view_cube_3d:
            self.view_cube_3d.update_size()

    def reset_view(self) -> None:
        self.renderer.ResetCamera()
        self.render()

    def set_quick_view(self, view_name: str) -> None:
        if not self.view_cube_3d:
            return
        mapping = {
            'FRONT': 'front',
            'BACK': 'back',
            'LEFT': 'left',
            'RIGHT': 'right',
            'TOP': 'top',
            'BOTTOM': 'bottom',
        }
        mapped = mapping.get(view_name.upper(), view_name.lower())
        self.view_cube_3d.set_main_camera_view(mapped)

    def finalize(self) -> None:
        self.widget.Finalize()
