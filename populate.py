from contractfinder import db, Notice, NoticeDetail, NoticeDocument

db.create_all()

notice = Notice(id=1321842,
                ref_no='ABC123',
                length=36)
db.session.add(notice)

details = NoticeDetail(id=1,
                       notice_id=1321842,
                       title='Air Quality Testing',
                       buying_org='MoD',
                       description='This is the description')
db.session.add(details)

file_ids = ['13523544-019b-49e5-9eee-93a6e0a5d551',
            'ad3a309e-3ecf-404e-a8e0-c108a783bded',
            '3a431024-f743-4158-b0f8-1cedafd3c222',]
            #'bea068c5-5637-4ed9-8bb9-f0d48ff4295a',
            #'725401f4-7839-44b6-9365-8a32b0a3362c',
            #'d85a7462-ac38-40ba-9b16-660badf6ee98']
for i, file_id in enumerate(file_ids):
    db.session.add(NoticeDocument(id=i, 
                                  notice_id=1321842,
                                  mimetype='application/pdf',
                                  file_id=file_id,
                                  filename='file{0}.pdf'.format(i),
                                  title='Document {0}'.format(i)))

db.session.commit()

the_notice = Notice.query.filter_by(id=1321842).first()
print(the_notice.details.title)
