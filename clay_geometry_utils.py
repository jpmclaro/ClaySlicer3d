import vtk
import numpy as np
from vtk.util import numpy_support
import math
import re

def separate_micro_spiral_points(gcode_data):
    """Separa pontos do skirt, ponto central, micro espiral, base+arco, paredes e taper via máquina de estados.
    Retorna: (skirt_points, center_points, micro_points, base_arc_points, wall_points, taper_points, base_segments)
    """
    if not gcode_data:
        return [], [], [], [], [], [], []
    skirt_points = []
    center_points = []
    micro_spiral_points = []
    base_arc_points = []
    wall_points = []
    taper_points = []
    
    # Segmentos da base com metadados de altura/largura
    base_segments = []
    # Rastrear parâmetros da camada atual
    current_layer_h = None
    current_layer_w = None
    
    current_base_segment = {'points': [], 'type': 'normal', 'height': None, 'width': None}
    
    current_pos = [0.0, 0.0, 0.0]
    center_start_pos = None
    is_parametric_mode = False

    # Fases: 'none' | 'skirt' | 'center' | 'micro' | 'basearc' | 'walls' | 'taper' | 'done'
    phase = 'none'

    for command in gcode_data:
        # Detectar parâmetros de camada da base
        if "; BASE_LAYER_PARAMS:" in command:
            # Ex: ; BASE_LAYER_PARAMS: FIRST_LAYER (H=5.0, W=2.0)
            h_match = re.search(r'H=([\d\.]+)', command)
            w_match = re.search(r'W=([\d\.]+)', command)
            if h_match and w_match:
                h_val = float(h_match.group(1))
                w_val = float(w_match.group(1))
                
                current_layer_h = h_val
                current_layer_w = w_val
                
                # Se o segmento atual tem pontos, salva ele e inicia um novo
                if current_base_segment['points']:
                    # ⭐ CORREÇÃO DE GAP: O novo segmento deve começar onde o anterior terminou
                    last_pt = current_base_segment['points'][-1]
                    base_segments.append(current_base_segment)
                    # Iniciar novo segmento com o último ponto para garantir continuidade visual
                    current_base_segment = {'points': [last_pt], 'type': 'normal', 'height': h_val, 'width': w_val}
                else:
                    # Se não tem pontos, apenas atualiza os parâmetros
                    current_base_segment['height'] = h_val
                    current_base_segment['width'] = w_val
                    current_base_segment['type'] = 'normal'
            continue

        # Detectar início de rampa
        if "; RAMP_START:" in command:
            hs_match = re.search(r'H_start=([\d\.]+)', command)
            he_match = re.search(r'H_end=([\d\.]+)', command)
            ws_match = re.search(r'W_start=([\d\.]+)', command)
            we_match = re.search(r'W_end=([\d\.]+)', command)
            
            if hs_match and he_match:
                # Fechar segmento atual
                if current_base_segment['points']:
                    last_pt = current_base_segment['points'][-1]
                    base_segments.append(current_base_segment)
                    # Iniciar segmento de rampa
                    current_base_segment = {
                        'points': [last_pt], 
                        'type': 'ramp',
                        'h_start': float(hs_match.group(1)),
                        'h_end': float(he_match.group(1)),
                        'w_start': float(ws_match.group(1)) if ws_match else (current_layer_w or 1.0),
                        'w_end': float(we_match.group(1)) if we_match else (current_layer_w or 1.0),
                    }
                else:
                    current_base_segment = {
                        'points': [], 
                        'type': 'ramp',
                        'h_start': float(hs_match.group(1)),
                        'h_end': float(he_match.group(1)),
                        'w_start': float(ws_match.group(1)) if ws_match else (current_layer_w or 1.0),
                        'w_end': float(we_match.group(1)) if we_match else (current_layer_w or 1.0),
                    }
            continue

        # Detectar fim de rampa
        if "; RAMP_END" in command:
            # Fechar segmento de rampa
            if current_base_segment['points']:
                last_pt = current_base_segment['points'][-1]
                base_segments.append(current_base_segment)
                # Retomar segmento normal com parâmetros da camada atual
                current_base_segment = {
                    'points': [last_pt],
                    'type': 'normal',
                    'height': current_layer_h,
                    'width': current_layer_w
                }
            continue

        if "; SKIRT_START" in command:
            phase = 'skirt'
            continue
        elif "; PARAMETRIC_MODE_START" in command:
            is_parametric_mode = True
            continue
        elif "; SKIRT_END" in command:
            phase = 'none'
            continue
        if "; CENTER_POINT_START" in command:
            phase = 'center'
            # Forçar captura do próximo movimento sem extrusão como ponto inicial
            center_start_pos = None
            continue
        elif "; CENTER_POINT_END" in command:
            # Garantir ao menos 2 pontos
            if len(center_points) == 1 and center_start_pos is not None:
                center_points.insert(0, center_start_pos[:])
            phase = 'none'
            continue
        if "; MICRO_SPIRAL_START" in command:
            phase = 'micro'
            continue
        elif "; MICRO_SPIRAL_END" in command:
            # Após micro, normalmente entramos na espiral principal
            phase = 'none'
            continue
        elif "; MAIN_SPIRAL_START" in command:
            phase = 'basearc'
            continue
        elif "; MAIN_SPIRAL_END" in command:
            # Ainda queremos capturar o ARCO até WALLS_START
            phase = 'basearc'
            continue
        elif "; WALLS_START" in command:
            # ⭐ TRANSIÇÃO VISUAL: Adicionar último ponto da base como primeiro da parede
            # Isso garante continuidade visual mesmo sendo geometrias separadas
            if base_arc_points and not wall_points:
                wall_points.append(base_arc_points[-1][:])
            phase = 'walls'
            continue
        elif "; WALLS_END" in command:
            phase = 'post_walls'  # Não 'done' - pode ter taper!
            continue
        elif "; TAPER_START" in command:
            phase = 'taper'
            continue
        elif "; TAPER_END" in command:
            phase = 'done'
            continue

        # Processar comandos de movimento com extrusão
        if 'G1' in command and 'E' in command:
            # Extrair coordenadas
            parts = command.split()
            x, y, z = current_pos[:]

            for part in parts:
                if part.startswith('X'):
                    try:
                        x = float(part[1:])
                    except ValueError:
                        continue
                elif part.startswith('Y'):
                    try:
                        y = float(part[1:])
                    except ValueError:
                        continue
                elif part.startswith('Z'):
                    try:
                        z = float(part[1:])
                    except ValueError:
                        continue

            new_pos = [x, y, z]

            # Só adiciona se houve mudança real de posição (ignora retrações E apenas)
            if new_pos != current_pos:
                current_pos = new_pos

                # Classificação por fase
                if phase == 'skirt':
                    skirt_points.append(current_pos[:])
                elif phase == 'center':
                    center_points.append(current_pos[:])
                elif phase == 'micro':
                    micro_spiral_points.append(current_pos[:])
                elif phase == 'walls':
                    wall_points.append(current_pos[:])
                elif phase == 'taper':
                    taper_points.append(current_pos[:])
                elif phase in ('basearc', 'none', 'post_walls'):
                    # 'none' cobre o período entre fim da micro e início da principal
                    # 'post_walls' cobre o período entre WALLS_END e TAPER_START
                    base_arc_points.append(current_pos[:])
                    # Adicionar também ao segmento atual da base (para renderização com altura correta)
                    current_base_segment['points'].append(current_pos[:])
                else:
                    # phase == 'done' → ignorar qualquer extrusão posterior
                    pass
            # Se estamos no centro e ainda não registramos o ponto inicial, use posição anterior
            if phase == 'center' and len(center_points) == 1 and center_start_pos is not None:
                # Inserir como primeiro ponto para formar segmento vertical
                center_points.insert(0, center_start_pos[:])
            
            continue

        # Atualizar posição em movimentos sem extrusão (G0 ou G1 sem E)
        if command.startswith('G0') or (command.startswith('G1') and 'E' not in command):
            parts = command.split()
            x, y, z = current_pos[:]
            for part in parts:
                if part.startswith('X'):
                    try:
                        x = float(part[1:])
                    except ValueError:
                        continue
                elif part.startswith('Y'):
                    try:
                        y = float(part[1:])
                    except ValueError:
                        continue
                elif part.startswith('Z'):
                    try:
                        z = float(part[1:])
                    except ValueError:
                        continue
            current_pos = [x, y, z]
            # Se estamos na fase central e ainda não temos ponto inicial confiável, capture-o
            if phase == 'center' and center_start_pos is None:
                center_start_pos = current_pos[:]
            continue

    # Adicionar último segmento da base se houver pontos
    if current_base_segment['points']:
        base_segments.append(current_base_segment)

    print(f"🔍 Pontos separados: ponto={len(center_points)}, micro={len(micro_spiral_points)}, base+arco={len(base_arc_points)}, paredes={len(wall_points)}, segs_base={len(base_segments)}")
    return skirt_points, center_points, micro_spiral_points, base_arc_points, wall_points, taper_points, base_segments

