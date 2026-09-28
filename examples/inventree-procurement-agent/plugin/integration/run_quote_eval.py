"""Run one live DeepSeek pass over the synthetic quote evaluation set.

In the isolated spike container, copy ``quote_eval_v1.json`` to
``/tmp/quote_eval_v1.json`` then run ``manage.py shell < run_quote_eval.py``.
Results are written only to /tmp for offline grading; no purchase actions run.
"""

import hashlib
import json
import os
from pathlib import Path
from time import monotonic

from inventree_procurement_plugin.quote import compare_quote, extract_quote


if os.environ.get('INVENTREE_SITE_URL') != 'http://127.0.0.1:18080':
    raise RuntimeError('This script runs only in the isolated inventree-spike instance')
if not os.environ.get('DEEPSEEK_API_KEY'):
    raise RuntimeError('DEEPSEEK_API_KEY is absent from the server process')

fixture = Path('/tmp/quote_eval_v1.json')
raw = fixture.read_bytes()
cases = json.loads(raw)['cases']
run_id = os.environ.get('QUOTE_EVAL_RUN_ID', 'deepseek-v1-1')
if run_id not in {
    'deepseek-v1-1', 'deepseek-v1-2', 'deepseek-v1-3',
    'deepseek-v2-1', 'deepseek-v2-2', 'deepseek-v2-3',
    'deepseek-v3-1', 'deepseek-v3-2', 'deepseek-v3-3',
    'deepseek-v4-1', 'deepseek-v4-2', 'deepseek-v4-3',
}:
    raise RuntimeError('Unsupported fixed run ID')
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
            'checks': compare_quote(result['extracted'], case['supplier_part']),
            'tool_calls': result['tool_calls'],
            'model': result['model'],
        }
        error = None
        error_message = None
    except Exception as failure:
        quote = None
        error = type(failure).__name__
        error_message = str(failure) if error in {'QuoteFailed', 'QuoteUnavailable'} else 'Unexpected failure'
    elapsed = round(monotonic() - started, 2)
    observations.append({'case_id': case['id'], 'run_id': run_id,
                         'quote': quote, 'latency_seconds': elapsed,
                         'error_type': error, 'error_message': error_message})
    print('case', case['id'], 'result', 'success' if quote else error,
          'latency_seconds', elapsed)

output = Path(f'/tmp/quote_eval_v1_{run_id}_observations.json')
output.write_text(json.dumps(observations, ensure_ascii=False, indent=2) + '\n')
print('fixture_sha256', hashlib.sha256(raw).hexdigest())
print('success_count', sum(item['quote'] is not None for item in observations),
      'case_count', len(observations))
print('observations_path', str(output))
