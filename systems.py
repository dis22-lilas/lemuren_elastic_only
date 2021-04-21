import os
import re
import json
import jsonlines
from elasticsearch import Elasticsearch, helpers
import re
from google_trans_new import google_translator
from elasticsearch.client.ingest import IngestClient


def load_json(directory, id_field):
    for path, subdir, file in os.walk(directory):
        extensions = tuple([".jsonl"])
        files = [f for f in file if f.endswith(extensions)]
        for f in files:
            with jsonlines.open(os.path.join(path, f), 'r') as reader:
                for obj in reader:  
                    yield {
                        '_op_type': 'index',
                        '_id': obj[id_field],
                        '_source': obj}

def load_settings(settings_path):
    with open(settings_path, encoding='utf-8') as json_file:
        return json.load(json_file)


def load_query_settings(query_settings_path, query_raw,
                        query_tokenized_eng, query_tokenized_german):
    f = open("./query_settings/lemuren_query_settings.txt", "r+", encoding="utf-8")
    content = f.read()
    content = content.replace('"query": "query_raw",', '"query": "' + query_raw + '",')
    content = content.replace('"query": "query_tokenized_eng",', '"query": "' + query_tokenized_eng + '",')
    content = content.replace('"query": "query_tokenized_german",', '"query": "' + query_tokenized_german + '",')
    return content


def load_ingest_pipeline_settings(es, pipeline_settings_path):
    p = IngestClient(es)
    #content = json.loads(pipeline_settings_path)
    #print(content.read())
    with open(pipeline_settings_path) as json_file:
        content = json.load(json_file)
    p.put_pipeline(id='attachment', body=content)

    return p

def clear_prep_data(prep_data_path):
    if os.path.exists(prep_data_path):
        os.remove(prep_data_path)
    else:
        print("Prep_data folder is already empty")

class Ranker(object):
    def __init__(self):
        self.INDEX = 'idx_test'
        self.index_settings_path = os.path.join('index_settings', 'lemuren_index_settings.json')
        self.query_settings_path = os.path.join('query_settings', 'lemuren_query_settings.txt')
        self.pipeline_settings_path = os.path.join("pipeline_settings", "pipeline_settings.json")

        self.es = Elasticsearch([{'host': 'localhost', 'port': 9200}])
        self.documents_path = './data/livivo/documents'

    def test(self):
        return self.es.info(), 200

    def index(self):

        load_ingest_pipeline_settings(self.es, self.pipeline_settings_path)
        
        if self.es.indices.exists(self.INDEX):
            print ("Index ", self.INDEX, " already exists. Inserting into index now.")
        else:
            self.es.indices.create(index=self.INDEX, body=load_settings(self.index_settings_path))

        for success, info in helpers.parallel_bulk(self.es, load_json(self.documents_path, 'DBRECORDID'),
                                            index=self.INDEX, pipeline="attachment"):
            #print("Insert into Index Complete")
            if not success:
                return 'A document failed: ' + info, 400
        print ("All Documents have been indexed.  >>END<<")

        #clear_prep_data('./prep_data/filtered_documents')
        return 'Index built with ' + ' docs', 200

    def rank_publications(self, query, page, rpp):

        itemlist = []
        start = page * rpp
        if query is not None:
            translator = google_translator()
            #operator = 'OR'  ### Kritisch weil User potentiell mehrere operatoren kombiniren könnte
            #if ' AND ' in query and not ' OR ' in query:  # wahrscheinlich nur query_string besser
            #    operator = 'AND'
            query_raw = query
            query = re.sub(r'[^\w\d\s]+', '', query)
            query = query.replace(" AND ", " +++++ ")
            query = query.replace(" UND ", " +++++ ")
            query = query.replace(" OR ", " ||||| ")
            query = query.replace(" ODER ", " ||||| ")

            try:
                query_eng = translator.translate(query, lang_tgt='en')
                query_de = translator.translate(query, lang_tgt='de')
            except:
                query_eng = query
                query_de = query

            if type(query_de) == list:
                query_de = query_de[1]

            #query_tokenized_german = tf.tokenize_string_german(query_de)
            #query_tokenized_ori = tf.tokenize_string_sci(query)
            #query_tokenized_eng = tf.tokenize_string_sci(query_eng)

            query_de = query_de.replace("+++++", "AND")
            query_de = query_de.replace("|||||", "OR")

            query_raw = re.sub(r'[^\w\d\s]+', '', query_raw)
            query_raw = query_raw.replace("+++++", "AND")
            query_raw = query_raw.replace("|||||", "OR")

            query_eng = query_eng.replace("+++++", "AND")
            query_eng = query_eng.replace("|||||", "OR")
            es = Elasticsearch([{'host': 'localhost', 'port': 9200}])

            result = es.search(index=self.INDEX,
                               from_=start,
                               size=rpp,
                               body=load_query_settings(self.query_settings_path, query_raw,
                                                        query_eng, query_de))

            for res in result["hits"]["hits"]:
                try:
                    itemlist.append(res['_source']['DBRECORDID'])
                except:
                    pass

        return {
            'page': page,
            'rpp': rpp,
            'query': query,
            'itemlist': itemlist,
            'num_found': len(itemlist)
        }


class Recommender(object):

    def __init__(self):
        self.index_documents = 'documents'
        self.index_documents_settings_path = os.path.join('index_settings', 'gesis-search_documents_settings.json')
        self.documents_path = './data/gesis-search/documents'

        self.index_datasets = 'datasets'
        self.index_datasets_settings_path = os.path.join('index_settings', 'gesis-search_datasets_settings.json')
        self.datasets_path = './data/gesis-search/datasets'

        self.es = Elasticsearch([{'host': 'localhost', 'port': 9200}])

    def index(self):
        self.es.indices.create(index=self.index_documents, body=load_settings(self.index_documents_settings_path))
        self.es.indices.create(index=self.index_datasets, body=load_settings(self.index_documents_settings_path))

        for success, info in helpers.parallel_bulk(self.es,
                                                   load_json(self.documents_path,
                                                             'id'), index=self.index_documents):
            if not success:
                return 'A document failed: ' + info, 400

        for success, info in helpers.parallel_bulk(self.es,
                                                   load_json(self.documents_path,
                                                             'id'), index=self.index_datasets):
            if not success:
                return 'A document failed: ' + info, 400

        return 'Indices built', 200

    def recommend_datasets(self, item_id, page, rpp):
        itemlist = []

        start = page * rpp

        if item_id is not None:

            es = Elasticsearch([{'host': 'localhost', 'port': 9200}])

            result = es.search(index=self.index_documents,
                               from_=start,
                               size=rpp,
                               body={"query": {"multi_match": {"query": item_id, "fields": ["id"]}}})

            if result["hits"]["hits"]:
                title = result["hits"]["hits"][0]['_source']['title']
                es = Elasticsearch([{'host': 'localhost', 'port': 9200}])

                result = es.search(index=self.index_datasets,
                                   from_=start,
                                   size=rpp,
                                   body={"query": {"multi_match": {"query": title, "fields": ["title", 'abstract']}}})

            for res in result["hits"]["hits"]:
                try:
                    itemlist.append(res['_source']['id'])
                except:
                    pass

        return {
            'page': page,
            'rpp': rpp,
            'item_id': item_id,
            'itemlist': itemlist,
            'num_found': len(itemlist)
        }

    def recommend_publications(self, item_id, page, rpp):
        itemlist = []

        return {
            'page': page,
            'rpp': rpp,
            'item_id': item_id,
            'itemlist': itemlist,
            'num_found': len(itemlist)
        }
