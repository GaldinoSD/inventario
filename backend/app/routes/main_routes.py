from flask import Blueprint, render_template
from sqlalchemy import func, case, desc
from app import db
from app.models import Location, Sector, Equipment, AlmoxItem, AlmoxMovement
from app.auth import login_required

bp = Blueprint("main", __name__)

@bp.get("/")
@login_required
def index():
    # Core counts
    counts = {
        "locations": Location.query.count(),
        "sectors": Sector.query.count(),
        "equipments": Equipment.query.count(),
    }

    # Equipment status breakdown
    status_rows = (
        db.session.query(
            Equipment.status.label("status"),
            func.count(Equipment.id).label("count"),
        )
        .group_by(Equipment.status)
        .all()
    )
    status_map = {r.status: int(r.count) for r in status_rows}
    counts["ativos"] = status_map.get("Ativo", 0)
    counts["manutencao"] = status_map.get("Manutenção", 0)
    counts["baixados"] = status_map.get("Baixado", 0)

    # Total patrimony value
    total_value_row = db.session.query(func.sum(Equipment.value)).scalar()
    counts["total_value"] = float(total_value_row) if total_value_row else 0.0

    # Almoxarifado stats
    almox_items_count = AlmoxItem.query.count()
    almox_total_qty_row = db.session.query(func.sum(AlmoxItem.qty)).scalar()
    almox_total_qty = int(almox_total_qty_row) if almox_total_qty_row else 0

    # Low stock items (qty <= 5)
    almox_low_stock = AlmoxItem.query.filter(AlmoxItem.qty <= 5).order_by(AlmoxItem.qty.asc()).limit(5).all()

    counts["almox_items"] = almox_items_count
    counts["almox_total_qty"] = almox_total_qty

    # By sector
    by_sector_rows = (
        db.session.query(
            Sector.id.label("id"),
            Sector.name.label("name"),
            func.count(Equipment.id).label("count"),
        )
        .outerjoin(Equipment, Equipment.sector_id == Sector.id)
        .group_by(Sector.id, Sector.name)
        .order_by(func.count(Equipment.id).desc(), Sector.name.asc())
        .all()
    )

    # By location
    by_location_rows = (
        db.session.query(
            Location.id.label("id"),
            Location.name.label("name"),
            func.count(Equipment.id).label("count"),
        )
        .outerjoin(Equipment, Equipment.location_id == Location.id)
        .group_by(Location.id, Location.name)
        .order_by(func.count(Equipment.id).desc(), Location.name.asc())
        .all()
    )

    by_sector = [{"id": r.id, "name": r.name, "count": int(r.count)} for r in by_sector_rows]
    by_location = [{"id": r.id, "name": r.name, "count": int(r.count)} for r in by_location_rows]

    # Recent equipment (last 5)
    recent_equipment = (
        Equipment.query
        .order_by(Equipment.created_at.desc())
        .limit(5)
        .all()
    )

    # Recent almox movements (last 8)
    recent_movements = (
        db.session.query(
            AlmoxMovement.id.label("id"),
            AlmoxMovement.created_at.label("created_at"),
            AlmoxMovement.type.label("type"),
            AlmoxMovement.qty.label("qty"),
            AlmoxMovement.local.label("local"),
            AlmoxMovement.motivo.label("motivo"),
            AlmoxItem.name.label("item_name"),
        )
        .join(AlmoxItem, AlmoxItem.id == AlmoxMovement.item_id)
        .order_by(AlmoxMovement.created_at.desc(), AlmoxMovement.id.desc())
        .limit(8)
        .all()
    )

    return render_template(
        "index.html",
        counts=counts,
        by_sector=by_sector,
        by_location=by_location,
        recent_equipment=recent_equipment,
        recent_movements=recent_movements,
        almox_low_stock=almox_low_stock,
    )
