import csv
import io
import os
import uuid
from datetime import date, datetime, time
from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, abort, jsonify, current_app
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateField, TimeField, FileField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Email, Optional, Length, Regexp
from werkzeug.utils import secure_filename
from PIL import Image
import qrcode
from sqlalchemy import or_

from models import db
from models.visitor import Visitor, VisitActivity
from models.host import Host
from models.notification import Notification, BlacklistEntry
from models.user import User
from .auth import roles_required

bp = Blueprint('visitors', __name__)

PHONE_RE = r'^\+?[0-9\s\-]{7,20}$'
ID_TYPES = [('Aadhaar', 'Aadhaar'), ('PAN', 'PAN'), ('Passport', 'Passport'), ('Driving Licence', 'Driving Licence'), ('Voter ID', 'Voter ID'), ('Other', 'Other')]


class VisitorForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=120)])
    phone = StringField('Mobile Number', validators=[DataRequired(), Regexp(PHONE_RE, message='Enter a valid phone number.')])
    email = StringField('Email', validators=[Optional(), Email(), Length(max=160)])
    company = StringField('Company / Organization', validators=[Optional(), Length(max=160)])
    address = TextAreaField('Address', validators=[Optional(), Length(max=1000)])
    host_id = SelectField('Person to Visit', coerce=int, validators=[DataRequired()])
    purpose = StringField('Purpose of Visit', validators=[DataRequired(), Length(min=2, max=250)])
    id_proof_type = SelectField('ID Proof Type', choices=ID_TYPES, validators=[DataRequired()])
    id_proof_number = StringField('ID Proof Number', validators=[DataRequired(), Length(min=3, max=120)])
    appointment_date = DateField('Appointment Date', validators=[DataRequired()], format='%Y-%m-%d')
    appointment_time = TimeField('Appointment Time', validators=[DataRequired()], format='%H:%M')
    photo = FileField('Visitor Photo', validators=[Optional()])
    submit = SubmitField('Save Visitor')


class ApprovalForm(FlaskForm):
    action = HiddenField('Action', validators=[DataRequired()])
    rejection_reason = TextAreaField('Rejection Reason', validators=[Optional(), Length(max=1000)])
    submit = SubmitField('Submit')


class BlacklistForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(min=2, max=120)])
    phone = StringField('Phone', validators=[DataRequired(), Regexp(PHONE_RE, message='Enter a valid phone number.')])
    reason = TextAreaField('Reason', validators=[DataRequired(), Length(min=3, max=1000)])
    submit = SubmitField('Add to Blacklist')


def _set_hosts(form):
    form.host_id.choices = [(h.id, f'{h.name} — {h.department}') for h in Host.query.filter_by(is_active=True).order_by(Host.name.asc()).all()]


def _allowed_image(file_storage):
    if not file_storage or not file_storage.filename:
        return False
    filename = secure_filename(file_storage.filename)
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext not in current_app.config['ALLOWED_IMAGE_EXTENSIONS'] or file_storage.mimetype not in current_app.config['ALLOWED_IMAGE_MIMETYPES']:
        return False
    try:
        file_storage.stream.seek(0)
        with Image.open(file_storage.stream) as image:
            image.verify()
            if image.format.lower() not in {'jpeg', 'png'}:
                return False
        file_storage.stream.seek(0)
        return True
    except Exception:
        try:
            file_storage.stream.seek(0)
        except Exception:
            pass
        return False


def _save_photo(file_storage):
    if not file_storage or not file_storage.filename:
        return None
    if not _allowed_image(file_storage):
        raise ValueError('Photo must be a valid JPG, JPEG, or PNG image under 2 MB.')
    ext = secure_filename(file_storage.filename).rsplit('.', 1)[-1].lower()
    filename = f'{uuid.uuid4().hex}.{ext}'
    file_storage.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
    return f'uploads/{filename}'


def _generate_visitor_id():
    year = datetime.utcnow().year
    prefix = f'VIS-{year}-'
    last = Visitor.query.filter(Visitor.visitor_id.like(f'{prefix}%')).order_by(Visitor.id.desc()).first()
    next_number = 1
    if last:
        try:
            next_number = int(last.visitor_id.split('-')[-1]) + 1
        except (ValueError, IndexError):
            next_number = Visitor.query.count() + 1
    return f'{prefix}{next_number:05d}'


def _add_activity(visitor, action, description):
    actor = current_user.email if current_user.is_authenticated else 'system'
    db.session.add(VisitActivity(visitor_id=visitor.id, action=action, description=description, created_by=actor))


