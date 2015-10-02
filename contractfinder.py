from flask import (Flask, abort, send_from_directory,
                   render_template, request, url_for,
                   Markup, redirect, make_response)
from flask.ext.sqlalchemy import SQLAlchemy
from reverse_proxied import ReverseProxied
import os
import pyes
import urlparse
import json

app = Flask(__name__)
app.wsgi_app = ReverseProxied(app.wsgi_app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'app.db')
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

def escape_query(query):
    # / denotes the start of a Lucene regex so needs escaping
    return query.replace('/', '\\/')

def make_query(query, page):
    try:
        es = pyes.ES('127.0.0.1:9200')
        if query:
            q = pyes.query.QueryStringQuery(escape_query(query))
            sort = "_score"
        else:
            q = pyes.query.MatchAllQuery()
            sort = "id"

        buying_org = pyes.aggs.TermsAgg('buying_org', field="buying_org.raw", size=0)
        location_name = pyes.aggs.TermsAgg('location_name', field="location_name.raw", size=0)
        business_name = pyes.aggs.TermsAgg('business_name', field="business_name.raw", size=0)

        start = (page - 1) * 20
        search_query = pyes.Search(q, size=20, start=start, sort=sort)
        search_query.agg.add(buying_org)
        search_query.agg.add(location_name)
        search_query.agg.add(business_name)
        print json.dumps(search_query.serialize(), indent=2)

        result = es.search(search_query, 'main-index', 'notices')
        return result
    except pyes.exceptions.NoServerAvailable, ex:
        return None

class SearchPaginator(object):
    def __init__(self, result, page):
        self.contracts = []
        self.total_records = 0
        self.total_pages = 1
        self.page = page

        if result:
            self.total_records = result.total

            for notice in result:
                self.contracts.append(Notice.query.get(notice['id']))

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

@app.route('/robots.txt')
def robots():
    txt = render_template('robots.html')
    response = make_response(txt)
    response.headers["Content-Type"] = "text/plain"
    return response

@app.route('/')
def front_page():
    return render_template('front.html')

@app.route('/contract/<int:notice_id>/')
def contract(notice_id):
    contract = Notice.query.filter_by(id=notice_id).first_or_404()
    return render_template('contract.html', contract=contract)

@app.route('/contracts/', endpoint='contracts', methods=['GET', 'POST'])
@app.route('/search/', endpoint='search', methods=['GET', 'POST'])
def search():
    errors = []
    query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)

    result = make_query(query, page)
    if result is None:
        errors.append('Server Error: Unable to perform search')
    pagination = SearchPaginator(result, page)

    if result:
        facets = result.aggs
    else:
        facets = {}

    prevlink = None
    if pagination.has_prev:
        prevlink = url_for('search', page=page-1, q=query)

    nextlink = None
    if pagination.has_next:
        nextlink = url_for('search', page=page+1, q=query)

    return render_template('contracts.html',
                           contracts=pagination.items,
                           query=query,
                           prevlink=prevlink,
                           nextlink=nextlink,
                           page=page,
                           total_pages=pagination.pages,
                           total=pagination.total,
                           errors=errors,
                           facets=facets)

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

@app.route('/data-feeds/')
def data_feeds():
    return render_template('data-feeds.html')

@app.template_filter('currency')
def currency(s):
    return Markup('&pound;{:,.2f}'.format(s).replace('.00', ''))

@app.template_filter('month')
def month(i):
    import calendar
    return calendar.month_abbr[i]

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
