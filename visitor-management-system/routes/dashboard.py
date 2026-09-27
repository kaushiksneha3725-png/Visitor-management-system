from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, jsonify, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import func
from models import db
from models.visitor import Visitor
from models.host import Host
from models.notification import Notification

bp = Blueprint('dashboard', __name__)


def dashboard_stats():
    today = date.today()
    total = Visitor.query.count()
    today_visitors = Visitor.query.filter(Visitor.appointment_date == today).count()
    currently_inside = Visitor.query.filter(Visitor.status == 'Checked In').count()
    checked_out_today = Visitor.query.filter(Visitor.check_out_time >= datetime.combine(today, datetime.min.time()), Visitor.check_out_time < datetime.combine(today + timedelta(days=1), datetime.min.time())).count()
    pending = Visitor.query.filter(Visitor.approval_status == 'Pending').count()
    hosts = Host.query.filter_by(is_active=True).count()
    return total, today_visitors, currently_inside, checked_out_today, pending, hosts


@bp.get('/')
@login_required
def index():
    total, today_visitors, currently_inside, checked_out_today, pending, hosts = dashboard_stats()
    start_day = date.today() - timedelta(days=6)
    daily = []
    for i in range(7):
        d = start_day + timedelta(days=i)
        count = Visitor.query.filter(Visitor.appointment_date == d).count()
        daily.append({'label': d.strftime('%d %b'), 'count': count})

    purpose_rows = db.session.query(Visitor.purpose, func.count(Visitor.id)).group_by(Visitor.purpose).order_by(func.count(Visitor.id).desc()).limit(8).all()
    dept_rows = db.session.query(Host.department, func.count(Visitor.id)).join(Visitor, Visitor.host_id == Host.id).group_by(Host.department).order_by(func.count(Visitor.id).desc()).limit(8).all()
    checked_in_count = Visitor.query.filter(Visitor.check_in_time.isnot(None), Visitor.check_out_time.is_(None)).count()
    checked_out_count = Visitor.query.filter(Visitor.check_out_time.isnot(None)).count()

    unread = Notification.query.filter_by(recipient=current_user.email, is_read=False).count()
    return render_template(
        'dashboard.html',
        stats={'total': total, 'today': today_visitors, 'inside': currently_inside, 'checkout': checked_out_today, 'pending': pending, 'hosts': hosts},
        daily=daily,
        purposes=[{'label': p or 'Other', 'count': c} for p, c in purpose_rows],
        departments=[{'label': d or 'Other', 'count': c} for d, c in dept_rows],
        movement={'checked_in': checked_in_count, 'checked_out': checked_out_count},
        unread_count=unread,
    )


@bp.get('/api/dashboard-stats')
@login_required
def api_dashboard_stats():
    total, today_visitors, currently_inside, checked_out_today, pending, hosts = dashboard_stats()
    return jsonify({'total': total, 'today': today_visitors, 'inside': currently_inside, 'checkout': checked_out_today, 'pending': pending, 'hosts': hosts})


@bp.get('/live-visitors')
@login_required
def live_visitors():
    visitors = Visitor.query.filter_by(status='Checked In').order_by(Visitor.check_in_time.desc()).all()
    return render_template('visitors/live.html', visitors=visitors)


@bp.get('/api/live-visitors')
@login_required
def api_live_visitors():
    visitors = Visitor.query.filter_by(status='Checked In').order_by(Visitor.check_in_time.desc()).all()
    return jsonify([
        {
            'visitor_id': v.visitor_id,
            'name': v.name,
            'host': v.host.name,
            'purpose': v.purpose,
            'check_in_time': v.check_in_time.strftime('%d %b %Y, %I:%M %p') if v.check_in_time else '',
            'duration': v.duration_display(),
            'status': v.status,
            'details_url': f'/visitors/{v.id}',
            'checkout_url': f'/visitors/{v.id}/checkout',
        }
        for v in visitors
    ])


@bp.get('/appointments')
@login_required
def appointments():
    return redirect(url_for('visitors.index', date=date.today().isoformat()))