def _notify(recipient, message, visitor=None, notification_type='info'):
    recipients = [recipient]
    # Hosts are not system users in the requested data model, so mirror host notices
    # to active ADMIN/RECEPTIONIST accounts so they are visible in the in-app dashboard.
    if not User.query.filter_by(email=recipient).first():
        staff_emails = [u.email for u in User.query.filter(User.is_active.is_(True), User.role.in_(['ADMIN', 'RECEPTIONIST'])).all()]
        recipients.extend([email for email in staff_emails if email not in recipients])
    for target in recipients:
        db.session.add(Notification(visitor_id=visitor.id if visitor else None, recipient=target, message=message, notification_type=notification_type))
        try:
            if current_app.extensions.get('mail') and '@' in target:
                from flask_mail import Message
                msg = Message(subject='Visitor Management System Notification', recipients=[target], body=message)
                current_app.extensions['mail'].send(msg)
        except Exception:
            current_app.logger.exception('Optional email notification failed')


def _find_blacklist(visitor):
    phone = visitor.phone.replace(' ', '').replace('-', '')
    entries = BlacklistEntry.query.all()
    for entry in entries:
        entry_phone = entry.phone.replace(' ', '').replace('-', '')
        if entry_phone and entry_phone == phone:
            return entry
        if entry.name.strip().lower() == visitor.name.strip().lower():
            return entry
    return None


def _visitor_query_from_request():
    q = request.args.get('q', '').strip()
    status = request.args.get('status', '').strip()
    department = request.args.get('department', '').strip()
    purpose = request.args.get('purpose', '').strip()
    date_filter = request.args.get('date', '').strip()
    host_id = request.args.get('host_id', '').strip()
    query = Visitor.query.join(Host, Visitor.host_id == Host.id)
    if q:
        like = f'%{q}%'
        query = query.filter(or_(Visitor.name.ilike(like), Visitor.phone.ilike(like), Visitor.visitor_id.ilike(like), Visitor.company.ilike(like), Host.name.ilike(like)))
    if status:
        query = query.filter(Visitor.status == status)
    if department:
        query = query.filter(Host.department == department)
    if purpose:
        query = query.filter(Visitor.purpose.ilike(f'%{purpose}%'))
    if date_filter:
        try:
            parsed = datetime.strptime(date_filter, '%Y-%m-%d').date()
            query = query.filter(Visitor.appointment_date == parsed)
        except ValueError:
            pass
    if host_id:
        try:
            query = query.filter(Visitor.host_id == int(host_id))
        except ValueError:
            pass
    return query


@bp.get('/')
@login_required
def index():
    query = _visitor_query_from_request().order_by(Visitor.created_at.desc())
    page = request.args.get('page', 1, type=int)
    pagination = query.paginate(page=page, per_page=10, error_out=False)
    departments = [r[0] for r in db.session.query(Host.department).filter(Host.is_active.is_(True)).distinct().order_by(Host.department).all()]
    hosts = Host.query.order_by(Host.name).all()
    return render_template('visitors/list.html', pagination=pagination, visitors=pagination.items, departments=departments, hosts=hosts, statuses=['Pending', 'Approved', 'Rejected', 'Checked In', 'Checked Out', 'Cancelled'], appointment_mode=(request.args.get('date') == date.today().isoformat()))


@bp.route('/add', methods=['GET', 'POST'])
@roles_required('ADMIN', 'SECURITY', 'RECEPTIONIST')
def add():
    form = VisitorForm()
    _set_hosts(form)
    if form.validate_on_submit():
        if form.appointment_date.data < date.today():
            flash('Appointment date cannot be in the past.', 'danger')
        elif not form.host_id.data:
            flash('Please select a host.', 'danger')
        else:
            try:
                photo_path = _save_photo(form.photo.data) if form.photo.data and form.photo.data.filename else None
            except ValueError as exc:
                flash(str(exc), 'danger')
                photo_path = None
            else:
                host = Host.query.get_or_404(form.host_id.data)
                approval = 'Approved' if current_user.role == 'SECURITY' else 'Pending'
                status = 'Approved' if approval == 'Approved' else 'Pending'
                visitor = Visitor(
                    visitor_id=_generate_visitor_id(), name=form.name.data.strip(), phone=form.phone.data.strip(),
                    email=form.email.data.strip().lower() if form.email.data else None, company=form.company.data.strip() if form.company.data else None,
                    address=form.address.data.strip() if form.address.data else None, purpose=form.purpose.data.strip(), host_id=host.id,
                    id_proof_type=form.id_proof_type.data, id_proof_number=form.id_proof_number.data.strip(), photo=photo_path,
                    appointment_date=form.appointment_date.data, appointment_time=form.appointment_time.data,
                    status=status, approval_status=approval,
                )
                db.session.add(visitor)
                db.session.flush()
                _add_activity(visitor, 'REGISTERED', f'Visitor registered for {host.name}.')
                if approval == 'Approved':
                    _notify(host.email, f'Visitor {visitor.name} ({visitor.visitor_id}) is registered and approved to visit you.', visitor, 'approved')
                else:
                    _notify(host.email, f'Visitor {visitor.name} ({visitor.visitor_id}) has been registered and is awaiting approval.', visitor, 'pending')
                db.session.commit()
                flash(f'Visitor {visitor.visitor_id} registered successfully.', 'success')
                return redirect(url_for('visitors.details', visitor_id=visitor.id))
    return render_template('visitors/add.html', form=form)


