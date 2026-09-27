"""Optional integration tests for the Visitor Management System.

Run with: python -m pytest -q tests.py
Requires the packages in requirements.txt.
"""
from datetime import date, time
import io

import pytest

from app import create_app
from models import db
from models.user import User
from models.host import Host
from models.visitor import Visitor, VisitActivity
from models.notification import BlacklistEntry, Notification


@pytest.fixture()
def app(tmp_path):
    database = tmp_path / 'test.db'
    app = create_app({'TESTING': True, 'WTF_CSRF_ENABLED': False, 'SQLALCHEMY_DATABASE_URI': f'sqlite:///{database}'})
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, email, password):
    return client.post('/login', data={'identity': email, 'password': password}, follow_redirects=True)


def test_admin_login_and_dashboard(client):
    response = login(client, 'admin@visitor.com', 'Admin@123')
    assert response.status_code == 200
    assert b'Dashboard' in response.data


def test_invalid_login(client):
    response = login(client, 'admin@visitor.com', 'wrong-password')
    assert b'Invalid login credentials' in response.data


def test_security_cannot_open_reports(client):
    login(client, 'security1@visitor.com', 'Security@123')
    response = client.get('/reports/')
    assert response.status_code == 403


def test_receptionist_approval_and_security_checkin_checkout(client, app):
    login(client, 'reception1@visitor.com', 'Reception@123')
    with app.app_context():
        host = Host.query.first()
        host_id = host.id
    response = client.post('/visitors/add', data={
        'name': 'Test Visitor', 'phone': '+919876543210', 'email': 'test@example.com', 'company': 'Test Co',
        'address': 'Test address', 'host_id': host_id, 'purpose': 'Interview', 'id_proof_type': 'PAN',
        'id_proof_number': 'ABCDE1234F', 'appointment_date': date.today().isoformat(), 'appointment_time': '11:30',
    }, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        visitor = Visitor.query.filter_by(name='Test Visitor').first()
        visitor_id = visitor.id
        assert visitor.status == 'Pending'
    response = client.post(f'/visitors/{visitor_id}/approval', data={'action': 'approve', 'rejection_reason': ''}, follow_redirects=True)
    assert b'Visitor approved' in response.data
    client.post('/logout')
    login(client, 'security1@visitor.com', 'Security@123')
    response = client.post(f'/visitors/{visitor_id}/checkin', follow_redirects=True)
    assert b'Visitor checked in successfully' in response.data
    response = client.post(f'/visitors/{visitor_id}/checkout', follow_redirects=True)
    assert b'Visitor checked out' in response.data
    with app.app_context():
        visitor = db.session.get(Visitor, visitor_id)
        assert visitor.check_in_time is not None and visitor.check_out_time is not None
        assert visitor.status == 'Checked Out'
        assert VisitActivity.query.filter_by(visitor_id=visitor_id).count() >= 3


def test_blacklist_blocks_checkin_for_security(client, app):
    with app.app_context():
        visitor = Visitor.query.filter_by(status='Approved').first()
        entry = BlacklistEntry(name=visitor.name, phone=visitor.phone, reason='Demo restriction', created_by='admin@visitor.com')
        db.session.add(entry); db.session.commit(); visitor_id=visitor.id
    login(client, 'security1@visitor.com', 'Security@123')
    response = client.post(f'/visitors/{visitor_id}/checkin', follow_redirects=True)
    assert b'blacklisted' in response.data
    with app.app_context():
        assert db.session.get(Visitor, visitor_id).status == 'Approved'


def test_csv_and_pdf_export(client):
    login(client, 'admin@visitor.com', 'Admin@123')
    csv_response = client.get('/reports/csv')
    assert csv_response.status_code == 200
    assert b'Visitor ID' in csv_response.data
    pdf_response = client.get('/reports/pdf')
    assert pdf_response.status_code == 200
    assert pdf_response.mimetype == 'application/pdf'
