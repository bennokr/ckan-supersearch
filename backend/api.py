from flask import Flask
from flask_restful import reqparse, Resource, Api
from flask.ext.cors import CORS
import requests
import json
 
import config

app = Flask(__name__)
CORS(app) # required for Cross-origin Request Sharing
api = Api(app)

parser = reqparse.RequestParser()

class CountRows(Resource):
 
    def get(self):
        # the base URL for a "schemas" object in Elasticsearch, e.g.
        # http://localhost:9200/eurodata/schemas/<schema_id>
        url = config.es_base_url['rows']+'/_search'
        q = {"query":{"match_all":{}}, "size":0}
        resp = requests.post(url, data=json.dumps(q))
        data = resp.json()
        # Return the full Elasticsearch object as a result
        return data['hits']['total']
# The API URLs all start with /api/v1, in case we need to implement different versions later
api.add_resource(CountRows, config.api_base_url+'/count')

class Row(Resource):
 
    def get(self, row_id):
        # the base URL for a "rows" object in Elasticsearch, e.g.
        # http://localhost:9200/eurodata/rows/<row_id>
        url = config.es_base_url['rows']+'/'+row_id
        # query Elasticsearch
        resp = requests.get(url)
        data = resp.json()
        if '_source' in data:
            # Return the full Elasticsearch object as a result
            row = data['_source']

            doc_id = data['_id'].rsplit('-',1)[0]

            url = config.es_base_url['schemas']+'/'+doc_id
            resp = requests.get(url)
            data = resp.json()
            row.update(data['_source'])

            url = config.es_base_url['packages']+'/_search'
            resp = requests.post(url, data=json.dumps({
                  "query": {
                    "match_phrase": { "resources.id": doc_id.split('.')[0] }
                  },
                  "fields": [],
                  "size": 1
                }))
            data = resp.json()
            packages = data['hits']['hits']
            if packages:
                row['package_id'] = packages[0]['_id']
            else:
                row['package_id'] = None
                print doc_id, 'not in ', url
        
            return row

# The API URLs all start with /api/v1, in case we need to implement different versions later
api.add_resource(Row, config.api_base_url+'/rows/<row_id>')

class Search(Resource):
 
    def get(self):
        # parse the query: ?q=[something]
        parser.add_argument('q')
        query_string = parser.parse_args()
        # base search URL
        url = config.es_base_url['rows']+'/_search'
        # Query Elasticsearch
        query = {
            "query": {
                "multi_match": {
                    "fields": ["_all"],
                    "query": query_string['q'],
                    "type": "cross_fields",
                    "use_dis_max": False
                }
            },
            "size": 100
        }
        resp = requests.post(url, data=json.dumps(query))
        data = resp.json()
        total = data['hits']['total']
        hits = data['hits']['hits']
        resource_ids = [hit['_id'].rsplit('-',1)[0] for hit in hits]

        schema_url = config.es_base_url['schemas']+'/_mget'
        schemas = requests.post(schema_url, data=json.dumps({"ids":resource_ids})).json()

        package_url = config.es_base_url['packages']+'/_msearch'
        queries = []
        for i in resource_ids:
            queries.extend([{},{
              "query": {
                "match_phrase": { "resources.id": i.split('.')[0] }
              },
              "size": 1
            }])
        queries = '\n'.join(json.dumps(q) for q in queries) + '\n'
        packages = requests.get(package_url, data=queries).json()
        packages = packages.get('responses', None)

        if 'docs' in schemas:
            schemas = schemas['docs']
            # Build an array of results
            results = {}
            for hit, schema, package in zip(hits, schemas, packages):
                pack = package['hits']['hits'][0]
                header = schema['_source']['schema']
                row = hit['_source']['row']
                if max(len(unicode(r)) for r in row) < 100:
                    # big fields are stupid
                    table_id = hash(pack['_id']+''.join(header))
                    res = results.setdefault(table_id, pack['_source'])
                    res['schema'] = header
                    res.setdefault('rows',[]).append(row)
                else:
                    total -= 1
            # print results
            return {"results": results, "total": total}
api.add_resource(Search, config.api_base_url+'/search')
