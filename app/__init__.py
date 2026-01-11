from flask import Flask, redirect, url_for, session, request
from flask_sqlalchemy import SQLAlchemy
from pathlib import Path

db = SQLAlchemy()


def create_app():
    app = Flask(__name__, instance_relative_config=True)

    # Pasta instance (para SQLite)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    app.config["SECRET_KEY"] = "dev-secret-change-me"
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{Path(app.instance_path) / 'app.db'}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    # importa models (pra criar tabelas)
    from .models import Location, Sector, Equipment  # noqa: F401

    # registra blueprints
    from .routes import bp as main_bp
    app.register_blueprint(main_bp)

    # auth blueprint (login/logout)
    from .auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    # opcional: se tentar acessar qualquer rota do "main" sem login, manda pro login
    @app.before_request
    def _protect_pages():
        # libera arquivos estáticos
        if request.endpoint and request.endpoint.startswith("static"):
            return None

        # libera rotas do auth
        if request.endpoint and request.endpoint.startswith("auth."):
            return None

        # se não está logado, manda pro login
        if not session.get("user_logged"):
            return redirect(url_for("auth.login"))

        return None

    with app.app_context():
        db.create_all()
        # ✅ REMOVIDO: qualquer seed automático (evita duplicidade)
        # _seed_sectors()

    return app
