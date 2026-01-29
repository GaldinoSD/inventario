from datetime import datetime

from sqlalchemy import func

from . import db


class Location(db.Model):
    __tablename__ = "locations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    address = db.Column(db.String(255))
    notes = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # ✅ 1 Localização -> N Setores
    sectors = db.relationship(
        "Sector",
        back_populates="location",
        cascade="all, delete-orphan",
        lazy=True,
    )

    # ✅ 1 Localização -> N Equipamentos
    equipments = db.relationship(
        "Equipment",
        back_populates="location",
        cascade="all, delete-orphan",
        lazy=True,
    )

    def __repr__(self):
        return f"<Location {self.name}>"


class Sector(db.Model):
    __tablename__ = "sectors"

    id = db.Column(db.Integer, primary_key=True)

    # ✅ Unicidade é por localização (ver constraint abaixo)
    name = db.Column(db.String(120), nullable=False)

    # ✅ Setor pertence a uma localização
    location_id = db.Column(db.Integer, db.ForeignKey("locations.id"), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # ✅ relacionamento reverso
    location = db.relationship("Location", back_populates="sectors")

    equipments = db.relationship(
        "Equipment",
        back_populates="sector",
        cascade="all, delete-orphan",
        lazy=True,
    )

    # ✅ evita duplicidade dentro da mesma localização
    #    (case-insensitive: "Setor A" = "setor a")
    __table_args__ = (
        db.UniqueConstraint("location_id", "name", name="uq_sector_location_name"),
        db.Index("ix_sector_location_lower_name", "location_id", func.lower(name)),
    )

    def __repr__(self):
        return f"<Sector {self.name} (loc={self.location_id})>"


class Equipment(db.Model):
    __tablename__ = "equipments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    brand = db.Column(db.String(120))
    value = db.Column(db.Numeric(12, 2))
    invoice_nf = db.Column(db.String(80))
    barcode_pat = db.Column(db.String(120), unique=True, nullable=False, index=True)

    # ✅ NOVO: arquivo/imagem da nota fiscal vinculada ao equipamento
    # Guarda apenas o nome do arquivo salvo (ex: "nf_12.jpg" ou "nf_12.pdf")
    invoice_file = db.Column(db.String(255), nullable=True)

    # ✅ Opcional: guarda o mime para facilitar preview (image/jpeg, application/pdf, etc.)
    invoice_mime = db.Column(db.String(80), nullable=True)

    location_id = db.Column(db.Integer, db.ForeignKey("locations.id"), nullable=False, index=True)
    sector_id = db.Column(db.Integer, db.ForeignKey("sectors.id"), nullable=False, index=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # ✅ Opcional: útil para auditoria / controle
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    location = db.relationship("Location", back_populates="equipments")
    sector = db.relationship("Sector", back_populates="equipments")

    def __repr__(self):
        return f"<Equipment {self.name} ({self.barcode_pat})>"


class AlmoxItem(db.Model):
    __tablename__ = "almox_items"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False, unique=True, index=True)
    qty = db.Column(db.Integer, nullable=False, default=0)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    movements = db.relationship(
        "AlmoxMovement",
        backref="item",
        lazy=True,
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<AlmoxItem {self.id} {self.name} qty={self.qty}>"


class AlmoxMovement(db.Model):
    __tablename__ = "almox_movements"

    id = db.Column(db.Integer, primary_key=True)

    # ENTRADA / USO / DANO / PERDA
    type = db.Column(db.String(16), nullable=False, index=True)

    qty = db.Column(db.Integer, nullable=False)  # sempre positivo
    local = db.Column(db.String(180), nullable=True)
    motivo = db.Column(db.String(220), nullable=True)

    item_id = db.Column(db.Integer, db.ForeignKey("almox_items.id"), nullable=False, index=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<AlmoxMovement {self.id} type={self.type} qty={self.qty} item_id={self.item_id}>"
