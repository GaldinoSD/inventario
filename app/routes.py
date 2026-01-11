from decimal import Decimal, InvalidOperation

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from . import db
from .models import Location, Sector, Equipment

bp = Blueprint("main", __name__)


# ======================================================
#  AUTH GUARD (proteção de rota)
# ======================================================
def login_required(view):
    """Decorator simples: exige session['user_logged'] == True."""
    from functools import wraps

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_logged"):
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def login_optional(view):
    """Decorator que NÃO exige login (ex.: API do scanner)."""
    from functools import wraps

    @wraps(view)
    def wrapped(*args, **kwargs):
        return view(*args, **kwargs)

    return wrapped


# ---------------------------
# Home / Dashboard
# ---------------------------
@bp.get("/")
@login_required
def index():
    counts = {
        "locations": Location.query.count(),
        "sectors": Sector.query.count(),
        "equipments": Equipment.query.count(),
    }

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

    return render_template("index.html", counts=counts, by_sector=by_sector, by_location=by_location)


# ======================================================
# ✅ TELA UNIFICADA (LOCALIZAÇÕES + SETORES POR LOCALIZAÇÃO)
# ======================================================
@bp.get("/cadastro-localizacao", endpoint="locations_sectors")
@login_required
def locations_sectors():
    q_loc = (request.args.get("q_loc") or "").strip()
    location_id = (request.args.get("location_id") or "").strip()

    selected_location_id = int(location_id) if location_id.isdigit() else None

    # locais para o select
    locations_all = Location.query.order_by(Location.name.asc()).all()

    # locais para a tabela (filtrável)
    loc_query = Location.query
    if q_loc:
        loc_query = loc_query.filter(Location.name.ilike(f"%{q_loc}%"))
    if selected_location_id:
        loc_query = loc_query.filter(Location.id == selected_location_id)

    locations_filtered = loc_query.order_by(Location.name.asc()).all()

    selected_location = Location.query.get(selected_location_id) if selected_location_id else None

    return render_template(
        "locations_sectors.html",
        locations=locations_all,
        locations_filtered=locations_filtered,
        selected_location_id=selected_location_id,
        selected_location=selected_location,
        q_loc=q_loc,
    )


# ======================================================
# ✅ SETORES VINCULADOS: CREATE / UPDATE / DELETE
# (usados pela tela unificada)
# ======================================================
@bp.post("/cadastro-localizacao/sector", endpoint="unified_sector_create")
@login_required
def unified_sector_create():
    name = (request.form.get("name") or "").strip()
    location_id = (request.form.get("location_id") or "").strip()

    if not location_id.isdigit():
        flash("Selecione uma localização válida para cadastrar o setor.", "error")
        return redirect(url_for("main.locations_sectors"))

    if not name:
        flash("Nome do setor é obrigatório.", "error")
        return redirect(url_for("main.locations_sectors", location_id=location_id))

    # ✅ IMPORTANTE: seu model Sector precisa ter location_id
    sector = Sector(name=name, location_id=int(location_id))
    db.session.add(sector)

    try:
        db.session.commit()
        flash("Setor cadastrado com sucesso.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Já existe um setor com esse nome nessa localização.", "error")

    return redirect(url_for("main.locations_sectors", location_id=location_id))


@bp.post("/cadastro-localizacao/sector/<int:sector_id>", endpoint="unified_sector_update")
@login_required
def unified_sector_update(sector_id):
    sector = Sector.query.get_or_404(sector_id)

    name = (request.form.get("name") or "").strip()
    location_id = (request.form.get("location_id") or "").strip()

    if not location_id.isdigit():
        flash("Selecione uma localização válida.", "error")
        return redirect(url_for("main.locations_sectors"))

    if not name:
        flash("Nome do setor é obrigatório.", "error")
        return redirect(url_for("main.locations_sectors", location_id=location_id))

    sector.name = name
    sector.location_id = int(location_id)

    try:
        db.session.commit()
        flash("Setor atualizado.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Não foi possível atualizar: setor duplicado nessa localização.", "error")

    return redirect(url_for("main.locations_sectors", location_id=location_id))


@bp.post("/cadastro-localizacao/sector/<int:sector_id>/delete", endpoint="unified_sector_delete")
@login_required
def unified_sector_delete(sector_id):
    sector = Sector.query.get_or_404(sector_id)

    # Protege se existir equipamentos vinculados
    if getattr(sector, "equipments", None) and sector.equipments:
        flash("Não é possível excluir: existem equipamentos vinculados a este setor.", "error")
        return redirect(url_for("main.locations_sectors", location_id=sector.location_id))

    loc_id = sector.location_id
    db.session.delete(sector)
    db.session.commit()
    flash("Setor excluído.", "success")
    return redirect(url_for("main.locations_sectors", location_id=loc_id))


# ---------------------------
# API — Buscar equipamento por PAT/Código (scanner)
# ---------------------------
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
                "created_at": eq.created_at.isoformat() if getattr(eq, "created_at", None) else None,
            },
        }
    )


