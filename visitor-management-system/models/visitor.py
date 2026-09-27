from datetime import datetime
from . import db


class Visitor(db.Model):
    __tablename__ = 'visitors'

    id = db.Column(db.Integer, primary_key=True)
    visitor_id = db.Column(db.String(40), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    phone = db.Column(db.String(30), nullable=False, index=True)
    email = db.Column(db.String(160), index=True)
    company = db.Column(db.String(160), index=True)
    address = db.Column(db.Text)
    purpose = db.Column(db.String(250), nullable=False, index=True)
    host_id = db.Column(db.Integer, db.ForeignKey('hosts.id'), nullable=False, index=True)
    id_proof_type = db.Column(db.String(50), nullable=False)
    id_proof_number = db.Column(db.String(120), nullable=False)
    photo = db.Column(db.String(255))
    appointment_date = db.Column(db.Date, nullable=False, index=True)
    appointment_time = db.Column(db.Time, nullable=False)
    check_in_time = db.Column(db.DateTime, index=True)
    check_out_time = db.Column(db.DateTime, index=True)
    status = db.Column(db.String(30), nullable=False, default='Pending', index=True)
    approval_status = db.Column(db.String(30), nullable=False, default='Pending', index=True)
    rejection_reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    host = db.relationship('Host', back_populates='visitors')
    notifications = db.relationship('Notification', back_populates='visitor', cascade='all, delete-orphan')
    activities = db.relationship('VisitActivity', back_populates='visitor', cascade='all, delete-orphan')

    def duration_seconds(self):
        if not self.check_in_time:
            return 0
        end = self.check_out_time or datetime.now()
        return max(0, int((end - self.check_in_time).total_seconds()))

    def duration_display(self):
        seconds = self.duration_seconds()
        hours, remainder = divmod(seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        return f'{hours}h {minutes:02d}m' if hours else f'{minutes}m'


class VisitActivity(db.Model):
    __tablename__ = 'visit_activities'

    id = db.Column(db.Integer, primary_key=True)
    visitor_id = db.Column(db.Integer, db.ForeignKey('visitors.id'), nullable=False, index=True)
    action = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    created_by = db.Column(db.String(160))

    visitor = db.relationship('Visitor', back_populates='activities')