def create_continuous_extrusion_cord(gcode_data, width, height):
    """Cria cordão contínuo seguindo exatamente as coordenadas do G-code"""
    try:
        print("🔧 Criando cordão de extrusão...")
        
        # Extrair todos os pontos de extrusão de forma simples e robusta
        points = []
        current_pos = [0.0, 0.0, 0.0]
        
        for command in gcode_data:
            if 'G1' in command and 'E' in command:
                # Extrair coordenadas usando regex
                x_match = re.search(r'X([-+]?\d*\.?\d+)', command)
                y_match = re.search(r'Y([-+]?\d*\.?\d+)', command)
                z_match = re.search(r'Z([-+]?\d*\.?\d+)', command)
                
                new_pos = current_pos.copy()
                if x_match:
                    new_pos[0] = float(x_match.group(1))
                if y_match:
                    new_pos[1] = float(y_match.group(1))
                if z_match:
                    new_pos[2] = float(z_match.group(1))
                
                if new_pos != current_pos:
                    points.append(new_pos.copy())
                    
                current_pos = new_pos
        
        if len(points) < 2:
            print("❌ Poucos pontos de extrusão")
            return None
            
        print(f"   • Pontos de extrusão: {len(points)}")
        
        # Mostrar análise geométrica
        x_coords = [p[0] for p in points]
        y_coords = [p[1] for p in points] 
        z_coords = [p[2] for p in points]
        
        print(f"   • Variação X: {min(x_coords):.1f} → {max(x_coords):.1f}mm")
        print(f"   • Variação Y: {min(y_coords):.1f} → {max(y_coords):.1f}mm")
        print(f"   • Variação Z: {min(z_coords):.1f} → {max(z_coords):.1f}mm")
        
        # Criar geometria VTK robusta
        vtk_points = vtk.vtkPoints()
        lines = vtk.vtkCellArray()
        
        for point in points:
            vtk_points.InsertNextPoint(point)
            
        # Linha contínua conectando todos os pontos
        lines.InsertNextCell(len(points))
        for i in range(len(points)):
            lines.InsertCellPoint(i)
            
        # Polydata
        polydata = vtk.vtkPolyData()
        polydata.SetPoints(vtk_points)
        polydata.SetLines(lines)
        
        # Criar tubo com seção transversal apropriada
        width_height_ratio = width / height
        print(f"   • Proporção largura/altura: {width_height_ratio:.2f}")
        
        if width_height_ratio <= 1.3:  # Aproximadamente circular
            # Usar raio médio para perfis quase circulares
            radius = (width + height) / 4.0
            tube = vtk.vtkTubeFilter()
            tube.SetInputData(polydata)
            tube.SetRadius(radius)
            tube.SetNumberOfSides(12)
            tube.Update()
            result = tube.GetOutput()
            print(f"   • Perfil: Circular (raio {radius:.2f}mm)")
        else:  # Seção elíptica - Criar tubo elíptico REAL
            # Usar método de varredura manual da elipse
            result = create_elliptical_tube(polydata, width, height)
            print(f"   • Perfil: Elíptico REAL ({width:.1f}x{height:.1f}mm)")
        
        print(f"✅ Cordão criado: {result.GetNumberOfPoints()} pontos, {result.GetNumberOfCells()} células")
        return result
        
    except Exception as e:
        print(f"❌ Erro ao criar cordão: {e}")
        import traceback
        traceback.print_exc()
        return None

