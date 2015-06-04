from flask import (Flask, abort, send_from_directory,
                   render_template, request, url_for,
                   Markup, redirect)
from flask.ext.sqlalchemy import SQLAlchemy
import os
import pyes
import urlparse
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/test.db'
db = SQLAlchemy(app)

class Notice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ref_no = db.Column(db.Text)
    length = db.Column(db.Integer)
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

    @property
    def details(self):
        # Quick fix - show details of first language (usually English)
        return self.all_details.order_by('language_id').first()

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
    parent_id = db.Column(db.Integer)

class Award(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    notice_id = db.Column(db.Integer, db.ForeignKey('notice.id'))
    notice = db.relationship('Notice',
                    backref=db.backref('award', uselist=False))

class AwardDetail(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    award_id = db.Column(db.Integer, db.ForeignKey('award.id'))
    award = db.relationship('Award',
                    backref=db.backref('details', uselist=False))
    business_name = db.Column(db.Text)
    business_address = db.Column(db.Text)

class SearchPaginator(object):
    def __init__(self, query, page):
        self.errors = []
        self.contracts = []
        self.total_records = 0
        self.total_pages = 0
        self.page = page

        try:
            es = pyes.ES('127.0.0.1:9200')
            if query:
                q = pyes.query.QueryStringQuery(query)
            else:
                q = pyes.query.MatchAllQuery()
            search_result = es.search(q, size=20, start=page-1)

            self.total_records = search_result.total

            for notice in search_result:
                self.contracts.append(Notice.query.get(notice['id']))
        except pyes.exceptions.NoServerAvailable:
            self.errors.append("Server Error: Unable to perform search")

        if self.total_records:
            self.total_pages = self.total_records / 20
            if self.total_records % 20:
                self.total_pages += 1

    @property
    def has_prev(self):
        return self.page > 1

    @property
    def has_next(self):
        return self.page < self.total_pages

    @property
    def items(self):
        return self.contracts

    @property
    def pages(self):
        return self.total_pages

    @property
    def total(self):
        return self.total_records

@app.route('/')
def front_page():
    return render_template('front.html')

@app.route('/contracts/')
def contracts():
    page = request.args.get('page', 1, type=int)
    pagination = Notice.query.paginate(page, 20, error_out=False)

    prevlink = None
    if pagination.has_prev:
        prevlink = url_for('contracts', page=page-1, _external=True)

    nextlink = None
    if pagination.has_next:
        nextlink = url_for('contracts', page=page+1, _external=True)

    return render_template('contracts.html',
                           contracts=pagination.items,
                           prevlink=prevlink,
                           nextlink=nextlink,
                           page=page,
                           total_pages=pagination.pages)

@app.route('/contract/<int:notice_id>/')
def contract(notice_id):
    contract = Notice.query.filter_by(id=notice_id).first_or_404()
    return render_template('contract.html', contract=contract)

@app.route('/search/')
def search():
    query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)

    pagination = SearchPaginator(query, page)

    prevlink = None
    if pagination.has_prev:
        prevlink = url_for('search', page=page-1, q=query, _external=True)

    nextlink = None
    if pagination.has_next:
        nextlink = url_for('search', page=page+1, q=query, _external=True)

    return render_template('contracts.html',
                           contracts=pagination.items,
                           query=query,
                           prevlink=prevlink,
                           nextlink=nextlink,
                           page=page,
                           total_pages=pagination.pages,
                           total=pagination.total,
                           errors=pagination.errors)

@app.route('/download/<int:notice_id>/<file_id>')
def download(notice_id, file_id):
    notice_id = str(notice_id)

    download_file = NoticeDocument.query.filter_by(file_id=file_id).first_or_404()
    
    directory = os.path.abspath(os.path.join(app.instance_path, 'documents', notice_id))
    filename = download_file.filename
    mimetype = download_file.mimetype

    return send_from_directory(directory,
                               file_id,
                               mimetype=mimetype,
                               as_attachment=True,
                               attachment_filename=filename)

@app.template_filter('currency')
def currency(s):
    return Markup('&pound;{:,.2f}'.format(s).replace('.00', ''))

@app.template_filter('external_link')
def external_link(s):
    """
    If the link has no protocol add http://

    If the link is an email address add mailto:
    """
    if '@' in s:
        return 'mailto:%s' % s
    else:
        return urlparse.urljoin('http://', s)

if __name__ == '__main__':
    app.debug = True
    app.run()
