from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from app import db
from app.models import AlmoxItem, AlmoxMovement, Shelf, ShelfLevel
from app.auth import login_required

bp = Blueprint("almoxarifado", __name__)

VALID_ALMOX_TYPES = {"ENTRADA", "SAIDA", "PERDA", "DANIFICADO"}


# ===================== PAGE =====================

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

    shelves = Shelf.query.order_by(func.lower(Shelf.name).asc()).all()

    return render_template(
        "almoxarifado.html",
        items=items,
        movements=movements,
        shelves=shelves,
    )


# ===================== API: SHELF LEVELS =====================

@bp.get("/almoxarifado/api/shelf/<int:shelf_id>/levels", endpoint="almoxarifado_shelf_levels_api")
@login_required
def shelf_levels_api(shelf_id):
    """Return shelf levels as JSON for cascading selects."""
    shelf = Shelf.query.get(shelf_id)
    if not shelf:
        return jsonify([])
    levels = ShelfLevel.query.filter_by(shelf_id=shelf_id).order_by(ShelfLevel.label).all()
    return jsonify([{"id": lv.id, "label": lv.label} for lv in levels])


# ===================== ITEMS =====================

@bp.post("/almoxarifado/add", endpoint="almoxarifado_add_item")
@login_required
def almoxarifado_add_item():
    name = (request.form.get("name") or "").strip()
    qty_raw = (request.form.get("qty") or "").strip()
    location = (request.form.get("location") or "").strip() or None
    shelf_id_raw = (request.form.get("shelf_id") or "").strip()
    shelf_level_id_raw = (request.form.get("shelf_level_id") or "").strip()

    if not name:
        flash("Informe o nome do item.", "error")
        return redirect(url_for("almoxarifado.almoxarifado"))

    try:
        qty = int(qty_raw)
    except ValueError:
        flash("Quantidade inválida.", "error")
        return redirect(url_for("almoxarifado.almoxarifado"))

    if qty <= 0:
        flash("Quantidade deve ser maior que zero.", "error")
        return redirect(url_for("almoxarifado.almoxarifado"))

    shelf_id = int(shelf_id_raw) if shelf_id_raw else None
    shelf_level_id = int(shelf_level_id_raw) if shelf_level_id_raw else None

    existing = AlmoxItem.query.filter(func.lower(AlmoxItem.name) == name.lower()).first()

    try:
        if existing:
            existing.qty = int(existing.qty or 0) + qty
            if shelf_id:
                existing.shelf_id = shelf_id
                existing.shelf_level_id = shelf_level_id
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
            return redirect(url_for("almoxarifado.almoxarifado"))

        item = AlmoxItem(
            name=name,
            qty=qty,
            location=location,
            shelf_id=shelf_id,
            shelf_level_id=shelf_level_id,
        )
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
        return redirect(url_for("almoxarifado.almoxarifado"))

    except IntegrityError:
        db.session.rollback()
        flash("Já existe um item com esse nome.", "error")
        return redirect(url_for("almoxarifado.almoxarifado"))
    except Exception:
        db.session.rollback()
        flash("Erro ao cadastrar item/entrada. Tente novamente.", "error")
        return redirect(url_for("almoxarifado.almoxarifado"))

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
        return redirect(url_for("almoxarifado.almoxarifado"))

    try:
        item_id = int(item_id_raw)
        qty = int(qty_raw)
    except ValueError:
        flash("Item ou Quantidade inválida.", "error")
        return redirect(url_for("almoxarifado.almoxarifado"))

    if qty <= 0:
        flash("Quantidade deve ser maior que zero.", "error")
        return redirect(url_for("almoxarifado.almoxarifado"))

    if type_ in {"SAIDA", "PERDA", "DANIFICADO"} and not motivo:
        flash("Informe o motivo (obrigatório para saída/perda/danificado).", "error")
        return redirect(url_for("almoxarifado.almoxarifado"))

    item = AlmoxItem.query.get(item_id)
    if not item:
        flash("Item não encontrado.", "error")
        return redirect(url_for("almoxarifado.almoxarifado"))

    try:
        current = int(item.qty or 0)

        if type_ == "ENTRADA":
            item.qty = current + qty
        else:
            if qty > current:
                flash(f"Estoque insuficiente. Disponível: {current}.", "error")
                return redirect(url_for("almoxarifado.almoxarifado"))
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
        return redirect(url_for("almoxarifado.almoxarifado"))

    except Exception:
        db.session.rollback()
        flash("Erro ao registrar movimentação. Tente novamente.", "error")
        return redirect(url_for("almoxarifado.almoxarifado"))

