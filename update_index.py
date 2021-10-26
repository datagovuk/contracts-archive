from flask import Flask
from models import db, Notice
import time
import os

app = Flask(__name__)
app.config.from_envvar('SETTINGS')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'app.db')

db.init_app(app)

INDEX = app.config['INDEX']

import pyes

es = pyes.ES('127.0.0.1:9200')

try:
    #es.indices.delete_index(INDEX)
    es.indices.create_index(INDEX)
    time.sleep(5)
    print("Created Index", INDEX)
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
    'location_path': {
        'type': 'string',
        'index': 'not_analyzed',
        'fields': {
            'tree': {
                'type': 'string',
                'analyzer': 'paths'
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

settings = {
    'analysis': {
        'analyzer': {
            'paths': {
                'tokenizer': 'path_hierarchy'
            }
        }
    }
}

es.indices.close_index(INDEX)
es.indices.update_settings(INDEX, settings)
es.indices.open_index(INDEX)

es.indices.put_mapping('notices', {'properties': mapping}, [INDEX])

with app.app_context():
    for notice in Notice.query.all():
        document = {}
        document['id'] = notice.id
        document['ref_no'] = notice.ref_no
        document['title'] = notice.details.title
        document['description'] = notice.details.description
        document['buying_org'] = notice.details.buying_org
        document['contact_address'] = notice.details.contact_address
        document['min_value'] = notice.min_value
        document['max_value'] = notice.max_value
        if notice.location:
            document['location_name'] = notice.location.name
            location_path = notice.location.location_path()
            document['location_path'] = location_path[len('/European Union'):]
        else:
            document['location_path'] = '/United Kingdom'
        if notice.awards:
            document['business_name'] = []
            document['business_address'] = []
            for award in notice.awards:
                if not award.details or not award.details.business_name:
                    continue
                document['business_name'].append(award.details.business_name)
                document['business_address'].append(award.details.business_address)
        if notice.date_awarded:
            document['date_awarded'] = notice.date_awarded.strftime('%Y-%m-%d')
        if notice.date_created:
            document['date_created'] = notice.date_created.strftime('%Y-%m-%d')
        if notice.deadline_date:
            document['deadline_date'] = notice.deadline_date.strftime('%Y-%m-%d')
        es.index(document, INDEX, 'notices', notice.id)
