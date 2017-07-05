from flask import (Flask, abort, send_from_directory,
                   render_template, request, url_for,
                   Markup, redirect, make_response)
from reverse_proxied import ReverseProxied
from models import db, Notice, NoticeDocument
import os
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ConnectionError
from elasticsearch_dsl import Search
from elasticsearch_dsl.query import QueryString, MatchAll
from elasticsearch_dsl.filter import F
import urlparse
import json
import collections

from util import get_redirect_target

from regions import regions_mapping

# For nl2br
import re
from jinja2 import evalcontextfilter, Markup, escape
_paragraph_re = re.compile(r'(?:\r\n|\r|\n){2,}')

app = Flask(__name__)
app.wsgi_app = ReverseProxied(app.wsgi_app)
app.config.from_envvar('SETTINGS')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'app.db')
db.init_app(app)

def escape_query(query):
    # / denotes the start of a Lucene regex so needs escaping
    return query.replace('/', '\\/')

SORT_BY = collections.OrderedDict()
SORT_BY['relevance'] = {'title': 'Relevance', 'value': '_score'}
SORT_BY['min_value'] = {'title': 'Minimum Contract Value Ascending', 'value': 'min_value'}
SORT_BY['min_value_desc'] = {'title': 'Minimum Contract Value Descending', 'value': '-min_value'}
SORT_BY['max_value'] = {'title': 'Maximum Contract Value Ascending', 'value': 'max_value'}
SORT_BY['max_value_desc'] = {'title': 'Maximum Contract Value Descending', 'value': '-max_value'}
SORT_BY['pub_date'] = {'title': 'Publication Date Ascending', 'value': 'date_created'}
SORT_BY['pub_date_desc'] = {'title': 'Publication Date Descending', 'value': '-date_created'}
SORT_BY['deadline_date'] = {'title': 'Deadline Date Ascending', 'value': 'deadline_date'}
SORT_BY['deadline_date_desc'] = {'title': 'Deadline Date Descending', 'value': '-deadline_date'}
SORT_BY['award_date'] = {'title': 'Awarded Date Ascending', 'value': 'date_awarded'}
SORT_BY['award_date_desc'] = {'title': 'Awarded Date Descending', 'value': '-date_awarded'}

DEFAULT_SORT_BY = 'pub_date_desc'

def make_query(query, filters, page, sort_by):
    try:
        client = Elasticsearch()
        s = Search(client, index=app.config['INDEX'])

        if query:
            s = s.query(QueryString(query=escape_query(query)))
            if not sort_by:
                sort_by = "relevance"
        else:
            s = s.query(MatchAll())
            if not sort_by:
                sort_by = DEFAULT_SORT_BY

        s = s.sort(SORT_BY.get(sort_by, DEFAULT_SORT_BY)['value'])

        start = (page - 1) * 20
        end = start + 20
        s = s[start:end]

        if filters:
            s = s.filter('bool', must=filters)

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
    back = get_redirect_target() or url_for('search')
    return render_template('contract.html', contract=contract, back=back)

@app.route('/contracts/', endpoint='contracts', methods=['GET', 'POST'])
@app.route('/search/', endpoint='search', methods=['GET', 'POST'])
def search():
    errors = []
    query = request.args.get('query', '') or request.args.get('q', '')
    page = request.args.get('page', 1, type=int)

    sort_by = request.args.get('sort_by')

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

    # Date Created
    date_created_range = {}
    date_created_min = request.args.get('publication_date_from')
    if date_created_min:
        date_created_range['gte'] = date_created_min

    date_created_max = request.args.get('publication_date_to')
    if date_created_max:
        date_created_range['lte'] = date_created_max

    if date_created_range:
        filters.append(F('range', date_created=date_created_range))

    # Deadline Date
    deadline_date_range = {}
    deadline_date_min = request.args.get('deadline_date_from')
    if deadline_date_min:
        deadline_date_range['gte'] = deadline_date_min

    deadline_date_max = request.args.get('deadline_date_from')
    if deadline_date_max:
        deadline_date_range['lte'] = deadline_date_max

    if deadline_date_range:
        filters.append(F('range', deadline_date=deadline_date_range))

    # Date Awarded
    date_awarded_range = {}
    date_awarded_min = request.args.get('award_date_from')
    if date_awarded_min:
        date_awarded_range['gte'] = date_awarded_min

    date_awarded_max = request.args.get('award_date_to')
    if date_awarded_max:
        date_awarded_range['lte'] = date_awarded_max

    if date_awarded_range:
        filters.append(F('range', date_awarded=date_awarded_range))


    result = make_query(query, filters, page, sort_by)
    if result is None:
        errors.append('Server Error: Unable to perform search')
    pagination = SearchPaginator(result, page)

    facets = {}

    facets['region'] = {'title': 'Region',
                        'buckets': [{'key': val} for val in regions_mapping.keys()]}

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
                           facets=facets,
                           sort=SORT_BY)

@app.route('/download/<int:notice_id>/<file_id>')
def download(notice_id, file_id):
    notice_id = str(notice_id)

    download_file = NoticeDocument.query.filter_by(file_id=file_id).first_or_404()

    directory = os.path.abspath(os.path.join(app.instance_path, 'documents', notice_id))
    filename = download_file.filename.encode('latin1', 'ignore')
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

@app.template_filter()
@evalcontextfilter
def nl2br(eval_ctx, value):
    result = u'\n\n'.join(u'<p>%s</p>' % p.replace('\n', '<br>\n') \
        for p in _paragraph_re.split(escape(value)))
    if eval_ctx.autoescape:
        result = Markup(result)
    return result


if __name__ == '__main__':
    app.debug = True
    app.run()
