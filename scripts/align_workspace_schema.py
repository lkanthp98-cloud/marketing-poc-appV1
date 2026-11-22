"""Align reporting contracts to supplied schema exports; never query or write Databricks."""
import csv
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
from backend.catalog import PAGES


def main():
    downloads=Path('C:/Users/Paleti Lakshmikanth/Downloads')
    files=[downloads/'Media_POC_Data_Explorer.csv']+[downloads/f'Media_POC_Data_Explorer ({i}).csv' for i in range(1,5)]
    tables, provenance = {}, {}
    for path in files:
        provenance[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
        with path.open(encoding='utf-8-sig',newline='') as stream:
            for row in csv.DictReader(stream):
                location=(row['catalog'],row['schema'])
                key='.'.join((*location,row['table']))
                entry=tables.setdefault(key,{'catalog':location[0],'schema':location[1],'name':row['table'],'columns':[]})
                if row['column name'] in {c['name'] for c in entry['columns']}:
                    raise ValueError('Duplicate column in export: '+key+'.'+row['column name'])
                entry['columns'].append({'name':row['column name'],'type':row['data type']})
    gold={v['name']:v for v in tables.values() if (v['catalog'],v['schema'])==('media-poc','gold')}
    use_cases={v['name']:v for v in tables.values() if (v['catalog'],v['schema'])==('source-data','usecases')}
    mapping={}
    for name, spec in gold.items():
        if not name.startswith('mart_'):continue
        suffix=name.removeprefix('mart_')
        candidates=[n for n in use_cases if n==suffix or n.endswith('_'+suffix)]
        if not candidates:continue
        if len(candidates)!=1:raise ValueError('Ambiguous Use Cases mapping: '+name)
        target=candidates[0]
        a={c['name']:c['type'] for c in spec['columns']}
        b={c['name']:c['type'] for c in use_cases[target]['columns'] if not c['name'].startswith('_uc_')}
        if a!=b:raise ValueError(f'Source/target column/type mismatch: {name} -> {target}: {a.keys() ^ b.keys()}')
        mapping[name]=target
    assert len(gold)==113 and len(use_cases)==30 and len(mapping)==28
    contract={'verification':'SCHEMA_EXPORTS_ONLY_NOT_LIVE_DATA_VALIDATION','source_files_sha256':provenance,
        'gold_location':{'catalog':'media-poc','schema':'gold'},'use_cases_location':{'catalog':'source-data','schema':'usecases'},
        'analytics_mapping':mapping,'tables':dict(sorted(tables.items()))}
    (APP/'data/workspace_contract.json').write_text(json.dumps(contract,indent=2)+'\n',encoding='utf-8')
    reports=[]
    for page,spec in PAGES.items():
        specs=[('metric',m.label,m.table,[m.expression],[]) for m in spec['metrics']]
        specs += [('chart',c.title,c.table,[m['expression'] for m in c.measures],c.dimensions) for c in spec['charts']]
        for kind,label,source,expressions,dimensions in specs:
            assert source in mapping, (page,label,'No exported Use Cases table',source)
            fields=set(dimensions)
            for expression in expressions:
                fields.update(re.findall(r'`([^`]+)`',expression))
                if re.fullmatch(r'[a-z][a-z0-9_]*',expression):fields.add(expression)
            target=mapping[source]
            columns={c['name'] for c in use_cases[target]['columns']}
            if fields-columns:raise ValueError(f'{page}/{label}: unexported columns {fields-columns}')
            reports.append([page,kind,label,'source-data.usecases.'+target,'media-poc.gold.'+source,', '.join(sorted(fields)),'SCHEMA_MATCH_NO_LIVE_VALUES_CHECKED'])
    with (APP/'docs/dashboard-data-mapping.csv').open('w',encoding='utf-8-sig',newline='') as file:
        writer=csv.writer(file);writer.writerow(['page','element','title','analytics_input','gold_reference','required_columns','validation']);writer.writerows(reports)
    summary=defaultdict(lambda:[0,0])
    for table in tables.values():
        summary[(table['catalog'],table['schema'])][0]+=1
        summary[(table['catalog'],table['schema'])][1]+=len(table['columns'])
    print('Export inventory:',dict(summary))
    print(f'Validated {len(reports)} dashboard elements against 28 Use Cases datasets; no data values or permissions were validated.')


if __name__=='__main__':main()
