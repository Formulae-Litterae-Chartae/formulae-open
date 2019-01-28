from elasticsearch import Elasticsearch
from glob import glob
import re
import json

def split_dates(multidate_str):
    date_list = multidate_str.rstrip(',').split(',')
    for date_str in date_list:
        if date_str.startswith("---"):
            yield {"day": int(date_str.lstrip('-'))}
            continue
        if date_str.startswith('--'):
            parts = date_str.lstrip('-').split('-')
            if len(parts) == 1:
                yield {"month": int(parts[0])}
                continue
            yield {"month": int(parts[0]), "day": int(parts[1])}
            continue
        parts = date_str.split('-')
        if len(parts) == 1:
            yield {"year": int(parts[0])}
            continue
        if len(parts) == 2:
            yield {"year": int(parts[0]), "month": int(parts[1])}
            continue
        yield {"year": int(parts[0]), "month": int(parts[1]), "day": int(parts[2])}
        
        
def find_all_dates(date_dict):
    date_list = []
    for date_range in date_dict['dating']:
        if 'gte' in date_range:
            date_list.append(date_range['gte'])
        if 'lte' in date_range:
            date_list.append(date_range['lte'])
    for spec_date in date_dict['specific_date']:
        year_string = ''
        month_string = ''
        day_string = ''
        if 'year' in spec_date:
            year_string = '{:04}'.format(spec_date['year'])
        else:
            continue
        if 'month' in spec_date:
            month_string = '-{:02}'.format(spec_date['month'])
        else:
            date_list.append(year_string)
            continue
        if 'day' in spec_date:
            day_string = '-{:02}'.format(spec_date['day'])
        else:
            date_list.append(year_string + month_string)
            continue
        date_list.append(year_string + month_string + day_string)
    return date_list


# For local ES
# es = Elasticsearch('http://localhost:9200')
# For Formulae - Litterae - Chartae Bonsai ES
es = Elasticsearch('https://7rjmvb3g9l:q3j3ss5xpe@matthews-first-sandb-6890251342.eu-central-1.bonsaisearch.net')
# For CJHNT Bonsai ES
# es = Elasticsearch('https://fkiyh8udo5:iuwd6ekete@cjhnt-testing-6879850075.eu-central-1.bonsaisearch.net')
# This list includes all collections that are not chartae. 
# I use coll_type.get(k, 'chartae') below to return 'chartae' if the coll isn't listed here.
coll_type = {'andecavensis': 'formulae'}

# I have commented the following line out in a move to using aliases and keeping at least one older version of indices.
# These older indices should probably be deleted by hand instead of being removed automatically.
# es.indices.delete('*') #replace with the index to be deleted or "*" for all indices.

files = glob('/home/matt/results/formulae-open/search/*.txt')
# This is the mapping for normalization of place names
with open('place_mapping.json') as f:
    place_mapping = json.load(f)

# The 'auto_analyzer' and 'auto_filter' are for the 'autocomplete field. Since this is not supported, and may never be necessary, I am commenting them out.
auto_filter = {"filter": {"autocomplete_filter": {"type": "edge_ngram", "min_gram": 1, "max_gram": 20}}}
auto_analyzer = {"analyzer": {"autocompletion": {"type": "custom", "tokenizer": "standard", "filter": ["lowercase", "autocomplete_filter"]}}}
# new_indices should also have the latest index name in it.
new_indices = {}
index_properties = {'urn': {'type': 'keyword'}, 'date_string': {'type': 'keyword'}}
index_properties.update({'dating': {'type': 'date_range', 'format': 'yyyy-MM-dd||yyyy-MM||yyyy'},
                         'specific_date': {'type': 'nested'},
                         'all_dates': {'type': 'date', 'format': 'yyyy-MM-dd||yyyy-MM||yyyy'},
                         'min_date': {'type': 'date', 'format': 'yyyy-MM-dd||yyyy-MM||yyyy'}})
