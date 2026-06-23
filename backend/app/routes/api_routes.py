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
