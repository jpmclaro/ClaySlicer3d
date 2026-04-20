#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Geração de paredes Non-Planar (modo vaso orgânico)
Respeita a forma tridimensional do objeto, gerando espiral que segue o contorno real.

Inspirado no fatiador.py, mas adaptado para geração direta de G-code.
"""
from __future__ import annotations

import math
from typing import List, Optional, Tuple
from collections import defaultdict

import numpy as np
import vtk
from vtk.util.numpy_support import vtk_to_numpy

from clay_geometry import EPSILON
from clay_models import MeshAnalysis, Point3D
from clay_mesh import MeshAnalyzer
from clay_settings import ClayPrintSettings


class NonPlanarWallPlanner:
    """
    Planejador de paredes non-planar que segue a forma orgânica do objeto.
    
    Abordagem:
    1. Detecta borda superior do objeto (z_top por ângulo θ)
    2. Para cada camada k, distribui pontos em ângulos θ
    3. Encontra pontos na superfície usando interseção plano × mesh
    4. Gera espiral contínua que sobe seguindo a forma real
    """
    
    def __init__(self, settings: ClayPrintSettings, mesh_analyzer: MeshAnalyzer):
        self.settings = settings
        self.mesh_analyzer = mesh_analyzer
        
    def plan_nonplanar_walls(
        self,
        analysis: MeshAnalysis,
        polydata: vtk.vtkPolyData,
        start_point: Point3D,
    ) -> List[Point3D]:
        """
        Gera percurso non-planar iniciando do start_point (último ponto da base).
        
        Args:
            analysis: Análise do mesh
            polydata: Geometria VTK
            start_point: Último ponto do arco de fechamento da base
            
        Returns:
            Lista de pontos 3D formando espiral orgânica
        """
        print("🌊 Iniciando geração Non-Planar...")
        
        # 1. Preparar dados básicos
        cx, cy = analysis.center_x, analysis.center_y
        C3 = np.array([cx, cy, 0.0])
        bzmin, bzmax = float(analysis.base_z), float(analysis.top_z)
        
        # Configurar parâmetros
        layer_height = max(EPSILON, self.settings.layer_height)
        angular_step_deg = getattr(self.settings, 'nonplanar_angular_step_deg', 1.0)
        angle_threshold_deg = getattr(self.settings, 'nonplanar_angle_threshold_deg', 60.0)
        z_epsilon = getattr(self.settings, 'nonplanar_z_epsilon', 0.03)
        
        # Algoritmo selecionado
        algo = getattr(self.settings, 'nonplanar_algorithm', 1)
        print(f"   • Algoritmo selecionado: {algo}")
        
        # Variáveis de trabalho (dependem do algoritmo)
        working_poly = None
        cx_working, cy_working = 0.0, 0.0
        C3_working = None
        start_point_working = None
        backbone = None # Apenas para Algo 1 e 3
        
        if algo == 2:
            # === ALGORITMO 2: ROBUST (Clean + Dihedral/Fallback, SEM WARPING) ===
            # Este modo replica a lógica do arquivo BCK que funciona para nonplanar.obj
            print("   🚀 Executando Algoritmo 2 (Robust - BCK Logic)...")
            
            # Limpar mesh (merge vertices)
            cleaner = vtk.vtkCleanPolyData()
            cleaner.SetInputData(polydata)
            cleaner.SetTolerance(0.0)
            cleaner.PointMergingOn()
            cleaner.Update()
            working_poly = cleaner.GetOutput()
            
            # Usar coordenadas originais
            cx_working, cy_working = cx, cy
            C3_working = C3
            start_point_working = start_point
            
            # Definir ângulos
            thetas = np.deg2rad(np.arange(0.0, 360.0, angular_step_deg))
            
            # Extrair dados para fatiamento
            V_working, F_working = self._extract_mesh_data(working_poly)
            
            # Detectar topo (Usando lógica do BCK - Dihedral + Fallback)
            # A lógica FeatureEdges anterior falhava em alguns casos
            z_top = self._detect_top_profile(V_working, F_working, thetas, cx_working, cy_working, angle_threshold_deg, bzmax, filter_positive_u=False, polydata=working_poly)
            
        else:
            # === ALGORITMO 1: LEGACY (Warping + Dihedral) ===
            print("   🐢 Executando Algoritmo 1 (Legacy)...")
            
            # Calcular backbone
            print("   • Calculando espinha dorsal (backbone)...")
            backbone = self._compute_backbone(polydata, bzmin, bzmax)
            
            # Warping
            print("   • Aplicando warping (endireitando mesh)...")
            working_poly = self._warp_mesh(polydata, backbone, inverse=False)
            
            # Coordenadas no espaço warped (centro em 0,0)
            cx_working, cy_working = 0.0, 0.0
            C3_working = np.array([0.0, 0.0, 0.0])
            
            # Ajustar start_point
            bx, by = self._get_backbone_at_z(backbone, start_point.z)
            start_point_working = Point3D(
                start_point.x - bx,
                start_point.y - by,
                start_point.z
            )
            
            # Definir ângulos
            thetas = np.deg2rad(np.arange(0.0, 360.0, angular_step_deg))
            
            # Extrair dados
            V_working, F_working = self._extract_mesh_data(working_poly)
            
            # Detectar topo (Legacy)
            z_top = self._detect_top_profile(V_working, F_working, thetas, cx_working, cy_working, angle_threshold_deg, bzmax, filter_positive_u=True)

        if V_working is None or F_working is None:
            print("❌ Erro: falha ao processar mesh de trabalho")
            return []

        # 4. Calcular número de camadas
        start_z = float(start_point.z)
        height_total = bzmax - start_z
        N_layers = max(1, int(round(height_total / layer_height)))
        
        print(f"   • Camadas: {N_layers}")
        print(f"   • Altura total: {height_total:.2f}mm")
        
        # 7. Pré-calcular interseções plano × mesh
        P0, P1, P2 = self._prep_plane_buffers(V_working, F_working)
        planes_cache = [
            self._plane_segments(P0, P1, P2, C3_working, th) 
            for th in thetas
        ]
        
        # 8. Ajustar ângulo inicial
        start_angle_idx = self._find_start_angle_index(
            start_point_working, cx_working, cy_working, thetas
        )
        
        # 9. Gerar pontos da espiral
        path_points_working = self._generate_spiral_path(
            N_layers,
            thetas,
            z_top,
            planes_cache,
            C3_working,
            cx_working,
            cy_working,
            start_z,
            bzmin,
            bzmax,
            z_epsilon,
            start_angle_idx,
            start_point_working,
            filter_positive_u=(algo == 1)
        )
        
        # Pós-processamento (Unwarping se necessário)
        final_path_points = []
        
        if algo == 1 and backbone is not None:
            print("   • Aplicando unwarping (restaurando curvatura)...")
            for p in path_points_working:
                bx, by = self._get_backbone_at_z(backbone, p.z)
                p_final = Point3D(p.x + bx, p.y + by, p.z)
                if hasattr(p, 'height_factor'):
                    p_final.height_factor = p.height_factor # type: ignore
                final_path_points.append(p_final)
        else:
            # Algo 2 não precisa de unwarping
            final_path_points = path_points_working
        
        print(f"✅ Non-Planar: {len(final_path_points)} pontos gerados")
        return final_path_points

    def _compute_backbone(self, polydata: vtk.vtkPolyData, z_min: float, z_max: float, slices: int = 100) -> List[Tuple[float, float, float]]:
        """
        Calcula a espinha dorsal (centroide por altura) do objeto.
        Retorna lista de (z, cx, cy) ordenada por Z.
        """
        backbone = []
        cutter = vtk.vtkCutter()
        cutter.SetInputData(polydata)
        plane = vtk.vtkPlane()
        plane.SetNormal(0, 0, 1)
        cutter.SetCutFunction(plane)
        
        # ⭐ CORREÇÃO: Calcular backbone apenas até 85% da altura
        # Isso evita que a borda irregular (non-planar) do topo distorça o centroide
        # quando o anel deixa de ser fechado (vira um "C" ou arcos desconexos).
        safe_limit_ratio = 0.85
        z_range = z_max - z_min
        
        # Se objeto muito baixo, não usar lógica complexa
        if z_range < 1.0:
             return [(z_min, 0.0, 0.0), (z_max, 0.0, 0.0)]

        z_start = z_min + 0.1
        z_safe_end = z_min + z_range * safe_limit_ratio
        
        # Número de fatias proporcional à altura segura
        safe_slices = int(slices * safe_limit_ratio)
        if safe_slices < 5: safe_slices = 5
        
        raw_backbone = []
        
        # 1. Calcular parte estável (onde o anel é provavelmente fechado)
        for i in range(safe_slices):
            z = z_start + (z_safe_end - z_start) * (i / (safe_slices - 1))
            plane.SetOrigin(0, 0, z)
            cutter.Update()
            cut = cutter.GetOutput()
            
            if cut.GetNumberOfPoints() > 0:
                pts = vtk_to_numpy(cut.GetPoints().GetData())
                cx, cy = np.mean(pts[:, 0]), np.mean(pts[:, 1])
                raw_backbone.append((z, cx, cy))
            else:
                # Se falhar, tentar interpolar do anterior
                if raw_backbone:
                    prev = raw_backbone[-1]
                    raw_backbone.append((z, prev[1], prev[2]))
        
        if not raw_backbone:
             return [(z_min, 0.0, 0.0), (z_max, 0.0, 0.0)]

        # 2. Extrapolar para o topo (z_max)
        # Pegar a tendência dos últimos 25% da parte estável para projetar o centro
        # nas camadas superiores irregulares
        num_samples = max(3, len(raw_backbone) // 4)
        last_pts = raw_backbone[-num_samples:]
        
        # Regressão linear simples para X e Y em função de Z
        zs_sample = np.array([p[0] for p in last_pts])
        xs_sample = np.array([p[1] for p in last_pts])
        ys_sample = np.array([p[2] for p in last_pts])
        
        # Ajuste linear: x = az + b
        if len(zs_sample) > 1:
            try:
                Az = np.vstack([zs_sample, np.ones(len(zs_sample))]).T
                mx, cx_b = np.linalg.lstsq(Az, xs_sample, rcond=None)[0]
                my, cy_b = np.linalg.lstsq(Az, ys_sample, rcond=None)[0]
                
                # Adicionar pontos extrapolados até z_max
                remaining_slices = slices - safe_slices
                if remaining_slices > 0:
                    for i in range(1, remaining_slices + 1):
                        z = z_safe_end + (z_max - z_safe_end) * (i / remaining_slices)
                        new_x = mx * z + cx_b
                        new_y = my * z + cy_b
                        raw_backbone.append((z, new_x, new_y))
            except Exception:
                # Fallback se regressão falhar
                last = raw_backbone[-1]
                raw_backbone.append((z_max, last[1], last[2]))
        else:
            # Se não der para extrapolar, repetir o último
            last = raw_backbone[-1]
            raw_backbone.append((z_max, last[1], last[2]))
        
        # 3. Suavizar backbone (média móvel)
        if len(raw_backbone) < 3:
            return raw_backbone
            
        zs = [p[0] for p in raw_backbone]
        xs = [p[1] for p in raw_backbone]
        ys = [p[2] for p in raw_backbone]
        
        window = 7 # Janela um pouco maior para suavidade
        xs_smooth = np.convolve(xs, np.ones(window)/window, mode='same')
        ys_smooth = np.convolve(ys, np.ones(window)/window, mode='same')
        
        edge = window // 2
        xs_smooth[:edge] = xs[:edge]
        xs_smooth[-edge:] = xs[-edge:]
        ys_smooth[:edge] = ys[:edge]
        ys_smooth[-edge:] = ys[-edge:]
        
        backbone = list(zip(zs, xs_smooth, ys_smooth))
                
        return backbone

    def _get_backbone_at_z(self, backbone: List[Tuple[float, float, float]], z: float) -> Tuple[float, float]:
        """Interpola o centro (cx, cy) para uma altura Z dada."""
        if not backbone:
            return 0.0, 0.0
            
        # Se Z fora dos limites, usar extremos
        if z <= backbone[0][0]:
            return backbone[0][1], backbone[0][2]
        if z >= backbone[-1][0]:
            return backbone[-1][1], backbone[-1][2]
            
        # Busca binária ou linear (linear é ok para poucos slices)
        for i in range(len(backbone) - 1):
            z1, x1, y1 = backbone[i]
            z2, x2, y2 = backbone[i+1]
            
            if z1 <= z <= z2:
                t = (z - z1) / (z2 - z1)
                cx = x1 + t * (x2 - x1)
                cy = y1 + t * (y2 - y1)
                return cx, cy
                
        return backbone[-1][1], backbone[-1][2]

    def _warp_mesh(self, polydata: vtk.vtkPolyData, backbone: List[Tuple[float, float, float]], inverse: bool = False) -> vtk.vtkPolyData:
        """
        Aplica deformação no mesh para endireitar (inverse=False) ou curvar (inverse=True).
        """
        new_poly = vtk.vtkPolyData()
        new_poly.DeepCopy(polydata)
        
        points = new_poly.GetPoints()
        num_pts = points.GetNumberOfPoints()
        
        # Converter para numpy para velocidade
        pts_data = vtk_to_numpy(points.GetData())
        new_pts = np.copy(pts_data)
        
        # Aplicar deslocamento para cada ponto
        # Otimização: vetorizar interpolação seria ideal, mas loop simples em Python
        # pode ser lento para meshes grandes. Vamos usar uma abordagem simplificada.
        
        # Pré-calcular tabela de lookup para interpolação rápida
        z_vals = np.array([b[0] for b in backbone])
        x_vals = np.array([b[1] for b in backbone])
        y_vals = np.array([b[2] for b in backbone])
        
        # Interpolar deslocamentos para todos os Zs dos pontos
        # np.interp é muito rápido
        bx = np.interp(new_pts[:, 2], z_vals, x_vals)
        by = np.interp(new_pts[:, 2], z_vals, y_vals)
        
        if inverse:
            new_pts[:, 0] += bx
            new_pts[:, 1] += by
        else:
            new_pts[:, 0] -= bx
            new_pts[:, 1] -= by
            
        # Atualizar pontos no vtkPolyData
        from vtk.util.numpy_support import numpy_to_vtk
        vtk_pts = numpy_to_vtk(new_pts, deep=1)
        points.SetData(vtk_pts)
        
        return new_poly

    
    def _extract_mesh_data(self, polydata: vtk.vtkPolyData) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Extrai vértices e faces trianguladas do polydata."""
        # Triangular o mesh
        triangle_filter = vtk.vtkTriangleFilter()
        triangle_filter.SetInputData(polydata)
        triangle_filter.Update()
        tri_output = triangle_filter.GetOutput()
        
        # Extrair vértices
        points = tri_output.GetPoints()
        if points is None or points.GetNumberOfPoints() == 0:
            return None, None
        vertices = vtk_to_numpy(points.GetData())
        
        # Extrair faces
        polys = tri_output.GetPolys()
        if polys is None:
            return None, None
        cell_array = vtk_to_numpy(polys.GetData())
        if cell_array.size == 0:
            return None, None
        
        # Reformatar faces (cada face tem 4 elementos: [3, v0, v1, v2])
        faces = cell_array.reshape(-1, 4)[:, 1:]
        
        return vertices, faces
    
    def _face_normals(self, V: np.ndarray, F: np.ndarray) -> np.ndarray:
        """Calcula normais das faces."""
        v0 = V[F[:, 0]]
        v1 = V[F[:, 1]]
        v2 = V[F[:, 2]]
        e1 = v1 - v0
        e2 = v2 - v0
        n = np.cross(e1, e2)
        ln = np.linalg.norm(n, axis=1, keepdims=True)
        ln[ln < 1e-12] = 1.0
        return n / ln
    
    def _edge_map(self, F: np.ndarray) -> dict:
        """Cria mapa de arestas → faces adjacentes."""
        edge_dict = defaultdict(list)
        for fi, (a, b, c) in enumerate(F):
            for u, v in ((a, b), (b, c), (c, a)):
                edge = tuple(sorted((u, v)))
                edge_dict[edge].append(fi)
        return edge_dict

    def _detect_top_profile(
        self,
        V: np.ndarray,
        F: np.ndarray,
        thetas: np.ndarray,
        cx: float,
        cy: float,
        angle_threshold_deg: float,
        bzmax: float,
        filter_positive_u: bool = False,
        polydata: Optional[vtk.vtkPolyData] = None
    ) -> np.ndarray:
        """
        Detecta perfil z_top(θ) da borda superior do objeto.
        Usa vtkFeatureEdges na geometria ORIGINAL (para preservar ângulos) e depois aplica warping.
        """
        # 1. Tentar detecção robusta via VTK na geometria ORIGINAL (Algo 3)
        if polydata is not None:
            # print("   🔍 Detectando bordas via vtkFeatureEdges (Original)...")
            feature = vtk.vtkFeatureEdges()
            feature.SetInputData(polydata)
            feature.BoundaryEdgesOn()
            feature.FeatureEdgesOn()
            feature.SetFeatureAngle(angle_threshold_deg)
            feature.ManifoldEdgesOff()
            feature.NonManifoldEdgesOff()
            feature.Update()
            
            edges_poly = feature.GetOutput()
            
            if edges_poly.GetNumberOfPoints() > 0:
                pts = vtk_to_numpy(edges_poly.GetPoints().GetData())
                
                # Filtrar pontos pela altura (apenas metade superior)
                zmin = polydata.GetBounds()[4]
                zmax = polydata.GetBounds()[5]
                
                pts_working = pts
                
                # Coletar pontos válidos (altura > 50%)
                valid_mask = (pts[:, 2] - zmin) / (zmax - zmin + 1e-12) > 0.5
                
                if np.any(valid_mask):
                    top_edges_pts = pts_working[valid_mask]
                    
                    print(f"   • Bordas detectadas (FeatureEdges): {len(top_edges_pts)} pontos")
                    z_top = []
                    
                    if isinstance(top_edges_pts, list):
                        top_edges_pts = np.array(top_edges_pts)
                    
                    for th in thetas:
                        d = np.array([math.cos(th), math.sin(th)])
                        u = (top_edges_pts[:, 0] - cx) * d[0] + (top_edges_pts[:, 1] - cy) * d[1]
                        idx_max = np.argmax(u)
                        z_top.append(top_edges_pts[idx_max, 2])
                    
                    z_top_array = np.array(z_top, float)
                    z_top_array = self._smooth_profile(z_top_array, window=15)
                    print(f"   • Z topo: {z_top_array.min():.2f} - {z_top_array.max():.2f}mm")
                    return z_top_array

        # 2. Legacy Logic (from backup) - Usado para Algo 1 e Fallback do Algo 3
        # print("   🐢 Executando detecção Legacy (Dihedral Angle)...")
        N = self._face_normals(V, F)
        E = self._edge_map(F)
        
        zmin = float(V[:, 2].min())
        zmax = float(V[:, 2].max())
        thr = math.radians(angle_threshold_deg)
        
        top_edges = []
        checked_edges = 0
        angle_passed = 0
        height_passed = 0
        normal_passed = 0
        
        for (i, j), adj in E.items():
            checked_edges += 1
            if len(adj) != 2:
                continue
            
            n1, n2 = N[adj[0]], N[adj[1]]
            ang = math.acos(float(np.clip(np.dot(n1, n2), -1.0, 1.0)))
            
            if ang < thr:
                continue
            angle_passed += 1
            
            v1, v2 = V[i], V[j]
            zmid = 0.5 * (v1[2] + v2[2])
            rel = (zmid - zmin) / (zmax - zmin + 1e-12)
            
            if rel <= 0.5:
                continue
            height_passed += 1
            
            # RELAXAR critério da normal: aceitar se qualquer normal tem componente Z positiva
            if n1[2] > 0 or n2[2] > 0:
                normal_passed += 1
                top_edges.append((v1, v2))
        
        print(f"   • Arestas verificadas: {checked_edges}")
        print(f"   • Passaram ângulo (>{angle_threshold_deg}°): {angle_passed}")
        print(f"   • Passaram altura (>50%): {height_passed}")
        print(f"   • Passaram normal (Z>0): {normal_passed}")
        print(f"   • Bordas detectadas: {len(top_edges)}")
        
        if not top_edges:
            # Fallback avançado (igual ao fatiador.py):
            print("   ⚠️ Borda superior não detectada por ângulo diédrico")
            print("   → Usando fallback: análise de segmentos por ângulo")
            
            C3_fallback = np.array([cx, cy, 0.0])
            P0, P1, P2 = self._prep_plane_buffers(V, F)
            z_top = []
            
            for th in thetas:
                segs, dvec = self._plane_segments(P0, P1, P2, C3_fallback, th)
                if not segs:
                    z_top.append(bzmax)
                    continue
                
                us, zs = [], []
                for a, b in segs:
                    for p in (a, b):
                        us.append(np.dot(p - C3_fallback, dvec))
                        zs.append(p[2])
                
                us = np.array(us)
                zs = np.array(zs)
                
                if filter_positive_u:
                    # Lógica Legacy (Correction 2) - Para Algo 1
                    front_mask = us > 0
                    if np.any(front_mask):
                        zs_front = zs[front_mask]
                        z_top.append(float(zs_front.max()))
                    else:
                        z_top.append(float(zs.max()))
                else:
                    # Lógica BCK (Robust) - Para Algo 2
                    u_max = us.max()
                    near_outer = zs[us >= (u_max - 0.5)]
                    if near_outer.size > 0:
                        z_top.append(float(near_outer.max()))
                    else:
                        z_top.append(float(zs.max()))
            
            z_top_array = np.array(z_top, float)
            print(f"   • Z topo (fallback): {z_top_array.min():.2f} - {z_top_array.max():.2f}mm")
            return z_top_array
        
        edge_verts = np.array([v for e in top_edges for v in e], float)
        z_top = []
        
        for th in thetas:
            d = np.array([math.cos(th), math.sin(th)])
            u = (edge_verts[:, 0] - cx) * d[0] + (edge_verts[:, 1] - cy) * d[1]
            z_top.append(edge_verts[int(np.argmax(u)), 2])
        
        z_top_array = np.array(z_top, float)
        z_top_array = self._smooth_profile(z_top_array, window=5)
        
        print(f"   • Z topo: {z_top_array.min():.2f} - {z_top_array.max():.2f}mm")
        return z_top_array
    
    def _smooth_profile(self, z_array: np.ndarray, window: int = 5) -> np.ndarray:
        """Suaviza perfil Z usando média móvel circular."""
        if len(z_array) < window:
            return z_array
        
        smoothed = np.copy(z_array)
        half_window = window // 2
        
        for i in range(len(z_array)):
            indices = [(i + j - half_window) % len(z_array) for j in range(window)]
            smoothed[i] = np.mean(z_array[indices])
        
        return smoothed
    
    def _prep_plane_buffers(self, V: np.ndarray, F: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Prepara buffers dos vértices das faces."""
        return V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    
    def _plane_segments(
        self,
        P0: np.ndarray,
        P1: np.ndarray,
        P2: np.ndarray,
        C3: np.ndarray,
        theta_rad: float
    ) -> Tuple[List[Tuple[np.ndarray, np.ndarray]], np.ndarray]:
        """
        Encontra segmentos da interseção plano vertical × mesh.
        
        O plano passa pelo centro C3 e tem ângulo θ.
        """
        # Normal do plano (perpendicular à direção radial no plano XY)
        n = np.array([-math.sin(theta_rad), math.cos(theta_rad), 0.0])
        
        # Direção radial (do centro para fora)
        d = np.array([math.cos(theta_rad), math.sin(theta_rad), 0.0])
        
        # Distâncias dos vértices ao plano
        s0 = (P0 - C3) @ n
        s1 = (P1 - C3) @ n
        s2 = (P2 - C3) @ n
        
        # Faces que cruzam o plano
        mask = (s0 * s1 <= 0) | (s1 * s2 <= 0) | (s2 * s0 <= 0)
        idxs = np.nonzero(mask)[0]
        
        segs = []
        for i in idxs:
            p0, p1, p2 = P0[i], P1[i], P2[i]
            pts = []
            
            # Verificar cada aresta do triângulo
            for a, b, sa, sb in ((p0, p1, s0[i], s1[i]),
                                 (p1, p2, s1[i], s2[i]),
                                 (p2, p0, s2[i], s0[i])):
                if sa * sb < 0:
                    # Aresta cruza o plano
                    t = sa / (sa - sb)
                    pts.append(a + t * (b - a))
                elif abs(sa) < 1e-12:
                    pts.append(a)
                elif abs(sb) < 1e-12:
                    pts.append(b)
            
            if len(pts) >= 2:
                arr = np.array(pts)
                # Usar par mais distante para estabilidade
                dmat = np.linalg.norm(arr[None, :, :] - arr[:, None, :], axis=2)
                ii, jj = np.unravel_index(np.argmax(dmat), dmat.shape)
                segs.append((arr[ii], arr[jj]))
        
        return segs, d
    
    def _point_on_outer_at_z(
        self,
        segs: List[Tuple[np.ndarray, np.ndarray]],
        dvec: np.ndarray,
        C3: np.ndarray,
        z: float,
        filter_positive_u: bool = False
    ) -> Optional[np.ndarray]:
        """
        Encontra ponto no perímetro externo em uma altura z específica.
        
        Args:
            segs: Segmentos da interseção plano × mesh
            dvec: Direção radial
            C3: Centro
            z: Altura desejada
            filter_positive_u: Se True, ignora pontos com projeção radial negativa (costas)
            
        Returns:
            Ponto 3D com maior projeção radial em z, ou None se não houver
        """
        best = None
        
        for a, b in segs:
            z1, z2 = a[2], b[2]
            
            # Verificar se segmento cruza a altura z
            if not ((z1 <= z <= z2) or (z2 <= z <= z1)):
                continue
            
            if abs(z2 - z1) < 1e-12:
                continue
            
            # Interpolar ponto em z
            t = (z - z1) / (z2 - z1)
            p = a + t * (b - a)
            
            # Projeção radial
            u = float(np.dot(p - C3, dvec))
            
            if filter_positive_u and u <= 0:
                continue
            
            # Guardar ponto com maior projeção (mais externo)
            if (best is None) or (u > best[0]):
                best = (u, p)
        
        return None if best is None else best[1]
    
    def _find_start_angle_index(
        self,
        start_point: Point3D,
        cx: float,
        cy: float,
        thetas: np.ndarray
    ) -> int:
        """Encontra índice do ângulo mais próximo do start_point."""
        dx = start_point.x - cx
        dy = start_point.y - cy
        start_angle = math.atan2(dy, dx)
        
        # Normalizar para [0, 2π)
        if start_angle < 0:
            start_angle += 2 * math.pi
        
        # Encontrar índice mais próximo
        angle_diffs = np.abs(thetas - start_angle)
        return int(np.argmin(angle_diffs))
    
    def _generate_spiral_path(
        self,
        N_layers: int,
        thetas: np.ndarray,
        z_top: np.ndarray,
        planes_cache: List[Tuple],
        C3: np.ndarray,
        cx: float,
        cy: float,
        start_z: float,
        bzmin: float,
        bzmax: float,
        z_epsilon: float,
        start_angle_idx: int,
        start_point: Point3D,
        filter_positive_u: bool = False
    ) -> List[Point3D]:
        """
        Gera espiral contínua seguindo a forma orgânica.
        
        Estratégia CORRIGIDA (igual ao fatiador.py):
        - Para cada camada k, varre todos os ângulos θ
        - Em cada (k, θ), calcula z_target baseado em z_top(θ) específico daquele ângulo
        - Isso faz o Z variar DENTRO da mesma camada, seguindo a forma orgânica
        - Conecta pontos formando espiral que acompanha a geometria 3D real
        """
        path_points = []
        
        # 🔧 ABORDAGEM CORRIGIDA (igual ao clay_walls.py):
        # Não criar rampa separada - em vez disso, começar do start_point
        # e interpolar continuamente até os pontos da espiral
        # A transição é natural através da interpolação contínua
        
        # Começar do ângulo alinhado com start_point
        dx_start = start_point.x - cx
        dy_start = start_point.y - cy
        start_angle = math.atan2(dy_start, dx_start)
        if start_angle < 0:
            start_angle += 2 * math.pi
        
        # Raio do último ponto da base (fixo para a rampa)
        base_radius = math.sqrt(dx_start**2 + dy_start**2)
        
        # Número total de ângulos
        num_angles = len(thetas)
        
        # Encontrar índice do ângulo mais próximo
        start_angle_idx_real = int(np.argmin(np.abs(thetas - start_angle)))
        
        print(f"   • Ângulo inicial: {math.degrees(start_angle):.1f}°, índice: {start_angle_idx_real}")
        print(f"   • Raio da base: {base_radius:.3f}mm")
        print(f"   • Start point: X={start_point.x:.3f} Y={start_point.y:.3f} Z={start_point.z:.3f}")
        
        # ========== RAMPA DE TRANSIÇÃO (180°) ==========
        # Arco com raio fixo da base, sobe de start_z até altura da camada base
        # Isso cria sobreposição com a última camada da base
        
        ramp_points = 90  # 90 pontos para 180° = 2° por ponto
        ramp_z_start = start_point.z  # Z inicial (pode estar ligeiramente abaixo)
        ramp_z_end = start_z  # Z da camada base (1.0mm)
        
        print(f"   • Rampa: {ramp_points} pontos, Z={ramp_z_start:.3f} → {ramp_z_end:.3f}mm")
        
        # ⭐ NÃO adicionar start_point - ele é o último ponto da base!
        # A rampa começa imediatamente a partir do start_point
        path_points = []
        prev_point = start_point
        point_count = 0
        
        print(f"   • Rampa inicia a partir do ponto: X={start_point.x:.3f} Y={start_point.y:.3f} Z={start_point.z:.3f}")
        
        # ⭐ Começar com i=0 para incluir o start_point como primeiro ponto da rampa
        for i in range(0, ramp_points + 1):
            # Ângulo varia de start_angle até start_angle + π (180°)
            t_ramp = i / ramp_points
            current_angle = start_angle + math.pi * t_ramp
            
            # Z sobe linearmente
            z_ramp = ramp_z_start + (ramp_z_end - ramp_z_start) * t_ramp
            
            # XY em círculo com raio fixo da base
            x_ramp = cx + base_radius * math.cos(current_angle)
            y_ramp = cy + base_radius * math.sin(current_angle)
            
            ramp_point = Point3D(x_ramp, y_ramp, z_ramp)
            
            # Debug primeiro ponto da rampa
            if i == 1:
                print(f"   • Segundo ponto (primeiro da rampa): X={x_ramp:.3f} Y={y_ramp:.3f} Z={z_ramp:.3f}")
                dist_from_start = math.sqrt((x_ramp - start_point.x)**2 + (y_ramp - start_point.y)**2)
                print(f"   • Distância do start_point: {dist_from_start:.3f}mm")
            
            path_points.append(ramp_point)
            prev_point = ramp_point
            point_count += 1
        
        print(f"   • Rampa concluída: {point_count} pontos")
        print(f"   • Posição após rampa: X={prev_point.x:.3f} Y={prev_point.y:.3f} Z={prev_point.z:.3f}")
        
        # ========== ESPIRAL DA PAREDE (a partir do final da rampa) ==========
        
        # Ângulo de início da espiral (onde a rampa terminou: start_angle + π)
        wall_start_angle = start_angle + math.pi
        if wall_start_angle >= 2 * math.pi:
            wall_start_angle -= 2 * math.pi
        
        # Encontrar índice correspondente
        wall_start_angle_idx = int(np.argmin(np.abs(thetas - wall_start_angle)))
        
        print(f"   • Início da espiral: {math.degrees(wall_start_angle):.1f}°, índice: {wall_start_angle_idx}")
        
        # Gerar espiral contínua a partir deste ponto
        points_per_revolution = num_angles
        total_points_needed = N_layers * points_per_revolution
        
        # ⭐ DETECTAR SE TAPER ESTÁ HABILITADO
        enable_taper = self.settings.enable_end_taper
        taper_start_layer = N_layers - 1 if enable_taper else N_layers + 1  # Última camada
        
        if enable_taper:
            print(f"   • Taper integrado: ativado na camada {taper_start_layer}/{N_layers-1}")
        
        # Cache para armazenar Z da penúltima camada (para taper)
        penultimate_layer_z = {}  # {angle_idx: z_value}
        
        # Percorrer em espiral: ângulo varia continuamente, z sobe gradualmente
        for global_idx in range(total_points_needed):
            # Índice do ângulo (circular) - começar do ângulo após a rampa
            angle_idx = (wall_start_angle_idx + global_idx) % num_angles
            theta = thetas[angle_idx]
            
            # Camada atual (progride continuamente)
            layer_progress = global_idx / points_per_revolution
            k = int(layer_progress)
            
            if k >= N_layers:
                break
            
            # ⭐ Z contínuo: t varia de 0 a 1 suavemente
            t = layer_progress / N_layers  # Fração contínua
            
            zt = z_top[angle_idx] - z_epsilon  # Topo específico deste ângulo!
            z_target_full = start_z + t * (zt - start_z)  # Interpola de start_z até zt(θ)
            
            # ⭐ Armazenar Z da penúltima camada para cada ângulo (ANTES de calcular taper)
            if enable_taper and k == taper_start_layer - 1:
                penultimate_layer_z[angle_idx] = z_target_full
            
            # ⭐ TAPER: Ajustar Z na última camada para achatar gradualmente
            if enable_taper and k >= taper_start_layer:
                # Progresso dentro da última revolução (0.0 → 1.0)
                revolution_progress = (global_idx % points_per_revolution) / points_per_revolution
                
                # Z da penúltima camada neste ângulo
                if angle_idx in penultimate_layer_z:
                    z_previous = penultimate_layer_z[angle_idx]
                else:
                    # Estimar Z da penúltima camada (uma camada abaixo)
                    t_prev = (k - 1) / N_layers
                    z_previous = start_z + t_prev * (zt - start_z)
                
                # Interpolar Z: início da última volta (z_target_full) → fim (z_previous)
                # Isso faz o bico "achatar" até ficar na mesma altura da camada anterior
                z_target = z_target_full * (1.0 - revolution_progress) + z_previous * revolution_progress
            else:
                z_target = z_target_full
            
            # Buscar ponto na superfície
            segs, dvec = planes_cache[angle_idx]
            if not segs:
                continue
            
            p = self._point_on_outer_at_z(segs, dvec, C3, z_target, filter_positive_u=filter_positive_u)
            
            if p is not None:
                # ⭐ APLICAR OFFSET RADIAL (metade da largura de extrusão para DENTRO)
                # Isso preserva as dimensões do objeto após impressão
                # (o cordão fica CENTRADO na superfície desejada)
                offset_distance = self.settings.other_layers_extrusion_width * 0.5
                
                # Vetor radial do centro para o ponto
                dx_offset = p[0] - cx
                dy_offset = p[1] - cy
                r_offset = math.sqrt(dx_offset**2 + dy_offset**2)
                
                if r_offset > 1e-6:
                    # Normalizar e aplicar offset para DENTRO (sinal negativo!)
                    dx_offset = -dx_offset / r_offset * offset_distance
                    dy_offset = -dy_offset / r_offset * offset_distance
                    
                    # Aplicar offset
                    p_offset = np.array([
                        p[0] + dx_offset,
                        p[1] + dy_offset,
                        p[2]  # Z não muda
                    ])
                else:
                    p_offset = p
                
                # Criar Point3D com offset aplicado
                point = Point3D(float(p_offset[0]), float(p_offset[1]), float(p_offset[2]))
                
                # ⭐ TAPER INTEGRADO: Se estiver na última camada, adicionar metadata
                if enable_taper and k >= taper_start_layer:
                    # Progresso dentro da última revolução (0.0 → 1.0)
                    revolution_progress = (global_idx % points_per_revolution) / points_per_revolution
                    
                    # Fator de altura: 1.0 (início da última volta) → 0.0 (fim)
                    height_factor = 1.0 - revolution_progress
                    
                    # Adicionar metadata ao ponto
                    point.height_factor = height_factor  # type: ignore
                
                # Filtrar pontos duplicados ou muito próximos
                if path_points:
                    dx = point.x - prev_point.x
                    dy = point.y - prev_point.y
                    dz = point.z - prev_point.z
                    dist = math.sqrt(dx*dx + dy*dy + dz*dz)
                    
                    # Pular se muito próximo (< 0.1mm)
                    if dist < 0.1:
                        continue
                
                path_points.append(point)
                prev_point = point
                point_count += 1
        
        print(f"   • Pontos válidos: {point_count}/{total_points_needed}")
        
        return path_points
    
    def generate_taper_nonplanar(
        self,
        analysis: MeshAnalysis,
        polydata: vtk.vtkPolyData,
        wall_points: List[Point3D],
        num_revolutions: float = 1.0,
    ) -> List[Point3D]:
        """
        Gera percurso de taper (fechamento suave) para non-planar.
        
        ⭐ NOVA ESTRATÉGIA: Detecta a última revolução e suaviza o término
        reduzindo gradualmente a ALTURA DA CAMADA (layer_height) até zero
        no último ponto, sem adicionar voltas extras.
        
        Args:
            analysis: Análise do mesh
            polydata: Dados do modelo
            wall_points: TODOS os pontos da parede
            num_revolutions: IGNORADO (mantido para compatibilidade)
            
        Returns:
            Lista de pontos da última revolução com metadata de altura
        """
        if not self.settings.enable_end_taper:
            return []
        
        if len(wall_points) < 360:
            print(f"⚠️ Pontos insuficientes para taper ({len(wall_points)} < 360)")
            return []
        
        print(f"🔄 Gerando taper non-planar (redução de altura)...")
        
        # ========== EXTRAIR ÚLTIMA REVOLUÇÃO ==========
        
        # Passo angular (1° = 360 pontos por volta)
        angular_step = self.settings.nonplanar_angular_step_deg
        points_per_revolution = int(360.0 / angular_step)
        
        # Pegar últimos N pontos (última revolução)
        last_revolution = wall_points[-points_per_revolution:]
        
        if len(last_revolution) < points_per_revolution:
            print(f"⚠️ Última revolução incompleta ({len(last_revolution)} pontos)")
            last_revolution = wall_points[-len(last_revolution):]
        
        print(f"   • Última revolução: {len(last_revolution)} pontos")
        print(f"   • Estratégia: Reduzir altura da camada 100% → 0%")
        
        # ========== MARCAR PONTOS COM REDUÇÃO DE ALTURA ==========
        
        taper_points: List[Point3D] = []
        total_points = len(last_revolution)
        
        for idx, point in enumerate(last_revolution):
            # Progresso: 0.0 (início) → 1.0 (fim)
            progress = idx / max(1, total_points - 1)
            
            # Fator de altura: 1.0 (100%) → 0.0 (0%)
            height_factor = 1.0 - progress
            
            # Criar novo ponto com metadata de altura
            # (XYZ permanecem iguais, mas precisamos sinalizar redução)
            taper_point = Point3D(point.x, point.y, point.z)
            
            # ⭐ IMPORTANTE: Adicionar atributo customizado para height_factor
            # Será usado no gerador de G-code para ajustar layer_height
            taper_point.height_factor = height_factor  # type: ignore
            
            taper_points.append(taper_point)
        
        print(f"   • Pontos do taper gerados: {len(taper_points)}")
        print(f"   • Altura inicial: 100% → final: 0%")
        
        return taper_points

    def _detect_top_profile_robust(
        self,
        polydata: vtk.vtkPolyData,
        thetas: np.ndarray,
        cx: float,
        cy: float
    ) -> np.ndarray:
        """
        Detecta perfil z_top(θ) usando vtkFeatureEdges (Robust).
        Ideal para meshes complexos/sujos onde o ângulo diédrico falha.
        """
        print("   🔍 Detectando borda superior (Robust - FeatureEdges)...")
        
        # 1. Extrair arestas de borda (boundary edges)
        feature_edges = vtk.vtkFeatureEdges()
        feature_edges.SetInputData(polydata)
        feature_edges.BoundaryEdgesOn()
        feature_edges.FeatureEdgesOff()
        feature_edges.NonManifoldEdgesOff()
        feature_edges.ManifoldEdgesOff()
        feature_edges.Update()
        
        edges_poly = feature_edges.GetOutput()
        
        # 2. Conectar arestas em linhas (stripper)
        stripper = vtk.vtkStripper()
        stripper.SetInputData(edges_poly)
        stripper.JoinContiguousSegmentsOn()
        stripper.Update()
        
        lines_poly = stripper.GetOutput()
        points = lines_poly.GetPoints()
        
        if points is None or lines_poly.GetNumberOfPoints() == 0:
            print("   ⚠️ Nenhuma borda detectada! Usando fallback plano.")
            z_max = polydata.GetBounds()[5]
            return np.full(len(thetas), z_max)
            
        # 3. Coletar pontos de todas as linhas de borda
        # Filtrar apenas a borda superior (z > z_mid)
        bounds = polydata.GetBounds()
        z_mid = (bounds[4] + bounds[5]) / 2.0
        
        # Converter para numpy
        all_points = vtk_to_numpy(points.GetData())
        
        # Filtrar pontos da metade superior
        top_mask = all_points[:, 2] > z_mid
        top_points = all_points[top_mask]
        
        if len(top_points) == 0:
            print("   ⚠️ Nenhuma borda superior encontrada! Usando z_max.")
            return np.full(len(thetas), bounds[5])
            
        print(f"   • Pontos de borda superior encontrados: {len(top_points)}")
        
        # 4. Mapear para z_top(θ) usando projeção radial (igual ao legacy, mas em pontos limpos)
        z_top = []
        
        for th in thetas:
            # Direção radial
            d = np.array([math.cos(th), math.sin(th)])
            
            # Projeção radial dos pontos da borda
            # u = (x-cx)*cos(th) + (y-cy)*sin(th)
            u = (top_points[:, 0] - cx) * d[0] + (top_points[:, 1] - cy) * d[1]
            
            # Pegar z do ponto mais externo (maior u)
            idx_max = np.argmax(u)
            z_top.append(top_points[idx_max, 2])
        
        z_top_array = np.array(z_top)
        
        # Suavizar
        z_top_array = self._smooth_profile(z_top_array, window=10)
        
        print(f"   • Z topo (Robust): {z_top_array.min():.2f} - {z_top_array.max():.2f}mm")
        return z_top_array