@bp.route('/<int:visitor_id>/edit', methods=['GET', 'POST'])
@roles_required('ADMIN', 'RECEPTIONIST')
def edit(visitor_id):
    visitor = Visitor.query.get_or_404(visitor_id)
    form = VisitorForm(obj=visitor)
    _set_hosts(form)
    if request.method == 'GET':
        form.host_id.data = visitor.host_id
        if visitor.appointment_date:
            form.appointment_date.data = visitor.appointment_date
        if visitor.appointment_time:
            form.appointment_time.data = visitor.appointment_time
    if form.validate_on_submit():
        if form.appointment_date.data < date.today() and visitor.status not in {'Checked In', 'Checked Out'}:
            flash('Appointment date cannot be in the past.', 'danger')
        else:
            if form.photo.data and form.photo.data.filename:
                try:
                    visitor.photo = _save_photo(form.photo.data)
                except ValueError as exc:
                    flash(str(exc), 'danger')
                    return render_template('visitors/edit.html', form=form, visitor=visitor)
            visitor.name = form.name.data.strip(); visitor.phone = form.phone.data.strip(); visitor.email = form.email.data.strip().lower() if form.email.data else None
            visitor.company = form.company.data.strip() if form.company.data else None; visitor.address = form.address.data.strip() if form.address.data else None
            visitor.host_id = form.host_id.data; visitor.purpose = form.purpose.data.strip(); visitor.id_proof_type = form.id_proof_type.data
            visitor.id_proof_number = form.id_proof_number.data.strip(); visitor.appointment_date = form.appointment_date.data; visitor.appointment_time = form.appointment_time.data
            _add_activity(visitor, 'UPDATED', 'Visitor information updated.')
            db.session.commit()
            flash('Visitor updated successfully.', 'success')
            return redirect(url_for('visitors.details', visitor_id=visitor.id))
    return render_template('visitors/edit.html', form=form, visitor=visitor)


@bp.get('/<int:visitor_id>')
@login_required
def details(visitor_id):
    visitor = Visitor.query.get_or_404(visitor_id)
    blacklist = _find_blacklist(visitor)
    approval_form = ApprovalForm()
    return render_template('visitors/details.html', visitor=visitor, blacklist=blacklist, approval_form=approval_form)


@bp.post('/<int:visitor_id>/delete')
@roles_required('ADMIN')
def delete(visitor_id):
    visitor = Visitor.query.get_or_404(visitor_id)
    photo_path = visitor.photo
    db.session.delete(visitor)
    db.session.commit()
    if photo_path:
        absolute = os.path.join(current_app.static_folder, photo_path)
        if os.path.exists(absolute):
            try:
                os.remove(absolute)
            except OSError:
                pass
    flash('Visitor record deleted.', 'success')
    return redirect(url_for('visitors.index'))


@bp.post('/<int:visitor_id>/checkin')
@roles_required('ADMIN', 'SECURITY')
def checkin(visitor_id):
    visitor = Visitor.query.get_or_404(visitor_id)
    override = request.form.get('override') == '1'
    if visitor.status == 'Checked In':
        flash('Visitor is already checked in.', 'warning')
        return redirect(url_for('visitors.details', visitor_id=visitor.id))
    if visitor.approval_status != 'Approved':
        flash('Visitor must be approved before check-in.', 'danger')
        return redirect(url_for('visitors.details', visitor_id=visitor.id))
    blacklist = _find_blacklist(visitor)
    if blacklist and not (override and current_user.role == 'ADMIN'):
        flash('WARNING: This visitor is currently blacklisted. An ADMIN override is required.', 'danger')
        return redirect(url_for('visitors.details', visitor_id=visitor.id))
    visitor.check_in_time = datetime.now()
    visitor.status = 'Checked In'
    _add_activity(visitor, 'CHECKED_IN', f'Visitor checked in to meet {visitor.host.name}.')
    _notify(visitor.host.email, f'Visitor {visitor.name} has arrived at reception to meet you.', visitor, 'arrival')
    db.session.commit()
    flash('Visitor checked in successfully.', 'success')
    return redirect(url_for('visitors.details', visitor_id=visitor.id))


