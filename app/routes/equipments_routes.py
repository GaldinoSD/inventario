from decimal import Decimal, InvalidOperation
from flask import Blueprint, render_template, request, redirect, url_for, flash
from sqlalchemy.exc import IntegrityError
from app import db
from app.models import Equipment, Location, Sector
from app.auth import login_required
from app.utils import _save_nf_file, _delete_nf_file

bp = Blueprint("equipments", __name__)

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
    status = (request.form.get("status") or "Ativo").strip()

    if not name or not barcode_pat or not location_id.isdigit() or not sector_id.isdigit():
        flash("Preencha: Nome, PAT/Código, Localização e Setor.", "error")
        return redirect(url_for("equipments.equipments_list"))

    value = None
    if value_raw:
        try:
            value = Decimal(value_raw.replace(".", "").replace(",", "."))
        except (InvalidOperation, ValueError):
            flash("Valor inválido. Ex.: 1500,00", "error")
            return redirect(url_for("equipments.equipments_list"))

    eq = Equipment(
        name=name,
        brand=brand,
        value=value,
        invoice_nf=invoice_nf,
        barcode_pat=barcode_pat,
        location_id=int(location_id),
        sector_id=int(sector_id),
        status=status,
    )

    db.session.add(eq)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("Já existe equipamento com esse PAT/Código de barras.", "error")
        return redirect(url_for("equipments.equipments_list"))

    f = request.files.get("invoice_image")
    if f and f.filename:
        try:
            filename, mime = _save_nf_file(f, eq.id)
            eq.invoice_file = filename
            eq.invoice_mime = mime
            db.session.commit()
        except ValueError:
            flash("Arquivo de NF inválido (use JPG/PNG/WebP/PDF).", "error")
        except Exception:
            db.session.rollback()
            flash("Falha ao salvar a imagem/PDF da NF.", "error")

    flash("Equipamento cadastrado com sucesso.", "success")
    return redirect(url_for("equipments.equipments_list"))

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
    status = (request.form.get("status") or "Ativo").strip()

    if not name or not barcode_pat or not location_id.isdigit() or not sector_id.isdigit():
        flash("Preencha: Nome, PAT/Código, Localização e Setor.", "error")
        return redirect(url_for("equipments.equipments_list"))

    value = None
    if value_raw:
        try:
            value = Decimal(value_raw.replace(".", "").replace(",", "."))
        except (InvalidOperation, ValueError):
            flash("Valor inválido. Ex.: 1500,00", "error")
            return redirect(url_for("equipments.equipments_list"))

    eq.name = name
    eq.brand = brand
    eq.value = value
    eq.invoice_nf = invoice_nf
    eq.barcode_pat = barcode_pat
    eq.location_id = int(location_id)
    eq.sector_id = int(sector_id)
    eq.status = status

    f = request.files.get("invoice_image")
    if f and f.filename:
        try:
            _delete_nf_file(getattr(eq, "invoice_file", None))
            filename, mime = _save_nf_file(f, eq.id)
            eq.invoice_file = filename
            eq.invoice_mime = mime
        except ValueError:
            flash("Arquivo de NF inválido (use JPG/PNG/WebP/PDF).", "error")
            return redirect(url_for("equipments.equipments_list"))
        except Exception:
            db.session.rollback()
            flash("Falha ao salvar a imagem/PDF da NF.", "error")
            return redirect(url_for("equipments.equipments_list"))

    try:
        db.session.commit()
        flash("Equipamento atualizado.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Já existe equipamento com esse PAT/Código de barras.", "error")

    return redirect(url_for("equipments.equipments_list"))

@bp.post("/equipments/<int:equipment_id>/delete")
@login_required
def equipments_delete(equipment_id):
    eq = Equipment.query.get_or_404(equipment_id)
    _delete_nf_file(getattr(eq, "invoice_file", None))
    db.session.delete(eq)
    db.session.commit()
    flash("Equipamento excluído.", "success")
    return redirect(url_for("equipments.equipments_list"))