def create_elliptical_tube(path_polydata: vtk.vtkPolyData, width: float, height: float) -> vtk.vtkPolyData:
    """Cria tubo com seção transversal elíptica REAL varrendo elipse ao longo do caminho (Otimizado com NumPy)"""
    try:
        print(f"   • Criando tubo elíptico REAL {width:.1f}x{height:.1f}mm (Otimizado)")
        
        # Extrair pontos do caminho
        points = path_polydata.GetPoints()
        n_points = points.GetNumberOfPoints()
        
        if n_points < 2:
            raise ValueError("Caminho deve ter ao menos 2 pontos")
            
        # Converter pontos VTK para NumPy
        path_points = numpy_support.vtk_to_numpy(points.GetData())
        
        # Parâmetros da elipse
        a = width / 2.0   # Semi-eixo maior (largura/2)
        b = height / 2.0  # Semi-eixo menor (altura/2) 
        n_sides = 32      # Qualidade da elipse
        
        # 1. Calcular tangentes (vetorizado)
        tangents = np.zeros_like(path_points)
        tangents[0] = path_points[1] - path_points[0]
        tangents[-1] = path_points[-1] - path_points[-2]
        tangents[1:-1] = path_points[2:] - path_points[:-2]
        
        # Normalizar tangentes
        norms = np.linalg.norm(tangents, axis=1, keepdims=True)
        norms[norms < 1e-12] = 1.0
        tangents /= norms
        
        # 2. Calcular frames (normais e binormais)
        up_world = np.array([0.0, 0.0, 1.0])
        
        # Verificar alinhamento com up_world
        dots = np.abs(np.dot(tangents, up_world))
        ups = np.tile(up_world, (n_points, 1))
        ups[dots > 0.95] = np.array([0.0, 1.0, 0.0])
        
        normals = np.cross(ups, tangents)
        n_norms = np.linalg.norm(normals, axis=1, keepdims=True)
        n_norms[n_norms < 1e-12] = 1.0
        normals /= n_norms
        
        binormals = np.cross(tangents, normals)
        b_norms = np.linalg.norm(binormals, axis=1, keepdims=True)
        b_norms[b_norms < 1e-12] = 1.0
        binormals /= b_norms
        
        # 3. Gerar pontos da elipse
        thetas = np.linspace(0, 2*np.pi, n_sides, endpoint=False)
        cos_thetas = np.cos(thetas)
        sin_thetas = np.sin(thetas)
        
        # Broadcasting: P + a*cos*N + b*sin*B
        P = path_points[:, np.newaxis, :]
        N = normals[:, np.newaxis, :]
        B = binormals[:, np.newaxis, :]
        
        term_N = a * cos_thetas[np.newaxis, :, np.newaxis] * N
        term_B = b * sin_thetas[np.newaxis, :, np.newaxis] * B
        
        tube_points_np = P + term_N + term_B
        tube_points_flat = tube_points_np.reshape(-1, 3)
        
        # 4. Criar VTK Points
        vtk_points = vtk.vtkPoints()
        vtk_points.SetData(numpy_support.numpy_to_vtk(tube_points_flat, deep=1))
        
        # 5. Gerar Células (Quads)
        i = np.arange(n_points - 1)
        j = np.arange(n_sides)
        I, J = np.meshgrid(i, j, indexing='ij')
        
        J_next = (J + 1) % n_sides
        
        v00 = I * n_sides + J
        v01 = I * n_sides + J_next
        v11 = (I + 1) * n_sides + J_next
        v10 = (I + 1) * n_sides + J
        
        quads = np.stack([v00, v01, v11, v10], axis=-1)
        quads_flat = quads.reshape(-1, 4)
        
        n_cells = quads_flat.shape[0]
        # Formato VTK: [n_pts, id0, id1, id2, id3]
        cells_data = np.column_stack([np.full(n_cells, 4, dtype=np.int64), quads_flat])
        cells_data_flat = cells_data.flatten()
        
        cells = vtk.vtkCellArray()
        cells.SetCells(n_cells, numpy_support.numpy_to_vtkIdTypeArray(cells_data_flat, deep=1))
        
        # Criar PolyData
        tube_polydata = vtk.vtkPolyData()
        tube_polydata.SetPoints(vtk_points)
        tube_polydata.SetPolys(cells)
        
        # Calcular normais
        normals_filter = vtk.vtkPolyDataNormals()
        normals_filter.SetInputData(tube_polydata)
        normals_filter.SplittingOff()
        normals_filter.ConsistencyOn()
        normals_filter.AutoOrientNormalsOn()
        normals_filter.Update()
        
        result = normals_filter.GetOutput()
        
        print(f"   • Tubo elíptico criado: {result.GetNumberOfPoints()} pontos, {result.GetNumberOfCells()} faces")
        
        return result
        
    except Exception as e:
        print(f"❌ Erro na criação do tubo elíptico: {e}")
        # Fallback para tubo circular
        tube = vtk.vtkTubeFilter()
        tube.SetInputData(path_polydata)
        tube.SetRadius(width / 2.0)
        tube.SetNumberOfSides(12)
        tube.CappingOn()
        tube.Update()
        return tube.GetOutput()

