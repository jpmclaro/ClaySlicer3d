from dataclasses import dataclass


@dataclass
class ClayPrintSettings:
    nozzle_diameter: float = 2.0
    extrusion_width: float = 2.5
    other_layers_extrusion_width: float = 2.5  # Largura de extrusão da 2ª camada em diante
    first_layer_height: float = 1.0
    layer_height: float = 1.0
    print_speed: float = 600.0
    travel_speed: float = 1200.0
    first_layer_speed: float = 600.0
    acceleration: float = 500.0  # mm/s²
    wall_speed: float = 600.0
    line_overlap: float = 0.2
    wall_overlap: float = 0.15
    max_volumetric_flow_mm3_s: float = 30.0
    print_center_x: float = 155.0
    print_center_y: float = 230.0
    spiral_spacing: float = 2.0
    angular_step_mm: float = 0.1
    enable_center_micro_spiral: bool = True
    enable_center_point_extrusion: bool = False
    center_point_width: float = 2.0
    center_point_height: float = 1.0
    center_point_dips: int = 2
    micro_spiral_flow_rate: float = 1.0
    flow_rate: float = 1.0
    pressure_advance: float = 0.0
    enable_pressure_advance: bool = False
    bed_temp: float = 25.0
    chamber_temp: float = 20.0
    retract_length: float = 1.0
    retract_speed: float = 1800.0
    base_layers_count: int = 1
    base_pattern: str = "archimedes"
    base_direction: str = "center_out"
    show_skirt_in_preview: bool = False
    base_ramp_only_first_transition: bool = False
    enable_end_taper: bool = False
    end_taper_revolutions: float = 1.0
    height_transition_revolutions: float = 1.0
    transition_blend_flow_factor: float = 1.0
    enable_overhang_compensation: bool = False
    min_vertical_overlap: float = 0.6  # Reutilizado como fator de largura extra para overhangs
    overhang_support_layers: int = 1
    max_overhang_angle_deg: float = 25.0
    preset_name: str = "manual"
    vase_mode_resolution_deg: float = 2.0
    perimeter_count: int = 1
    smoothing_tolerance: float = 0.2

    wall_flow_multiplier: float = 1.0

    # Compensação de curvatura nas paredes (sub-voltas nas transições)
    # wall_lateral_fraction: fração da largura de extrusão permitida por sub-volta (0.1–1.0)
    # wall_curve_sensitivity: multiplicador do desvio padrão para detectar pico (0.5–4.0)
    wall_lateral_fraction: float = 0.4
    wall_curve_sensitivity: float = 1.5

    # Parametric object mode (perfil gerado sem malha)
    enable_parametric_mode: bool = False
    parametric_object_type: str = "plate"  # plate, cup, jar, bottle
    parametric_enable_sharp_corners: bool = False
    parametric_transition_length_mm: float = 3.0
    parametric_base_transition_radius_mm: float = 6.0
    parametric_base_transition_curve_mode: str = "fillet"  # fillet, s_curve
    parametric_base_transition_curve_strength: float = 0.5  # 0..1
    parametric_max_overhang_angle_deg: float = 25.0
    # Altura de extrusão alvo na zona do arco (0.0 = automático pelo limite radial).
    # Valores menores produzem camadas mais finas no filete base→parede.
    parametric_arc_layer_height: float = 0.0
    parametric_wall_layer_height: float = 0.0   # 0 = Auto (usa wall_h do preset)
    # Ângulo do ponto inicial da espiral (costura), em graus [0..360).
    # 0° = direita (Leste), 90° = topo (Norte, frente da peça), 180° = esquerda.
    parametric_seam_angle_deg: float = 0.0

    # Keyframes intermediários genéricos — aplicados a todos os tipos de objeto.
    # A altura é em mm a partir da base (0 = base do corpo, acima do arco).
    parametric_mid1_enabled: bool = False
    parametric_mid1_height: float = 30.0
    parametric_mid1_radius: float = 40.0
    parametric_mid2_enabled: bool = False
    parametric_mid2_height: float = 60.0
    parametric_mid2_radius: float = 45.0

    # Plate
    plate_base_diameter: float = 60.0
    plate_top_diameter: float = 140.0
    plate_wall_height: float = 30.0

    # Cup
    cup_base_diameter: float = 55.0
    cup_top_diameter: float = 85.0
    cup_height: float = 90.0

    # Jar
    jar_base_diameter: float = 55.0
    jar_max_body_diameter: float = 110.0
    jar_body_height: float = 85.0
    jar_top_diameter: float = 70.0
    jar_neck_height: float = 20.0

    # Bottle
    bottle_base_diameter: float = 55.0
    bottle_body_height: float = 100.0
    bottle_body_top_diameter: float = 80.0
    bottle_neck_diameter: float = 36.0
    bottle_neck_height: float = 45.0
    bottle_shoulder_height: float = 20.0
    
    # Non-Planar mode settings
    enable_nonplanar_mode: bool = False
    nonplanar_algorithm: int = 1  # 1=Legacy (Warping), 2=Robust (Clean+FeatureEdges)
    nonplanar_angular_step_deg: float = 1.0
    nonplanar_angle_threshold_deg: float = 60.0
    nonplanar_z_epsilon: float = 0.03

