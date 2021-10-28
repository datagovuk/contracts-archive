contracts-archive
=================

This repository contains the source for https://data.gov.uk/data/contracts-finder-archive

It's a little Flask application which uses sqlite and Elasticsearch to provide
a search interface for historical government contracts. Contract files are served
from the filesystem (in AWS, via a mounted EBS volume).

Infrastructure
--------------

#### AWS 

Historically, this application ran on a single AWS EC2 instance.

The sqlite file was simply a file on disk, and the instance used a locally running elasticsearch.

Contract files were stored on an EBS volume, which was attached to the instance. `contracts-archive/instance/documents` was symlinked to `/datadrive/files` which
was the mount point for the volume.

#### GOV.UK PaaS

The application would be significantly easier to maintain on GOV.UK PaaS.

To make this work properly we would need to:

- Move the contract files to AWS S3 (and either load them using S3FS, or make S3 API calls directly)
- Migrate the sqlite database to GOV.UK PaaS' postgres service (e.g. using https://pgloader.io/)
- Create a GOV.UK PaaS elasticsearch service and populate the search indexes from the database

The application should run fine using the python buildpack, which supports Flask.