@bp.post('/<int:visitor_id>/checkout')
@roles_required('ADMIN', 'SECURITY')
def checkout(visitor_id):
    visitor = Visitor.query.get_or_404(visitor_id)
    if visitor.status != 'Checked In':
        flash('Only checked-in visitors can be checked out.', 'warning')
        return redirect(url_for('visitors.details', visitor_id=visitor.id))
    visitor.check_out_time = datetime.utcnow()
    visitor.status = 'Checked Out'
    _add_activity(visitor, 'CHECKED_OUT', f'Visitor checked out. Duration: {visitor.duration_display()}.')
    _notify(visitor.host.email, f'Visitor {visitor.name} ({visitor.visitor_id}) has checked out.', visitor, 'checkout')
    db.session.commit()
    flash(f'Visitor checked out. Visit duration: {visitor.duration_display()}.', 'success')
    return redirect(url_for('visitors.details', visitor_id=visitor.id))


@bp.post('/<int:visitor_id>/approval')
@roles_required('ADMIN', 'RECEPTIONIST')
def approval(visitor_id):
    visitor = Visitor.query.get_or_404(visitor_id)
    action = request.form.get('action', '').lower()
    reason = request.form.get('rejection_reason', '').strip()
    if action == 'approve':
        visitor.approval_status = 'Approved'; visitor.status = 'Approved'; visitor.rejection_reason = None
        _add_activity(visitor, 'APPROVED', 'Visitor appointment approved.')
        _notify(visitor.host.email, f'Visitor {visitor.name} ({visitor.visitor_id}) has been approved to visit you.', visitor, 'approved')
        flash('Visitor approved.', 'success')
    elif action == 'reject':
        if not reason:
            flash('Rejection reason is required.', 'danger')
            return redirect(url_for('visitors.details', visitor_id=visitor.id))
        visitor.approval_status = 'Rejected'; visitor.status = 'Rejected'; visitor.rejection_reason = reason
        _add_activity(visitor, 'REJECTED', f'Visitor rejected: {reason}')
        _notify(visitor.host.email, f'Visitor {visitor.name} ({visitor.visitor_id}) was rejected. Reason: {reason}', visitor, 'rejected')
        flash('Visitor rejected.', 'warning')
    elif action == 'cancel':
        visitor.approval_status = 'Cancelled'; visitor.status = 'Cancelled'
        _add_activity(visitor, 'CANCELLED', 'Visitor appointment cancelled.')
        _notify(visitor.host.email, f'Visitor {visitor.name} ({visitor.visitor_id}) appointment was cancelled.', visitor, 'cancelled')
        flash('Visitor appointment cancelled.', 'info')
    else:
        flash('Invalid approval action.', 'danger')
    db.session.commit()
    return redirect(url_for('visitors.details', visitor_id=visitor.id))


@bp.get('/<int:visitor_id>/pass')
@login_required
def visitor_pass(visitor_id):
    visitor = Visitor.query.get_or_404(visitor_id)
    payload = visitor.visitor_id
    qr = qrcode.make(payload)
    buf = io.BytesIO(); qr.save(buf, format='PNG'); buf.seek(0)
    import base64
    qr_data = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')
    from datetime import timedelta
    expected_checkout = (datetime.combine(visitor.appointment_date, visitor.appointment_time) + timedelta(hours=2)).strftime('%I:%M %p')
    return render_template('visitors/pass.html', visitor=visitor, qr_data=qr_data, expected_checkout=expected_checkout)


@bp.get('/blacklist')
@roles_required('ADMIN')
def blacklist():
    entries = BlacklistEntry.query.order_by(BlacklistEntry.created_at.desc()).all()
    form = BlacklistForm()
    return render_template('visitors/blacklist.html', entries=entries, form=form)


@bp.post('/blacklist/add')
@roles_required('ADMIN')
def blacklist_add():
    form = BlacklistForm()
    if form.validate_on_submit():
        entry = BlacklistEntry(name=form.name.data.strip(), phone=form.phone.data.strip(), reason=form.reason.data.strip(), created_by=current_user.email)
        db.session.add(entry); db.session.commit()
        flash('Visitor added to blacklist.', 'success')
    else:
        flash('Please correct the blacklist form errors.', 'danger')
    return redirect(url_for('visitors.blacklist'))


@bp.post('/blacklist/<int:entry_id>/delete')
@roles_required('ADMIN')
def blacklist_delete(entry_id):
    entry = BlacklistEntry.query.get_or_404(entry_id)
    db.session.delete(entry); db.session.commit()
    flash('Blacklist entry removed.', 'success')
    return redirect(url_for('visitors.blacklist'))