# ---------------------------
# Locations (mantidas) — mas redirecionando para tela unificada
# ---------------------------
@bp.get("/locations")
@login_required
def locations_list():
    # ✅ se você quer tudo centralizado na nova tela, redireciona:
    return redirect(url_for("main.locations_sectors"))


@bp.get("/locations/new")
@login_required
def locations_new():
    return redirect(url_for("main.locations_sectors"))


@bp.post("/locations/new")
@login_required
def locations_create():
    name = (request.form.get("name") or "").strip()
    address = (request.form.get("address") or "").strip() or None
    notes = (request.form.get("notes") or "").strip() or None

    if not name:
        flash("Nome da localização/igreja é obrigatório.", "error")
        return redirect(url_for("main.locations_sectors"))

    loc = Location(name=name, address=address, notes=notes)
    db.session.add(loc)
    try:
        db.session.commit()
        flash("Localização cadastrada com sucesso.", "success")
        return redirect(url_for("main.locations_sectors", location_id=loc.id))
    except IntegrityError:
        db.session.rollback()
        flash("Já existe uma localização com esse nome.", "error")
        return redirect(url_for("main.locations_sectors"))


@bp.get("/locations/<int:location_id>/edit")
@login_required
def locations_edit(location_id):
    return redirect(url_for("main.locations_sectors", location_id=location_id))


@bp.post("/locations/<int:location_id>/edit")
@login_required
def locations_update(location_id):
    loc = Location.query.get_or_404(location_id)

    name = (request.form.get("name") or "").strip()
    address = (request.form.get("address") or "").strip() or None
    notes = (request.form.get("notes") or "").strip() or None

    if not name:
        flash("Nome da localização/igreja é obrigatório.", "error")
        return redirect(url_for("main.locations_sectors", location_id=loc.id))

    loc.name = name
    loc.address = address
    loc.notes = notes

    try:
        db.session.commit()
        flash("Localização atualizada.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Já existe uma localização com esse nome.", "error")

    return redirect(url_for("main.locations_sectors", location_id=loc.id))


@bp.post("/locations/<int:location_id>/delete")
@login_required
def locations_delete(location_id):
    loc = Location.query.get_or_404(location_id)

    # bloqueia se houver equipamentos
    if getattr(loc, "equipments", None) and loc.equipments:
        flash("Não é possível excluir: existem equipamentos vinculados a esta localização.", "error")
        return redirect(url_for("main.locations_sectors", location_id=loc.id))

    # bloqueia se houver setores vinculados
    if getattr(loc, "sectors", None) and loc.sectors:
        flash("Não é possível excluir: existem setores vinculados a esta localização.", "error")
        return redirect(url_for("main.locations_sectors", location_id=loc.id))

    db.session.delete(loc)
    db.session.commit()
    flash("Localização excluída.", "success")
    return redirect(url_for("main.locations_sectors"))


# ---------------------------
# Sectors (ROTAS ANTIGAS) — desativadas (evita erro sem location_id)
# ---------------------------
@bp.get("/sectors")
@login_required
def sectors_list():
    return redirect(url_for("main.locations_sectors"))


@bp.get("/sectors/new")
@login_required
def sectors_new():
    return redirect(url_for("main.locations_sectors"))


@bp.post("/sectors/new")
@login_required
def sectors_create():
    flash("Cadastro de setores agora é feito dentro de uma localização (tela unificada).", "error")
    return redirect(url_for("main.locations_sectors"))


@bp.get("/sectors/<int:sector_id>/edit")
@login_required
def sectors_edit(sector_id):
    return redirect(url_for("main.locations_sectors"))


@bp.post("/sectors/<int:sector_id>/edit")
@login_required
def sectors_update(sector_id):
    flash("Edição de setores agora é feita dentro da tela unificada.", "error")
    return redirect(url_for("main.locations_sectors"))


@bp.post("/sectors/<int:sector_id>/delete")
@login_required
def sectors_delete(sector_id):
    flash("Exclusão de setores agora é feita dentro da tela unificada.", "error")
    return redirect(url_for("main.locations_sectors"))


# ---------------------------
# Equipments
# ---------------------------
@bp.get("/equipments")
@login_required
def equipments_list():
    q = (request.args.get("q") or "").strip()
    location_id = (request.args.get("location_id") or "").strip()
    sector_id = (request.args.get("sector_id") or "").strip()

    query = Equipment.query

    if q:
        query = query.filter(
            (Equipment.name.ilike(f"%{q}%"))
            | (Equipment.brand.ilike(f"%{q}%"))
            | (Equipment.barcode_pat.ilike(f"%{q}%"))
            | (Equipment.invoice_nf.ilike(f"%{q}%"))
        )

    if location_id.isdigit():
        query = query.filter(Equipment.location_id == int(location_id))

    if sector_id.isdigit():
        query = query.filter(Equipment.sector_id == int(sector_id))

    equipments = query.order_by(Equipment.created_at.desc()).all()
    locations = Location.query.order_by(Location.name.asc()).all()
    sectors = Sector.query.order_by(Sector.name.asc()).all()

    return render_template(
        "equipments/list.html",
        equipments=equipments,
        q=q,
        locations=locations,
        sectors=sectors,
        location_id=location_id,
        sector_id=sector_id,
    )


