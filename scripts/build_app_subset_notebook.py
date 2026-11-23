"""Build the portable IPYNB from the canonical Databricks Python notebook."""
import json
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
SOURCE = APP/'notebooks/08_publish_app_gold_subset.py'


def main():
    code = SOURCE.read_text(encoding='utf-8').replace('# Databricks notebook source\n','',1)
    cells = []
    for chunk in code.split('# COMMAND ----------'):
        chunk = chunk.strip()
        if chunk.startswith('# MAGIC %md'):
            lines = chunk.splitlines()
            content = '\n'.join(line.removeprefix('# MAGIC ').removeprefix('# MAGIC') for line in lines[1:])
            cells.append(dict(cell_type='markdown',metadata={},source=content+'\n'))
        elif chunk:
            compile(chunk,'app_subset_cell','exec')
            cells.append(dict(cell_type='code',execution_count=None,metadata={},outputs=[],source=chunk+'\n'))
    notebook = dict(cells=cells,metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},
        'language_info':{'name':'python','version':'3.11'}},nbformat=4,nbformat_minor=5)
    # Reproducible cell IDs allow validation using current Jupyter notebook schemas.
    for i,cell in enumerate(cells):cell['id']='app-gold-subset-'+str(i+1)
    target = SOURCE.with_suffix('.ipynb')
    target.write_bytes((json.dumps(notebook,indent=2,ensure_ascii=False)+'\n').encode('utf-8'))
    print('Generated '+str(target)+' ('+str(len(cells))+' cells)')


if __name__=='__main__':main()