def create_path_geometry(points, width, height):
    """Cria geometria de tubo para uma lista de pontos"""
    if len(points) < 2:
        return None
    
    # Criar pontos VTK
    vtk_points = vtk.vtkPoints()
    lines = vtk.vtkCellArray()
    
    for point in points:
        vtk_points.InsertNextPoint(point)
    
    # Conectar pontos
    lines.InsertNextCell(len(points))
    for i in range(len(points)):
        lines.InsertCellPoint(i)
    
    # Criar polydata
    path_polydata = vtk.vtkPolyData()
    path_polydata.SetPoints(vtk_points)
    path_polydata.SetLines(lines)
    
    # Decidir perfil: circular (quando width≈height) ou elíptico real
    if height <= 0:
        return None
    ratio = width / height
    near_circular = abs(ratio - 1.0) <= 0.05  # 5% de tolerância
    if near_circular:
        tube = vtk.vtkTubeFilter()
        tube.SetInputData(path_polydata)
        tube.SetRadius(width / 2.0)
        tube.SetNumberOfSides(24)
        tube.CappingOn()
        tube.Update()
        return tube.GetOutput()
    else:
        # Elipse REAL ao longo do caminho
        return create_elliptical_tube(path_polydata, width, height)

def create_path_geometry_with_taper(points, width, height, taper_revolutions: float, layer_height: float):
    """Cria geometria contínua representando taper no final."""
    if len(points) < 2:
        return None

    # Criar polyline contínua
    vtk_points = vtk.vtkPoints()
    lines = vtk.vtkCellArray()
    for p in points:
        vtk_points.InsertNextPoint(p)
    lines.InsertNextCell(len(points))
    for i in range(len(points)):
        lines.InsertCellPoint(i)

    path_polydata = vtk.vtkPolyData()
    path_polydata.SetPoints(vtk_points)
    path_polydata.SetLines(lines)

    # Cálculo do fator de taper por ponto
    zs = np.array([p[2] for p in points])
    top_z = float(zs.max())
    base_radius = width / 2.0
    ratio = width / max(1e-6, height)
    near_circular = abs(ratio - 1.0) <= 0.05

    def taper_factor(z):
        remaining_turns = (top_z - z) / max(1e-6, layer_height)
        if remaining_turns <= taper_revolutions:
            return max(0.0, min(1.0, remaining_turns / max(1e-6, taper_revolutions)))
        return 1.0

    if near_circular:
        # Radius escalar por ponto
        scalars = vtk.vtkDoubleArray()
        scalars.SetName("TubeRadius")
        for z in zs:
            f = taper_factor(float(z))
            scalars.InsertNextValue(max(1e-6, base_radius * f))
        path_polydata.GetPointData().SetScalars(scalars)

        tube = vtk.vtkTubeFilter()
        tube.SetInputData(path_polydata)
        tube.SetNumberOfSides(24)
        # Usar raio absoluto a partir do escalar
        try:
            tube.SetVaryRadiusToVaryRadiusByAbsoluteScalar()
            tube.SetRadius(1.0)
        except Exception:
            # Fallback: usar multiplicativo
            tube.SetVaryRadius(1)
            tube.SetRadius(base_radius)
        tube.CappingOn()
        tube.Update()
        return tube.GetOutput()
    else:
        # Elipse com semi-eixos variáveis por ponto
        return create_elliptical_tube_variable(path_polydata, width, height, taper_revolutions, layer_height)

