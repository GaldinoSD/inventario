from decimal import Decimal, InvalidOperation
from functools import wraps
import os
import mimetypes

from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, jsonify, session, current_app
)
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename

from . import db
from .models import Location, Sector, Equipment, AlmoxItem, AlmoxMovement

bp = Blueprint("main", __name__)


# ======================================================
#  AUTH GUARD (proteção de rota)
# ======================================================
def login_required(view):
    """Decorator simples: exige session['user_logged'] == True."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_logged"):
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def login_optional(view):
    """Decorator que NÃO exige login (ex.: API do scanner)."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        return view(*args, **kwargs)
    return wrapped


# ======================================================
#  Upload NF helpers
# ======================================================
ALLOWED_NF_EXT = {"png", "jpg", "jpeg", "webp", "pdf"}


def _ensure_nf_upload_folder():
    folder = current_app.config.get("NF_UPLOAD_FOLDER")
    if not folder:
        folder = os.path.join(current_app.root_path, "static", "uploads", "nf")
        current_app.config["NF_UPLOAD_FOLDER"] = folder
    os.makedirs(folder, exist_ok=True)
    return folder


def _allowed_nf_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_NF_EXT


def _save_nf_file(file_storage, equipment_id: int) -> tuple[str, str]:
    """
    Salva arquivo da NF e retorna (filename, mime).
    Nome final: nf_<equipment_id>.<ext>
    """
    _ensure_nf_upload_folder()

    original = file_storage.filename or ""
    if not original:
        raise ValueError("missing_filename")

    if not _allowed_nf_file(original):
        raise ValueError("invalid_ext")

    safe = secure_filename(original)
    ext = safe.rsplit(".", 1)[1].lower()

    final_name = f"nf_{equipment_id}.{ext}"
    folder = current_app.config["NF_UPLOAD_FOLDER"]
    save_path = os.path.join(folder, final_name)

    file_storage.save(save_path)

    # mime: tenta pelo content_type, senão deduz pela extensão
    mime = (file_storage.mimetype or "").strip()
    if not mime:
        mime = mimetypes.guess_type(final_name)[0] or None

    return final_name, mime


def _delete_nf_file(filename: str | None):
    if not filename:
        return
    folder = current_app.config.get("NF_UPLOAD_FOLDER") or os.path.join(
        current_app.root_path, "static", "uploads", "nf"
    )
    path = os.path.join(folder, filename)
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        # não derruba o fluxo por falha de delete
        pass


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

    locations_all = Location.query.order_by(Location.name.asc()).all()

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

    if getattr(sector, "equipments", None) and sector.equipments:
        flash("Não é possível excluir: existem equipamentos vinculados a este setor.", "error")
        return redirect(url_for("main.locations_sectors", location_id=sector.location_id))

    loc_id = sector.location_id
    db.session.delete(sector)
    db.session.commit()
    flash("Setor excluído.", "success")
    return redirect(url_for("main.locations_sectors", location_id=loc_id))


# ======================================================
# ✅ ALMOXARIFADO
# ======================================================
VALID_ALMOX_TYPES = {"ENTRADA", "SAIDA", "PERDA", "DANIFICADO"}


@bp.get("/almoxarifado", endpoint="almoxarifado")
@login_required
def almoxarifado():
    items = AlmoxItem.query.order_by(func.lower(AlmoxItem.name).asc()).all()

    movements = (
        db.session.query(
            AlmoxMovement.id.label("id"),
            AlmoxMovement.created_at.label("created_at"),
            AlmoxMovement.type.label("type"),
            AlmoxMovement.qty.label("qty"),
            AlmoxMovement.local.label("local"),
            AlmoxMovement.motivo.label("motivo"),
            AlmoxMovement.item_id.label("item_id"),
            AlmoxItem.name.label("item_name"),
        )
        .join(AlmoxItem, AlmoxItem.id == AlmoxMovement.item_id)
        .order_by(AlmoxMovement.created_at.desc(), AlmoxMovement.id.desc())
        .limit(200)
        .all()
    )

    return render_template("almoxarifado.html", items=items, movements=movements)


