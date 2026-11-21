from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

LOWT_GOVERNING_MIN_K = 2.0
LOWT_GOVERNING_MAX_K = 4.5
COOLPROP_HELIUM_ANCILLARY_MIN_K = 2.1768

OUTPUTS = {
    "density_kg_m3": "Dmass",
    "enthalpy_J_kg": "Hmass",
    "entropy_J_kgK": "Smass",
    "cp_J_kgK": "Cpmass",
    "cv_J_kgK": "Cvmass",
    "viscosity_Pa_s": "VISCOSITY",
    "conductivity_W_mK": "CONDUCTIVITY",
}


@dataclass(frozen=True)
class PropertyRequest:
    temperature_K: float
    pressure_Pa: float
    fluid: str = "Helium"
    authority: str = "INDEPENDENT_CHECK"
    point_id: str | None = None


@dataclass
class PropertyResult:
    status: str
    provider: str | None
    authority_role: str
    request: dict[str, Any]
    values: dict[str, float | None]
    phase: str | None
    evidence: dict[str, Any]
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def is_lowt_governing_band(T: float) -> bool:
    return LOWT_GOVERNING_MIN_K <= T <= LOWT_GOVERNING_MAX_K


def _empty_result(request: PropertyRequest, status: str, error: str) -> PropertyResult:
    return PropertyResult(
        status=status,
        provider=None,
        authority_role=request.authority,
        request=asdict(request),
        values={name: None for name in OUTPUTS},
        phase=None,
        evidence={},
        errors=[error],
    )


class CoolPropProvider:
    name = "CoolProp"

    def evaluate(self, request: PropertyRequest) -> PropertyResult:
        from CoolProp import CoolProp as CP
        import CoolProp

        values: dict[str, float | None] = {}
        errors: list[str] = []
        for name, key in OUTPUTS.items():
            try:
                value = float(CP.PropsSI(key, "T", request.temperature_K, "P", request.pressure_Pa, "HEOS::Helium"))
                values[name] = value if math.isfinite(value) else None
                if values[name] is None:
                    errors.append(f"{key}: non-finite result")
            except Exception as exc:
                values[name] = None
                errors.append(f"{key}: {exc}")
        try:
            phase = CP.PhaseSI("T", request.temperature_K, "P", request.pressure_Pa, "HEOS::Helium")
        except Exception as exc:
            phase = None
            errors.append(f"PhaseSI: {exc}")

        if request.temperature_K < COOLPROP_HELIUM_ANCILLARY_MIN_K and errors:
            status = "OUT_OF_DOMAIN_EXPECTED"
        else:
            status = "PASS" if not errors else "FAIL"

        return PropertyResult(
            status=status,
            provider=self.name,
            authority_role="INDEPENDENT_CHECK",
            request=asdict(request),
            values=values,
            phase=phase,
            evidence={
                "providerVersion": getattr(CoolProp, "__version__", "UNKNOWN"),
                "providerGitRevision": getattr(CoolProp, "__gitrevision__", "UNKNOWN"),
                "backend": "HEOS",
                "fluid": "Helium",
                "coolpropHeliumAncillaryMinK": COOLPROP_HELIUM_ANCILLARY_MIN_K,
            },
            errors=errors,
        )


class HepakWorkbenchProvider:
    name = "HEPAK"

    def __init__(self, workbench_path: Path):
        self.path = workbench_path
        self.data = json.loads(workbench_path.read_text(encoding="utf-8"))

    def _candidate_points(self):
        for calc in self.data.get("calculations", []):
            for key in ("p1", "p2"):
                point = calc.get(key)
                if isinstance(point, dict):
                    yield point

    def evaluate(self, request: PropertyRequest, *, abs_T_tol_K: float = 1e-6, abs_P_tol_Pa: float = 1e-3) -> PropertyResult:
        match = None
        for point in self._candidate_points():
            T = point.get("temperature_K")
            P = point.get("pressure_Pa")
            if T is None or P is None:
                continue
            if abs(float(T) - request.temperature_K) <= abs_T_tol_K and abs(float(P) - request.pressure_Pa) <= abs_P_tol_Pa:
                match = point
                break

        if match is None:
            return _empty_result(request, "DEFER_HEPAK_POINT_MISSING", "No exact matching source-bound HEPAK point in workbench receipt")

        source = match.get("calculationSource") or {}
        if match.get("evidenceClass") != "HEPAK_SOURCE_BOUND" or source.get("authorityRole") != "GOVERNING":
            return _empty_result(request, "REJECT_HEPAK_EVIDENCE_CLASS", "Matching point is not source-bound governing HEPAK evidence")

        values = {
            "density_kg_m3": match.get("density_kg_m3"),
            "enthalpy_J_kg": match.get("enthalpy_J_kg"),
            "entropy_J_kgK": match.get("entropy_J_kgK"),
            "cp_J_kgK": match.get("cp_J_kgK"),
            "cv_J_kgK": match.get("cv_J_kgK"),
            "viscosity_Pa_s": match.get("viscosity_Pa_s"),
            "conductivity_W_mK": match.get("conductivity_W_mK"),
        }
        return PropertyResult(
            status="PASS",
            provider=self.name,
            authority_role="GOVERNING",
            request=asdict(request),
            values=values,
            phase=match.get("phase"),
            evidence={
                "workbench": str(self.path),
                "evidenceClass": match.get("evidenceClass"),
                "calculationSource": source,
                "contractRefs": match.get("contractRefs", []),
                "rtmRefs": match.get("rtmRefs", []),
            },
            errors=[],
        )


class HeliumPropertyRouter:
    def __init__(self, hepak_workbench: Path | None = None):
        self.coolprop = CoolPropProvider()
        self.hepak = HepakWorkbenchProvider(hepak_workbench) if hepak_workbench and hepak_workbench.exists() else None

    def evaluate(self, request: PropertyRequest) -> PropertyResult:
        authority = request.authority.upper()
        if authority not in {"GOVERNING", "INDEPENDENT_CHECK"}:
            return _empty_result(request, "REJECT_AUTHORITY", f"Unsupported authority role: {request.authority}")

        if authority == "GOVERNING" and is_lowt_governing_band(request.temperature_K):
            if self.hepak is None:
                return _empty_result(
                    request,
                    "DEFER_HEPAK_REQUIRED",
                    "QPS contract requires governing HEPAK in the 2.0-4.5 K band; silent CoolProp substitution is forbidden",
                )
            return self.hepak.evaluate(request)

        result = self.coolprop.evaluate(request)
        if authority == "GOVERNING":
            result.authority_role = "VALIDATION_REQUIRED_BEFORE_GOVERNING"
            if result.status == "PASS":
                result.status = "PASS_INDEPENDENT_BACKEND_REQUIRES_VALIDATION"
        return result
