import csv
import io
from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, request, Response, make_response
from flask_login import login_required
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from models import db
from models.visitor import Visitor
from models.host import Host
from .auth import roles_required

bp = Blueprint('reports', __name__)


def get_report_query():
    start = request.args.get('start_date', '').strip()
    end = request.args.get('end_date', '').strip()
    status = request.args.get('status', '').strip()
    host_id = request.args.get('host_id', '').strip()
    department = request.args.get('department', '').strip()
    query = Visitor.query.join(Host, Visitor.host_id == Host.id)
    if start:
        try: query = query.filter(Visitor.appointment_date >= datetime.strptime(start, '%Y-%m-%d').date())
        except ValueError: pass
    if end:
        try: query = query.filter(Visitor.appointment_date <= datetime.strptime(end, '%Y-%m-%d').date())
        except ValueError: pass
    if status:
        query = query.filter(Visitor.status == status)
    if host_id:
        try: query = query.filter(Visitor.host_id == int(host_id))
        except ValueError: pass
    if department:
        query = query.filter(Host.department == department)
    return query.order_by(Visitor.appointment_date.desc(), Visitor.appointment_time.desc())


@bp.get('/')
@roles_required('ADMIN')
def index():
    visitors = get_report_query().all()
    hosts = Host.query.order_by(Host.name).all()
    departments = [x[0] for x in db.session.query(Host.department).distinct().order_by(Host.department).all()]
    return render_template('reports/visitors.html', visitors=visitors, hosts=hosts, departments=departments, statuses=['Pending','Approved','Rejected','Checked In','Checked Out','Cancelled'])


@bp.get('/csv')
@roles_required('ADMIN')
def csv_export():
    visitors = get_report_query().all()
    output = io.StringIO(); writer = csv.writer(output)
    writer.writerow(['Visitor ID','Name','Phone','Email','Company','Host','Department','Purpose','Appointment Date','Appointment Time','Check In','Check Out','Duration','Status','Approval','Rejection Reason'])
    for v in visitors:
        writer.writerow([v.visitor_id,v.name,v.phone,v.email or '',v.company or '',v.host.name,v.host.department,v.purpose,v.appointment_date.isoformat(),v.appointment_time.strftime('%H:%M'),v.check_in_time.isoformat() if v.check_in_time else '',v.check_out_time.isoformat() if v.check_out_time else '',v.duration_display(),v.status,v.approval_status,v.rejection_reason or ''])
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    response.headers['Content-Disposition'] = f'attachment; filename=visitor-report-{date.today().isoformat()}.csv'
    return response


@bp.get('/pdf')
@roles_required('ADMIN')
def pdf_export():
    visitors = get_report_query().all()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=20, leftMargin=20, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    story = [Paragraph('Visitor Management System — Visitor Report', styles['Title']), Spacer(1, 10)]
    data = [['Visitor ID','Name','Host','Department','Purpose','Date','Status','Duration']]
    for v in visitors:
        data.append([v.visitor_id, v.name, v.host.name, v.host.department, v.purpose[:24], v.appointment_date.strftime('%d-%m-%Y'), v.status, v.duration_display()])
    table = Table(data, repeatRows=1, colWidths=[65,65,65,65,70,55,60,50])
    table.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#17324d')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),0.25,colors.grey),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),7),('VALIGN',(0,0),(-1,-1),'TOP')
    ]))
    story.append(table)
    doc.build(story)
    buf.seek(0)
    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=f'visitor-report-{date.today().isoformat()}.pdf')
