from extensions import db
from datetime import datetime


class Report(db.Model):
    __tablename__ = 'reports'

    id          = db.Column(db.Integer, primary_key=True)
    reason      = db.Column(db.String(500), nullable=False)
    status      = db.Column(db.String(20),  default='pending')  # pending / actioned / dismissed
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    # Foreign keys
    reporter_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'),  nullable=False)
    item_id     = db.Column(db.Integer, db.ForeignKey('items.id', ondelete='CASCADE'),  nullable=False)

    def get_report_details(self) -> str:
        return (
            f"Report #{self.id} | Item: {self.item_id} | "
            f"Reason: {self.reason} | Status: {self.status}"
        )

    def to_dict(self):
        return {
            'id':          self.id,
            'reason':      self.reason,
            'status':      self.status,
            'reporter_id': self.reporter_id,
            'item_id':     self.item_id,
            'created_at':  self.created_at.isoformat(),
        }

    def __repr__(self):
        return f'<Report {self.id} on Item {self.item_id}>'


class Notification(db.Model):
    """تنبيهات تُرسل للمستخدم عند تغيير حالة غرضه أو حذفه."""
    __tablename__ = 'notifications'

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    message    = db.Column(db.String(1000), nullable=False)
    link       = db.Column(db.String(500), nullable=True)
    is_read    = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', back_populates='notifications')

    @staticmethod
    def send(user_id: int, message: str, link: str = None):
        notif = Notification(user_id=user_id, message=message, link=link)
        db.session.add(notif)
        # لا نعمل commit هنا — يُترك للـ caller

    def __repr__(self):
        return f'<Notification {self.id} → user {self.user_id}>'

