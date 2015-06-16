#!/bin/bash

for year in 2011 2012 2013 2014 2015
do
    for month in 01 02 03 04 05 06 07 08 09 10 11 12
    do
        wget "http://www.contractsfinder.businesslink.gov.uk/public_files/Notices/Monthly/notices_${year}_${month}.csv"
        wget "http://www.contractsfinder.businesslink.gov.uk/public_files/Notices/Monthly/notices_${year}_${month}.xml"
    done
done
