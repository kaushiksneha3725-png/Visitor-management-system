from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Email, Length
from models import db
from models.host import Host
from sqlalchemy import func, or_
from .auth import roles_required

bp = Blueprint('hosts', __name__)


class HostForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=120)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=160)])
    phone = StringField('Phone', validators=[DataRequired(), Length(min=7, max=30)])
    department = StringField('Department', validators=[DataRequired(), Length(min=2, max=120)])
    designation = StringField('Designation', validators=[DataRequired(), Length(min=2, max=120)])
    submit = SubmitField('Save Host')


@bp.get('/')
@login_required
def index():
    q = request.args.get('q', '').strip()
    query = Host.query
    if q:
        like = f'%{q}%'
        query = query.filter(or_(Host.name.ilike(like), Host.email.ilike(like), Host.department.ilike(like), Host.designation.ilike(like), Host.phone.ilike(like)))
    hosts = query.order_by(Host.name.asc()).all()
    return render_template('hosts/list.html', hosts=hosts, q=q)


@bp.route('/add', methods=['GET', 'POST'])
@roles_required('ADMIN', 'RECEPTIONIST')
def add():
    form = HostForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        if Host.query.filter(func.lower(Host.email) == email).first():
            flash('A host with that email already exists.', 'danger')
        else:
            host = Host(name=form.name.data.strip(), email=email, phone=form.phone.data.strip(), department=form.department.data.strip(), designation=form.designation.data.strip())
            db.session.add(host)
            db.session.commit()
            flash('Host added successfully.', 'success')
            return redirect(url_for('hosts.index'))
    return render_template('hosts/form.html', form=form, title='Add Host')


@bp.route('/<int:host_id>/edit', methods=['GET', 'POST'])
@roles_required('ADMIN', 'RECEPTIONIST')
def edit(host_id):
    host = Host.query.get_or_404(host_id)
    form = HostForm(obj=host)
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        if Host.query.filter(func.lower(Host.email) == email, Host.id != host.id).first():
            flash('A host with that email already exists.', 'danger')
        else:
            host.name = form.name.data.strip(); host.email = email; host.phone = form.phone.data.strip(); host.department = form.department.data.strip(); host.designation = form.designation.data.strip()
            db.session.commit()
            flash('Host updated successfully.', 'success')
            return redirect(url_for('hosts.index'))
    return render_template('hosts/form.html', form=form, title='Edit Host', host=host)


@bp.get('/<int:host_id>')
@login_required
def details(host_id):
    host = Host.query.get_or_404(host_id)
    visitors = host.visitors.order_by(db.text('appointment_date DESC'), db.text('appointment_time DESC')).limit(50).all()
    return render_template('hosts/details.html', host=host, visitors=visitors)


@bp.post('/<int:host_id>/toggle')
@roles_required('ADMIN')
def toggle(host_id):
    host = Host.query.get_or_404(host_id)
    host.is_active = not host.is_active
    db.session.commit()
    flash(f"Host {'activated' if host.is_active else 'deactivated'}.", 'success')
    return redirect(url_for('hosts.index'))