@bp.post("/almoxarifado/item/update", endpoint="almoxarifado_item_update")
@login_required
def almoxarifado_item_update():
    item_id_raw = (request.form.get("item_id") or "").strip()
    name = (request.form.get("name") or "").strip()
    location = (request.form.get("location") or "").strip() or None
    shelf_id_raw = (request.form.get("shelf_id") or "").strip()
    shelf_level_id_raw = (request.form.get("shelf_level_id") or "").strip()
    add_qty_raw = (request.form.get("add_qty") or "0").strip()
    sub_qty_raw = (request.form.get("sub_qty") or "0").strip()
    motivo = (request.form.get("motivo") or "").strip() or None

    try:
        item_id = int(item_id_raw)
    except ValueError:
        flash("Item inválido.", "error")
        return redirect(url_for("almoxarifado.almoxarifado"))

    item = AlmoxItem.query.get(item_id)
    if not item:
        flash("Item não encontrado.", "error")
        return redirect(url_for("almoxarifado.almoxarifado"))

    if not name:
        flash("Nome não pode ficar vazio.", "error")
        return redirect(url_for("almoxarifado.almoxarifado"))

    try:
        add_qty = int(add_qty_raw)
        sub_qty = int(sub_qty_raw)
    except ValueError:
        flash("Quantidade inválida.", "error")
        return redirect(url_for("almoxarifado.almoxarifado"))

    if add_qty < 0 or sub_qty < 0:
        flash("Quantidades devem ser 0 ou maiores.", "error")
        return redirect(url_for("almoxarifado.almoxarifado"))

    try:
        item.name = name
        item.location = location
        item.shelf_id = int(shelf_id_raw) if shelf_id_raw else None
        item.shelf_level_id = int(shelf_level_id_raw) if shelf_level_id_raw else None

        current = int(item.qty or 0)
        new_qty = current + add_qty - sub_qty
        if new_qty < 0:
            flash(f"Não é possível subtrair mais que o estoque atual ({current}).", "error")
            return redirect(url_for("almoxarifado.almoxarifado"))

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
        return redirect(url_for("almoxarifado.almoxarifado"))

    except IntegrityError:
        db.session.rollback()
        flash("Já existe um item com esse nome.", "error")
        return redirect(url_for("almoxarifado.almoxarifado"))
    except Exception:
        db.session.rollback()
        flash("Erro ao atualizar item.", "error")
        return redirect(url_for("almoxarifado.almoxarifado"))

@bp.post("/almoxarifado/item/delete", endpoint="almoxarifado_item_delete")
@login_required
def almoxarifado_item_delete():
    item_id_raw = (request.form.get("item_id") or "").strip()

    try:
        item_id = int(item_id_raw)
    except ValueError:
        flash("Item inválido.", "error")
        return redirect(url_for("almoxarifado.almoxarifado"))

    item = AlmoxItem.query.get(item_id)
    if not item:
        flash("Item não encontrado.", "error")
        return redirect(url_for("almoxarifado.almoxarifado"))

    try:
        db.session.delete(item)
        db.session.commit()
        flash("Item excluído com sucesso.", "success")
        return redirect(url_for("almoxarifado.almoxarifado"))
    except Exception:
        db.session.rollback()
        flash("Erro ao excluir item.", "error")
        return redirect(url_for("almoxarifado.almoxarifado"))


# ===================== SHELVES =====================

