from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

import vtk

from clay_geometry import (
    EPSILON,
    LinearRing,
    LineString,
    MultiPolygon,
    Polygon,
    ShapelyPoint,
    angular_diff,
    angle_of,
    distance_xy,
    unary_union,
)
from clay_models import LayerSlice, MeshAnalysis
from clay_settings import ClayPrintSettings


class MeshAnalyzer:
    def __init__(self, settings: ClayPrintSettings):
        self.settings = settings

    def analyze(self, polydata: vtk.vtkPolyData) -> MeshAnalysis:
        bounds = polydata.GetBounds()
        if bounds is None:
            raise ValueError("polydata has no bounds")
        center_x = (bounds[0] + bounds[1]) * 0.5
        center_y = (bounds[2] + bounds[3]) * 0.5
        base_z = bounds[4]
        top_z = bounds[5]
        height = top_z - base_z
        return MeshAnalysis(
            bounds=bounds,
            center_x=center_x,
            center_y=center_y,
            height=height,
            base_z=base_z,
            top_z=top_z,
        )

    def slice_polygons_at_z(self, polydata: vtk.vtkPolyData, z: float) -> List[Polygon]:
        plane = vtk.vtkPlane()
        plane.SetOrigin(0.0, 0.0, z)
        plane.SetNormal(0.0, 0.0, 1.0)

        cutter = vtk.vtkCutter()
        cutter.SetCutFunction(plane)
        cutter.SetInputData(polydata)
        cutter.Update()

        stripper = vtk.vtkStripper()
        stripper.SetInputConnection(cutter.GetOutputPort())
        stripper.Update()

        output = stripper.GetOutput()
        lines = output.GetLines()
        polygons: List[Polygon] = []
        if lines is None:
            return polygons

        lines.InitTraversal()
        id_list = vtk.vtkIdList()
        while lines.GetNextCell(id_list):
            coords: List[Tuple[float, float]] = []
            for i in range(id_list.GetNumberOfIds()):
                pid = id_list.GetId(i)
                px, py, _pz = output.GetPoint(pid)
                if not coords or distance_xy(coords[-1], (px, py)) > 1e-6:
                    coords.append((px, py))
            if len(coords) < 3:
                continue
            if distance_xy(coords[0], coords[-1]) > 1e-6:
                coords.append(coords[0])
            try:
                ring = LinearRing(coords)
            except Exception:
                continue
            if not ring.is_ccw:
                coords = list(ring.coords)[::-1]
            try:
                poly = Polygon(coords)
            except Exception:
                continue
            if poly.is_valid and poly.area > 1e-3:
                polygons.append(poly)

        if not polygons:
            cut_output = cutter.GetOutput()
            num_points = cut_output.GetNumberOfPoints() if cut_output is not None else 0
            if num_points >= 3:
                cx = cy = 0.0
                points = []
                for idx in range(num_points):
                    px, py, _pz = cut_output.GetPoint(idx)
                    points.append((px, py))
                    cx += px
                    cy += py
                cx /= num_points
                cy /= num_points
                points.sort(key=lambda pt: math.atan2(pt[1] - cy, pt[0] - cx))
                if distance_xy(points[0], points[-1]) > 1e-6:
                    points.append(points[0])
                try:
                    fallback_poly = Polygon(points)
                except Exception:
                    fallback_poly = None
                if fallback_poly and fallback_poly.is_valid and fallback_poly.area > 1e-3:
                    return [fallback_poly]
            return []
        merged = unary_union(polygons)
        if isinstance(merged, Polygon):
            return [merged]
        if isinstance(merged, MultiPolygon):
            return [poly for poly in merged.geoms if poly.area > 1e-3]
        return []

    def build_shell_layers(self, polydata: vtk.vtkPolyData, z_positions: Sequence[float]) -> List[LayerSlice]:
        slices: List[LayerSlice] = []
        for z in z_positions:
            polygons = self.slice_polygons_at_z(polydata, z)
            if polygons:
                slices.append(LayerSlice(z=z, polygons=polygons))
        return slices

    def outer_polygon_at(self, polydata: vtk.vtkPolyData, z: float, analysis: MeshAnalysis) -> Optional[Polygon]:
        cache_key = round(z, 5)
        cached = analysis.contour_cache.get(cache_key)
        if cached is not None:
            return cached
        polygons = self.slice_polygons_at_z(polydata, z)
        if not polygons:
            analysis.contour_cache[cache_key] = None
            return None
        outer = max(polygons, key=lambda p: p.area if p.is_valid else 0.0)
        analysis.contour_cache[cache_key] = outer
        return outer

    @staticmethod
    def point_on_polygon_at_angle(
        polygon: Polygon,
        center: Tuple[float, float],
        angle: float,
    ) -> Tuple[float, float]:
        target_angle = math.atan2(math.sin(angle), math.cos(angle))
        best_point = None
        best_diff = float("inf")
        for x, y in polygon.exterior.coords:
            diff = angular_diff(angle_of((x, y), center), target_angle)
            if diff < best_diff:
                best_diff = diff
                best_point = (x, y)
        if best_point is None:
            x, y = polygon.exterior.coords[0]
            return (x, y)
        return best_point


__all__ = ["MeshAnalyzer"]

