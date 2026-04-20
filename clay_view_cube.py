import vtk

class ViewCube3D:
    """Cubo de navegação 3D real estilo Fusion 360 - renderizado como cubo 3D no VTK"""
    
    def __init__(self, main_renderer, render_window):
        self.main_renderer = main_renderer
        self.render_window = render_window
        
        # Criar renderer separado para o ViewCube
        self.cube_renderer = vtk.vtkRenderer()
        self.cube_renderer.SetLayer(1)  # Camada superior
        self.cube_renderer.SetBackground(0.95, 0.95, 0.95)  # Fundo claro
        
        # Configurar viewport (canto superior direito)
        self.update_viewport()
        
        # Adicionar renderer ao render window
        self.render_window.SetNumberOfLayers(2)
        self.render_window.AddRenderer(self.cube_renderer)
        
        # Estado de sincronização (definir ANTES dos métodos que os usam)
        self.sync_enabled = True
        self.interaction_sensitivity = 1.1  # Fator de velocidade aumentada (80%)
        
        # Estado atual
        self.current_view = 'FRONT'
        self.is_interacting = False
        self.last_mouse_pos = None
        
        # Definir vistas de câmera
        self.camera_views = {
            'FRONT': {'pos': (0, -5, 0), 'up': (0, 0, 1)},
            'BACK': {'pos': (0, 5, 0), 'up': (0, 0, 1)},
            'LEFT': {'pos': (-5, 0, 0), 'up': (0, 0, 1)},
            'RIGHT': {'pos': (5, 0, 0), 'up': (0, 0, 1)},
            'TOP': {'pos': (0, 0, 5), 'up': (0, 1, 0)},
            'BOTTOM': {'pos': (0, 0, -5), 'up': (0, -1, 0)},
        }
        
        # Criar geometria do cubo 3D
        self.create_cube_geometry()
        
        # Configurar interação customizada
        self.setup_custom_interactor()
        
    def update_viewport(self):
        """Atualiza viewport do cubo (canto superior direito)"""
        # Tamanho do cubo em pixels
        cube_size = 120
        
        # Obter tamanho da janela
        window_size = self.render_window.GetSize()
        width, height = window_size
        
        if width > 0 and height > 0:
            # Calcular posição normalizada (0-1)
            margin = 10
            x_max = (width - margin) / width
            y_max = (height - margin) / height
            x_min = (width - cube_size - margin) / width
            y_min = (height - cube_size - margin) / height
            
            # Definir viewport
            self.cube_renderer.SetViewport(x_min, y_min, x_max, y_max)
        
    def create_cube_geometry(self):
        """Cria geometria do cubo 3D com faces texturizadas"""
        # Criar cubo básico
        cube_source = vtk.vtkCubeSource()
        cube_source.SetXLength(2.0)
        cube_source.SetYLength(2.0) 
        cube_source.SetZLength(2.0)
        cube_source.Update()
        
        # Criar mapeamento de texturas para cada face
        self.create_face_textures()
        
        # Mapper
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(cube_source.GetOutputPort())
        
        # Actor do cubo
        self.cube_actor = vtk.vtkActor()
        self.cube_actor.SetMapper(mapper)
        
        # Propriedades do material
        prop = self.cube_actor.GetProperty()
        prop.SetColor(0.9, 0.9, 0.95)  # Cor base clara
        prop.SetSpecular(0.3)
        prop.SetSpecularPower(20)
        prop.SetAmbient(0.3)
        prop.SetDiffuse(0.7)
        
        # Adicionar ao renderer
        self.cube_renderer.AddActor(self.cube_actor)
        
        # Configurar câmera do cubo
        camera = self.cube_renderer.GetActiveCamera()
        camera.SetPosition(4, 4, 4)
        camera.SetFocalPoint(0, 0, 0)
        camera.SetViewUp(0, 0, 1)
        
        # Fixar zoom do cubo
        camera.SetParallelScale(1.5)
        camera.ParallelProjectionOn()  # Projeção paralela para evitar perspectiva
        
        self.cube_renderer.ResetCamera()
        
        # Iluminação suave
        light1 = vtk.vtkLight()
        light1.SetPosition(3, 3, 3)
        light1.SetFocalPoint(0, 0, 0)
        light1.SetColor(1, 1, 1)
        light1.SetIntensity(0.6)
        self.cube_renderer.AddLight(light1)
        
        # Luz de preenchimento
        light2 = vtk.vtkLight()
        light2.SetPosition(-2, -2, 2)
        light2.SetFocalPoint(0, 0, 0)
        light2.SetColor(1, 1, 1)
        light2.SetIntensity(0.3)
        self.cube_renderer.AddLight(light2)
        
        # Criar textos das faces
        self.create_face_labels()
        
        # Configurar interactor style específico para o cubo (apenas rotação)
        self.setup_cube_interactor_style()
    
    def create_face_textures(self):
        """Cria texturas para identificar as faces"""
        # Por enquanto, usando cores diferentes para cada face
        pass
    
    def create_face_labels(self):
        """Cria labels de texto para cada face"""
        # Posições das faces do cubo
        face_positions = {
            'FRONT': (0, -1.1, 0),
            'BACK': (0, 1.1, 0), 
            'LEFT': (-1.1, 0, 0),
            'RIGHT': (1.1, 0, 0),
            'TOP': (0, 0, 1.1),
            'BOTTOM': (0, 0, -1.1)
        }
        
        self.text_actors = {}
        
        for face, pos in face_positions.items():
            # Criar texto 3D
            text_source = vtk.vtkVectorText()
            text_source.SetText(face)
            
            # Mapper
            text_mapper = vtk.vtkPolyDataMapper()
            text_mapper.SetInputConnection(text_source.GetOutputPort())
            
            # Actor
            text_actor = vtk.vtkActor()
            text_actor.SetMapper(text_mapper)
            text_actor.SetPosition(pos)
            text_actor.SetScale(0.15, 0.15, 0.15)
            
            # Propriedades
            text_actor.GetProperty().SetColor(0.2, 0.2, 0.2)
            
            # Orientar texto para face
            if face == 'TOP':
                text_actor.RotateX(90)
            elif face == 'BOTTOM':
                text_actor.RotateX(-90)
            elif face == 'LEFT':
                text_actor.RotateZ(90)
            elif face == 'RIGHT':
                text_actor.RotateZ(-90)
            elif face == 'BACK':
                text_actor.RotateZ(180)
            
            self.text_actors[face] = text_actor
            self.cube_renderer.AddActor(text_actor)
    
    def setup_custom_interactor(self):
        """Configura interação customizada para sincronização"""
        self.picker = vtk.vtkCellPicker()
        self.picker.SetTolerance(0.01)
        
        # Conectar eventos de mouse para sincronização
        interactor = self.render_window.GetInteractor()
        interactor.AddObserver('LeftButtonPressEvent', self.on_left_button_press)
        interactor.AddObserver('LeftButtonReleaseEvent', self.on_left_button_release)
        interactor.AddObserver('MouseMoveEvent', self.on_mouse_move)
        interactor.AddObserver('MiddleButtonPressEvent', self.on_middle_button_press)
        
        # Configurar interactor style personalizado
        self.setup_main_camera_interactor()
        
    def setup_main_camera_interactor(self):
        """Configura interactor style personalizado para câmera principal"""
        style = vtk.vtkInteractorStyleTrackballCamera()
        
        # Ajustar sensibilidade de movimento (50% da velocidade normal)
        style.SetMotionFactor(self.interaction_sensitivity)
        
        interactor = self.render_window.GetInteractor()
        interactor.SetInteractorStyle(style)
        
        # Conectar eventos para sincronização - usar StartInteractionEvent para melhor responsividade
        style.AddObserver('InteractionEvent', self.on_main_camera_interaction)
        style.AddObserver('EndInteractionEvent', self.on_main_camera_interaction)
    
    def on_left_button_press(self, obj, event):
        """Trata pressionar botão esquerdo"""
        interactor = obj
        click_pos = interactor.GetEventPosition()
        self.last_mouse_pos = click_pos
        
        # Verificar se clique está na área do cubo
        if self.is_click_in_cube_area(click_pos):
            # Clique no cubo - ativar modo de interação do cubo
            self.picker.Pick(click_pos[0], click_pos[1], 0, self.cube_renderer)
            
            if self.picker.GetActor() == self.cube_actor:
                self.is_interacting = True
                # Desabilitar sincronização temporariamente para permitir controle manual
                self.sync_enabled = False
                print("🎯 Interação iniciada no cubo")
        else:
            # Clique fora do cubo - interação normal com cena principal
            self.is_interacting = False
    
    def on_left_button_release(self, obj, event):
        """Trata soltar botão esquerdo"""
        if self.is_interacting:
            # Finalizar interação com o cubo
            interactor = obj
            current_pos = interactor.GetEventPosition()
            
            # Reativar sincronização
            self.sync_enabled = True
            print("🔄 Sincronização reativada")
            
            # Verificar se foi clique rápido para mudança de vista
            if self.last_mouse_pos:
                dx = current_pos[0] - self.last_mouse_pos[0]
                dy = current_pos[1] - self.last_mouse_pos[1]
                distance = (dx*dx + dy*dy) ** 0.5
                
                # Se movimento foi pequeno, considerar como clique de mudança de vista
                if distance < 10:  # pixels
                    picked_pos = self.picker.GetPickPosition()
                    face = self.determine_clicked_face(picked_pos)
                    if face:
                        self.set_main_camera_view(face)
                        print(f"📷 Vista alterada para: {face}")
        
        self.is_interacting = False
        self.last_mouse_pos = None
    
    def on_mouse_move(self, obj, event):
        """Trata movimento do mouse - rotação do cubo ou sincronização"""
        interactor = obj
        current_pos = interactor.GetEventPosition()
        
        # Se está interagindo com o cubo, rotacionar a cena principal
        if self.is_interacting and self.last_mouse_pos:
            dx = current_pos[0] - self.last_mouse_pos[0]
            dy = current_pos[1] - self.last_mouse_pos[1]
            
            # Aplicar rotação na câmera principal baseada no movimento do mouse
            self.rotate_main_camera_from_cube(dx, dy)
            self.last_mouse_pos = current_pos
            
        # Se está interagindo com a cena principal, sincronizar cubo
        elif (self.sync_enabled and 
              hasattr(interactor, 'GetLeftButtonPressEvent') and 
              interactor.GetLeftButtonPressEvent() and 
              not self.is_interacting):
            
            self.sync_cube_with_main_camera()
    
    def on_middle_button_press(self, obj, event):
        """Desabilita zoom/pan no cubo, permite apenas na cena principal"""
        interactor = obj
        click_pos = interactor.GetEventPosition()
        
        # Se clique no cubo, ignorar (não permitir zoom/pan do cubo)
        if self.is_click_in_cube_area(click_pos):
            return
    
    def on_main_camera_interaction(self, obj, event):
        """Sincroniza cubo quando câmera principal muda"""
        if self.sync_enabled:
            # Sincronizar sempre que a câmera principal mudar
            self.sync_cube_with_main_camera()
    
    def is_click_in_cube_area(self, click_pos):
        """Verifica se o clique está na área do cubo"""
        # Obter viewport do cubo
        viewport = self.cube_renderer.GetViewport()
        window_size = self.render_window.GetSize()
        
        # Converter para coordenadas de pixel
        x_min = viewport[0] * window_size[0]
        y_min = viewport[1] * window_size[1] 
        x_max = viewport[2] * window_size[0]
        y_max = viewport[3] * window_size[1]
        
        x, y = click_pos
        return x_min <= x <= x_max and y_min <= y <= y_max
    
    def determine_clicked_face(self, picked_pos):
        """Determina qual face foi clicada baseada na posição"""
        x, y, z = picked_pos
        
        # Tolerância para determinar a face
        tol = 0.5
        
        if abs(x) > abs(y) and abs(x) > abs(z):
            return 'RIGHT' if x > 0 else 'LEFT'
        elif abs(y) > abs(x) and abs(y) > abs(z):
            return 'BACK' if y > 0 else 'FRONT'  
        else:
            return 'TOP' if z > 0 else 'BOTTOM'
    
    def set_main_camera_view(self, view_name):
        """Define a vista da câmera principal"""
        if view_name not in self.camera_views:
            return
            
        view_data = self.camera_views[view_name]
        camera_pos = view_data['pos']
        up_vector = view_data['up']
        
        # Obter câmera principal
        main_camera = self.main_renderer.GetActiveCamera()
        
        # Calcular ponto focal (centro da cena)
        bounds = [0, 0, 0, 0, 0, 0]
        if self.main_renderer.GetActors().GetNumberOfItems() > 0:
            self.main_renderer.ComputeVisiblePropBounds(bounds)
            focal_point = [
                (bounds[0] + bounds[1]) / 2,
                (bounds[2] + bounds[3]) / 2,
                (bounds[4] + bounds[5]) / 2
            ]
        else:
            focal_point = [0, 0, 0]
        
        # Distância da câmera
        distance = 100
        final_camera_pos = [
            focal_point[0] + camera_pos[0] * distance,
            focal_point[1] + camera_pos[1] * distance, 
            focal_point[2] + camera_pos[2] * distance
        ]
        
        # Configurar câmera principal
        main_camera.SetPosition(final_camera_pos)
        main_camera.SetFocalPoint(focal_point)
        main_camera.SetViewUp(up_vector)
        
        # Reset do zoom
        self.main_renderer.ResetCamera()
        
        # Renderizar
        self.render_window.Render()
        
        self.current_view = view_name
        
        # Sincronizar cubo com nova posição da câmera
        if self.sync_enabled:
            self.sync_cube_with_main_camera()
    
    def sync_cube_with_main_camera(self):
        """Sincroniza orientação do cubo com a câmera principal"""
        if not hasattr(self, 'cube_actor'):
            return
            
        # Obter orientação da câmera principal
        main_camera = self.main_renderer.GetActiveCamera()
        
        # Calcular orientação do cubo baseada na câmera
        position = main_camera.GetPosition()
        focal_point = main_camera.GetFocalPoint()
        up_vector = main_camera.GetViewUp()
        
        # Calcular vetor de visão
        view_vector = [
            position[0] - focal_point[0],
            position[1] - focal_point[1], 
            position[2] - focal_point[2]
        ]
        
        # Normalizar
        length = (view_vector[0]**2 + view_vector[1]**2 + view_vector[2]**2) ** 0.5
        if length > 0:
            view_vector = [v/length for v in view_vector]
        
        # Configurar câmera do cubo para mostrar mesma orientação
        cube_camera = self.cube_renderer.GetActiveCamera()
        
        # Posicionar câmera do cubo baseada na orientação principal
        cube_distance = 4.0  # Distância fixa do cubo
        cube_pos = [
            view_vector[0] * cube_distance,
            view_vector[1] * cube_distance,
            view_vector[2] * cube_distance
        ]
        
        cube_camera.SetPosition(cube_pos)
        cube_camera.SetFocalPoint(0, 0, 0)
        cube_camera.SetViewUp(up_vector)
        
        # Manter zoom fixo do cubo
        cube_camera.SetParallelScale(1.5)
        
        # Forçar atualização da renderização do cubo
        self.cube_renderer.Modified()
        self.render_window.Render()
    
    def rotate_main_camera_from_cube(self, delta_x, delta_y):
        """Rotaciona a câmera principal baseada no movimento do mouse no cubo"""
        main_camera = self.main_renderer.GetActiveCamera()
        
        # Aplicar rotação com sensibilidade ajustada
        sensitivity = self.interaction_sensitivity * 0.5  # Reduzir um pouco para controle fino
        
        # Rotação horizontal (azimute)
        main_camera.Azimuth(-delta_x * sensitivity)
        
        # Rotação vertical (elevação)  
        main_camera.Elevation(delta_y * sensitivity)
        
        # Manter câmera ortogonal
        main_camera.OrthogonalizeViewUp()
        
        # Renderizar cena principal
        self.main_renderer.ResetCameraClippingRange()
        self.render_window.Render()
        
        print(f"🔄 Rotação aplicada: dx={delta_x}, dy={delta_y}")
    
    def determine_clicked_face(self, world_pos):
        """Determina qual face do cubo foi clicada"""
        if not world_pos:
            return None
            
        x, y, z = world_pos
        
        # Tolerância para determinar face
        tolerance = 0.1
        
        # Determinar face baseada na coordenada com maior valor absoluto
        abs_x, abs_y, abs_z = abs(x), abs(y), abs(z)
        
        if abs_x > abs_y and abs_x > abs_z:
            return "right" if x > 0 else "left"
        elif abs_y > abs_z:
            return "back" if y > 0 else "front"
        else:
            return "top" if z > 0 else "bottom"
    
    def set_main_camera_view(self, face):
        """Define vista da câmera principal baseada na face clicada"""
        main_camera = self.main_renderer.GetActiveCamera()
        
        # Calcular centro da cena dinamicamente (onde o objeto realmente está)
        bounds = [0, 0, 0, 0, 0, 0]
        if self.main_renderer.GetActors().GetNumberOfItems() > 0:
            self.main_renderer.ComputeVisiblePropBounds(bounds)
            scene_center = [
                (bounds[0] + bounds[1]) / 2,
                (bounds[2] + bounds[3]) / 2,
                (bounds[4] + bounds[5]) / 2
            ]
        else:
            # Fallback para centro padrão
            scene_center = [0, 0, 0]
        
        print(f"🎯 Centro da cena detectado: {scene_center}")
        
        # Definir direções relativas de câmera para cada face
        camera_directions = {
            "front": (0, -1, 0, 0, 0, 1),    # Olhar de frente para trás, up = Z
            "back": (0, 1, 0, 0, 0, 1),      # Olhar de trás para frente, up = Z
            "left": (-1, 0, 0, 0, 0, 1),     # Olhar da esquerda, up = Z
            "right": (1, 0, 0, 0, 0, 1),     # Olhar da direita, up = Z
            "top": (0, 0, 1, 0, 1, 0),       # Olhar de cima, up = Y
            "bottom": (0, 0, -1, 0, 1, 0)    # Olhar de baixo, up = Y
        }
        
        if face in camera_directions:
            dir_x, dir_y, dir_z, up_x, up_y, up_z = camera_directions[face]
            
            # MANTER distância atual da câmera para preservar zoom
            current_pos = main_camera.GetPosition()
            current_focal = main_camera.GetFocalPoint()
            
            # Calcular distância atual
            current_distance = ((current_pos[0] - current_focal[0])**2 + 
                              (current_pos[1] - current_focal[1])**2 + 
                              (current_pos[2] - current_focal[2])**2) ** 0.5
            
            # Se distância muito pequena, usar distância padrão
            if current_distance < 10:
                current_distance = 100
            
            print(f"📏 Mantendo distância atual: {current_distance:.1f}")
            
            # Posição da câmera mantendo a distância atual
            camera_pos = [
                scene_center[0] + dir_x * current_distance,
                scene_center[1] + dir_y * current_distance,
                scene_center[2] + dir_z * current_distance
            ]
            
            print(f"📷 Vista {face}: câmera em {camera_pos}, focando {scene_center}")
            
            # Configurar câmera
            main_camera.SetPosition(camera_pos)
            main_camera.SetFocalPoint(scene_center)
            main_camera.SetViewUp(up_x, up_y, up_z)
            
            # Resetar clipping e renderizar
            self.main_renderer.ResetCameraClippingRange()
            self.render_window.Render()
            
            # Sincronizar cubo com nova vista
            self.sync_cube_with_main_camera()
    
    def sync_main_camera_with_cube_rotation(self, delta_x, delta_y):
        """Sincroniza câmera principal com rotação do cubo"""
        if not self.sync_enabled:
            return
            
        main_camera = self.main_renderer.GetActiveCamera()
        
        # Aplicar rotação suave à câmera principal
        sensitivity = self.interaction_sensitivity
        
        # Rotação horizontal (azimute)
        main_camera.Azimuth(delta_x * sensitivity * 0.5)
        
        # Rotação vertical (elevação)
        main_camera.Elevation(delta_y * sensitivity * 0.5)
        
        # Manter câmera ortogonal
        main_camera.OrthogonalizeViewUp()
        
        # Renderizar cena principal
        self.main_renderer.ResetCameraClippingRange()
        
        # Sincronizar cubo
        self.sync_cube_with_main_camera()
    
    def setup_cube_interactor_style(self):
        """Configura estilo de interação específico para o cubo (apenas rotação)"""
        # Criar estilo customizado que bloqueia zoom/pan no cubo
        cube_style = CubeOnlyRotationStyle()
        cube_style.SetDefaultRenderer(self.cube_renderer)
        cube_style.view_cube = self
        
    def disable_cube_zoom_pan(self):
        """Desabilita zoom e pan no cubo, mantendo apenas rotação"""
        cube_camera = self.cube_renderer.GetActiveCamera()
        
        # Sempre manter zoom fixo
        cube_camera.SetParallelScale(1.5)
        
        # Sempre manter posição focal no centro
        cube_camera.SetFocalPoint(0, 0, 0)
    
    def update_size(self):
        """Atualiza tamanho e posição do cubo quando janela redimensiona"""
        self.update_viewport()
        self.disable_cube_zoom_pan()  # Garantir que zoom/pan permaneçam desabilitados
        self.render_window.Render()


