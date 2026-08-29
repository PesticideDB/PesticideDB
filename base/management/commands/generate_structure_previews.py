import html
from pathlib import Path

import numpy as np
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Generate lightweight SVG preview images from local PDB structure files."

    def add_arguments(self, parser):
        parser.add_argument("--overwrite", action="store_true")
        parser.add_argument(
            "--width",
            type=int,
            default=900,
            help="SVG preview width in pixels.",
        )
        parser.add_argument(
            "--height",
            type=int,
            default=650,
            help="SVG preview height in pixels.",
        )

    def handle(self, *args, **options):
        pdb_dir = settings.MEDIA_ROOT / "protein_structures" / "pdb"
        image_dir = settings.MEDIA_ROOT / "protein_structures" / "images"
        image_dir.mkdir(parents=True, exist_ok=True)

        if not pdb_dir.exists():
            self.stdout.write(self.style.WARNING(f"No PDB directory found: {pdb_dir}"))
            return

        created = 0
        skipped = 0
        failed = 0

        for pdb_path in sorted(pdb_dir.glob("*.pdb")):
            svg_path = image_dir / f"{pdb_path.stem}.svg"
            if svg_path.exists() and not options["overwrite"]:
                skipped += 1
                continue

            try:
                coords = self.extract_backbone_coordinates(pdb_path)
                if len(coords) < 2:
                    raise ValueError("No backbone coordinates found.")
                svg_path.write_text(
                    self.render_svg(
                        pdb_id=pdb_path.stem,
                        coords=coords,
                        width=options["width"],
                        height=options["height"],
                    )
                )
                created += 1
                self.stdout.write(self.style.SUCCESS(f"Generated preview: {svg_path.name}"))
            except Exception as exc:
                failed += 1
                self.stdout.write(
                    self.style.WARNING(f"Could not generate preview for {pdb_path.name}: {exc}")
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Structure previews complete. Created: {created}. "
                f"Skipped existing: {skipped}. Failed: {failed}."
            )
        )

    def extract_backbone_coordinates(self, pdb_path):
        coords = []
        fallback = []

        for line in pdb_path.read_text(errors="ignore").splitlines():
            if not line.startswith("ATOM"):
                continue

            atom_name = line[12:16].strip()
            try:
                coord = [
                    float(line[30:38]),
                    float(line[38:46]),
                    float(line[46:54]),
                ]
            except ValueError:
                continue

            if atom_name == "CA":
                coords.append(coord)
            elif atom_name in {"N", "C", "O"}:
                fallback.append(coord)

        return np.array(coords or fallback, dtype=float)

    def render_svg(self, pdb_id, coords, width, height):
        projected = self.project_coordinates(coords)
        points = self.scale_to_canvas(projected, width=width, height=height)
        depths = projected[:, 2]
        depth_min = float(depths.min())
        depth_range = float(depths.max() - depth_min) or 1.0

        polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
        circles = []
        step = max(len(points) // 80, 1)
        for idx in range(0, len(points), step):
            x, y = points[idx]
            depth_ratio = (float(depths[idx]) - depth_min) / depth_range
            color = self.interpolate_color(depth_ratio)
            radius = 2.7 + depth_ratio * 2.0
            circles.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" '
                f'fill="{color}" opacity="0.95" />'
            )

        title = html.escape(pdb_id)
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="Predicted protein structure preview for {title}">
  <rect width="100%" height="100%" fill="#f8fafc"/>
  <text x="36" y="48" font-family="Arial, sans-serif" font-size="24" font-weight="700" fill="#1f2937">{title}</text>
  <text x="36" y="78" font-family="Arial, sans-serif" font-size="15" fill="#64748b">Predicted structure preview generated from local PDB backbone coordinates</text>
  <g filter="drop-shadow(0 12px 18px rgba(15, 23, 42, 0.18))">
    <polyline points="{polyline}" fill="none" stroke="#0f766e" stroke-width="5.5" stroke-linecap="round" stroke-linejoin="round" opacity="0.72"/>
    <polyline points="{polyline}" fill="none" stroke="#14b8a6" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" opacity="0.9"/>
    {''.join(circles)}
  </g>
</svg>
'''

    def project_coordinates(self, coords):
        centered = coords - coords.mean(axis=0)
        _, _, vh = np.linalg.svd(centered, full_matrices=False)
        projected = centered @ vh.T
        return projected[:, :3]

    def scale_to_canvas(self, projected, width, height):
        xy = projected[:, :2]
        mins = xy.min(axis=0)
        maxs = xy.max(axis=0)
        span = np.maximum(maxs - mins, 1.0)
        padding_x = width * 0.09
        padding_y = height * 0.16
        available = np.array([width - padding_x * 2, height - padding_y * 2])
        scale = min(available / span)
        scaled = (xy - mins - span / 2) * scale
        scaled[:, 0] += width / 2
        scaled[:, 1] += height / 2 + height * 0.06
        return scaled

    def interpolate_color(self, ratio):
        start = np.array([13, 148, 136])
        end = np.array([37, 99, 235])
        color = (start + (end - start) * ratio).astype(int)
        return f"rgb({color[0]}, {color[1]}, {color[2]})"
