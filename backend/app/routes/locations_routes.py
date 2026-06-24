from flask import Blueprint, render_template, request, redirect, url_for, flash
from sqlalchemy.exc import IntegrityError
from app import db
from app.models import Location, Sector
from app.auth import login_required

bp = Blueprint("locations", __name__)

@bp.get("/cadastro-localizacao", endpoint="locations_sectors")
@login_required
def locations_sectors():
    location_id = (request.args.get("location_id") or "").strip()
    selected_location_id = int(location_id) if location_id.isdigit() else None

    locations_all = Location.query.order_by(Location.name.asc()).all()
    selected_location = Location.query.get(selected_location_id) if selected_location_id else None

    return render_template(
        "locations_sectors.html",
        locations=locations_all,
        selected_location_id=selected_location_id,
        selected_location=selected_location,
    )

@bp.post("/cadastro-localizacao/sector", endpoint="unified_sector_create")
@login_required
def unified_sector_create():
    name = (request.form.get("name") or "").strip()
    location_id = (request.form.get("location_id") or "").strip()

    if not location_id.isdigit():
        flash("Selecione uma localização válida para cadastrar o setor.", "error")
        return redirect(url_for("locations.locations_sectors"))

    if not name:
        flash("Nome do setor é obrigatório.", "error")
        return redirect(url_for("locations.locations_sectors"))

    sector = Sector(name=name, location_id=int(location_id))
    db.session.add(sector)

    try:
        db.session.commit()
        flash("Setor cadastrado com sucesso.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Já existe um setor com esse nome nessa localização.", "error")

    return redirect(url_for("locations.locations_sectors", location_id=location_id))

@bp.post("/cadastro-localizacao/sector/<int:sector_id>", endpoint="unified_sector_update")
@login_required
def unified_sector_update(sector_id):
    sector = Sector.query.get_or_404(sector_id)

    name = (request.form.get("name") or "").strip()
    location_id = (request.form.get("location_id") or "").strip()

    if not location_id.isdigit():
        flash("Selecione uma localização válida.", "error")
        return redirect(url_for("locations.locations_sectors"))

    if not name:
        flash("Nome do setor é obrigatório.", "error")
        return redirect(url_for("locations.locations_sectors"))

    sector.name = name
    sector.location_id = int(location_id)

    try:
        db.session.commit()
        flash("Setor atualizado.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Não foi possível atualizar: setor duplicado nessa localização.", "error")

    return redirect(url_for("locations.locations_sectors", location_id=location_id))

@bp.post("/cadastro-localizacao/sector/<int:sector_id>/delete", endpoint="unified_sector_delete")
@login_required
def unified_sector_delete(sector_id):
    sector = Sector.query.get_or_404(sector_id)

    if getattr(sector, "equipments", None) and sector.equipments:
        flash("Não é possível excluir: existem equipamentos vinculados a este setor.", "error")
        return redirect(url_for("locations.locations_sectors"))

    loc_id = sector.location_id
    db.session.delete(sector)
    db.session.commit()
    flash("Setor excluído.", "success")
    return redirect(url_for("locations.locations_sectors", location_id=loc_id))

@bp.get("/locations")
@login_required
def locations_list():
    return redirect(url_for("locations.locations_sectors"))

@bp.get("/locations/new")
@login_required
def locations_new():
    return redirect(url_for("locations.locations_sectors"))

@bp.post("/locations/new")
@login_required
def locations_create():
    name = (request.form.get("name") or "").strip()
    address = (request.form.get("address") or "").strip() or None
    notes = (request.form.get("notes") or "").strip() or None

    if not name:
        flash("Nome da localização/igreja é obrigatório.", "error")
        return redirect(url_for("locations.locations_sectors"))

    loc = Location(name=name, address=address, notes=notes)
    db.session.add(loc)
    try:
        db.session.commit()
        flash("Localização cadastrada com sucesso.", "success")
        return redirect(url_for("locations.locations_sectors", location_id=loc.id))
    except IntegrityError:
        db.session.rollback()
        flash("Já existe uma localização com esse nome.", "error")
        return redirect(url_for("locations.locations_sectors"))

@bp.get("/locations/<int:location_id>/edit")
@login_required
def locations_edit(location_id):
    return redirect(url_for("locations.locations_sectors", location_id=location_id))

@bp.post("/locations/<int:location_id>/edit")
@login_required
def locations_update(location_id):
    loc = Location.query.get_or_404(location_id)

    name = (request.form.get("name") or "").strip()
    address = (request.form.get("address") or "").strip() or None
    notes = (request.form.get("notes") or "").strip() or None

    if not name:
        flash("Nome da localização/igreja é obrigatório.", "error")
        return redirect(url_for("locations.locations_sectors"))

    loc.name = name
    loc.address = address
    loc.notes = notes

    try:
        db.session.commit()
        flash("Localização atualizada.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Já existe uma localização com esse nome.", "error")

    return redirect(url_for("locations.locations_sectors", location_id=location_id))

@bp.post("/locations/<int:location_id>/delete")
@login_required
def locations_delete(location_id):
    loc = Location.query.get_or_404(location_id)

    if getattr(loc, "equipments", None) and loc.equipments:
        flash("Não é possível excluir: existem equipamentos vinculados a esta localização.", "error")
        return redirect(url_for("locations.locations_sectors"))

    if getattr(loc, "sectors", None) and loc.sectors:
        flash("Não é possível excluir: existem setores vinculados a esta localização.", "error")
        return redirect(url_for("locations.locations_sectors"))

    db.session.delete(loc)
    db.session.commit()
    flash("Localização excluída.", "success")
    return redirect(url_for("locations.locations_sectors"))
