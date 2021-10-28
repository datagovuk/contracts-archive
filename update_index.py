from flask import Flask
from models import db, Notice
import time
import os
from elasticsearch import Elasticsearch

app = Flask(__name__)
app.config.from_envvar('SETTINGS')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'app.db')

db.init_app(app)

INDEX = app.config['INDEX']

es = Elasticsearch()

try:
    es.indices.delete(index=INDEX)
    es.indices.create(index=INDEX)
    time.sleep(5)
    print("Created Index", INDEX)
    pass
except:
    pass

mapping = {
    'location_name': {
        'type': 'text',
        'fields': {
            'raw' : {
                'type': 'text',
                'index': 'false'
            }
        }
    },
    'location_path': {
        'type': 'text',
        'index': 'false',
        'fields': {
            'tree': {
                'type': 'text',
                'analyzer': 'paths'
            }
        }
    },
    'buying_org': {
        'type': 'text',
        'fields': {
            'raw' : {
                'type': 'text',
                'index': 'false'
            }
        }
    },
    'business_name': {
        'type': 'text',
        'fields': {
            'raw': {
                'type': 'text',
                'index': 'false'
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

es.indices.close(index=INDEX)
es.indices.put_settings(index=INDEX, body=settings)
es.indices.open(index=INDEX)

es.indices.put_mapping(include_type_name=True, doc_type='notices', body={'properties': mapping}, index=INDEX)

with app.app_context():
    for notice in Notice.query.all():
        document = {}
        details = notice.details
        document['id'] = notice.id
        document['ref_no'] = notice.ref_no
        document['title'] = details.title
        document['description'] = details.description
        document['buying_org'] = details.buying_org
        document['contact_address'] = details.contact_address
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

        print("Adding notice: " + details.title)
        es.index(document=document, index=INDEX, doc_type='notices', id=notice.id)