class CubeOnlyRotationStyle(vtk.vtkInteractorStyleTrackballCamera):
    """Estilo de interação que permite apenas rotação no ViewCube"""
    
    def __init__(self):
        super().__init__()
        self.view_cube = None
        
        # Desabilitar todas as interações exceto rotação
        self.SetMotionFactor(0.3)  # Movimento mais lento
        
    def OnMouseMove(self):
        """Override para controlar movimento do mouse"""
        if self.GetInteractor() and self.view_cube:
            # Verificar se está na área do cubo
            pos = self.GetInteractor().GetEventPosition()
            
            if self.view_cube.is_click_in_cube_area(pos):
                # No cubo - apenas rotação, bloquear zoom/pan
                if self.GetState() == vtk.vtkInteractorStyleTrackballCamera.VTKIS_ROTATE:
                    super().OnMouseMove()
                    # Garantir que zoom/pan não foram alterados
                    self.view_cube.disable_cube_zoom_pan()
            else:
                # Fora do cubo - interação normal
                super().OnMouseMove()
    
    def OnMiddleButtonDown(self):
        """Bloquear pan no cubo"""
        if self.view_cube:
            pos = self.GetInteractor().GetEventPosition()
            if not self.view_cube.is_click_in_cube_area(pos):
                super().OnMiddleButtonDown()
    
    def OnRightButtonDown(self):
        """Bloquear zoom no cubo"""
        if self.view_cube:
            pos = self.GetInteractor().GetEventPosition()
            if not self.view_cube.is_click_in_cube_area(pos):
                super().OnRightButtonDown()
    
    def OnMouseWheelForward(self):
        """Bloquear wheel zoom no cubo"""
        if self.view_cube:
            pos = self.GetInteractor().GetEventPosition()
            if not self.view_cube.is_click_in_cube_area(pos):
                super().OnMouseWheelForward()
    
    def OnMouseWheelBackward(self):
        """Bloquear wheel zoom no cubo"""
        if self.view_cube:
            pos = self.GetInteractor().GetEventPosition()
            if not self.view_cube.is_click_in_cube_area(pos):
                super().OnMouseWheelBackward()
