import argparse
from app import create_app
from models import db
from app import _seed_if_empty

parser = argparse.ArgumentParser(description='Initialize or reset Visitor Management System database.')
parser.add_argument('--reset', action='store_true', help='Drop and recreate all tables, then insert demo seed data.')
args = parser.parse_args()

app = create_app()
with app.app_context():
    if args.reset:
        db.drop_all()
        db.create_all()
        _seed_if_empty()
        print('Database reset and demo data inserted.')
    else:
        db.create_all()
        _seed_if_empty()
        print('Database ready and demo data ensured.')
