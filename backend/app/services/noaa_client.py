"""NOAA SWPC telemetry client.

Endpoints verified live on 2026-08-12 (all return current data):
  - planetary_k_index_1m.json          -> {time_tag, kp_index, estimated_kp, kp}
  - rtsw/rtsw_mag_1m.json              -> {time_tag, bt, bz_gsm, bx_gsm, ...}
  - rtsw/rtsw_wind_1m.json             -> plasma: speed, density, temperature
  - goes/primary/differential-protons-6-hour.json -> {time_tag, satellite, flux, energy, channel}
  - goes/primary/xray-flares-latest.json
  - ace/epam/ace_epam_5m.json          -> ACE proton channels
"""
import time
from typing import Any, Optional

import httpx

from app.config import get_settings
from app.models.schemas import TelemetrySnapshot


class NOAAClient:
    """Small cached HTTP client for NOAA SWPC JSON endpoints."""

    def __init__(self, base_url: Optional[str] = None, ttl: Optional[int] = None):
        s = get_settings()
        self.base_url = (base_url or s.noaa_base_url).rstrip("/")
        self.ttl = ttl or s.cache_ttl_seconds
        self._cache: dict[str, tuple[float, Any]] = {}

    async def _get_json(self, path: str, ttl: Optional[int] = None) -> Any:
        key = f"{path}#{ttl or self.ttl}"
        now = time.monotonic()
        if key in self._cache:
            ts, data = self._cache[key]
            if now - ts < (ttl or self.ttl):
                return data
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(f"{self.base_url}/{path}")
            resp.raise_for_status()
            data = resp.json()
        self._cache[key] = (now, data)
        return data

    async def get_planetary_kp(self) -> Optional[float]:
        """Latest planetary Kp index (0-9)."""
        try:
            rows = await self._get_json("planetary_k_index_1m.json")
            return float(rows[-1]["kp_index"]) if rows else None
        except Exception:
            return None

    async def get_solar_wind(self) -> dict:
        """Latest solar wind magnetic field + plasma."""
        out: dict = {}
        try:
            mag = await self._get_json("rtsw/rtsw_mag_1m.json")
            last = mag[-1]
            out["bt"] = last.get("bt")
            out["bz_gsm"] = last.get("bz_gsm")
        except Exception:
            pass
        try:
            wind = await self._get_json("rtsw/rtsw_wind_1m.json")
            last = wind[-1]
            out["speed_km_s"] = last.get("proton_speed") or last.get("speed") or last.get("velocity")
        except Exception:
            pass
        return out

    async def get_spe_proton_flux(self) -> Optional[float]:
        """SPE proxy flux (pfu): max flux across channels with energy >= 10 MeV.

        Channel energies look like '1020-1860 keV', '10000-30000 keV', '30000-60000 keV',
        '60000-100000 keV', '100000-115000 keV', '115000-143000 keV'.
        Returns max flux in pfu (1 pfu = 1 proton/cm2/sr/s) across high-energy channels.
        """
        try:
            rows = await self._get_json("goes/primary/differential-protons-6-hour.json")
            peak = 0.0
            for row in rows:
                energy: str = row.get("energy") or ""
                try:
                    lower_kev = float(energy.split("-")[0].strip())
                except (ValueError, IndexError):
                    continue
                if lower_kev >= 10_000:  # >= 10 MeV
                    peak = max(peak, float(row.get("flux") or 0.0))
            return peak if peak > 0 else None
        except Exception:
            return None

    async def get_xray_flare_class(self) -> Optional[str]:
        """Most recent flare class (e.g. 'M1.2')."""
        try:
            rows = await self._get_json("goes/primary/xray-flares-latest.json")
            if not rows:
                return None
            last = rows[-1]
            cls = last.get("flare_class") or last.get("class")
            return str(cls) if cls else None
        except Exception:
            return None

    async def get_proton_flux_series(self, hours: int = 6) -> list[dict]:
        """Time series of SPE-proxy flux (pfu, >= 10 MeV channels).

        Returns [{time_tag, flux_pfu}] at the source cadence (5 min) for the
        requested window, using the max flux across high-energy channels.
        """
        try:
            rows = await self._get_json("goes/primary/differential-protons-6-hour.json", ttl=180)
        except Exception:
            return []
        out: list[dict] = []
        by_time: dict[str, float] = {}
        for row in rows:
            energy: str = row.get("energy") or ""
            try:
                lower_kev = float(energy.split("-")[0].strip())
            except (ValueError, IndexError):
                continue
            if lower_kev < 10_000:
                continue
            tag = row.get("time_tag")
            if not tag:
                continue
            flux = float(row.get("flux") or 0.0)
            by_time[tag] = max(by_time.get(tag, 0.0), flux)
        for tag in sorted(by_time.keys()):
            out.append({"time_tag": tag, "flux_pfu": round(by_time[tag], 3)})
        if hours > 0:
            out = out[-int(hours * 12):]
        return out

    async def get_kp_series(self, points: int = 288) -> list[dict]:
        """Sampled planetary Kp history: [{time_tag, kp_index}] (max `points`)."""
        try:
            rows = await self._get_json("planetary_k_index_1m.json", ttl=300)
        except Exception:
            return []
        sampled = rows[-points:]
        out = []
        for row in sampled:
            kp = row.get("kp_index")
            if kp is None:
                continue
            out.append({"time_tag": row.get("time_tag"), "kp_index": float(kp)})
        return out

    async def latest_snapshot(self) -> TelemetrySnapshot:
        """Aggregate the latest telemetry into a snapshot."""
        kp = await self.get_planetary_kp()
        wind = await self.get_solar_wind()
        spe = await self.get_spe_proton_flux()
        flare = await self.get_xray_flare_class()
        ok = kp is not None or spe is not None or bool(wind)
        return TelemetrySnapshot(
            time_tag=None,
            kp_index=kp,
            estimated_kp=kp,
            solar_wind_bt=wind.get("bt"),
            solar_wind_bz_gsm=wind.get("bz_gsm"),
            solar_wind_speed_km_s=wind.get("speed_km_s"),
            spe_proton_flux=spe,
            xray_flare_class=flare,
            sources_ok=ok,
            degraded=not ok,
        )