def create_elliptical_tube_variable(path_polydata: vtk.vtkPolyData, width: float, height: float,
                                    taper_revolutions: float, layer_height: float) -> vtk.vtkPolyData:
    """Varre elipse REAL contínua, escalando semi-eixos (a,b) por ponto conforme taper (Otimizado com NumPy)."""
    try:
        points = path_polydata.GetPoints()
        n_points = points.GetNumberOfPoints()
        if n_points < 2:
            raise ValueError("Caminho deve ter ao menos 2 pontos")

        # Converter pontos VTK para NumPy
        path_points = numpy_support.vtk_to_numpy(points.GetData())
        
        # OTIMIZAÇÃO: Se muitos pontos (>10000), reduzir para evitar travamento
        if n_points > 10000:
            skip = max(1, n_points // 6000)
            indices = np.arange(0, n_points, skip)
            if indices[-1] != n_points - 1:
                indices = np.append(indices, n_points - 1)
            path_points = path_points[indices]
            n_points = len(path_points)
            print(f"[Otimizacao] Reduzindo para {n_points} pontos para visualizacao do taper")

        n_sides = 32
        
        # 1. Calcular tangentes (vetorizado)
        tangents = np.zeros_like(path_points)
        tangents[0] = path_points[1] - path_points[0]
        tangents[-1] = path_points[-1] - path_points[-2]
        tangents[1:-1] = path_points[2:] - path_points[:-2]
        
        norms = np.linalg.norm(tangents, axis=1, keepdims=True)
        norms[norms < 1e-12] = 1.0
        tangents /= norms
        
        # 2. Calcular frames
        up_world = np.array([0.0, 0.0, 1.0])
        dots = np.abs(np.dot(tangents, up_world))
        ups = np.tile(up_world, (n_points, 1))
        ups[dots > 0.95] = np.array([0.0, 1.0, 0.0])
        
        normals = np.cross(ups, tangents)
        n_norms = np.linalg.norm(normals, axis=1, keepdims=True)
        n_norms[n_norms < 1e-12] = 1.0
        normals /= n_norms
        
        binormals = np.cross(tangents, normals)
        b_norms = np.linalg.norm(binormals, axis=1, keepdims=True)
        b_norms[b_norms < 1e-12] = 1.0
        binormals /= b_norms
        
        # 3. Calcular fatores de escala (taper)
        zs = path_points[:, 2]
        top_z = np.max(zs)
        
        remaining_turns = (top_z - zs) / max(1e-6, layer_height)
        
        f = np.ones_like(remaining_turns)
        mask = remaining_turns <= taper_revolutions
        f[mask] = np.clip(remaining_turns[mask] / max(1e-6, taper_revolutions), 0.0, 1.0)
        
        a_arr = np.maximum(1e-6, (width / 2.0) * f)
        b_arr = np.maximum(1e-6, (height / 2.0) * f)
        
        # 4. Gerar pontos
        thetas = np.linspace(0, 2*np.pi, n_sides, endpoint=False)
        cos_thetas = np.cos(thetas)
        sin_thetas = np.sin(thetas)
        
        P = path_points[:, np.newaxis, :]
        N = normals[:, np.newaxis, :]
        B = binormals[:, np.newaxis, :]
        
        term_N = a_arr[:, np.newaxis, np.newaxis] * cos_thetas[np.newaxis, :, np.newaxis] * N
        term_B = b_arr[:, np.newaxis, np.newaxis] * sin_thetas[np.newaxis, :, np.newaxis] * B
        
        tube_points_np = P + term_N + term_B
        tube_points_flat = tube_points_np.reshape(-1, 3)
        
        # 5. Criar VTK
        vtk_points = vtk.vtkPoints()
        vtk_points.SetData(numpy_support.numpy_to_vtk(tube_points_flat, deep=1))
        
        # 6. Células
        i = np.arange(n_points - 1)
        j = np.arange(n_sides)
        I, J = np.meshgrid(i, j, indexing='ij')
        J_next = (J + 1) % n_sides
        
        v00 = I * n_sides + J
        v01 = I * n_sides + J_next
        v11 = (I + 1) * n_sides + J_next
        v10 = (I + 1) * n_sides + J
        
        quads = np.stack([v00, v01, v11, v10], axis=-1).reshape(-1, 4)
        n_cells = quads.shape[0]
        cells_data = np.column_stack([np.full(n_cells, 4, dtype=np.int64), quads])
        
        cells = vtk.vtkCellArray()
        cells.SetCells(n_cells, numpy_support.numpy_to_vtkIdTypeArray(cells_data.flatten(), deep=1))
        
        tube_poly = vtk.vtkPolyData()
        tube_poly.SetPoints(vtk_points)
        tube_poly.SetPolys(cells)
        
        normals_filter = vtk.vtkPolyDataNormals()
        normals_filter.SetInputData(tube_poly)
        normals_filter.SplittingOff()
        normals_filter.ConsistencyOn()
        normals_filter.AutoOrientNormalsOn()
        normals_filter.Update()
        
        return normals_filter.GetOutput()
        
    except Exception as e:
        print(f"❌ Erro elipse variável: {e}")
        # Fallback: converter vtkPoints para lista se necessário
        pts_list = []
        if points:
            for i in range(points.GetNumberOfPoints()):
                pts_list.append(points.GetPoint(i))
        return create_path_geometry(pts_list, width, height)

def create_variable_height_tube(points, width: float, first_h: float, other_h: float,
                                z0: float, span_z: float) -> vtk.vtkPolyData:
    """Cria tubo com seção elíptica REAL variando apenas a altura (h) de first_h→other_h ao longo de span_z (Otimizado com NumPy)."""
    try:
        if not points or len(points) < 2:
            return None

        # Converter lista de pontos para NumPy
        path_points = np.array(points)
        n_points = len(path_points)
        n_sides = 32
        
        # 1. Calcular tangentes (vetorizado)
        tangents = np.zeros_like(path_points)
        tangents[0] = path_points[1] - path_points[0]
        tangents[-1] = path_points[-1] - path_points[-2]
        tangents[1:-1] = path_points[2:] - path_points[:-2]
        
        norms = np.linalg.norm(tangents, axis=1, keepdims=True)
        norms[norms < 1e-12] = 1.0
        tangents /= norms
        
        # 2. Calcular frames
        up_world = np.array([0.0, 0.0, 1.0])
        dots = np.abs(np.dot(tangents, up_world))
        ups = np.tile(up_world, (n_points, 1))
        ups[dots > 0.95] = np.array([0.0, 1.0, 0.0])
        
        normals = np.cross(ups, tangents)
        n_norms = np.linalg.norm(normals, axis=1, keepdims=True)
        n_norms[n_norms < 1e-12] = 1.0
        normals /= n_norms
        
        binormals = np.cross(tangents, normals)
        b_norms = np.linalg.norm(binormals, axis=1, keepdims=True)
        b_norms[b_norms < 1e-12] = 1.0
        binormals /= b_norms
        
        # 3. Calcular altura variável
        zs = path_points[:, 2]
        
        # t = (z - z0) / span_z, clamped [0, 1]
        if span_z <= 1e-9:
            h_arr = np.full(n_points, other_h)
        else:
            t = np.clip((zs - z0) / span_z, 0.0, 1.0)
            h_arr = (1.0 - t) * first_h + t * other_h
        
        h_arr = np.maximum(1e-6, h_arr)
        
        a = max(1e-6, width / 2.0)
        b_arr = h_arr / 2.0
        
        # 4. Gerar pontos
        thetas = np.linspace(0, 2*np.pi, n_sides, endpoint=False)
        cos_thetas = np.cos(thetas)
        sin_thetas = np.sin(thetas)
        
        P = path_points[:, np.newaxis, :]
        N = normals[:, np.newaxis, :]
        B = binormals[:, np.newaxis, :]
        
        # a é constante, b varia
        term_N = a * cos_thetas[np.newaxis, :, np.newaxis] * N
        term_B = b_arr[:, np.newaxis, np.newaxis] * sin_thetas[np.newaxis, :, np.newaxis] * B
        
        tube_points_np = P + term_N + term_B
        tube_points_flat = tube_points_np.reshape(-1, 3)
        
        # 5. Criar VTK
        vtk_points = vtk.vtkPoints()
        vtk_points.SetData(numpy_support.numpy_to_vtk(tube_points_flat, deep=1))
        
        # 6. Células
        i = np.arange(n_points - 1)
        j = np.arange(n_sides)
        I, J = np.meshgrid(i, j, indexing='ij')
        J_next = (J + 1) % n_sides
        
        v00 = I * n_sides + J
        v01 = I * n_sides + J_next
        v11 = (I + 1) * n_sides + J_next
        v10 = (I + 1) * n_sides + J
        
        quads = np.stack([v00, v01, v11, v10], axis=-1).reshape(-1, 4)
        n_cells = quads.shape[0]
        cells_data = np.column_stack([np.full(n_cells, 4, dtype=np.int64), quads])
        
        cells = vtk.vtkCellArray()
        cells.SetCells(n_cells, numpy_support.numpy_to_vtkIdTypeArray(cells_data.flatten(), deep=1))
        
        tube_poly = vtk.vtkPolyData()
        tube_poly.SetPoints(vtk_points)
        tube_poly.SetPolys(cells)
        
        normals_filter = vtk.vtkPolyDataNormals()
        normals_filter.SetInputData(tube_poly)
        normals_filter.SplittingOff()
        normals_filter.ConsistencyOn()
        normals_filter.AutoOrientNormalsOn()
        normals_filter.Update()
        
        return normals_filter.GetOutput()
        
    except Exception as e:
        print(f"❌ Erro rampa de altura: {e}")
        # Fallback: altura constante other_h
        return create_path_geometry(points, width, other_h)

def create_extrusion_actor(geometry, color=(0.8, 0.4, 0.1)):
    """Cria actor VTK com cor específica"""
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(geometry)
    
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    actor.GetProperty().SetColor(color[0], color[1], color[2])
    actor.GetProperty().SetOpacity(1.0)
    
    return actor

def _normalize(v, eps=1e-12):
    """Normaliza um vetor numpy"""
    norm = np.linalg.norm(v)
    return v if norm < eps else (v / norm)

def create_flattened_extrusion_cord(path_polydata: vtk.vtkPolyData, width: float, height: float) -> vtk.vtkPolyData:
    """Cria cordão com aparência achatada SEM deformar o caminho espacial"""
    try:
        print(f"   • Criando cordão com aparência achatada {width:.1f}x{height:.1f}mm")
        
        # SOLUÇÃO: Usar poucos lados e raio baseado na largura
        # Isso cria aparência "achatada" sem deformar geometria espacial
        
        radius = width / 2.0  # Raio baseado na largura (dimensão dominante)
        num_sides = 6  # POUCOS lados criam aparência achatada/angular
        
        tube = vtk.vtkTubeFilter()
        tube.SetInputData(path_polydata)
        tube.SetRadius(radius)
        tube.SetNumberOfSides(num_sides)  # Hexágono aparenta achatado
        tube.CappingOn()
        tube.Update()
        
        print(f"   • Raio: {radius:.2f}mm")
        print(f"   • Lados: {num_sides} (aparência angular/achatada)")
        print(f"   • SEM deformação espacial (caminho preservado)")
        
        return tube.GetOutput()
        
    except Exception as e:
        print(f"❌ Erro na criação do cordão achatado: {e}")
        # Fallback: tubo circular simples
        tube = vtk.vtkTubeFilter()
        tube.SetInputData(path_polydata)
        tube.SetRadius(width / 2.0)
        tube.SetNumberOfSides(8)
        tube.CappingOn()
        tube.Update()
        return tube.GetOutput()

def extract_extrusion_segments(gcode_data):
    """Extrai segmentos contínuos onde há extrusão de material"""
    import re
    
    segments = []
    current_segment = []
    current_pos = [0.0, 0.0, 0.0]
    
    for command in gcode_data:
        if command.startswith('G1') and 'E' in command:  # Movimento com extrusão
            # Extrair coordenadas
            x_match = re.search(r'X([-+]?\d*\.?\d+)', command)
            y_match = re.search(r'Y([-+]?\d*\.?\d+)', command)
            z_match = re.search(r'Z([-+]?\d*\.?\d+)', command)
            
            new_pos = current_pos.copy()
            if x_match:
                new_pos[0] = float(x_match.group(1))
            if y_match:
                new_pos[1] = float(y_match.group(1))
            if z_match:
                new_pos[2] = float(z_match.group(1))
            
            # Adicionar ao segmento atual
            if current_pos != new_pos:
                if not current_segment:  # Primeiro ponto do segmento
                    current_segment.append(current_pos.copy())
                current_segment.append(new_pos.copy())
            
            current_pos = new_pos
            
        elif command.startswith('G0') or (command.startswith('G1') and 'E' not in command):
            # Movimento sem extrusão (viagem) - finalizar segmento atual
            if current_segment and len(current_segment) >= 2:
                segments.append(current_segment)
                current_segment = []
                
            # Atualizar posição para viagens
            x_match = re.search(r'X([-+]?\d*\.?\d+)', command)
            y_match = re.search(r'Y([-+]?\d*\.?\d+)', command)
            z_match = re.search(r'Z([-+]?\d*\.?\d+)', command)
            
            if x_match:
                current_pos[0] = float(x_match.group(1))
            if y_match:
                current_pos[1] = float(y_match.group(1))
            if z_match:
                current_pos[2] = float(z_match.group(1))
    
    # Adicionar último segmento se existir
    if current_segment and len(current_segment) >= 2:
        segments.append(current_segment)
        
    return segments

def create_segment_tube(points, width, height):
    """Cria tubo para um segmento específico"""
    if len(points) < 2:
        return None
        
    # Criar pontos VTK
    vtk_points = vtk.vtkPoints()
    lines = vtk.vtkCellArray()
    
    for point in points:
        vtk_points.InsertNextPoint(point)
        
    # Conectar pontos
    lines.InsertNextCell(len(points))
    for i in range(len(points)):
        lines.InsertCellPoint(i)
        
    # Criar polydata do segmento
    segment_polydata = vtk.vtkPolyData()
    segment_polydata.SetPoints(vtk_points)
    segment_polydata.SetLines(lines)
    
    # Criar tubo para este segmento
    tube_filter = vtk.vtkTubeFilter()
    tube_filter.SetInputData(segment_polydata)
    
    # Configurar seção transversal
    width_height_ratio = width / height
    
    if width_height_ratio <= 1.2:  # Circular
        radius = width / 2.0
        tube_filter.SetRadius(radius)
        tube_filter.SetNumberOfSides(8)  # Performance balanceada
    else:  # Elíptico
        avg_radius = (width + height) / 4.0
        tube_filter.SetRadius(avg_radius)
        tube_filter.SetNumberOfSides(6)
        
    tube_filter.Update()
    
    # Aplicar deformação elíptica se necessário
    result = tube_filter.GetOutput()
    if width_height_ratio > 1.2:
        result = apply_elliptical_deformation(result, width, height)
        
    return result

def create_taper_geometry_with_linear_reduction(points, width, height):
    """
    Cria geometria do taper com altura reduzindo LINEARMENTE baseado no índice.
    
    - Primeiro ponto: altura = height (100%)
    - Último ponto: altura = 0 (0%)
    - Redução linear entre eles
    """
    if len(points) < 2:
        return None
    
    try:
        import numpy as np
        
        # Criar polyline
        vtk_points = vtk.vtkPoints()
        lines = vtk.vtkCellArray()
        for p in points:
            vtk_points.InsertNextPoint(p)
        lines.InsertNextCell(len(points))
        for i in range(len(points)):
            lines.InsertCellPoint(i)

        path_polydata = vtk.vtkPolyData()
        path_polydata.SetPoints(vtk_points)
        path_polydata.SetLines(lines)
        
        # Criar tubo elíptico com altura variável
        n_points = len(points)
        n_sides = 32
        thetas = np.linspace(0, 2*np.pi, n_sides, endpoint=False)
        
        a = width / 2.0  # Semi-eixo maior (largura)
        
        tube_points = vtk.vtkPoints()
        cells = vtk.vtkCellArray()
        
        # Extrair pontos do caminho
        path_pts = [np.array(points[i]) for i in range(n_points)]
        
        # Para cada ponto do caminho, criar seção transversal elíptica
        for i, center in enumerate(path_pts):
            # Fator de redução linear: 1.0 → 0.0
            progress = i / max(1, n_points - 1)
            reduction_factor = 1.0 - progress
            
            # Altura reduz linearmente
            b = (height / 2.0) * reduction_factor  # Semi-eixo menor (altura)
            
            # Se altura zerou, não adicionar seção
            if b < 0.001:
                continue
            
            # Calcular vetor tangente
            if i < n_points - 1:
                tangent = path_pts[i+1] - center
            else:
                tangent = center - path_pts[i-1]
            
            tangent_norm = np.linalg.norm(tangent)
            if tangent_norm < 1e-9:
                tangent = np.array([0, 0, 1])
            else:
                tangent = tangent / tangent_norm
            
            # Sistema de coordenadas local
            up = np.array([0.0, 0.0, 1.0])
            if abs(np.dot(tangent, up)) > 0.999:
                up = np.array([0.0, 1.0, 0.0])
            
            normal = np.cross(tangent, up)
            normal_norm = np.linalg.norm(normal)
            if normal_norm < 1e-9:
                normal = np.array([1, 0, 0])
            else:
                normal = normal / normal_norm
            
            binormal = np.cross(tangent, normal)
            binormal = binormal / max(1e-9, np.linalg.norm(binormal))
            
            # Criar elipse na seção transversal
            section_offset = i * n_sides
            for theta in thetas:
                # Ponto na elipse no plano local
                local_x = a * np.cos(theta)
                local_y = b * np.sin(theta)
                
                # Transformar para espaço 3D
                point_3d = center + local_x * normal + local_y * binormal
                tube_points.InsertNextPoint(point_3d)

        # Conectar quads
        n_sections = tube_points.GetNumberOfPoints() // n_sides
        for i in range(n_sections - 1):
            for j in range(n_sides):
                jn = (j + 1) % n_sides
                v00 = i * n_sides + j
                v01 = i * n_sides + jn
                v11 = (i + 1) * n_sides + jn
                v10 = (i + 1) * n_sides + j
                quad = vtk.vtkQuad()
                quad.GetPointIds().SetId(0, v00)
                quad.GetPointIds().SetId(1, v01)
                quad.GetPointIds().SetId(2, v11)
                quad.GetPointIds().SetId(3, v10)
                cells.InsertNextCell(quad)

        tube_poly = vtk.vtkPolyData()
        tube_poly.SetPoints(tube_points)
        tube_poly.SetPolys(cells)

        normals = vtk.vtkPolyDataNormals()
        normals.SetInputData(tube_poly)
        normals.SplittingOff()
        normals.ConsistencyOn()
        normals.AutoOrientNormalsOn()
        normals.Update()
        return normals.GetOutput()
    except Exception as e:
        print(f"❌ Erro taper linear: {e}")
        # Fallback: usar método normal
        return create_path_geometry(points, width, height)

def apply_elliptical_deformation(tube_geometry, width, height):
    """Aplica deformação elíptica ao tubo circular"""
    # Calcular fatores de escala
    avg_radius = (width + height) / 4.0
    scale_x = (width / 2.0) / avg_radius
    scale_z = (height / 2.0) / avg_radius  # Z é a "altura" do perfil
    
    # Aplicar transformação de escala não-uniforme
    transform = vtk.vtkTransform()
    transform.Scale(scale_x, 1.0, scale_z)  # Y mantém (direção do caminho)
    
    transform_filter = vtk.vtkTransformPolyDataFilter()
    transform_filter.SetInputData(tube_geometry)
    transform_filter.SetTransform(transform)
    transform_filter.Update()
    
    return transform_filter.GetOutput()

def create_interpolated_segment_tube(points, w_start, w_end, h_start, h_end):
    """Cria tubo com altura e largura interpoladas linearmente ao longo dos pontos (baseado no índice)."""
    try:
        if not points or len(points) < 2:
            return None

        # Converter lista de pontos para NumPy
        path_points = np.array(points)
        n_points = len(path_points)
        n_sides = 32
        
        # 1. Calcular tangentes (vetorizado)
        tangents = np.zeros_like(path_points)
        tangents[0] = path_points[1] - path_points[0]
        tangents[-1] = path_points[-1] - path_points[-2]
        tangents[1:-1] = path_points[2:] - path_points[:-2]
        
        norms = np.linalg.norm(tangents, axis=1, keepdims=True)
        norms[norms < 1e-12] = 1.0
        tangents /= norms
        
        # 2. Calcular frames
        up_world = np.array([0.0, 0.0, 1.0])
        dots = np.abs(np.dot(tangents, up_world))
        ups = np.tile(up_world, (n_points, 1))
        ups[dots > 0.95] = np.array([0.0, 1.0, 0.0])
        
        normals = np.cross(ups, tangents)
        n_norms = np.linalg.norm(normals, axis=1, keepdims=True)
        n_norms[n_norms < 1e-12] = 1.0
        normals /= n_norms
        
        binormals = np.cross(tangents, normals)
        b_norms = np.linalg.norm(binormals, axis=1, keepdims=True)
        b_norms[b_norms < 1e-12] = 1.0
        binormals /= b_norms
        
        # 3. Calcular altura e largura variáveis (interpolação linear por índice)
        indices = np.arange(n_points)
        t = indices / max(1, n_points - 1)
        
        h_arr = h_start + (h_end - h_start) * t
        w_arr = w_start + (w_end - w_start) * t
        
        h_arr = np.maximum(1e-6, h_arr)
        w_arr = np.maximum(1e-6, w_arr)
        
        a_arr = w_arr / 2.0
        b_arr = h_arr / 2.0
        
        # 4. Gerar pontos
        thetas = np.linspace(0, 2*np.pi, n_sides, endpoint=False)
        cos_thetas = np.cos(thetas)
        sin_thetas = np.sin(thetas)
        
        P = path_points[:, np.newaxis, :]
        N = normals[:, np.newaxis, :]
        B = binormals[:, np.newaxis, :]
        
        term_N = a_arr[:, np.newaxis, np.newaxis] * cos_thetas[np.newaxis, :, np.newaxis] * N
        term_B = b_arr[:, np.newaxis, np.newaxis] * sin_thetas[np.newaxis, :, np.newaxis] * B
        
        tube_points_np = P + term_N + term_B
        tube_points_flat = tube_points_np.reshape(-1, 3)
        
        # 5. Criar VTK
        vtk_points = vtk.vtkPoints()
        vtk_points.SetData(numpy_support.numpy_to_vtk(tube_points_flat, deep=1))
        
        # 6. Células
        i = np.arange(n_points - 1)
        j = np.arange(n_sides)
        I, J = np.meshgrid(i, j, indexing='ij')
        J_next = (J + 1) % n_sides
        
        v00 = I * n_sides + J
        v01 = I * n_sides + J_next
        v11 = (I + 1) * n_sides + J_next
        v10 = (I + 1) * n_sides + J
        
        quads = np.stack([v00, v01, v11, v10], axis=-1).reshape(-1, 4)
        n_cells = quads.shape[0]
        cells_data = np.column_stack([np.full(n_cells, 4, dtype=np.int64), quads])
        
        cells = vtk.vtkCellArray()
        cells.SetCells(n_cells, numpy_support.numpy_to_vtkIdTypeArray(cells_data.flatten(), deep=1))
        
        tube_poly = vtk.vtkPolyData()
        tube_poly.SetPoints(vtk_points)
        tube_poly.SetPolys(cells)
        
        normals_filter = vtk.vtkPolyDataNormals()
        normals_filter.SetInputData(tube_poly)
        normals_filter.SplittingOff()
        normals_filter.ConsistencyOn()
        normals_filter.AutoOrientNormalsOn()
        normals_filter.Update()
        
        return normals_filter.GetOutput()
        
    except Exception as e:
        print(f"❌ Erro tubo interpolado: {e}")
        # Fallback: altura constante média
        return create_path_geometry(points, (w_start+w_end)/2, (h_start+h_end)/2)
