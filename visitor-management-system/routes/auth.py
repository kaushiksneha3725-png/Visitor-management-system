from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Length
from models import db
from models.user import User
from sqlalchemy import func, or_

bp = Blueprint('auth', __name__)


class LoginForm(FlaskForm):
    identity = StringField('Email / Username', validators=[DataRequired(), Length(max=160)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=128)])
    remember = BooleanField('Remember me')
    submit = SubmitField('Sign in')


class UserForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=120)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=160)])
    phone = StringField('Phone', validators=[DataRequired(), Length(min=7, max=30)])
    role = StringField('Role', validators=[DataRequired(), Length(max=30)])
    password = PasswordField('Password', validators=[Length(min=6, max=128)])
    submit = SubmitField('Save User')


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated or not current_user.is_active or current_user.role not in roles:
                from flask import abort
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    form = LoginForm()
    if form.validate_on_submit():
        identity = form.identity.data.strip().lower()
        user = User.query.filter(func.lower(User.email) == identity).first()
        if user and user.is_active and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            flash('Welcome back!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page if next_page and next_page.startswith('/') else url_for('dashboard.index'))
        flash('Invalid login credentials or inactive account.', 'danger')
    return render_template('login.html', form=form)


@bp.post('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


@bp.route('/users')
@roles_required('ADMIN')
def users():
    q = request.args.get('q', '').strip()
    query = User.query
    if q:
        like = f'%{q}%'
        query = query.filter(or_(User.name.ilike(like), User.email.ilike(like), User.role.ilike(like)))
    users = query.order_by(User.created_at.desc()).all()
    return render_template('users/list.html', users=users, q=q)


@bp.route('/users/add', methods=['GET', 'POST'])
@roles_required('ADMIN')
def add_user():
    form = UserForm()
    if form.validate_on_submit():
        role = form.role.data.strip().upper()
        if role not in {'ADMIN', 'SECURITY', 'RECEPTIONIST'}:
            flash('Role must be ADMIN, SECURITY, or RECEPTIONIST.', 'danger')
        elif not form.password.data:
            flash('Password is required when creating a user.', 'danger')
        elif User.query.filter(func.lower(User.email) == form.email.data.strip().lower()).first():
            flash('A user with that email already exists.', 'danger')
        else:
            user = User(name=form.name.data.strip(), email=form.email.data.strip().lower(), phone=form.phone.data.strip(), role=role)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            flash('User created successfully.', 'success')
            return redirect(url_for('auth.users'))
    return render_template('users/form.html', form=form, title='Add User')


@bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@roles_required('ADMIN')
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    form = UserForm(obj=user)
    if request.method == 'GET':
        form.role.data = user.role
    if form.validate_on_submit():
        role = form.role.data.strip().upper()
        if role not in {'ADMIN', 'SECURITY', 'RECEPTIONIST'}:
            flash('Role must be ADMIN, SECURITY, or RECEPTIONIST.', 'danger')
        elif user.id == current_user.id and role != 'ADMIN':
            flash('You cannot remove your own ADMIN role.', 'danger')
        elif User.query.filter(func.lower(User.email) == form.email.data.strip().lower(), User.id != user.id).first():
            flash('A user with that email already exists.', 'danger')
        else:
            user.name = form.name.data.strip()
            user.email = form.email.data.strip().lower()
            user.phone = form.phone.data.strip()
            user.role = role
            if form.password.data:
                user.set_password(form.password.data)
            db.session.commit()
            flash('User updated successfully.', 'success')
            return redirect(url_for('auth.users'))
    return render_template('users/form.html', form=form, title='Edit User', user=user)


@bp.post('/users/<int:user_id>/toggle')
@roles_required('ADMIN')
def toggle_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot deactivate your own account.', 'warning')
    else:
        user.is_active = not user.is_active
        db.session.commit()
        flash(f"User {'activated' if user.is_active else 'deactivated'}.", 'success')
    return redirect(url_for('auth.users'))


@bp.post('/users/<int:user_id>/reset-password')
@roles_required('ADMIN')
def reset_password(user_id):
    user = User.query.get_or_404(user_id)
    password = request.form.get('password', '')
    if len(password) < 6:
        flash('Password must be at least 6 characters.', 'danger')
    else:
        user.set_password(password)
        db.session.commit()
        flash('Password reset successfully.', 'success')
    return redirect(url_for('auth.users'))


@bp.get('/settings')
@login_required
def settings():
    return render_template('users/settings.html')