index_properties.update({'comp_ort': {"type": "keyword"}})
index_properties.update({'orig_comp_ort': {"type": "keyword"}})
index_properties.update({'autocomplete': {"type": "text", "analyzer": "autocompletion", "search_analyzer": "standard"}})
index_properties.update({'autocomplete_lemmas': {"type": "text", "analyzer": "autocompletion", "search_analyzer": "standard"}})


for file in files:
    with open(file) as f:
        s = f.read()
    try:
        name, urn, dating, text, lemmas = s.split('\n******\n')
    except Exception as E:
        print(E, file)
        continue
    coll = urn.split(':')[-1].split('.')[0]
    name, date_string, comp_ort = name.split('*!')
    orig_comp_ort = comp_ort
    comp_ort = place_mapping.get(comp_ort, comp_ort)
    name = re.sub('\s+', ' ', name)
    dates = {'specific_date': [], "dating": [], 'all_dates': []}
    for date in dating.strip().split('\n'):
        groups = {}
        for m in re.finditer(r'(\w+): ([\d\-,]+)', date):
            groups.update({m.group(1): m.group(2)})
        if 'when' in groups.keys():
            try:
                dates['specific_date'] += [x for x in split_dates(groups['when'])]
            except ValueError as E:
                print(E, file)
        elif "gte" in groups.keys() or "lte" in groups.keys():
            dates['dating'].append(groups)
    dates['all_dates'] = find_all_dates(dates)
    if coll not in new_indices:
        new_indices[coll] = {'old': [], 'new': ''}
        if es.indices.exists('{}*'.format(coll)):
            try:
                new_indices[coll]['old'] = list(es.indices.get('{}*'.format(coll)).keys())
            except Exception as E:
                print(coll, E)
            try:
                new_index = re.sub('\d+', lambda x: str(int(x.group(0)) + 1),
                                   sorted(new_indices[coll]['old'],
                                          key=lambda y: int(re.search('\d+', y).group(0)))[-1])
                if new_index == coll:
                    new_index = coll + '_v1'
            except IndexError:
                new_index = coll + '_v1'
        else:
            new_index = coll + '_v1'
        new_indices[coll]['new'] = new_index
    if not es.indices.exists(new_indices[coll]['new']):
        print("Creating index {}".format(new_indices[coll]['new']))
        # 1 shard searches faster
        # Add the following back in if I ever use the autocomplete analyzer:
        # "analysis": {"filter": auto_filter["filter"],
        # "analyzer": auto_analyzer["analyzer"]}
        es.indices.create(index=new_indices[coll]['new'], body={"settings": {"index": {"number_of_shards": 1, "number_of_replicas": 0},
                                                                "analysis": {"filter": auto_filter["filter"],
                                                                             "analyzer": auto_analyzer["analyzer"]}},
                                                                "mappings": {coll: {"properties": index_properties}}})
    body = {'text': text, 'lemmas': lemmas, 'title': name, 'urn': urn, 'date_string': date_string or ' ', 'comp_ort': comp_ort or ' ',
            'autocomplete': text, 'autocomplete_lemmas': lemmas, 'orig_comp_ort': orig_comp_ort or ' '}
    if dates["dating"]:
        body["dating"] = dates['dating']
    if dates["specific_date"]:
        body["specific_date"] = dates["specific_date"]
    if dates['all_dates']:
        body['all_dates'] = dates['all_dates']
        body['min_date'] = min(dates['all_dates'])
    try:
        es.index(index=new_indices[coll]['new'], doc_type=coll, id=urn, body=body)
    except Exception as E:
        print(E, file)
    
# delete previous aliases to each of the collections and point them instead to the new index
for k, v in new_indices.items():
    if v['old']:
        # removes all connections between the old index names and any aliases they may have had
        es.indices.delete_alias(index=v['old'], name='*')
    # enables search by collection
    es.indices.put_alias(index=v['new'], name=k)
    # enables search by collection type
    es.indices.put_alias(index=v['new'], name=coll_type.get(k, 'chartae'))
    # enables searching on all documents
    es.indices.put_alias(index=v['new'], name='all')
