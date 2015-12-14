from flask import Flask
from models import db, Notice
import time
import os

app = Flask(__name__)
app.config.from_envvar('SETTINGS')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'app.db')

db.init_app(app)

def remove_award_address(notice):
    notice.award.details.business_address = ''

with app.app_context():
    for notice_id in ['642561', '473294', '425644']:
        notice = Notice.query.filter_by(id=notice_id).first()
        remove_award_address(notice)
        db.session.commit()
