"""User-authorized Genie chat proxy. Generated SQL is displayed, never replayed by the app."""
import hashlib
import hmac
import json
import os
import re
import secrets
import urllib.error
import urllib.request
from .store import DataError

_secret=secrets.token_bytes(32)
EXAMPLES=['Show marketing spend by platform in USD','Show funded accounts by month','Show experiment conversion by variant']


def safe_id(value):
    if not re.fullmatch(r'[A-Za-z0-9-]{1,100}',value or ''):raise DataError('Invalid Genie identifier.',400)
    return value


def space():
    value=os.getenv('GENIE_SPACE_ID','')
    if not value:raise DataError('Attach a Genie space using resource key genie-space before using live chat.')
    return safe_id(value)


def proof(user,conversation):
    return hmac.new(_secret,(user.cache_key+'|'+space()+'|'+safe_id(conversation)).encode(),hashlib.sha256).hexdigest()


def authorize(user,conversation,key):
    if not hmac.compare_digest(proof(user,conversation),key or ''):
        raise DataError('Start a new Genie conversation in this signed-in session.',403)


def request(store,user,path,body=None):
    store.validate_runtime(require_warehouse=False)
    if not user.token:raise DataError('Configure Databricks user authorization with sql and genie scopes.',401)
    req=urllib.request.Request(store.host+'/api/2.0/genie/spaces/'+space()+path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Authorization':'Bearer '+user.token,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=25) as response:return json.load(response)
    except urllib.error.HTTPError as error:
        if error.code in {401,403}:raise DataError('Enable the genie and sql user scopes, Genie space access and underlying table permissions.',403) from error
        if error.code==429:raise DataError('Genie is busy. Wait briefly and retry.',429) from error
        raise DataError('Genie could not complete this request. Check the space configuration and workspace availability.') from error
    except (OSError,ValueError) as error:raise DataError('Genie is unavailable. Retry shortly.') from error


def normalize(store,user,message,conversation,message_id):
    status=message.get('status','SUBMITTED')
    text=[]; queries=[]
    if status in {'FAILED','CANCELLED','QUERY_RESULT_EXPIRED'}:
        return {'conversation_id':conversation,'message_id':message_id,'status':status,
            'text':'Genie did not complete this answer. Ask again or start a new conversation.','queries':[]}
    for attachment in message.get('attachments',[]):
        if attachment.get('text',{}).get('content'):text.append(attachment['text']['content'])
        if attachment.get('query'):
            query=attachment['query']; item={'sql':query.get('query',''),'title':query.get('title','Query result'),'columns':[],'rows':[]}
            if status=='COMPLETED' and attachment.get('attachment_id'):
                path=f'/conversations/{safe_id(conversation)}/messages/{safe_id(message_id)}/attachments/{safe_id(attachment["attachment_id"])}/query-result'
                try:
                    data=request(store,user,path)
                    statement=data.get('statement_response',data)
                    if statement.get('status',{}).get('state') not in {None,'SUCCEEDED'}:
                        item['error']='Query results are not ready or have expired. Ask again.'
                    else:
                        columns=statement.get('manifest',{}).get('schema',{}).get('columns',[])
                        rows=statement.get('result',{}).get('data_array',[])
                        item.update(columns=[c['name'] for c in columns],rows=rows[:100],
                            truncated=bool(len(rows)>100 or statement.get('manifest',{}).get('truncated') or statement.get('result',{}).get('next_chunk_internal_link')))
                except DataError as error:item['error']=str(error)
            queries.append(item)
    return {'conversation_id':conversation,'message_id':message_id,'status':status,'text':'\n\n'.join(text),'queries':queries}


def send(store,user,question,conversation='',key=''):
    if conversation:
        authorize(user,conversation,key)
        response=request(store,user,f'/conversations/{safe_id(conversation)}/messages',{'content':question})
    else:response=request(store,user,'/start-conversation',{'content':question})
    message=response.get('message',response)
    conversation=response.get('conversation_id') or message.get('conversation_id') or response.get('conversation',{}).get('conversation_id') or response.get('conversation',{}).get('id') or conversation
    message_id=response.get('message_id') or message.get('message_id') or message.get('id')
    safe_id(conversation); safe_id(message_id)
    result=normalize(store,user,message,conversation,message_id)
    result['conversation_key']=proof(user,conversation)
    return result


def poll(store,user,conversation,message_id,key):
    authorize(user,conversation,key)
    message=request(store,user,f'/conversations/{safe_id(conversation)}/messages/{safe_id(message_id)}')
    return normalize(store,user,message,conversation,message_id)


def sample(store,user,question):
    if question not in EXAMPLES:
        return {'status':'COMPLETED','text':'Local mode supports the three suggested sample questions. Connect a Genie space for open-ended questions and contextual follow-ups.','queries':[]}
    source,sql = {
        EXAMPLES[0]:('mart_vendor_media_daily',"SELECT platform, SUM(spend_amount) AS spend_usd FROM {table} WHERE currency='USD' GROUP BY platform ORDER BY spend_usd DESC"),
        EXAMPLES[1]:('mart_banking_funded_accounts_monthly','SELECT opening_month, SUM(funded_accounts) AS funded_accounts FROM {table} GROUP BY opening_month ORDER BY opening_month'),
        EXAMPLES[2]:('mart_demo_experiment_variant','SELECT variant_id, SUM(converted_units) AS converted_units, SUM(eligible_units) AS eligible_units, 1.0*SUM(converted_units)/NULLIF(SUM(eligible_units),0) AS conversion_rate FROM {table} GROUP BY variant_id'),
    }[question]
    sql=sql.format(table=store.table(source))
    rows=store.query(sql,{},user)
    columns=list(rows[0]) if rows else []
    return {'status':'COMPLETED','text':'Guided sample result from the source CSV-derived local fixture. This answer was not generated by live Genie.',
        'queries':[{'title':question,'sql':sql,'columns':columns,'rows':[[r[c] for c in columns] for r in rows],'truncated':False}]}
