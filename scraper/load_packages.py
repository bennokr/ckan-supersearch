from __future__ import print_function
from datetime import datetime
from elasticsearch import Elasticsearch, helpers
import pandas as pd
import numpy as np
import feather
import sys
import collections, itertools

def get_package(line, index):
    response = json.loads(line)
    package = response#['result']
    package['_id'] = package['id']
    package['_index'] = index
    package['_type'] = 'package'
    return package

if __name__ == '__main__':
    import argparse, os, json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', default="eurodata", help="index name")
    parser.add_argument('packages', type=argparse.FileType())
    args = parser.parse_args()

    es = Elasticsearch()
    r = helpers.streaming_bulk(es, 
        (get_package(l, args.index) for l in args.packages),
        raise_on_error = False,
        raise_on_exception = False)
    print ('Indexed', sum(1 for _ in r), 'packages')
            