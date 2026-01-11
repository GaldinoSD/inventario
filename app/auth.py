# app/auth.py
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, session

bp = Blueprint("auth", __name__)

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_logged"):
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped

@bp.get("/login")
def login():
    # se já estiver logado, manda pro dashboard
    if session.get("user_logged"):
        return redirect(url_for("main.index"))
    return render_template("auth/login.html")

@bp.post("/login")
def login_post():
    username = (request.form.get("username") or "").strip()
    password = (request.form.get("password") or "").strip()

    # ✅ simples (troque depois por DB / hash)
    USER_OK = "admin"
    PASS_OK = "1234"

    if username == USER_OK and password == PASS_OK:
        session["user_logged"] = True
        session["user_name"] = username
        flash("Bem-vindo!", "success")
        return redirect(url_for("main.index"))

    flash("Usuário ou senha inválidos.", "error")
    return redirect(url_for("auth.login"))

@bp.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
