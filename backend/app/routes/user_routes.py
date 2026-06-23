# app/routes/user_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from ..models import User
from .. import db

bp = Blueprint("users", __name__)

@bp.route("/usuarios")
def users_list():
    users = User.query.order_by(User.username).all()
    return render_template("users/list.html", users=users)

@bp.route("/usuarios/cadastrar", methods=["POST"])
def user_create():
    username = (request.form.get("username") or "").strip()
    password = (request.form.get("password") or "").strip()

    if not username or not password:
        flash("Nome de usuário e senha são obrigatórios.", "error")
        return redirect(url_for("users.users_list"))

    # Verifica se já existe
    existing = User.query.filter_by(username=username).first()
    if existing:
        flash("Este nome de usuário já está cadastrado.", "error")
        return redirect(url_for("users.users_list"))

    user = User(username=username, role="viewer")
    user.set_password(password)

    # Permissões padrão para novo usuário (apenas visualização do dashboard)
    user.can_view_dashboard = True
    user.can_manage_locations = False
    user.can_manage_equipments = False
    user.can_manage_almoxarifado = False
    user.can_manage_users = False

    try:
        db.session.add(user)
        db.session.commit()
        flash("Usuário cadastrado com sucesso!", "success")
    except Exception:
        db.session.rollback()
        flash("Erro ao cadastrar usuário.", "error")

    return redirect(url_for("users.users_list"))

@bp.route("/usuarios/editar/<int:user_id>", methods=["POST"])
def user_edit(user_id):
    user = User.query.get_or_404(user_id)
    password = (request.form.get("password") or "").strip()

    # Leitura dos checkboxes das permissões
    can_view_dashboard = True if request.form.get("can_view_dashboard") else False
    can_manage_locations = True if request.form.get("can_manage_locations") else False
    can_manage_equipments = True if request.form.get("can_manage_equipments") else False
    can_manage_almoxarifado = True if request.form.get("can_manage_almoxarifado") else False
    can_manage_users = True if request.form.get("can_manage_users") else False

    # Trava de Segurança: Não permite remover a própria permissão de gerenciar usuários
    if user.username == session.get("user_name") and not can_manage_users:
        flash("Você não pode remover sua própria permissão de gerenciar usuários.", "error")
        return redirect(url_for("users.users_list"))

    user.can_view_dashboard = can_view_dashboard
    user.can_manage_locations = can_manage_locations
    user.can_manage_equipments = can_manage_equipments
    user.can_manage_almoxarifado = can_manage_almoxarifado
    user.can_manage_users = can_manage_users

    # Atualiza a senha se preenchida
    if password:
        user.set_password(password)

    try:
        db.session.commit()
        flash("Permissões do usuário atualizadas com sucesso!", "success")
    except Exception:
        db.session.rollback()
        flash("Erro ao atualizar as permissões.", "error")

    return redirect(url_for("users.users_list"))

@bp.route("/usuarios/excluir/<int:user_id>", methods=["POST"])
def user_delete(user_id):
    user = User.query.get_or_404(user_id)

    # Trava de Segurança: Não permite deletar a si mesmo
    if user.username == session.get("user_name"):
        flash("Você não pode excluir sua própria conta.", "error")
        return redirect(url_for("users.users_list"))

    try:
        db.session.delete(user)
        db.session.commit()
        flash("Usuário excluído com sucesso!", "success")
    except Exception:
        db.session.rollback()
        flash("Erro ao excluir usuário.", "error")

    return redirect(url_for("users.users_list"))
