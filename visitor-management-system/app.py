import os
from flask import Flask, render_template
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from models import db
from models.user import User
from models.host import Host
from models.visitor import Visitor, VisitActivity
from models.notification import Notification, BlacklistEntry
from config import Config

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'warning'
csrf = CSRFProtect()


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    if app.config.get('MAIL_SERVER') and app.config.get('MAIL_USERNAME'):
        try:
            from flask_mail import Mail
            Mail(app)
        except Exception:
            app.logger.exception('Flask-Mail could not be initialized; continuing without email.')

    from routes.auth import bp as auth_bp
    from routes.dashboard import bp as dashboard_bp
    from routes.visitors import bp as visitors_bp
    from routes.hosts import bp as hosts_bp
    from routes.notifications import bp as notifications_bp
    from routes.reports import bp as reports_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(visitors_bp, url_prefix='/visitors')
    app.register_blueprint(hosts_bp, url_prefix='/hosts')
    app.register_blueprint(notifications_bp, url_prefix='/notifications')
    app.register_blueprint(reports_bp, url_prefix='/reports')

    @app.context_processor
    def inject_globals():
        from datetime import date, timedelta
        from models.notification import Notification
        from flask_login import current_user
        unread = 0
        try:
            if current_user.is_authenticated:
                unread = Notification.query.filter_by(recipient=current_user.email, is_read=False).count()
        except Exception:
            unread = 0
        today = date.today()
        return {
            'app_name': 'Visitor Management System',
            'unread_count': unread,
            'today': today,
            'now_date': today,
            'week_start': today - timedelta(days=6),
            'month_start': today.replace(day=1),
        }

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except (ValueError, TypeError):
            return None

    @app.errorhandler(403)
    def forbidden(error):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(413)
    def too_large(error):
        from flask import flash, redirect, request, url_for
        flash('Uploaded file is too large. Maximum size is 2 MB.', 'danger')
        return redirect(request.referrer or url_for('dashboard.index'))

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500

    with app.app_context():
        db.create_all()
        _seed_if_empty()

    return app


def _seed_if_empty():
    from werkzeug.security import generate_password_hash
    from datetime import date, time, timedelta, datetime
    if not User.query.filter_by(email='admin@visitor.com').first():
        users = [
            User(name='System Admin', email='admin@visitor.com', password_hash=generate_password_hash('Admin@123'), role='ADMIN', phone='+91 90000 00001'),
            User(name='Security One', email='security1@visitor.com', password_hash=generate_password_hash('Security@123'), role='SECURITY', phone='+91 90000 00002'),
            User(name='Security Two', email='security2@visitor.com', password_hash=generate_password_hash('Security@123'), role='SECURITY', phone='+91 90000 00003'),
            User(name='Reception One', email='reception1@visitor.com', password_hash=generate_password_hash('Reception@123'), role='RECEPTIONIST', phone='+91 90000 00004'),
            User(name='Reception Two', email='reception2@visitor.com', password_hash=generate_password_hash('Reception@123'), role='RECEPTIONIST', phone='+91 90000 00005'),
        ]
        db.session.add_all(users)
        db.session.flush()

    if Host.query.count() == 0:
        departments = [('Administration','Manager'),('Human Resources','HR Manager'),('Information Technology','IT Manager'),('Finance','Finance Manager'),('Operations','Operations Lead'),('Sales','Sales Manager'),('Marketing','Marketing Lead'),('Facilities','Facilities Manager'),('Academics','Professor'),('Security','Security Manager')]
        hosts = []
        for i, (dept, designation) in enumerate(departments, 1):
            hosts.append(Host(name=f'Host Person {i}', email=f'host{i}@visitor.com', phone=f'+91 98{10000000+i:08d}', department=dept, designation=designation))
        db.session.add_all(hosts)
        db.session.flush()

    if Visitor.query.count() == 0 and Host.query.count() >= 10:
        import random
        purpose_choices = ['Meeting','Interview','Delivery','Maintenance','Campus Visit','Vendor Discussion','Document Submission','Consultation']
        first_names = ['Rahul','Priya','Amit','Neha','Rohan','Kavya','Arjun','Meera','Sahil','Ananya','Vivek','Pooja','Nikhil','Riya','Manish','Simran','Karan','Tanya','Dev','Isha']
        today = date.today()
        hosts = Host.query.order_by(Host.id).all()
        for i in range(20):
            appointment_date = today - timedelta(days=(i % 6)) if i < 8 else today + timedelta(days=((i-8) % 7))
            status = 'Checked Out' if i < 5 else ('Checked In' if 5 <= i < 8 else ('Pending' if i < 14 else 'Approved'))
            approval = 'Approved' if status in {'Checked Out','Checked In','Approved'} else 'Pending'
            visitor = Visitor(
                visitor_id=f'VIS-{today.year}-{i+1:05d}', name=f'{first_names[i]} Visitor', phone=f'+91 97{20000000+i:08d}',
                email=f'visitor{i+1}@example.com', company=f'Company {i%5+1}', address='Sample address for demo data', purpose=purpose_choices[i % len(purpose_choices)], host_id=hosts[i % len(hosts)].id,
                id_proof_type=['Aadhaar','PAN','Passport'][i % 3], id_proof_number=f'DEMO{i+1:08d}', appointment_date=appointment_date,
                appointment_time=time(10 + (i % 7), 15), status=status, approval_status=approval
            )
            if status == 'Checked Out':
                visitor.check_in_time = datetime.combine(appointment_date, time(10, 0))
                visitor.check_out_time = datetime.combine(appointment_date, time(12, 30))
            elif status == 'Checked In':
                visitor.check_in_time = datetime.now() - timedelta(minutes=25+i)
            db.session.add(visitor)
            db.session.flush()
            _actor = 'seed@system'
            db.session.add(VisitActivity(visitor_id=visitor.id, action='REGISTERED', description='Seeded demo visitor record.', created_by=_actor))
            if status == 'Checked Out':
                db.session.add(VisitActivity(visitor_id=visitor.id, action='CHECKED_OUT', description='Seeded demo checkout record.', created_by=_actor))
            elif status == 'Checked In':
                db.session.add(VisitActivity(visitor_id=visitor.id, action='CHECKED_IN', description='Seeded demo check-in record.', created_by=_actor))

    db.session.commit()


app = create_app()

if __name__ == '__main__':
    host = os.environ.get('FLASK_HOST', '127.0.0.1')
    port = int(os.environ.get('FLASK_PORT', '5000'))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host=host, port=port, debug=debug)
