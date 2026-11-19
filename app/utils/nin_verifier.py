"""
NIN Verification Utility.

Verification priority (checked in order):
  1. Local NIN Registry (nin_records table)  — always used when a record exists
  2. VerifyMe API                            — used when VERIFYME_API_KEY is set
                                               and no local record was found
  3. Simulation fallback                     — used when neither 1 nor 2 is available

This means:
  • A local record always wins over external APIs.
  • If a NIN is not in the local registry the system falls through to VerifyMe
    (or simulation in development).
  • Admins populate the local registry via /admin/nin-registry.

VerifyMe documentation: https://docs.verifyme.ng/identity-verifications/national-identification-number
Test persona (VerifyMe sandbox): NIN 10000000001 / John Doe / 04-04-1944
"""

import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Format validation (no DB, no network)
# ---------------------------------------------------------------------------

def validate_nin_format(nin: str) -> bool:
    """
    Return True if the string is a plausible NIN.

    Rules:
      1. Exactly 11 numeric digits.
      2. Not all the same digit (e.g. 00000000000, 11111111111 …).
      3. Not a simple ascending or descending sequence (12345678901,
         98765432109, etc.) — these are common test-entry mistakes.
    """
    if not (nin and re.fullmatch(r"\d{11}", nin.strip())):
        return False

    nin = nin.strip()

    # Rule 2 — all identical digits
    if len(set(nin)) == 1:
        return False

    # Rule 3 — ascending or descending run of 8+ consecutive digits
    # e.g. 12345678901 → "12345678" is 8 consecutive ascending chars
    for i in range(len(nin) - 7):
        window = nin[i:i + 8]
        diffs = [ord(window[j + 1]) - ord(window[j]) for j in range(7)]
        if all(d == 1 for d in diffs) or all(d == -1 for d in diffs):
            return False

    return True


# ---------------------------------------------------------------------------
# Local registry lookup
# ---------------------------------------------------------------------------

def _verify_local(nin: str, firstname: str = "", lastname: str = "",
                  dob: str = "") -> dict | None:
    """
    Look up the NIN in the local nin_records table.

    Returns a result dict if the NIN is found (active), None if absent.
    When name/dob are supplied the response includes per-field match flags.
    """
    try:
        from app.models.nin_record import NinRecord
        record = NinRecord.find_by_nin(nin)
    except Exception as exc:
        logger.warning("Local NIN registry lookup failed: %s", exc)
        return None

    if not record:
        return None

    # Field matching
    field_matches = {}
    if firstname:
        field_matches["firstname"] = record.firstname.lower() == firstname.lower()
    if lastname:
        field_matches["lastname"]  = record.lastname.lower()  == lastname.lower()
    if dob:
        # Normalise both to DD-MM-YYYY before comparing
        field_matches["dob"] = _normalise_dob(record.birthdate) == _normalise_dob(dob)

    return {
        "verified":      True,
        "message":       "NIN verified successfully (local registry).",
        "source":        "local",
        "data":          record.to_verification_dict(),
        "field_matches": field_matches if field_matches else None,
    }


def _normalise_dob(dob: str) -> str:
    """Coerce common DOB formats to DD-MM-YYYY for comparison."""
    if not dob:
        return ""
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(dob.strip(), fmt).strftime("%d-%m-%Y")
        except ValueError:
            continue
    return dob.strip()


# ---------------------------------------------------------------------------
# VerifyMe API (live external call)
# ---------------------------------------------------------------------------

