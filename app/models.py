from datetime import datetime
from . import db


class Location(db.Model):
    __tablename__ = "locations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    address = db.Column(db.String(255))
    notes = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # ✅ 1 Localização -> N Setores
    sectors = db.relationship(
        "Sector",
        back_populates="location",
        cascade="all, delete-orphan",
        lazy=True
    )

    # ✅ 1 Localização -> N Equipamentos (como você já tinha)
    equipments = db.relationship(
        "Equipment",
        back_populates="location",
        cascade="all, delete-orphan",
        lazy=True
    )

    def __repr__(self):
        return f"<Location {self.name}>"


class Sector(db.Model):
    __tablename__ = "sectors"

    id = db.Column(db.Integer, primary_key=True)

    # ✅ REMOVIDO unique=True (agora a unicidade é por localização)
    name = db.Column(db.String(120), nullable=False)

    # ✅ NOVO: Setor pertence a uma localização
    location_id = db.Column(db.Integer, db.ForeignKey("locations.id"), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # ✅ relacionamento reverso
    location = db.relationship("Location", back_populates="sectors")

    equipments = db.relationship(
        "Equipment",
        back_populates="sector",
        cascade="all, delete-orphan",
        lazy=True
    )

    # ✅ evita duplicidade: mesmo setor repetido dentro da mesma localização
    __table_args__ = (
        db.UniqueConstraint("location_id", "name", name="uq_sector_location_name"),
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
    barcode_pat = db.Column(db.String(120), unique=True, nullable=False)

    location_id = db.Column(db.Integer, db.ForeignKey("locations.id"), nullable=False)
    sector_id = db.Column(db.Integer, db.ForeignKey("sectors.id"), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    location = db.relationship("Location", back_populates="equipments")
    sector = db.relationship("Sector", back_populates="equipments")

    def __repr__(self):
        return f"<Equipment {self.name} ({self.barcode_pat})>"
