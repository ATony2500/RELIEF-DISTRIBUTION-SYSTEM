"""
NIN Verification Utility.

In production this would connect to the NIMC API.
In development / testing it uses a simulated lookup from a local seed table.

A valid NIN:
  - exactly 11 digits
  - all numeric characters
"""

import re
from typing import Optional


def validate_nin_format(nin: str) -> bool:
    """
    Return True if the string looks like a valid NIN (11 numeric digits).
    Does NOT contact NIMC; just format checks.
    """
    return bool(nin and re.fullmatch(r"\d{11}", nin.strip()))


def verify_nin(nin: str) -> dict:
    """
    Simulate NIN verification against NIMC.

    Returns a dict:
        {
            "verified": bool,
            "message":  str,
            "data":     dict | None   # partial demographic data on success
        }

    In production, replace the body with a real NIMC API call.
    """
    nin = nin.strip() if nin else ""

    if not validate_nin_format(nin):
        return {
            "verified": False,
            "message": "Invalid NIN format. NIN must be exactly 11 numeric digits.",
            "data": None,
        }

    # ---------------------------------------------------------------
    # Simulated verification:
    # NINs ending in 0 or 5 are treated as "not found" for demo purposes.
    # All other well-formed NINs pass.
    # ---------------------------------------------------------------
    if nin[-1] in ("0", "5"):
        return {
            "verified": False,
            "message": "NIN not found in NIMC database (simulated).",
            "data": None,
        }

    return {
        "verified": True,
        "message": "NIN verified successfully.",
        "data": {
            "nin": nin,
            "verification_source": "NIMC-SIM",
        },
    }
