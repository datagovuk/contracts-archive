from contractfinder import Notice

import pyes

es = pyes.ES('127.0.0.1:9200')

try:
    #es.indices.delete_index('main-index')
    #es.indices.create_index('main-index')
    pass
except:
    pass

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
    es.index(document, 'main-index', 'notices', notice.id)
