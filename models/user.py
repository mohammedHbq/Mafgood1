from extensions import db, bcrypt, login_manager
from flask_login import UserMixin
from datetime import datetime


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(db.Model, UserMixin):
    __tablename__ = 'users'

    # ── Shared fields (Profile in class diagram) ──────────────────────────
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80),  unique=True, nullable=False)
    full_name     = db.Column(db.String(120), nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    profile_status = db.Column(db.String(20), default='active')   # active / suspended / blocked
    is_admin      = db.Column(db.Boolean, default=False)
    email_verified = db.Column(db.Boolean, default=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    # ── Student-specific fields ───────────────────────────────────────────
    university_email = db.Column(db.String(120), nullable=True)
    phone_number     = db.Column(db.String(20),  nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────
    items         = db.relationship('Item',         backref='owner',     lazy=True,
                                    cascade='all, delete-orphan')
    reports       = db.relationship('Report',       backref='reporter', lazy=True,
                                    cascade='all, delete-orphan')
    notifications = db.relationship('Notification', back_populates='user', lazy=True,
                                    cascade='all, delete-orphan')

    # ── Password helpers ──────────────────────────────────────────────────
    def set_password(self, password: str):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, password)

    # ── Profile methods (from diagram) ────────────────────────────────────
    def reset_password(self, new_password: str) -> str:
        self.set_password(new_password)
        db.session.commit()
        return 'Password reset successfully'

    def view_profile(self):
        return {
            'id':       self.id,
            'username': self.username,
            'fullName': self.full_name,
            'email':    self.email,
            'status':   self.profile_status,
        }

    def verify_email(self):
        self.email_verified = True
        db.session.commit()

    def update_profile_info(self, **kwargs) -> bool:
        try:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)
            db.session.commit()
            return True
        except Exception:
            db.session.rollback()
            return False

    # ── User methods (from diagram) ───────────────────────────────────────
    def view_items(self):
        from models.item import Item, ItemStatus
        return Item.query.filter_by(status=ItemStatus.NOT_FOUND).all()

    def search_item(self, item_name=None, category=None, status=None):
        from models.item import Item
        query = Item.query
        if item_name:
            query = query.filter(Item.item_name.ilike(f'%{item_name}%'))
        if category:
            query = query.filter_by(category=category)
        if status:
            query = query.filter_by(status=status)
        return query.all()

    def submit_report(self, item_id: int, reason: str) -> bool:
        from models.report import Report
        try:
            report = Report(item_id=item_id, reason=reason, reporter_id=self.id)
            db.session.add(report)
            db.session.commit()
            return True
        except Exception:
            db.session.rollback()
            return False

    def __repr__(self):
        return f'<User {self.username}>'