def _verify_verifyme(nin: str, firstname: str = "", lastname: str = "",
                     dob: str = "") -> dict:
    """POST to VerifyMe NIN endpoint."""
    import requests
    from flask import current_app

    api_key  = current_app.config.get("VERIFYME_API_KEY", "")
    base_url = current_app.config.get("VERIFYME_BASE_URL", "https://vapi.verifyme.ng/v1")
    url      = f"{base_url}/verifications/identities/nin/{nin.strip()}"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json",
    }
    payload = {}
    if firstname: payload["firstname"] = firstname
    if lastname:  payload["lastname"]  = lastname
    if dob:       payload["dob"]       = dob

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
    except requests.exceptions.Timeout:
        logger.warning("VerifyMe NIN check timed out for NIN %s***", nin[:3])
        return _api_error("Verification service timed out. Please try again later.")
    except requests.exceptions.RequestException as exc:
        logger.warning("VerifyMe NIN network error: %s", exc)
        return _api_error("Could not reach verification service. Please try again later.")

    if resp.status_code in (200, 201):
        try:
            body = resp.json()
        except ValueError:
            return _api_error("Unexpected response from verification service.")
        if body.get("status") == "success":
            d = body.get("data", {})
            return {
                "verified": True,
                "message":  "NIN verified successfully via NIMC.",
                "source":   "verifyme",
                "data": {
                    "nin":        str(d.get("nin", "")),
                    "firstname":  d.get("firstname", ""),
                    "lastname":   d.get("lastname", ""),
                    "middlename": d.get("middlename", ""),
                    "gender":     d.get("gender", ""),
                    "birthdate":  d.get("birthdate", ""),
                    "phone":      d.get("phone", ""),
                },
                "field_matches": d.get("fieldMatches"),
            }

    err_map = {
        401: "NIN verification authentication failed. Contact the administrator.",
        404: "NIN not found in NIMC database. Please check and re-enter.",
        400: "Invalid verification request. Ensure your details are correct.",
        422: "Verification service temporarily unavailable. Please try again.",
        503: "NIMC verification service is currently unavailable.",
    }
    try:
        api_msg = resp.json().get("message", "")
    except ValueError:
        api_msg = ""
    msg = err_map.get(resp.status_code, api_msg or "NIN could not be verified.")
    logger.info("VerifyMe check failed: HTTP %s — %s", resp.status_code, api_msg)
    return _api_error(msg, source="verifyme")


def _api_error(message: str, source: str = "verifyme") -> dict:
    return {"verified": False, "message": message, "source": source,
            "data": None, "field_matches": None}


# ---------------------------------------------------------------------------
# Simulation fallback (development / no API key)
# ---------------------------------------------------------------------------

def _simulate(nin: str) -> dict:
    """
    Deterministic simulation for development.
    NINs ending in 0 or 5 → not found.
    """
    if nin[-1] in ("0", "5"):
        return {"verified": False, "message": "NIN not found in NIMC database (simulated).",
                "source": "simulation", "data": None, "field_matches": None}
    return {"verified": True,  "message": "NIN verified successfully (simulated).",
            "source": "simulation",
            "data": {"nin": nin, "verification_source": "NIMC-SIM"},
            "field_matches": None}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def verify_nin(nin: str, firstname: str = "", lastname: str = "",
               dob: str = "") -> dict:
    """
    Verify a NIN using the first available source:
      1. Local registry  — instant, no network
      2. VerifyMe API    — if VERIFYME_API_KEY is configured
      3. Simulation      — development fallback

    Parameters
    ----------
    nin       : 11-digit NIN string.
    firstname : Optional first name for field-matching.
    lastname  : Optional last name for field-matching.
    dob       : Optional date of birth (any common format).

    Returns
    -------
    {
        "verified":      bool,
        "message":       str,
        "source":        "local" | "verifyme" | "simulation" | "validation",
        "data":          dict | None,
        "field_matches": dict | None,
    }
    """
    nin = nin.strip() if nin else ""

    if not validate_nin_format(nin):
        return {"verified": False,
                "message":  "Invalid NIN format. NIN must be exactly 11 numeric digits.",
                "source":   "validation", "data": None, "field_matches": None}

    # 1. Local registry
    local = _verify_local(nin, firstname=firstname, lastname=lastname, dob=dob)
    if local is not None:
        return local

    # 2. VerifyMe API (if key configured)
    try:
        from flask import current_app
        api_key = current_app.config.get("VERIFYME_API_KEY", "")
    except RuntimeError:
        api_key = ""

    if api_key:
        return _verify_verifyme(nin, firstname=firstname, lastname=lastname, dob=dob)

    # 3. Simulation fallback
    logger.debug("No local record and no API key — using simulation for NIN %s***", nin[:3])
    return _simulate(nin)