@bp.post("/almoxarifado/add", endpoint="almoxarifado_add_item")
@login_required
def almoxarifado_add_item():
    name = (request.form.get("name") or "").strip()
    qty_raw = (request.form.get("qty") or "").strip()

    if not name:
        flash("Informe o nome do item.", "error")
        return redirect(url_for("main.almoxarifado"))

    try:
        qty = int(qty_raw)
    except ValueError:
        flash("Quantidade inválida.", "error")
        return redirect(url_for("main.almoxarifado"))

    if qty <= 0:
        flash("Quantidade deve ser maior que zero.", "error")
        return redirect(url_for("main.almoxarifado"))

    existing = AlmoxItem.query.filter(func.lower(AlmoxItem.name) == name.lower()).first()

    try:
        if existing:
            existing.qty = int(existing.qty or 0) + qty
            db.session.add(existing)

            db.session.add(
                AlmoxMovement(
                    type="ENTRADA",
                    qty=qty,
                    local=None,
                    motivo="Entrada de estoque",
                    item_id=existing.id,
                )
            )

            db.session.commit()
            flash(f"Entrada registrada: +{qty} em '{existing.name}'.", "success")
            return redirect(url_for("main.almoxarifado"))

        item = AlmoxItem(name=name, qty=qty)
        db.session.add(item)
        db.session.flush()

        db.session.add(
            AlmoxMovement(
                type="ENTRADA",
                qty=qty,
                local=None,
                motivo="Cadastro inicial",
                item_id=item.id,
            )
        )

        db.session.commit()
        flash(f"Item cadastrado: '{item.name}' com {qty} em estoque.", "success")
        return redirect(url_for("main.almoxarifado"))

    except IntegrityError:
        db.session.rollback()
        flash("Já existe um item com esse nome.", "error")
        return redirect(url_for("main.almoxarifado"))
    except Exception:
        db.session.rollback()
        flash("Erro ao cadastrar item/entrada. Tente novamente.", "error")
        return redirect(url_for("main.almoxarifado"))


@bp.post("/almoxarifado/movimento", endpoint="almoxarifado_movimento")
@login_required
def almoxarifado_movimento():
    item_id_raw = (request.form.get("item_id") or "").strip()
    type_ = (request.form.get("type") or "SAIDA").strip().upper()
    qty_raw = (request.form.get("qty") or "").strip()
    local = (request.form.get("local") or "").strip() or None
    motivo = (request.form.get("motivo") or "").strip()

    if type_ == "USO":
        type_ = "SAIDA"
    elif type_ == "DANO":
        type_ = "DANIFICADO"

    if type_ not in VALID_ALMOX_TYPES:
        flash("Tipo de movimentação inválido.", "error")
        return redirect(url_for("main.almoxarifado"))

    try:
        item_id = int(item_id_raw)
    except ValueError:
        flash("Item inválido.", "error")
        return redirect(url_for("main.almoxarifado"))

    try:
        qty = int(qty_raw)
    except ValueError:
        flash("Quantidade inválida.", "error")
        return redirect(url_for("main.almoxarifado"))

    if qty <= 0:
        flash("Quantidade deve ser maior que zero.", "error")
        return redirect(url_for("main.almoxarifado"))

    if type_ in {"SAIDA", "PERDA", "DANIFICADO"} and not motivo:
        flash("Informe o motivo (obrigatório para saída/perda/danificado).", "error")
        return redirect(url_for("main.almoxarifado"))

    item = AlmoxItem.query.get(item_id)
    if not item:
        flash("Item não encontrado.", "error")
        return redirect(url_for("main.almoxarifado"))

    try:
        current = int(item.qty or 0)

        if type_ == "ENTRADA":
            item.qty = current + qty
        else:
            if qty > current:
                flash(f"Estoque insuficiente. Disponível: {current}.", "error")
                return redirect(url_for("main.almoxarifado"))
            item.qty = current - qty

        db.session.add(item)

        db.session.add(
            AlmoxMovement(
                type=type_,
                qty=qty,
                local=local,
                motivo=motivo or ("Entrada de estoque" if type_ == "ENTRADA" else None),
                item_id=item.id,
            )
        )

        db.session.commit()
        flash("Movimentação registrada com sucesso.", "success")
        return redirect(url_for("main.almoxarifado"))

    except Exception:
        db.session.rollback()
        flash("Erro ao registrar movimentação. Tente novamente.", "error")
        return redirect(url_for("main.almoxarifado"))


