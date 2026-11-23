"""Run as the data owner to grant an existing app read access to its 30-table subset."""
import argparse
import re
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.store import APP_TABLES


def quoted(value):
    if not re.fullmatch(r'[A-Za-z0-9_-]+',value):raise ValueError('Use a simple catalog/schema identifier')
    return '`'+value+'`'


def execute(client,warehouse,statement,parameters=None):
    body={'warehouse_id':warehouse,'statement':statement,'format':'JSON_ARRAY','disposition':'INLINE',
          'wait_timeout':'10s','on_wait_timeout':'CONTINUE','parameters':parameters or []}
    result=client.api_client.do('POST','/api/2.0/sql/statements',body=body)
    deadline=time.monotonic()+100
    while result.get('status',{}).get('state') in {'PENDING','RUNNING'}:
        statement_id=result['statement_id']
        if time.monotonic()>=deadline:
            client.api_client.do('POST','/api/2.0/sql/statements/'+statement_id+'/cancel')
            raise RuntimeError('Setup SQL timed out. Review warehouse history before retrying.')
        time.sleep(0.5)
        result=client.api_client.do('GET','/api/2.0/sql/statements/'+statement_id)
    if result.get('status',{}).get('state')!='SUCCEEDED':
        code=result.get('status',{}).get('error',{}).get('error_code','UNKNOWN')
        raise RuntimeError('Setup SQL failed ['+str(code)+']. Run as an owner allowed to grant access; inspect warehouse query history.')
    return result


def configure(client,app_name,warehouse,catalog='source-data',schema='app_gold'):
    target=quoted(catalog)+'.'+quoted(schema)
    application=client.apps.get(name=app_name)
    principal=str(uuid.UUID(application.service_principal_client_id))
    # Refuse a full source Gold schema or another accidental dataset. Only names are read.
    inventory=execute(client,warehouse,'SELECT table_name FROM '+quoted(catalog)+
        '.information_schema.tables WHERE table_schema=:schema',
        [{'name':'schema','value':schema,'type':'STRING'}])
    rows=inventory.get('result',{}).get('data_array',[])
    if {row[0] for row in rows}!=APP_TABLES:
        raise ValueError('The destination must contain exactly the 30 app tables before granting shared access.')
    if inventory.get('result',{}).get('next_chunk_internal_link'):
        raise ValueError('Unexpected extra inventory chunks; inspect the destination before granting access.')
    grant_sql=[
        'GRANT USE CATALOG ON CATALOG '+quoted(catalog)+' TO '+quoted(principal),
        'GRANT USE SCHEMA ON SCHEMA '+target+' TO '+quoted(principal),
        'GRANT SELECT ON SCHEMA '+target+' TO '+quoted(principal),
    ]
    for statement in grant_sql:execute(client,warehouse,statement)
    return {'app':app_name,'service_principal_application_id':principal,'dataset':catalog+'.'+schema,'grants':3}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app-name',required=True)
    parser.add_argument('--warehouse-id',required=True)
    parser.add_argument('--catalog',default='source-data')
    parser.add_argument('--schema',default='app_gold')
    parser.add_argument('--profile',default='DEFAULT')
    args=parser.parse_args()
    from databricks.sdk import WorkspaceClient
    result=configure(WorkspaceClient(profile=args.profile),args.app_name,args.warehouse_id,args.catalog,args.schema)
    print('Granted read-only dataset access: '+result['dataset']+'; app principal: '+result['service_principal_application_id'])
    print('No tables were created or changed. Warehouse CAN USE is supplied by the attached sql-warehouse resource.')


if __name__=='__main__':main()
