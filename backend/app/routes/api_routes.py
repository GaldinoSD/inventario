from flask import Blueprint, jsonify, request, url_for, render_template, flash
from app.models import Equipment
from app.auth import login_required
from functools import wraps

bp = Blueprint("api", __name__)

def login_optional(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        return view(*args, **kwargs)
    return wrapped

@bp.get("/api/equipment/by-barcode")
@login_optional
def api_equipment_by_barcode():
    code = (request.args.get("code") or "").strip()
    if not code:
        return jsonify({"ok": False, "error": "missing_code"}), 400

    eq = Equipment.query.filter(Equipment.barcode_pat == code).first()
    if not eq:
        return jsonify({"ok": True, "found": False, "code": code})

    location_name = eq.location.name if getattr(eq, "location", None) else None
    sector_name = eq.sector.name if getattr(eq, "sector", None) else None

    invoice_url = None
    if getattr(eq, "invoice_file", None):
        invoice_url = url_for("static", filename=f"uploads/nf/{eq.invoice_file}")

    return jsonify(
        {
            "ok": True,
            "found": True,
            "equipment": {
                "id": eq.id,
                "barcode_pat": eq.barcode_pat,
                "name": eq.name,
                "brand": eq.brand,
                "invoice_nf": eq.invoice_nf,
                "value": str(eq.value) if eq.value is not None else None,
                "location": location_name,
                "sector": sector_name,
                "status": getattr(eq, "status", "Ativo"),
                "created_at": eq.created_at.isoformat() if getattr(eq, "created_at", None) else None,
                "invoice_file": getattr(eq, "invoice_file", None),
                "invoice_mime": getattr(eq, "invoice_mime", None),
                "invoice_url": invoice_url,
            },
        }
    )

@bp.get("/scan")
@login_required
def scan_page():
    code = (request.args.get("code") or "").strip()
    result = None
    if code:
        result = Equipment.query.filter(Equipment.barcode_pat == code).first()
        if not result:
            flash("Nenhum equipamento encontrado com esse PAT/Código.", "error")
    return render_template("scan.html", code=code, result=result)

@bp.get("/api/dashboard/sector/<int:sector_id>")
@login_required
def api_dashboard_sector(sector_id):
    from app.models import Sector, Equipment
    from app import db
    from sqlalchemy import func

    sector = Sector.query.get(sector_id)
    if not sector:
        return jsonify({"ok": False, "error": "sector_not_found"}), 404

    # Equipment status breakdown for this sector
    status_rows = (
        db.session.query(
            Equipment.status.label("status"),
            func.count(Equipment.id).label("count"),
        )
        .filter(Equipment.sector_id == sector_id)
        .group_by(Equipment.status)
        .all()
    )
    status_map = {r.status: int(r.count) for r in status_rows}

    # Total equipments in sector
    total_equipments = sum(status_map.values())

    # Sector total value
    total_value_row = db.session.query(func.sum(Equipment.value)).filter(Equipment.sector_id == sector_id).scalar()
    total_value = float(total_value_row) if total_value_row else 0.0

    # Sector equipment list (last 10 recent)
    equipments_rows = (
        Equipment.query
        .filter(Equipment.sector_id == sector_id)
        .order_by(Equipment.created_at.desc())
        .limit(10)
        .all()
    )

    equipments = []
    for eq in equipments_rows:
        equipments.append({
            "id": eq.id,
            "name": eq.name,
            "brand": eq.brand or "-",
            "barcode_pat": eq.barcode_pat,
            "status": eq.status or "Ativo",
            "value": float(eq.value) if eq.value is not None else None,
            "location_name": eq.location.name if eq.location else "-"
        })

    return jsonify({
        "ok": True,
        "sector_name": sector.name,
        "counts": {
            "equipments": total_equipments,
            "total_value": total_value,
            "ativos": status_map.get("Ativo", 0),
            "manutencao": status_map.get("Manutenção", 0),
            "baixados": status_map.get("Baixado", 0)
        },
        "equipments": equipments
    })

@bp.post("/api/equipment/<int:equipment_id>/status")
@login_required
def api_update_equipment_status(equipment_id):
    from app import db
    eq = Equipment.query.get(equipment_id)
    if not eq:
        return jsonify({"ok": False, "error": "equipment_not_found"}), 404

    data = request.get_json(silent=True) or {}
    status = (data.get("status") or "").strip()
    
    if not status:
        return jsonify({"ok": False, "error": "missing_status"}), 400

    valid_statuses = ["Ativo", "Manutenção", "Baixado"]
    if status not in valid_statuses:
        return jsonify({"ok": False, "error": "invalid_status"}), 400

    eq.status = status
    try:
        db.session.commit()
        return jsonify({"ok": True, "status": eq.status})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": "db_error", "details": str(e)}), 500

