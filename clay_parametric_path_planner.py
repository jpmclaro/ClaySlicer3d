from __future__ import annotations

import math
from dataclasses import dataclass

from clay_geometry import EPSILON, clamp
from clay_models import Point3D


@dataclass
class ParametricPathPlan:
	object_type: str
	wall_height: float
	keyframes: list[tuple[float, float]]
	first_layer_height: float
	wall_layer_height: float
	base_points: list[Point3D]
	wall_points: list[Point3D]
	transition_radius_mm: float
	transition_curve_mode: str
	transition_curve_strength: float
	sharp_corners: bool
	transition_length_mm: float


class ParametricSpiralPlanner:
	def __init__(self, settings):
		self.settings = settings

	def _build_profile(self) -> tuple[list[tuple[float, float]], float]:
		s = self.settings
		obj = str(getattr(s, 'parametric_object_type', 'plate')).strip().lower()

		if obj == 'cup':
			h = max(1.0, float(getattr(s, 'cup_height', 90.0)))
			r0 = max(0.5, float(getattr(s, 'cup_base_diameter', 55.0)) * 0.5)
			r1 = max(0.5, float(getattr(s, 'cup_top_diameter', 85.0)) * 0.5)
			kfs: list[tuple[float, float]] = [(0.0, r0), (h, r1)]
			wall_h = h

		elif obj == 'jar':
			h_body = max(1.0, float(getattr(s, 'jar_body_height', 85.0)))
			h_neck = max(1.0, float(getattr(s, 'jar_neck_height', 20.0)))
			h = h_body + h_neck
			r0 = max(0.5, float(getattr(s, 'jar_base_diameter', 55.0)) * 0.5)
			r_mid = max(0.5, float(getattr(s, 'jar_max_body_diameter', 110.0)) * 0.5)
			r_top = max(0.5, float(getattr(s, 'jar_top_diameter', 70.0)) * 0.5)
			kfs = [(0.0, r0), (h_body, r_mid), (h, r_top)]
			wall_h = h

		elif obj == 'bottle':
			h_body = max(1.0, float(getattr(s, 'bottle_body_height', 100.0)))
			h_shoulder = max(0.5, float(getattr(s, 'bottle_shoulder_height', 20.0)))
			h_neck = max(1.0, float(getattr(s, 'bottle_neck_height', 45.0)))
			h = h_body + h_shoulder + h_neck
			r0 = max(0.5, float(getattr(s, 'bottle_base_diameter', 55.0)) * 0.5)
			r_body_top = max(0.5, float(getattr(s, 'bottle_body_top_diameter', 80.0)) * 0.5)
			r_neck = max(0.5, float(getattr(s, 'bottle_neck_diameter', 36.0)) * 0.5)
			kfs = [
				(0.0, r0),
				(h_body, r_body_top),
				(h_body + h_shoulder, r_neck),
				(h, r_neck),
			]
			wall_h = h

		else:  # plate (default)
			h = max(1.0, float(getattr(s, 'plate_wall_height', 30.0)))
			r0 = max(0.5, float(getattr(s, 'plate_base_diameter', 60.0)) * 0.5)
			r1 = max(0.5, float(getattr(s, 'plate_top_diameter', 140.0)) * 0.5)
			kfs = [(0.0, r0), (h, r1)]
			wall_h = h

		# Keyframes intermediários genéricos: inseridos entre o primeiro e o último,
		# ordenados por altura. Pontos fora do intervalo [0, wall_h] são ignorados.
		extra: list[tuple[float, float]] = []
		if getattr(s, 'parametric_mid1_enabled', False):
			h1 = float(getattr(s, 'parametric_mid1_height', 30.0))
			r1 = max(0.5, float(getattr(s, 'parametric_mid1_radius', 40.0)))
			if EPSILON < h1 < wall_h - EPSILON:
				extra.append((h1, r1))
		if getattr(s, 'parametric_mid2_enabled', False):
			h2 = float(getattr(s, 'parametric_mid2_height', 60.0))
			r2 = max(0.5, float(getattr(s, 'parametric_mid2_radius', 45.0)))
			if EPSILON < h2 < wall_h - EPSILON:
				extra.append((h2, r2))
		if extra:
			first = kfs[0]
			last  = kfs[-1]
			middle = sorted(kfs[1:-1] + extra, key=lambda kf: kf[0])
			kfs = [first] + middle + [last]

		return kfs, wall_h

	def _interpolate_radius_profile(
		self,
		z_rel: float,
		keyframes: list[tuple[float, float]],
		sharp_corners: bool,
		transition_len_mm: float,
	) -> float:
		if not keyframes:
			return 1.0
		if z_rel <= keyframes[0][0]:
			return keyframes[0][1]

		if sharp_corners or transition_len_mm <= EPSILON or len(keyframes) < 3:
			for idx in range(1, len(keyframes)):
				z0, r0 = keyframes[idx - 1]
				z1, r1 = keyframes[idx]
				if z_rel <= z1:
					if abs(z1 - z0) <= EPSILON:
						return r1
					t = (z_rel - z0) / (z1 - z0)
					return r0 + (r1 - r0) * t
			return keyframes[-1][1]

		half_win = max(0.0, transition_len_mm * 0.5)
		for corner_idx in range(1, len(keyframes) - 1):
			zc, rc = keyframes[corner_idx]
			z_left, r_left = keyframes[corner_idx - 1]
			z_right, r_right = keyframes[corner_idx + 1]

			left_room = max(EPSILON, zc - z_left)
			right_room = max(EPSILON, z_right - zc)
			local_half = min(half_win, left_room * 0.45, right_room * 0.45)
			if local_half <= EPSILON:
				continue

			z_a = zc - local_half
			z_b = zc + local_half
			if z_rel < z_a or z_rel > z_b:
				continue

			t_prev = (z_rel - z_left) / max(EPSILON, zc - z_left)
			r_prev = r_left + (rc - r_left) * t_prev
			t_next = (z_rel - zc) / max(EPSILON, z_right - zc)
			r_next = rc + (r_right - rc) * t_next

			t = (z_rel - z_a) / max(EPSILON, z_b - z_a)
			t_smooth = t * t * (3.0 - 2.0 * t)
			return r_prev + (r_next - r_prev) * t_smooth

		for idx in range(1, len(keyframes)):
			z0, r0 = keyframes[idx - 1]
			z1, r1 = keyframes[idx]
			if z_rel <= z1:
				if abs(z1 - z0) <= EPSILON:
					return r1
				t = (z_rel - z0) / (z1 - z0)
				return r0 + (r1 - r0) * t
		return keyframes[-1][1]

	def _compute_wall_slope(self, z_rel: float, keyframes: list[tuple[float, float]]) -> float:
		if len(keyframes) < 2:
			return 0.0
		if z_rel <= keyframes[0][0]:
			z0, r0 = keyframes[0]
			z1, r1 = keyframes[1]
			return (r1 - r0) / max(EPSILON, z1 - z0)

		for idx in range(1, len(keyframes)):
			z0, r0 = keyframes[idx - 1]
			z1, r1 = keyframes[idx]
			if z_rel <= z1 + EPSILON:
				return (r1 - r0) / max(EPSILON, z1 - z0)

		z0, r0 = keyframes[-2]
		z1, r1 = keyframes[-1]
		return (r1 - r0) / max(EPSILON, z1 - z0)

	@staticmethod
	def _hermite_radius(p0: float, p1: float, m0: float, m1: float, u: float, length: float) -> float:
		u2 = u * u
		u3 = u2 * u
		h00 = 2.0 * u3 - 3.0 * u2 + 1.0
		h10 = u3 - 2.0 * u2 + u
		h01 = -2.0 * u3 + 3.0 * u2
		h11 = u3 - u2
		return h00 * p0 + h10 * (m0 * length) + h01 * p1 + h11 * (m1 * length)

	@staticmethod
	def _apply_curve_mode(u: float, mode: str, strength: float) -> float:
		if mode != 's_curve':
			return u
		power = 1.0 + 3.0 * clamp(strength, 0.0, 1.0)
		a = u ** power
		b = (1.0 - u) ** power
		return a / max(EPSILON, a + b)

	def build_plan(self) -> ParametricPathPlan:
		# ════════════════════════════════════════════════════════════════
		# FASE 1 — Parâmetros
		# ════════════════════════════════════════════════════════════════
		s = self.settings
		keyframes, wall_height = self._build_profile()
		base_r    = keyframes[0][1]

		sharp     = bool(getattr(s, 'parametric_enable_sharp_corners', False))
		trans_len = max(0.0, float(getattr(s, 'parametric_transition_length_mm', 3.0)))
		crv_mode  = str(getattr(s, 'parametric_base_transition_curve_mode', 'fillet')).strip().lower()
		crv_str   = clamp(float(getattr(s, 'parametric_base_transition_curve_strength', 0.5)), 0.0, 1.0)

		first_h   = max(0.05, float(getattr(s, 'first_layer_height', 1.0)))
		wall_h    = max(0.05, float(getattr(s, 'layer_height', 1.0)))
		z0        = first_h

		base_w    = max(0.1, float(getattr(s, 'extrusion_width', 1.0)))
		wall_w    = max(0.1, float(getattr(s, 'other_layers_extrusion_width', base_w)))

		max_deg   = clamp(float(getattr(s, 'parametric_max_overhang_angle_deg', 25.0)), 5.0, 85.0)
		tan_lim   = math.tan(math.radians(max_deg))

		lat_frac  = clamp(float(getattr(s, 'wall_lateral_fraction', 0.4)), 0.1, 1.0)
		max_lat   = lat_frac * wall_w

		res_deg   = clamp(float(getattr(s, 'vase_mode_resolution_deg', 2.0)), 0.5, 8.0)
		spr       = max(45, int(round(360.0 / res_deg)))   # steps per revolution
		dtheta    = (2.0 * math.pi) / float(spr)

		# Raio do fillet: 0 se sharp_corners, limitado a 45 % da altura
		req_fillet = max(0.0, float(getattr(s, 'parametric_base_transition_radius_mm', 6.0)))
		R = min(req_fillet, wall_height * 0.45) if (not sharp and req_fillet > EPSILON) else 0.0

		# ════════════════════════════════════════════════════════════════
		# FASE 2 — Espiral de Arquimedes (base plana em Z = z0)
		# ════════════════════════════════════════════════════════════════
		spacing = max(0.1, base_w * (1.0 - s.line_overlap))
		b       = spacing / (2.0 * math.pi)
		drift   = 0.07          # deriva de fase por volta para suavizar junta
		theta   = 0.0
		end_angle = 0.0
		base_pts: list[Point3D] = [Point3D(0.0, 0.0, z0)]

		for _ in range(25000):
			r   = min(base_r, b * theta)
			ang = theta + 2.0 * math.pi * drift * (theta / (2.0 * math.pi))
			pt  = Point3D(r * math.cos(ang), r * math.sin(ang), z0)
			if pt.distance_to(base_pts[-1]) > 1e-5:
				base_pts.append(pt)
			end_angle = ang
			if r >= base_r:
				break
			step = spacing / max(r, spacing * 0.5)
			theta += max(math.radians(0.35), min(math.radians(5.0), step))

		# Garantir que a espiral termina exatamente em base_r
		end_r = math.hypot(base_pts[-1].x, base_pts[-1].y)
		if abs(base_r - end_r) > max(0.02, spacing * 0.08):
			base_pts.append(Point3D(base_r * math.cos(end_angle), base_r * math.sin(end_angle), z0))

		# Anel de fechamento: garante cobertura entre a última volta Arquimediana
		# (em base_r) e o ponto de início do arco helicoidal.
		# O arco θ-uniforme começa em r=base_r+R·sin(Δθ) ≈ base_r; com o anel
		# garantimos que não há gap na transição vista de cima.
		for i in range(1, spr + 1):
			ang = end_angle + 2.0 * math.pi * i / spr
			base_pts.append(Point3D(base_r * math.cos(ang), base_r * math.sin(ang), z0))
		end_angle = end_angle + 2.0 * math.pi  # atualiza ângulo para o helicoide partir daqui

		# ════════════════════════════════════════════════════════════════
		# FASE 3 — Profile polyline (z_rel, r)
		#
		# ZONA 1 — ARCO CIRCULAR  z ∈ [0, z_t]
		#   r(z) = base_r + √(2Rz − z²)     (círculo de raio R)
		#   z=0   → tangente horizontal (C¹ com a base plana)
		#   z=z_t → tangente = m_wall   (C¹ com a parede — sem joelho)
		#
		#   z_t é o ponto onde dr/dz do arco iguala m_wall:
		#     (R − z) / √(2Rz − z²) = m_wall
		#     → z_t = R · (1 − m / √(1 + m²))
		#
		#   Se m_wall é pequeno (xícara, garrafa), z_t → R (arco completo).
		#   Se m_wall é grande (prato), z_t é pequeno — e a curva visível
		#   fica corretamente concentrada na base, exatamente como na foto.
		#
		# ZONA 2 — PAREDE  z ∈ [z_t, H]
		#   A parede tem slope m_wall e parte de r_t = arc_r(z_t).
		#   Keyframes ajustados de modo que o ponto (z_t, r_t) é a âncora
		#   e o ponto final do design é preservado.
		#   Sem clamp aqui — controle de cordão via sub-rev na FASE 4.
		# ════════════════════════════════════════════════════════════════

		# Inclinação da parede entre os dois primeiros keyframes originais
		m_wall = 0.0
		if len(keyframes) >= 2:
			m_wall = (keyframes[1][1] - keyframes[0][1]) / max(EPSILON, keyframes[1][0] - keyframes[0][0])

		# z_t: ponto exato onde o arco se une à parede com C¹.
		# Condição: slope do arco em z_t == slope efetiva da parede (r_t→r_kf1).
		#   slope_arco(z_t) = (R - z_t) / √(2Rz_t - z_t²)
		#   slope_parede    = (r_kf1 - r_t) / (z_kf1 - z_t)
		#                   = (r_kf1 - base_r - √(2Rz_t - z_t²)) / (z_kf1 - z_t)
		# Resolvemos numericamente por bissecção em z_t ∈ (0, R).
		z_kf1 = keyframes[1][0]
		r_kf1 = keyframes[1][1]

		def slope_err(zt: float) -> float:
			disc = max(EPSILON, 2.0 * R * zt - zt * zt)
			sq   = math.sqrt(disc)
			s_arc  = (R - zt) / sq
			r_t_   = base_r + sq
			s_wall = (r_kf1 - r_t_) / max(EPSILON, z_kf1 - zt)
			return s_arc - s_wall

		if R > EPSILON and m_wall > EPSILON:
			# Bissecção: err(0⁺) > 0 (slope_arco=∞), err(R) pode ser <0
			lo, hi = EPSILON, R - EPSILON
			if slope_err(hi) < 0.0:
				for _ in range(60):
					mid = 0.5 * (lo + hi)
					if slope_err(mid) > 0.0:
						lo = mid
					else:
						hi = mid
				z_t = 0.5 * (lo + hi)
			else:
				z_t = R   # nunca cruza — arco completo (parede muito suave)
		elif R > EPSILON:
			z_t = R
		else:
			z_t = 0.0

		# Ponto de junção e slope confirmado
		disc_t = max(EPSILON, 2.0 * R * z_t - z_t * z_t)
		r_t    = base_r + math.sqrt(disc_t) if R > EPSILON else base_r

		# Keyframes ajustados: palavra arranca de (z_t, r_t), destinos preservados
		adj_kf: list[tuple[float, float]] = [(z_t, r_t)] + list(keyframes[1:])

		def arc_r(z_local: float) -> float:
			disc = max(0.0, 2.0 * R * z_local - z_local * z_local)
			return base_r + math.sqrt(disc)

		# Profile da parede: começa em (z_t, r_t) e avança em passos wall_h.
		# O arco (z∈[0,z_t]) será gerado analiticamente na Fase 4, sem profile.
		profile: list[tuple[float, float]] = [(z_t, r_t)]
		z_rel  = z_t
		prev_r = r_t

		# Pontos da parede (passo = wall_h, começa após o arco em z_t)
		while z_rel < wall_height - 1e-6:
			z_rel = min(wall_height, z_rel + wall_h)
			new_r = max(0.1, self._interpolate_radius_profile(z_rel, adj_kf, sharp, trans_len))
			profile.append((z_rel, new_r))
			prev_r = new_r

		# ════════════════════════════════════════════════════════════════
		# FASE 4 — Gerar wall_points: espiral helicoidal θ-uniforme + parede
		#
		# ZONA DE TRANSIÇÃO (base → parede): arco circular parametrizado por θ
		# de forma uniforme — r(θ) = base_r + R·sin(θ), z(θ) = R(1−cos(θ)).
		# Isso evita o salto brusco em z que ocorre quando r→r_t (sin→1).
		#
		# n_radial usa o passo Arquimediano: max Δr por revolução ≈ R·Δθ
		# na zona θ≈0, garantindo cobertura equivalente à espiral da base.
		# ════════════════════════════════════════════════════════════════
		extrusion_w      = max(EPSILON, getattr(s, 'other_layers_extrusion_width',
		                       getattr(s, 'extrusion_width', 3.0)))
		lateral_fraction = max(0.1, min(1.0, getattr(s, 'wall_lateral_fraction', 0.4)))
		max_lat          = lateral_fraction * extrusion_w

		wall_pts: list[Point3D] = []
		theta_w = end_angle

		# arc_layer_h: controla pitch do arco E dos segmentos de contração (dr<0)
		arc_layer_h = float(getattr(s, 'parametric_arc_layer_height', 0.0))
		if arc_layer_h <= EPSILON:
			arc_layer_h = wall_h  # Auto: mesma altura de camada da parede

		# ── Zona 1: arco circular θ-uniforme com n_revs controlado ────
		if R > EPSILON and z_t > EPSILON:
			cos_t       = max(-1.0, min(1.0, 1.0 - z_t / R))
			theta_arc_t = math.acos(cos_t)

			# n_radial: passo Arquimediano — Δr máximo ≈ R·Δθ (em θ≈0)
			n_radial     = max(1, math.ceil(R * theta_arc_t / spacing))
			n_z          = max(1, math.ceil(z_t / arc_layer_h))
			num_arc_revs = max(n_radial, n_z)
			print(f"[HELIX] base_r={base_r:.2f} r_t={r_t:.2f} z_t={z_t:.3f} "
			      f"θ_t={math.degrees(theta_arc_t):.1f}° n_rad={n_radial} "
			      f"n_z={n_z} revs={num_arc_revs} Δz/rev={z_t/num_arc_revs:.3f}")

			total_arc_steps = num_arc_revs * spr
			for step in range(1, total_arc_steps + 1):
				theta_arc = theta_arc_t * step / float(total_arc_steps)
				r_pt = max(0.1, base_r + R * math.sin(theta_arc))
				z_pt = z0 + R * (1.0 - math.cos(theta_arc))
				theta_w += dtheta
				wall_pts.append(Point3D(r_pt * math.cos(theta_w), r_pt * math.sin(theta_w), z_pt))
		elif z_t > EPSILON:
			# R=0 (canto vivo): rampeia verticalmente até z_t
			n_z = max(1, math.ceil(z_t / wall_h))
			total_arc_steps = n_z * spr
			for step in range(1, total_arc_steps + 1):
				t   = step / float(total_arc_steps)
				z_pt = z0 + z_t * t
				theta_w += dtheta
				wall_pts.append(Point3D(r_t * math.cos(theta_w), r_t * math.sin(theta_w), z_pt))

		# ── Zona 2: parede ────────────────────────────────────────────
		# Mesma fórmula da Zona 1 (arco): para cada span do adj_kf,
		#   n_radial = ceil(|dr| / spacing) — Δr/rev ≤ spacing (Arquimediano)
		#   n_z      = ceil(dz / wall_layer_h_w) — pitch ≈ wall_layer_h_w
		#   n_revs   = max(n_radial, n_z)
		#   total    = n_revs × spr
		#
		# Iterar sobre adj_kf (spans do perfil) e NÃO sobre o profile amostrado
		# (wall_h fixo) é essencial: com dz=wall_h cada segmento já equivale
		# a ~1 revolução, então n_revs>1 comprimiria o pitch para wall_h/n_revs
		# criando a "trança". Com spans completos, n_z domina e pitch≈wall_layer_h_w.
		# A interpolação suave (fillet/s_curve) é preservada via _interpolate_radius_profile.
		wall_layer_h_w = float(getattr(s, 'parametric_wall_layer_height', 0.0))
		if wall_layer_h_w <= EPSILON:
			wall_layer_h_w = wall_h   # Auto

		for span_idx in range(1, len(adj_kf)):
			z_start, r_start_kf = adj_kf[span_idx - 1]
			z_end,   r_end_kf   = adj_kf[span_idx]
			dz = z_end - z_start
			dr = r_end_kf - r_start_kf
			if dz <= EPSILON:
				continue

			n_radial    = max(1, math.ceil(abs(dr) / spacing)) if abs(dr) > EPSILON else 1
			n_z         = max(1, math.ceil(dz / wall_layer_h_w))
			n_revs      = max(n_radial, n_z)
			total_steps = n_revs * spr

			for step in range(1, total_steps + 1):
				t        = step / float(total_steps)
				z_rel_pt = z_start + dz * t
				# Raio com interpolação suave (fillet/s_curve) baked no adj_kf
				r_pt = max(0.1, self._interpolate_radius_profile(
					z_rel_pt, adj_kf, sharp, trans_len))
				z_pt = z0 + z_rel_pt
				theta_w += dtheta
				wall_pts.append(Point3D(r_pt * math.cos(theta_w), r_pt * math.sin(theta_w), z_pt))

		# ════════════════════════════════════════════════════════════════
		# FASE 5 — Ângulo de costura (ponto inicial) + Retorno
		# ════════════════════════════════════════════════════════════════
		# Rotaciona toda a geometria em torno de Z para posicionar a costura.
		seam_rad = math.radians(float(getattr(s, 'parametric_seam_angle_deg', 0.0)))
		if abs(seam_rad) > 1e-9:
			cos_a = math.cos(seam_rad)
			sin_a = math.sin(seam_rad)
			base_pts = [
				Point3D(p.x * cos_a - p.y * sin_a, p.x * sin_a + p.y * cos_a, p.z)
				for p in base_pts
			]
			wall_pts = [
				Point3D(p.x * cos_a - p.y * sin_a, p.x * sin_a + p.y * cos_a, p.z)
				for p in wall_pts
			]

		return ParametricPathPlan(
			object_type      = str(getattr(s, 'parametric_object_type', 'plate')).strip().lower(),
			wall_height      = wall_height,
			keyframes        = keyframes,
			first_layer_height   = first_h,
			wall_layer_height    = wall_h,
			base_points      = base_pts,
			wall_points      = wall_pts,
			transition_radius_mm     = R,
			transition_curve_mode    = crv_mode,
			transition_curve_strength= crv_str,
			sharp_corners    = sharp,
			transition_length_mm = trans_len,
		)
