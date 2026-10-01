"""Read-only import of supplied raw EIS workbooks. Never modifies sources.
Run with the bundled document Python (openpyxl, numpy) and a PCB_Testing path.
"""
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
from openpyxl import load_workbook

root = Path(sys.argv[1])
output = Path(__file__).resolve().parents[1]/"calibration"/"stim2_pt.json"
groups = {"pt": sorted((root/"EIS_device_190126/raw").glob("*Pt*.xlsx"))}
for bp in (0, 1):
    for arm in ("WE", "CE"):
        groups[f"bp{bp}_{arm.lower()}"] = sorted((root/"EIS_140126/raw/CE_WE_arms").glob(f"EIS_stim2_{bp}_*_{arm}_*.xlsx"))
result = {"version": "stim2-pt-2026-01-raw-v1", "approved": False,
          "notes": ["1 Hz instrument warning: no frequencies approved for physical use yet.",
                    "WE includes monitoring resistor. Filter ON is bypass 0.",
                    "Opposite terminals disconnected for separate arm measurements."], "groups": {}}
for group, paths in groups.items():
    if len(paths) != 3:
        raise ValueError(f"Expected three samples in {group}: {paths}")
    curves, provenance = [], []
    for path in paths:
        book = load_workbook(path, read_only=True, data_only=True)
        sheet = book.active
        # Autolab exports incorrect worksheet dimensions; read actual XML rows.
        sheet.reset_dimensions()
        rows = list(sheet.values)
        values = np.array(rows[1:], dtype=float)
        book.close()
        frequency = values[:, 1]
        z = values[:, 2]-1j*values[:, 3]
        if not np.allclose(abs(z), values[:, 4]) or not np.allclose(np.angle(z, deg=True), -values[:, 5]):
            raise ValueError(f"Magnitude/phase cross-check failed: {path}")
        if curves and not np.array_equal(frequency, curves[0][0]):
            raise ValueError("Different frequency grids")
        curves.append((frequency, z))
        provenance.append({"file": str(path.relative_to(root)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    stack = np.array([z for f, z in curves])
    order = np.argsort(frequency)
    mean = stack.mean(axis=0)
    result["groups"][group] = {"frequency_hz": frequency[order].tolist(), "real": mean.real[order].tolist(),
        "imag": mean.imag[order].tolist(), "sample_real": stack.real[:, order].tolist(),
        "sample_imag": stack.imag[:, order].tolist(), "sources": provenance}
output.parent.mkdir(exist_ok=True)
output.write_text(json.dumps(result, indent=2), encoding="utf-8")
print(f"Imported {sum(len(x) for x in groups.values())} recordings into {output}")
