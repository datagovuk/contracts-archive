from flask import (Flask, abort, send_from_directory,
                   render_template, request, url_for,
                   Markup, redirect, make_response)
from flask.ext.sqlalchemy import SQLAlchemy
from reverse_proxied import ReverseProxied
import os
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ConnectionError
from elasticsearch_dsl import Search
from elasticsearch_dsl.query import QueryString, MatchAll
from elasticsearch_dsl.filter import F
import urlparse
import json

from regions import regions_mapping

app = Flask(__name__)
app.wsgi_app = ReverseProxied(app.wsgi_app)
app.config.from_envvar('SETTINGS')
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

def make_query(query, filters, page):
    try:
        client = Elasticsearch()
        s = Search(client, index=app.config['INDEX'])

        if query:
            s = s.query(QueryString(query=escape_query(query))).sort("_score")
        else:
            s = s.query(MatchAll()).sort("id")

        s.aggs.bucket('global', 'global', None)
        s.aggs['global'].bucket('buying_org',
                                'terms',
                                field='buying_org.raw',
                                size=0,
                                order={'_term': 'asc'})
        s.aggs['global'].bucket('business_name',
                                'terms',
                                field='business_name.raw',
                                size=0,
                                order={'_term': 'asc'})

        start = (page - 1) * 20
        end = start + 20
        s = s[start:end]

        if filters:
            #s = s.post_filter('bool', must=filters)
            s = s.filter('bool', must=filters)

        #print json.dumps(s.to_dict(), indent=2)

        result = s.execute()
        return result
    except ConnectionError, ex:
        return None

class SearchPaginator(object):
    def __init__(self, result, page):
        self.contracts = []
        self.total_records = 0
        self.total_pages = 1
        self.page = page

        if result:
            self.total_records = result.hits.total

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

    filters = []

    buying_org = request.args.get('buying_org')
    if buying_org:
        filters.append(F('term', **{'buying_org.raw': buying_org}))

    business_name = request.args.get('business_name')
    if business_name:
        filters.append(F('term', **{'business_name.raw': business_name}))

    region = request.args.get('region')
    if region:
        filters.append(F('term', **{'location_path.tree': regions_mapping[region]}))

    try:
        min_value = request.args.get('min_value')
        if min_value != '' and min_value is not None:
            filters.append(F('range', min_value={'gte': float(min_value)}))
    except ValueError:
        errors.append('Error: parsing Minimum Contract Value')

    try:
        max_value = request.args.get('max_value')
        if max_value != '' and max_value is not None:
            filters.append(F('range', max_value={'lte': float(max_value)}))
    except ValueError:
        errors.append('Error: parsing Maximum Contract Value')

    result = make_query(query, filters, page)
    if result is None:
        errors.append('Server Error: Unable to perform search')
    pagination = SearchPaginator(result, page)

    facets = {}

    facets['region'] = {'buckets': [{'key': val} for val in regions_mapping.keys()]}

    for name, facet in result.aggregations['global'].items():
        if name in ['doc_count']:
            continue

        facets[name] = facet

    parameters = dict(request.args.items())

    prevlink = None
    if pagination.has_prev:
        parameters['page'] = page - 1
        prevlink = url_for('search', **parameters)

    nextlink = None
    if pagination.has_next:
        parameters['page'] = page + 1
        nextlink = url_for('search', **parameters)

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

@app.template_filter('sort_bucket')
def sort_bucket(bucket):
    """
    Sort buckets alphabetically

    Aggregation is sorted by _term, but because it is a not_analyzed field the
    sorting is case sensitive which is not what we want.

    See this issue:

    https://stackoverflow.com/questions/30135448/elasticsearch-terms-aggregation-order-case-insensitive
    """
    def case_insensitive_cmp(x, y):
        return cmp(
            x['key'].lower().strip(),
            y['key'].lower().strip()
        )
    return sorted(bucket, cmp=case_insensitive_cmp)

if __name__ == '__main__':
    app.debug = True
    app.run()
