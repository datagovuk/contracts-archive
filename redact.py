'''Tool for redacting the Contracts Archive'''

import argparse
import re
import os.path

contract_url = 'https://data.gov.uk/data/contracts-finder-archive/contract/'
document_url = 'https://data.gov.uk/data/contracts-finder-archive/download/%s/%s'

def redact_documents_command(args):
    contracts_and_documents = []

    if args.filename:
        contracts_and_documents += list(
            extract_contracts_and_documents_from_file(args.filename))
        if not contracts_and_documents:
            raise Exception('No contracts provided in file %s', args.filename)

    if not contracts_and_documents:
        raise Exception('No contracts provided')
    print '%s contracts / documents provided' % len(contracts_and_documents)

    errors = []

    documents = resolve_contracts_to_documents(contracts_and_documents,
                                               errors,
                                               args.document_path)

    print '%s documents' % len(documents)

    print_document_urls(documents)

    delete_documents(documents, errors,
                     document_path=args.document_path,
                     write=args.write)

    if errors:
        print '\nNB There were %s errors:' % len(errors)
        for err in errors:
            print err
        print '\nFinished with errors'
    else:
        print 'Finished'

def extract_contracts_and_documents_from_file(filename, verbose=False):
    with open(filename, 'rb') as f:
        for line in f.readlines():
            line = line.strip()
            if not line:
                continue
            if verbose:
                print line
            contract, document = parse_contract_and_document(line)
            if not contract:
                raise Exception('ERROR: Could not parse a contract on this '
                                'line: %r', line)
            if verbose:
                print '-> %s%s/%s\n' % (contract_url, contract, document or '')
            yield contract, document


def resolve_contracts_to_documents(contracts_and_documents, errors, document_path):
    '''Given a list of contracts and documents, for each contract it replaces
    it in the list with all of its documents.

    Only looks at files on disk, not the db.'''
    documents = []
    for contract, document in contracts_and_documents:
        if document:
            document_filename = '%s%s/%s' % (document_path, contract, document)
            if not os.path.exists(document_filename):
                err = 'No file %s' % document_filename
                print 'ERROR: ', err
                errors.append(err)
            documents.append((contract, document))
            continue
        else:
            doc_dir = '%s%s/' % (document_path, contract)
            docs = os.listdir(doc_dir)
            if not docs:
                err = 'No documents for contract: %s' % doc_dir
                print 'ERROR: ', err
                errors.append(err)
            for document in docs:
                document_filename = '%s%s/%s' % (document_path, contract,
                                                 document)
                assert os.path.exists(document_filename), \
                    'No file %s after all' % document_filename
                documents.append((contract, document))
    return documents

def parse_contract_and_document(line):
    match = re.search(r'contract\/(?P<contract>\d+)\/(?P<document>\d+)?',
                      line)
    if match:
        return match.groups()
    return None, None

def print_document_urls(documents):
    print '\nDocument urls (%s) (to tell Google to stop caching):' \
        % len(documents)
    for doc in documents:
        print document_url % doc

def delete_documents(documents, errors, document_path, write=False):
    print '\nDeleting %s documents' % len(documents) \
        + (' (not really) ' if not write else '') + \
        ':'
    for doc in documents:
        document_filename = '%s%s/%s' % (document_path, doc[0], doc[1])
        print document_filename
        if write:
            try:
                os.remove(document_filename)
            except OSError, e:
                err = 'Could not delete %s: %s' % (document_filename, e)
                print 'ERROR: ', err
                errors.append(err)

# from flask import Flask
# from models import db, Notice
# import time
# import os

# app = Flask(__name__)
# app.config.from_envvar('SETTINGS')
# app.config['SQLALCHEMY_DATABASE_URI'] = \
#     'sqlite:///' + os.path.join(app.instance_path, 'app.db')

# db.init_app(app)

# def remove_award_address(notice):
#     notice.award.details.business_address = ''

# with app.app_context():
#     for notice_id in ['642561', '473294', '425644']:
#         notice = Notice.query.filter_by(id=notice_id).first()
#         remove_award_address(notice)
#         db.session.commit()

if __name__ == '__main__':
    parser_main = argparse.ArgumentParser(description=__doc__)
    parser_main.add_argument(
        '--document-path', metavar='PATH',
        default='~/src/contracts-finder/instance/documents/',
        help='Path of the document files')
    parser_main.add_argument(
        '-w', '--write', action='store_true',
        help='Write the changes (otherwise it does a harmless trial run)')
    subparsers = parser_main.add_subparsers()

    parser_doc = subparsers.add_parser('document',
                                       help='Documents to be redacted')
    parser_doc.add_argument('-f', '--filename', metavar='FILE',
                            help='file listing documents')
    parser_doc.set_defaults(func=redact_documents_command)

    args = parser_main.parse_args()
    if args.document_path:
        args.document_path = os.path.expanduser(args.document_path)
    args.func(args)

    if not args.write:
        print 'Nothing done. Use --write to do it for real.'
