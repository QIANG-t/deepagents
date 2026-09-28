"""Run one live DeepSeek pass over the synthetic quote evaluation set.

In the isolated spike container, copy the selected fixed fixture to ``/tmp``
then run ``manage.py shell < run_quote_eval.py``.
Results are written only to /tmp for offline grading; no purchase actions run.
"""

import hashlib
import json
import os
from pathlib import Path
from time import monotonic

from inventree_procurement_plugin.quote import QuoteFailed, QuoteUnavailable, compare_quote, extract_quote


if os.environ.get('INVENTREE_SITE_URL') != 'http://127.0.0.1:18080':
    raise RuntimeError('This script runs only in the isolated inventree-spike instance')
if not os.environ.get('DEEPSEEK_API_KEY'):
    raise RuntimeError('DEEPSEEK_API_KEY is absent from the server process')

fixture_name = os.environ.get('QUOTE_EVAL_FIXTURE', 'quote_eval_v1.json')
if fixture_name not in {'quote_eval_v1.json', 'quote_eval_v2.json'}:
    raise RuntimeError('Unsupported fixed quote evaluation fixture')
fixture = Path('/tmp') / fixture_name
raw = fixture.read_bytes()
cases = json.loads(raw)['cases']
run_id = os.environ.get('QUOTE_EVAL_RUN_ID', 'deepseek-v1-1')
v1_run_ids = {
    'deepseek-v1-1', 'deepseek-v1-2', 'deepseek-v1-3',
    'deepseek-v2-1', 'deepseek-v2-2', 'deepseek-v2-3',
    'deepseek-v3-1', 'deepseek-v3-2', 'deepseek-v3-3',
    'deepseek-v4-1', 'deepseek-v4-2', 'deepseek-v4-3',
    'deepseek-v5-1', 'deepseek-v5-2', 'deepseek-v5-3',
}
v2_run_ids = {
    'deepseek-v2set-1', 'deepseek-v2set-2', 'deepseek-v2set-3',
    'deepseek-v2set-fixed-1', 'deepseek-v2set-fixed-2', 'deepseek-v2set-fixed-3',
}
allowed_run_ids = v1_run_ids if fixture_name == 'quote_eval_v1.json' else v2_run_ids
if run_id not in allowed_run_ids:
    raise RuntimeError('Run ID does not match the fixed fixture')
observations = []
for case in cases:
    started = monotonic()
    try:
        result = extract_quote(case['source_text'], case['supplier_part'])
        quote = {
            'supplier_part_id': case['supplier_part']['supplier_part_id'],
            'source_text': case['source_text'],
            'source_sha256': hashlib.sha256(case['source_text'].encode('utf-8')).hexdigest(),
            'extracted': result['extracted'],
            'checks': compare_quote(result['extracted'], case['supplier_part'], case['source_text']),
            'tool_calls': result['tool_calls'],
            'model': result['model'],
        }
        error = None
        failure_stage = None
        failure_code = None
    except Exception as failure:
        quote = None
        error = type(failure).__name__
        if isinstance(failure, QuoteFailed):
            failure_stage = failure.stage
            failure_code = failure.code
        elif isinstance(failure, QuoteUnavailable):
            failure_stage = 'runtime'
            failure_code = 'quote_unavailable'
        else:
            failure_stage = 'runtime'
            failure_code = 'unexpected_failure'
    elapsed = round(monotonic() - started, 2)
    observations.append({'case_id': case['id'], 'run_id': run_id,
                         'quote': quote, 'latency_seconds': elapsed,
                         'error_type': error, 'failure_stage': failure_stage,
                         'failure_code': failure_code})
    print('case', case['id'], 'result', 'success' if quote else error,
          'latency_seconds', elapsed)

output = Path(f'/tmp/{fixture.stem}_{run_id}_observations.json')
output.write_text(json.dumps(observations, ensure_ascii=False, indent=2) + '\n')
print('fixture_sha256', hashlib.sha256(raw).hexdigest())
print('success_count', sum(item['quote'] is not None for item in observations),
      'case_count', len(observations))
print('observations_path', str(output))
