"""
Internal JSON API routes — used by JavaScript front-end components.
Not a public REST API; all endpoints require authentication.
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required
from app import db
from app.models.zone import State, LocalGovernmentArea, DistributionPoint
from app.models.inventory import Warehouse, InventoryItem
from app.models.beneficiary import Beneficiary
from app.models.distribution import DistributionRecord
from app.utils.helpers import beneficiary_nin_lookup
from app.utils.nin_verifier import validate_nin_format, verify_nin

api_bp = Blueprint("api", __name__)


@api_bp.route("/nin/verify", methods=["POST"])
@login_required
def nin_verify():
    """
    Live NIN verification via VerifyMe API.
    Called client-side from beneficiary register and apply forms.

    POST JSON: { "nin": "12345678901", "firstname": "", "lastname": "", "dob": "" }
    Returns:   { "verified": bool, "message": str, "source": str }
    Note:      `data` and `field_matches` are omitted to avoid leaking PII.
    """
    body = request.get_json(silent=True) or {}
    nin       = str(body.get("nin",       "")).strip()
    firstname = str(body.get("firstname", "")).strip()
    lastname  = str(body.get("lastname",  "")).strip()
    dob       = str(body.get("dob",       "")).strip()

    if not validate_nin_format(nin):
        return jsonify({"verified": False, "message": "NIN must be exactly 11 numeric digits.", "source": "validation"}), 400

    result = verify_nin(nin, firstname=firstname, lastname=lastname, dob=dob)
    return jsonify({
        "verified": result["verified"],
        "message":  result["message"],
        "source":   result["source"],
    })


@api_bp.route("/states")
@login_required
def get_states():
    states = State.query.order_by(State.name).all()
    return jsonify([{"id": s.id, "name": s.name, "code": s.code} for s in states])


@api_bp.route("/states/<int:state_id>/lgas")
@login_required
def get_lgas(state_id):
    lgas = (
        LocalGovernmentArea.query
        .filter_by(state_id=state_id)
        .order_by(LocalGovernmentArea.name)
        .all()
    )
    return jsonify([{"id": l.id, "name": l.name} for l in lgas])


@api_bp.route("/lgas/<int:lga_id>/distribution-points")
@login_required
def get_distribution_points(lga_id):
    points = (
        DistributionPoint.query
        .filter_by(lga_id=lga_id, is_active=True)
        .order_by(DistributionPoint.name)
        .all()
    )
    return jsonify([
        {
            "id": p.id,
            "name": p.name,
            "latitude": p.latitude,
            "longitude": p.longitude,
        }
        for p in points
    ])


@api_bp.route("/warehouses/<int:wh_id>/items")
@login_required
def get_warehouse_items(wh_id):
    items = (
        InventoryItem.query
        .filter_by(warehouse_id=wh_id)
        .filter(InventoryItem.quantity_available > 0)
        .order_by(InventoryItem.item_name)
        .all()
    )
    return jsonify([
        {
            "id": i.id,
            "name": i.item_name,
            "category": i.category,
            "quantity": i.quantity_available,
            "unit": i.unit,
        }
        for i in items
    ])


@api_bp.route("/beneficiary/lookup")
@login_required
def beneficiary_lookup():
    nin = request.args.get("nin", "").strip()
    name = request.args.get("name", "").strip()

    if nin:
        return jsonify(beneficiary_nin_lookup(nin))

    if name:
        like = f"%{name}%"
        results = (
            Beneficiary.query
            .filter(
                db.or_(
                    Beneficiary.first_name.ilike(like),
                    Beneficiary.last_name.ilike(like),
                ),
                Beneficiary.status == "active",
            )
            .limit(10)
            .all()
        )
        return jsonify([
            {"id": b.id, "full_name": b.full_name, "masked_nin": b.masked_nin}
            for b in results
        ])

    return jsonify([])


@api_bp.route("/dashboard/stats")
@login_required
def dashboard_stats():
    total_b = Beneficiary.query.filter_by(status="active").count()
    completed_d = DistributionRecord.query.filter_by(status="completed").count()
    low_stock = (
        InventoryItem.query
        .filter(
            db.or_(
                InventoryItem.quantity_available <= 0,
                db.and_(
                    InventoryItem.minimum_threshold > 0,
                    InventoryItem.quantity_available <= InventoryItem.minimum_threshold,
                ),
            )
        ).count()
    )
    return jsonify({
        "total_beneficiaries": total_b,
        "completed_distributions": completed_d,
        "low_stock_items": low_stock,
    })
