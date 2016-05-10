from flask.ext.sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Notice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ref_no = db.Column(db.Text)
    length = db.Column(db.Integer)
    length_type = db.Column(db.Text)
    location_code = db.Column(db.Text, db.ForeignKey('region.code'))
    location = db.relationship('Region',
                    backref=db.backref('all_notices', lazy='dynamic'))
    is_framework = db.Column(db.Integer)
    is_sme_friendly = db.Column(db.Integer)
    is_voluntary_friendly = db.Column(db.Integer)
    date_awarded = db.Column(db.DateTime)
    date_created = db.Column(db.DateTime)
    deadline_date = db.Column(db.DateTime)
    min_value = db.Column(db.Integer)
    max_value = db.Column(db.Integer)
    status = db.Column(db.Integer)
    type_id = db.Column(db.Integer)

    @property
    def details(self):
        # Quick fix - show details of first language (usually English)
        return self.all_details.order_by('language_id').first()
    @property
    def type(self):
        if self.type_id == 33:
            return 'Pipeline'
        else:
            return 'Tender or contract'
    

class NoticeDetail(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    notice_id = db.Column(db.Integer, db.ForeignKey('notice.id'))
    notice = db.relationship('Notice',
                    backref=db.backref('all_details', lazy='dynamic'))
    title = db.Column(db.Text)
    description = db.Column(db.Text)
    buying_org = db.Column(db.Text)
    language_id = db.Column(db.Integer)
    contact_email = db.Column(db.Text)
    location_text = db.Column(db.Text)
    supplier_instructions = db.Column(db.Text)
    deadline_for = db.Column(db.Text)
    contact_web = db.Column(db.Text)
    contact_fax = db.Column(db.Text)
    contact_name = db.Column(db.Text)
    contact_tel = db.Column(db.Text)
    contact_extension = db.Column(db.Text)
    contact_address = db.Column(db.Text)

class NoticeDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    notice_id = db.Column(db.Integer, db.ForeignKey('notice.id'))
    notice = db.relationship('Notice',
                    backref=db.backref('documents', lazy='dynamic'))
    mimetype = db.Column(db.Text)
    file_id = db.Column(db.String(36))
    filename = db.Column(db.Text)
    title = db.Column(db.Text)

class Region(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text)
    code = db.Column(db.Text)
    parent_id = db.Column(db.Integer, db.ForeignKey('region.id'))
    parent_region = db.relationship('Region', remote_side='Region.id')

    def location_path(self):
        parts = [self.name]
        parent = self.parent_region
        while parent is not None:
            parts.insert(0, parent.name)
            parent = parent.parent_region

        return '/' + '/'.join(parts)

class Award(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    notice_id = db.Column(db.Integer, db.ForeignKey('notice.id'))
    notice = db.relationship('Notice',
                    backref=db.backref('awards'))

class AwardDetail(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    award_id = db.Column(db.Integer, db.ForeignKey('award.id'))
    award = db.relationship('Award',
                    backref=db.backref('details', uselist=False))
    business_name = db.Column(db.Text)
    business_address = db.Column(db.Text)

