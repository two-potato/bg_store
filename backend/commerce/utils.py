import os
from typing import Optional, Dict
import httpx
import logging
import time
from django.conf import settings


DADATA_TOKEN = getattr(settings, "DADATA_TOKEN", os.getenv("DADATA_TOKEN", ""))


log = logging.getLogger("commerce")


def reverse_geocode(lat: float, lon: float) -> Optional[Dict[str, str]]:
    """Use DaData geolocate API to get address by coordinates.

    Returns dict with keys: country, city, street, postcode.
    """
    if not DADATA_TOKEN:
        return None
    url = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/geolocate/address"
    headers = {"Authorization": f"Token {DADATA_TOKEN}", "Content-Type": "application/json"}
    payload = {"lat": float(lat), "lon": float(lon), "count": 1, "radius_meters": 50}
    start = time.perf_counter_ns()
    try:
        with httpx.Client(timeout=10) as c:
            r = c.post(url, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json() or {}
            sugs = data.get("suggestions") or []
            if not sugs:
                log.info("revgeo_empty", extra={"lat": lat, "lon": lon, "duration_ms": round((time.perf_counter_ns()-start)/1_000_000,2)})
                return None
            item = sugs[0].get("data") or {}
            addr = item.get("address") or {}
            data_part = addr.get("data") or {}
            data_out = {
                "country": (data_part.get("country") or "").strip(),
                "city": (data_part.get("city_with_type") or data_part.get("settlement_with_type") or "").strip(),
                "street": (data_part.get("street_with_type") or "").strip(),
                "postcode": (data_part.get("postal_code") or "").strip(),
            }
            log.info("revgeo_ok", extra={"lat": lat, "lon": lon, "duration_ms": round((time.perf_counter_ns()-start)/1_000_000,2)})
            return data_out
    except Exception:
        log.exception("revgeo_error", extra={"lat": lat, "lon": lon, "duration_ms": round((time.perf_counter_ns()-start)/1_000_000,2)})
        return None
