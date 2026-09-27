from flask import Blueprint, render_template, jsonify, request, redirect, url_for, flash
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Email, Length
from flask_login import login_required, current_user
from models import db
from models.notification import Notification
from models.user import User
from .auth import roles_required

bp = Blueprint('notifications', __name__)


@bp.get('/')
@login_required
def index():
    notifications = Notification.query.filter_by(recipient=current_user.email).order_by(Notification.created_at.desc()).all()
    return render_template('notifications.html', notifications=notifications)


@bp.get('/api')
@login_required
def api_notifications():
    notifications = Notification.query.filter_by(recipient=current_user.email).order_by(Notification.created_at.desc()).limit(15).all()
    unread = sum(1 for n in notifications if not n.is_read)
    return jsonify({
        'unread': unread,
        'notifications': [
            {'id': n.id, 'message': n.message, 'type': n.notification_type, 'is_read': n.is_read, 'created_at': n.created_at.strftime('%d %b %I:%M %p')} for n in notifications
        ]
    })


@bp.post('/<int:notification_id>/read')
@login_required
def mark_read(notification_id):
    notification = Notification.query.filter_by(id=notification_id, recipient=current_user.email).first_or_404()
    notification.is_read = True
    db.session.commit()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return jsonify({'ok': True})
    flash('Notification marked as read.', 'success')
    return redirect(url_for('notifications.index'))


@bp.post('/read-all')
@login_required
def mark_all_read():
    Notification.query.filter_by(recipient=current_user.email, is_read=False).update({'is_read': True})
    db.session.commit()
    flash('All notifications marked as read.', 'success')
    return redirect(url_for('notifications.index'))


class SendNotificationForm(FlaskForm):
    recipient = StringField('Recipient email', validators=[DataRequired(), Email(), Length(max=160)])
    message = TextAreaField('Message', validators=[DataRequired(), Length(min=3, max=1000)])
    submit = SubmitField('Send Notification')


@bp.route('/send', methods=['GET', 'POST'])
@roles_required('ADMIN', 'RECEPTIONIST')
def send_notification():
    form = SendNotificationForm()
    if form.validate_on_submit():
        target = form.recipient.data.strip().lower()
        message = form.message.data.strip()
        db.session.add(Notification(recipient=target, message=message, notification_type='manual'))
        db.session.commit()
        flash('Notification sent to the selected email address.', 'success')
        return redirect(url_for('notifications.index'))
    return render_template('notifications/send.html', form=form)
