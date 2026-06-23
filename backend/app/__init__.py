from flask import Flask, redirect, url_for, session, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from pathlib import Path

db = SQLAlchemy()
migrate = Migrate()


def create_app():
    current_dir = Path(__file__).resolve().parent
    project_root = current_dir.parent.parent
    template_dir = project_root / "frontend" / "templates"
    static_dir = project_root / "frontend" / "static"

    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder=str(template_dir),
        static_folder=str(static_dir)
    )

    # Pasta instance (para SQLite)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    app.config["SECRET_KEY"] = "dev-secret-change-me"
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{Path(app.instance_path) / 'app.db'}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    migrate.init_app(app, db)

    # importa models (pra criar tabelas)
    from .models import Location, Sector, Equipment, AlmoxItem, AlmoxMovement, Shelf, ShelfLevel  # noqa: F401

    # registra blueprints refatorados
    from .routes.main_routes import bp as main_bp
    from .routes.locations_routes import bp as locations_bp
    from .routes.equipments_routes import bp as equipments_bp
    from .routes.almoxarifado_routes import bp as almoxarifado_bp
    from .routes.api_routes import bp as api_bp
    from .routes.user_routes import bp as user_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(locations_bp)
    app.register_blueprint(equipments_bp)
    app.register_blueprint(almoxarifado_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(user_bp)

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

        # Carrega o usuário atual do banco em tempo real
        from .models import User
        user = User.query.filter_by(username=session.get("user_name")).first()
        if not user:
            session.clear()
            return redirect(url_for("auth.login"))

        # Atualiza a sessão com as permissões mais recentes do banco
        session["can_view_dashboard"] = user.can_view_dashboard
        session["can_manage_locations"] = user.can_manage_locations
        session["can_manage_equipments"] = user.can_manage_equipments
        session["can_manage_almoxarifado"] = user.can_manage_almoxarifado
        session["can_manage_users"] = user.can_manage_users

        # Proteção de rotas com base nas permissões
        endpoint = request.endpoint
        if endpoint:
            if "locations" in endpoint and not user.can_manage_locations:
                flash("Você não tem permissão para acessar Localizações.", "error")
                return redirect(url_for("main.index"))
            if "equipments" in endpoint and not user.can_manage_equipments:
                flash("Você não tem permissão para acessar Equipamentos.", "error")
                return redirect(url_for("main.index"))
            if "almoxarifado" in endpoint and not user.can_manage_almoxarifado:
                flash("Você não tem permissão para acessar o Almoxarifado.", "error")
                return redirect(url_for("main.index"))
            if "users" in endpoint and not user.can_manage_users:
                flash("Você não tem permissão para acessar o Gerenciamento de Usuários.", "error")
                return redirect(url_for("main.index"))

        return None

    with app.app_context():
        pass
        # _seed_sectors()

    return app
