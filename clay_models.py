from dataclasses import dataclass, field
from typing import Dict, List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from shapely.geometry import Polygon


@dataclass
class Point3D:
    x: float
    y: float
    z: float

    def distance_to(self, other: "Point3D") -> float:
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2 + (self.z - other.z) ** 2) ** 0.5


@dataclass
class MeshAnalysis:
    bounds: Tuple[float, float, float, float, float, float]
    center_x: float
    center_y: float
    height: float
    base_z: float
    top_z: float
    contour_cache: Dict[float, "Polygon | None"] = field(default_factory=dict)


@dataclass
class LayerSlice:
    z: float
    polygons: List["Polygon"]
