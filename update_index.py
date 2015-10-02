from flask import Flask
from contractfinder import Notice

app = Flask(__name__)
app.config.from_envvar('SETTINGS')

INDEX = app.config['INDEX']

import pyes

es = pyes.ES('127.0.0.1:9200')

try:
    #es.indices.delete_index(INDEX)
    #es.indices.create_index(INDEX)
    pass
except:
    pass

mapping = {
    'location_name': {
        'type': 'string',
        'fields': {
            'raw' : {
                'type': 'string',
                'index': 'not_analyzed'
            }
        }
    },
    'buying_org': {
        'type': 'string',
        'fields': {
            'raw' : {
                'type': 'string',
                'index': 'not_analyzed'
            }
        }
    },
    'business_name': {
        'type': 'string',
        'fields': {
            'raw' : {
                'type': 'string',
                'index': 'not_analyzed'
            }
        }
    },
}

es.indices.put_mapping('notices', {'properties': mapping}, [INDEX])

for notice in Notice.query.all():
    document = {}
    document['id'] = notice.id
    document['ref_no'] = notice.ref_no
    document['title'] = notice.details.title
    document['description'] = notice.details.description
    document['buying_org'] = notice.details.buying_org
    document['contact_address'] = notice.details.contact_address
    if notice.location:
        document['location_name'] = notice.location.name
    if notice.award and notice.award.details:
        document['business_name'] = notice.award.details.business_name
        document['business_address'] = notice.award.details.business_address
    es.index(document, INDEX, 'notices', notice.id)
