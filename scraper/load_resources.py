from __future__ import print_function
from datetime import datetime
from elasticsearch import Elasticsearch, helpers
import pandas as pd
import numpy as np
import feather
import sys
import collections, itertools

if __name__ == '__main__':
    import argparse, os, json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', default="eurodata", help="index name")
    parser.add_argument('--meta', default="{}", help="metadata")
    parser.add_argument('paths', type=argparse.FileType())
    args = parser.parse_args()

    es = Elasticsearch()
    meta = json.loads(args.meta)

    for fpath in args.paths:
        fpath = fpath.strip()
        df = feather.read_dataframe(fpath)
        df = df.where((pd.notnull(df)), None) # convert NaN to None
        
        name = os.path.basename(fpath)
        res = es.index(index=args.index, doc_type='schema', id=name, body={
            'schema': [s.decode('utf8', 'ignore') for s in df.columns],
            'scrape_meta': meta
        })
        try:
            it = ({
                    '_index': args.index,
                    '_type': 'row',
                    '_id': '%s-%s' % (name, i),
                    '_source': {'row':[str(r).decode('utf8') for r in row]}
                } for i,row in df.iterrows())
            print (name, '\t', sum(1 for _ in helpers.streaming_bulk(es, it)))
        except Exception as e:
            print (name, '\t', e, file=sys.stderr)
            