@bp.post("/almoxarifado/item/update", endpoint="almoxarifado_item_update")
@login_required
def almoxarifado_item_update():
    item_id_raw = (request.form.get("item_id") or "").strip()
    name = (request.form.get("name") or "").strip()
    add_qty_raw = (request.form.get("add_qty") or "0").strip()
    sub_qty_raw = (request.form.get("sub_qty") or "0").strip()
    motivo = (request.form.get("motivo") or "").strip() or None

    try:
        item_id = int(item_id_raw)
    except ValueError:
        flash("Item inválido.", "error")
        return redirect(url_for("main.almoxarifado"))

    item = AlmoxItem.query.get(item_id)
    if not item:
        flash("Item não encontrado.", "error")
        return redirect(url_for("main.almoxarifado"))

    if not name:
        flash("Nome não pode ficar vazio.", "error")
        return redirect(url_for("main.almoxarifado"))

    try:
        add_qty = int(add_qty_raw)
        sub_qty = int(sub_qty_raw)
    except ValueError:
        flash("Quantidade inválida.", "error")
        return redirect(url_for("main.almoxarifado"))

    if add_qty < 0 or sub_qty < 0:
        flash("Quantidades devem ser 0 ou maiores.", "error")
        return redirect(url_for("main.almoxarifado"))

    try:
        item.name = name

        current = int(item.qty or 0)
        new_qty = current + add_qty - sub_qty
        if new_qty < 0:
            flash(f"Não é possível subtrair mais que o estoque atual ({current}).", "error")
            return redirect(url_for("main.almoxarifado"))

        item.qty = new_qty
        db.session.add(item)

        if add_qty > 0:
            db.session.add(
                AlmoxMovement(
                    type="ENTRADA",
                    qty=add_qty,
                    local=None,
                    motivo=motivo or "Ajuste (entrada)",
                    item_id=item.id,
                )
            )

        if sub_qty > 0:
            db.session.add(
                AlmoxMovement(
                    type="PERDA",
                    qty=sub_qty,
                    local=None,
                    motivo=motivo or "Ajuste (baixa)",
                    item_id=item.id,
                )
            )

        db.session.commit()
        flash("Item atualizado.", "success")
        return redirect(url_for("main.almoxarifado"))

    except IntegrityError:
        db.session.rollback()
        flash("Já existe um item com esse nome.", "error")
        return redirect(url_for("main.almoxarifado"))
    except Exception:
        db.session.rollback()
        flash("Erro ao atualizar item.", "error")
        return redirect(url_for("main.almoxarifado"))


@bp.post("/almoxarifado/item/delete", endpoint="almoxarifado_item_delete")
@login_required
def almoxarifado_item_delete():
    item_id_raw = (request.form.get("item_id") or "").strip()

    try:
        item_id = int(item_id_raw)
    except ValueError:
        flash("Item inválido.", "error")
        return redirect(url_for("main.almoxarifado"))

    item = AlmoxItem.query.get(item_id)
    if not item:
        flash("Item não encontrado.", "error")
        return redirect(url_for("main.almoxarifado"))

    try:
        db.session.delete(item)
        db.session.commit()
        flash("Item excluído com sucesso.", "success")
        return redirect(url_for("main.almoxarifado"))
    except Exception:
        db.session.rollback()
        flash("Erro ao excluir item.", "error")
        return redirect(url_for("main.almoxarifado"))


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
                "created_at": eq.created_at.isoformat() if getattr(eq, "created_at", None) else None,
                "invoice_file": getattr(eq, "invoice_file", None),
                "invoice_mime": getattr(eq, "invoice_mime", None),
                "invoice_url": invoice_url,
            },
        }
    )


# ---------------------------
# Locations (mantidas) — redirecionando para tela unificada
# ---------------------------
@bp.get("/locations")
@login_required
def locations_list():
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

    if getattr(loc, "equipments", None) and loc.equipments:
        flash("Não é possível excluir: existem equipamentos vinculados a esta localização.", "error")
        return redirect(url_for("main.locations_sectors", location_id=loc.id))

    if getattr(loc, "sectors", None) and loc.sectors:
        flash("Não é possível excluir: existem setores vinculados a esta localização.", "error")
        return redirect(url_for("main.locations_sectors", location_id=loc.id))

    db.session.delete(loc)
    db.session.commit()
    flash("Localização excluída.", "success")
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
        # primeiro commit pra garantir eq.id
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("Já existe equipamento com esse PAT/Código de barras.", "error")
        return redirect(url_for("main.equipments_list"))

    # ✅ UPLOAD NF (opcional)
    f = request.files.get("invoice_image")
    if f and f.filename:
        try:
            filename, mime = _save_nf_file(f, eq.id)
            eq.invoice_file = filename
            eq.invoice_mime = mime
            db.session.commit()
        except ValueError as ve:
            # apaga o equipamento se quiser bloquear cadastro sem NF válida (aqui NÃO apaga, só avisa)
            flash("Arquivo de NF inválido (use JPG/PNG/WebP/PDF).", "error")
        except Exception:
            db.session.rollback()
            flash("Falha ao salvar a imagem/PDF da NF.", "error")

    flash("Equipamento cadastrado com sucesso.", "success")
    return redirect(url_for("main.equipments_list"))


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

    # ✅ UPLOAD NF (se enviar, substitui a antiga)
    f = request.files.get("invoice_image")
    if f and f.filename:
        try:
            # apaga arquivo anterior
            _delete_nf_file(getattr(eq, "invoice_file", None))

            filename, mime = _save_nf_file(f, eq.id)
            eq.invoice_file = filename
            eq.invoice_mime = mime
        except ValueError:
            flash("Arquivo de NF inválido (use JPG/PNG/WebP/PDF).", "error")
            return redirect(url_for("main.equipments_list"))
        except Exception:
            db.session.rollback()
            flash("Falha ao salvar a imagem/PDF da NF.", "error")
            return redirect(url_for("main.equipments_list"))

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

    # apaga NF vinculada
    _delete_nf_file(getattr(eq, "invoice_file", None))

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
