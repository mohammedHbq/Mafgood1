from extensions import db
from datetime import datetime
import enum


class ItemCategory(enum.Enum):
    ELECTRONICS = 'electronics'
    DOCUMENTS   = 'documents'
    KEYS        = 'keys'
    CLOTHING    = 'clothing'
    BAGS        = 'bags'
    JEWELRY     = 'jewelry'
    OTHER       = 'other'


class ItemStatus(enum.Enum):
    NOT_FOUND   = 'لم يُعثر عليه'   # الغرض لم يحصل عليه صاحبه بعد
    FOUND_OWNER = 'تم إيجاد صاحبه'  # الغرض وصل لصاحبه


class ItemType(enum.Enum):
    LOST  = 'lost'
    FOUND = 'found'


class Item(db.Model):
    __tablename__ = 'items'

    # ── Core fields (from class diagram) ─────────────────────────────────
    id         = db.Column(db.Integer, primary_key=True)
    item_name  = db.Column(db.String(120), nullable=False)
    category   = db.Column(db.Enum(ItemCategory), nullable=False)
    status     = db.Column(db.Enum(ItemStatus), default=ItemStatus.NOT_FOUND)
    item_type  = db.Column(db.Enum(ItemType),  nullable=False)  # lost / found
    image_path = db.Column(db.String(256), nullable=True)
    location   = db.Column(db.String(200), nullable=True)
    description = db.Column(db.Text, nullable=True)
    date_lost_found = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # ── Foreign keys ──────────────────────────────────────────────────────
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)

    # ── Relationships ─────────────────────────────────────────────────────
    reports = db.relationship('Report', backref='item', lazy=True,
                              cascade='all, delete-orphan', passive_deletes=True)
    matches_as_source = db.relationship(
        'Match', foreign_keys='Match.source_item_id', backref='source_item', lazy=True,
        cascade='all, delete-orphan', passive_deletes=True
    )
    matches_as_target = db.relationship(
        'Match', foreign_keys='Match.matched_item_id', backref='matched_item', lazy=True,
        cascade='all, delete-orphan', passive_deletes=True
    )

    # ── Item methods (from class diagram) ─────────────────────────────────
    @staticmethod
    def create_item(user_id, item_name, category, item_type,
                    image_path=None, location=None, description=None,
                    date_lost_found=None) -> bool:
        try:
            item = Item(
                user_id=user_id,
                item_name=item_name,
                category=category,
                item_type=item_type,
                image_path=image_path,
                location=location,
                description=description,
                date_lost_found=date_lost_found,
            )
            db.session.add(item)
            db.session.commit()
            return True
        except Exception:
            db.session.rollback()
            return False

    def show_item_details(self) -> str:
        return (
            f"Item: {self.item_name} | Category: {self.category.value} | "
            f"Status: {self.status.value} | Location: {self.location} | "
            f"Type: {self.item_type.value}"
        )

    def update_details(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        db.session.commit()

    def update_item_status(self, new_status: ItemStatus):
        self.status = new_status
        db.session.commit()

    def delete_item(self) -> bool:
        try:
            db.session.delete(self)
            db.session.commit()
            return True
        except Exception:
            db.session.rollback()
            return False

    def to_dict(self):
        return {
            'id':          self.id,
            'item_name':   self.item_name,
            'category':    self.category.value,
            'status':      self.status.value,
            'item_type':   self.item_type.value,
            'image_path':  self.image_path,
            'location':    self.location,
            'description': self.description,
            'created_at':  self.created_at.isoformat(),
            'owner_id':    self.user_id,
        }

    def __repr__(self):
        return f'<Item {self.item_name} [{self.item_type.value}]>'


class Match(db.Model):
    """Stores AI-generated match logs between lost and found items."""
    __tablename__ = 'matches'

    id              = db.Column(db.Integer, primary_key=True)
    source_item_id  = db.Column(db.Integer, db.ForeignKey('items.id', ondelete='CASCADE'), nullable=False)
    matched_item_id = db.Column(db.Integer, db.ForeignKey('items.id', ondelete='CASCADE'), nullable=False)
    similarity_score = db.Column(db.Float, nullable=False)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    notified        = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<Match {self.source_item_id} ↔ {self.matched_item_id} ({self.similarity_score:.2f})>'
