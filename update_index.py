from contractfinder import Notice

import pyes

es = pyes.ES('127.0.0.1:9200')

try:
    es.indices.delete_index('main-index')
    es.indices.create_index('main-index')
except:
    pass

for notice in Notice.query.all():
    document = {}
    document['id'] = notice.id
    document['title'] = notice.details.title
    document['description'] = notice.details.description
    es.index(document, 'main-index', 'notices', notice.id)