@bp.get("/equipments/new")
@login_required
def equipments_new():
    locations = Location.query.order_by(Location.name.asc()).all()
    sectors = Sector.query.order_by(Sector.name.asc()).all()

    if not locations:
        flash("Cadastre pelo menos 1 localização antes de cadastrar equipamentos.", "error")
        return redirect(url_for("main.locations_sectors"))
    if not sectors:
        flash("Cadastre pelo menos 1 setor antes de cadastrar equipamentos.", "error")
        return redirect(url_for("main.locations_sectors"))

    return render_template("equipments/form.html", equipment=None, locations=locations, sectors=sectors)


@bp.post("/equipments/new")
@login_required
def equipments_create():
    name = (request.form.get("name") or "").strip()
    brand = (request.form.get("brand") or "").strip() or None
    value_raw = (request.form.get("value") or "").strip()
    invoice_nf = (request.form.get("invoice_nf") or "").strip() or None
    barcode_pat = (request.form.get("barcode_pat") or "").strip()
    location_id = (request.form.get("location_id") or "").strip()
    sector_id = (request.form.get("sector_id") or "").strip()

    if not name or not barcode_pat or not location_id.isdigit() or not sector_id.isdigit():
        flash("Preencha: Nome, PAT/Código, Localização e Setor.", "error")
        return redirect(url_for("main.equipments_list"))

    value = None
    if value_raw:
        try:
            value = Decimal(value_raw.replace(".", "").replace(",", "."))
        except (InvalidOperation, ValueError):
            flash("Valor inválido. Ex.: 1500,00", "error")
            return redirect(url_for("main.equipments_list"))

    eq = Equipment(
        name=name,
        brand=brand,
        value=value,
        invoice_nf=invoice_nf,
        barcode_pat=barcode_pat,
        location_id=int(location_id),
        sector_id=int(sector_id),
    )

    db.session.add(eq)
    try:
        db.session.commit()
        flash("Equipamento cadastrado com sucesso.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Já existe equipamento com esse PAT/Código de barras.", "error")
        return redirect(url_for("main.equipments_list"))

    return redirect(url_for("main.equipments_list"))


@bp.get("/equipments/<int:equipment_id>/edit")
@login_required
def equipments_edit(equipment_id):
    eq = Equipment.query.get_or_404(equipment_id)
    locations = Location.query.order_by(Location.name.asc()).all()
    sectors = Sector.query.order_by(Sector.name.asc()).all()
    return render_template("equipments/form.html", equipment=eq, locations=locations, sectors=sectors)


@bp.post("/equipments/<int:equipment_id>/edit")
@login_required
def equipments_update(equipment_id):
    eq = Equipment.query.get_or_404(equipment_id)

    name = (request.form.get("name") or "").strip()
    brand = (request.form.get("brand") or "").strip() or None
    value_raw = (request.form.get("value") or "").strip()
    invoice_nf = (request.form.get("invoice_nf") or "").strip() or None
    barcode_pat = (request.form.get("barcode_pat") or "").strip()
    location_id = (request.form.get("location_id") or "").strip()
    sector_id = (request.form.get("sector_id") or "").strip()

    if not name or not barcode_pat or not location_id.isdigit() or not sector_id.isdigit():
        flash("Preencha: Nome, PAT/Código, Localização e Setor.", "error")
        return redirect(url_for("main.equipments_list"))

    value = None
    if value_raw:
        try:
            value = Decimal(value_raw.replace(".", "").replace(",", "."))
        except (InvalidOperation, ValueError):
            flash("Valor inválido. Ex.: 1500,00", "error")
            return redirect(url_for("main.equipments_list"))

    eq.name = name
    eq.brand = brand
    eq.value = value
    eq.invoice_nf = invoice_nf
    eq.barcode_pat = barcode_pat
    eq.location_id = int(location_id)
    eq.sector_id = int(sector_id)

    try:
        db.session.commit()
        flash("Equipamento atualizado.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Já existe equipamento com esse PAT/Código de barras.", "error")
        return redirect(url_for("main.equipments_list"))

    return redirect(url_for("main.equipments_list"))


@bp.post("/equipments/<int:equipment_id>/delete")
@login_required
def equipments_delete(equipment_id):
    eq = Equipment.query.get_or_404(equipment_id)
    db.session.delete(eq)
    db.session.commit()
    flash("Equipamento excluído.", "success")
    return redirect(url_for("main.equipments_list"))


# ---------------------------
# Scan page
# ---------------------------
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