@bp.post("/almoxarifado/shelf/add", endpoint="almoxarifado_shelf_add")
@login_required
def almoxarifado_shelf_add():
    name = (request.form.get("name") or "").strip()
    level_count_raw = (request.form.get("level_count") or "1").strip()

    if not name:
        flash("Informe o nome da estante.", "error")
        return redirect(url_for("almoxarifado.almoxarifado"))

    try:
        level_count = int(level_count_raw)
    except ValueError:
        level_count = 1

    if level_count < 1:
        level_count = 1
    if level_count > 26:
        level_count = 26

    try:
        shelf = Shelf(name=name)
        db.session.add(shelf)
        db.session.flush()

        for i in range(level_count):
            label = chr(65 + i)  # A, B, C, ...
            db.session.add(ShelfLevel(label=label, shelf_id=shelf.id))

        db.session.commit()
        flash(f"Estante '{name}' criada com {level_count} prateleira(s).", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Já existe uma estante com esse nome.", "error")
    except Exception:
        db.session.rollback()
        flash("Erro ao criar estante.", "error")

    return redirect(url_for("almoxarifado.almoxarifado"))


@bp.post("/almoxarifado/shelf/delete", endpoint="almoxarifado_shelf_delete")
@login_required
def almoxarifado_shelf_delete():
    shelf_id_raw = (request.form.get("shelf_id") or "").strip()

    try:
        shelf_id = int(shelf_id_raw)
    except ValueError:
        flash("Estante inválida.", "error")
        return redirect(url_for("almoxarifado.almoxarifado"))

    shelf = Shelf.query.get(shelf_id)
    if not shelf:
        flash("Estante não encontrada.", "error")
        return redirect(url_for("almoxarifado.almoxarifado"))

    try:
        # Unlink items before deleting
        AlmoxItem.query.filter_by(shelf_id=shelf_id).update(
            {"shelf_id": None, "shelf_level_id": None}
        )
        db.session.delete(shelf)
        db.session.commit()
        flash(f"Estante '{shelf.name}' excluída. Itens desvinculados.", "success")
    except Exception:
        db.session.rollback()
        flash("Erro ao excluir estante.", "error")

    return redirect(url_for("almoxarifado.almoxarifado"))


@bp.post("/almoxarifado/shelf/rename", endpoint="almoxarifado_shelf_rename")
@login_required
def almoxarifado_shelf_rename():
    shelf_id_raw = (request.form.get("shelf_id") or "").strip()
    new_name = (request.form.get("name") or "").strip()

    if not new_name:
        flash("Nome não pode ficar vazio.", "error")
        return redirect(url_for("almoxarifado.almoxarifado"))

    try:
        shelf_id = int(shelf_id_raw)
    except ValueError:
        flash("Estante inválida.", "error")
        return redirect(url_for("almoxarifado.almoxarifado"))

    shelf = Shelf.query.get(shelf_id)
    if not shelf:
        flash("Estante não encontrada.", "error")
        return redirect(url_for("almoxarifado.almoxarifado"))

    try:
        shelf.name = new_name
        db.session.commit()
        flash(f"Estante renomeada para '{new_name}'.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Já existe uma estante com esse nome.", "error")
    except Exception:
        db.session.rollback()
        flash("Erro ao renomear estante.", "error")

    return redirect(url_for("almoxarifado.almoxarifado"))


@bp.post("/almoxarifado/shelf/add-level", endpoint="almoxarifado_shelf_add_level")
@login_required
def almoxarifado_shelf_add_level():
    shelf_id_raw = (request.form.get("shelf_id") or "").strip()

    try:
        shelf_id = int(shelf_id_raw)
    except ValueError:
        flash("Estante inválida.", "error")
        return redirect(url_for("almoxarifado.almoxarifado"))

    shelf = Shelf.query.get(shelf_id)
    if not shelf:
        flash("Estante não encontrada.", "error")
        return redirect(url_for("almoxarifado.almoxarifado"))

    existing_labels = {lv.label for lv in shelf.levels}
    next_label = None
    for i in range(26):
        candidate = chr(65 + i)
        if candidate not in existing_labels:
            next_label = candidate
            break

    if not next_label:
        flash("Limite de 26 prateleiras (A-Z) atingido.", "error")
        return redirect(url_for("almoxarifado.almoxarifado"))

    try:
        db.session.add(ShelfLevel(label=next_label, shelf_id=shelf.id))
        db.session.commit()
        flash(f"Prateleira '{next_label}' adicionada à estante '{shelf.name}'.", "success")
    except Exception:
        db.session.rollback()
        flash("Erro ao adicionar prateleira.", "error")

    return redirect(url_for("almoxarifado.almoxarifado"))


@bp.post("/almoxarifado/shelf/remove-level", endpoint="almoxarifado_shelf_remove_level")
@login_required
def almoxarifado_shelf_remove_level():
    level_id_raw = (request.form.get("level_id") or "").strip()

    try:
        level_id = int(level_id_raw)
    except ValueError:
        flash("Prateleira inválida.", "error")
        return redirect(url_for("almoxarifado.almoxarifado"))

    level = ShelfLevel.query.get(level_id)
    if not level:
        flash("Prateleira não encontrada.", "error")
        return redirect(url_for("almoxarifado.almoxarifado"))

    try:
        # Unlink items from this level
        AlmoxItem.query.filter_by(shelf_level_id=level_id).update(
            {"shelf_level_id": None}
        )
        db.session.delete(level)
        db.session.commit()
        flash(f"Prateleira '{level.label}' removida.", "success")
    except Exception:
        db.session.rollback()
        flash("Erro ao remover prateleira.", "error")

    return redirect(url_for("almoxarifado.almoxarifado"))
