"""Exercise the quote endpoint through HTTP in the isolated spike instance.

Run with ``manage.py shell < verify_quote.py`` inside the spike server. This
creates one task and one paid DeepSeek extraction from synthetic quote text.
"""

import json
import os
from hashlib import sha256
from time import monotonic
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from django.contrib.auth.models import User
from django.middleware.csrf import get_token
from django.test import Client, RequestFactory

from build.models import Build
from company.models import SupplierPart
from inventree_procurement_plugin.service import create_analysis_task
from order.models import PurchaseOrder, PurchaseOrderLineItem


if os.environ.get('INVENTREE_SITE_URL') != 'http://127.0.0.1:18080':
    raise RuntimeError('This script runs only in the isolated inventree-spike instance')
if not os.environ.get('DEEPSEEK_API_KEY'):
    raise RuntimeError('DEEPSEEK_API_KEY is absent from the server process')

owner = User.objects.get(username='spike_buyer_reader')
other = User.objects.get(username='spike_owner')
build = Build.objects.get(reference='BO-9001')
supplier_part = SupplierPart.objects.get(SKU='SPIKE-QUOTE-001')
task = create_analysis_task(owner, build.pk)
path = f'/plugin/inventree_procurement/tasks/{task.pk}/quote/'
source_text = (
    'Supplier: SPIKE Quote Supplier\n'
    'SKU: SPIKE-QUOTE-001\n'
    'Unit price: USD 12.50 per pack\n'
    'Pack quantity: 5 pcs\n'
    'Valid until: 2026-12-31\n'
    'Lead time: 14 days\n'
)
payload = {'supplier_part_id': supplier_part.pk, 'text': source_text}
orders_before = (PurchaseOrder.objects.count(), PurchaseOrderLineItem.objects.count())


def session_headers(user, *, csrf=False):
    client = Client()
    client.force_login(user)
    headers = {'Host': '127.0.0.1:18080'}
    cookies = [f"sessionid={client.cookies['sessionid'].value}"]
    if csrf:
        request = RequestFactory().get('/')
        token = get_token(request)
        cookies.append(f"csrftoken={request.META['CSRF_COOKIE']}")
        headers['X-CSRFToken'] = token
    headers['Cookie'] = '; '.join(cookies)
    return headers


def http(method, *, headers=None, data=None):
    body = json.dumps(data).encode('utf-8') if data is not None else None
    request = Request(
        'http://127.0.0.1:8000' + path,
        data=body if method == 'POST' else None,
        method=method,
        headers=headers or {'Host': '127.0.0.1:18080'},
    )
    if method == 'POST':
        request.add_header('Content-Type', 'application/json')
    try:
        with urlopen(request, timeout=120) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        try:
            return error.code, json.load(error)
        except ValueError:
            return error.code, {'code': 'non_json_error'}


owner_headers = session_headers(owner, csrf=True)
assert http('GET')[0] == 401
assert http('GET', headers=session_headers(other))[0] == 404
assert http('GET', headers=owner_headers) == (
    409, {'error': 'Quote has not been extracted', 'code': 'quote_unavailable'}
)
assert http('POST', headers=session_headers(owner), data=payload)[0] == 403
assert http('POST', headers=owner_headers, data={'supplier_part_id': -1, 'text': source_text})[0] == 400

started = monotonic()
status, created = http('POST', headers=owner_headers, data=payload)
elapsed = round(monotonic() - started, 2)
print('quote_post_status', status, 'elapsed_seconds', elapsed, 'task_id', str(task.pk))
if status != 201:
    print('quote_error_code', created.get('code'))
    raise AssertionError('Live quote extraction did not succeed')

quote = created['quote']
assert quote['supplier_part_id'] == supplier_part.pk
assert quote['source_text'] == source_text
assert quote['source_sha256'] == sha256(source_text.encode('utf-8')).hexdigest()
assert quote['model'] == 'deepseek-flash'
assert len(quote['tool_calls']) == 1
call = quote['tool_calls'][0]
assert call['name'] == 'read_quote_snapshot' and call['status'] == 'success'
assert call['tool_call_id'] and len(call['result_sha256']) == 64
for field, item in quote['extracted'].items():
    if item is not None:
        assert source_text[item['start']:item['end']] == item['evidence'], field
assert http('GET', headers=owner_headers) == (200, created)
assert http('POST', headers=owner_headers, data=payload) == (200, created)
changed = dict(payload, text=source_text + 'Revised text\n')
assert http('POST', headers=owner_headers, data=changed)[0] == 409
assert (PurchaseOrder.objects.count(), PurchaseOrderLineItem.objects.count()) == orders_before
print('extracted', json.dumps(quote['extracted'], ensure_ascii=False))
print('checks', json.dumps(quote['checks'], ensure_ascii=False))
print('tool_call', call['name'], call['status'], call['result_sha256'])
print('cache_reused', True, 'purchase_orders_unchanged', True)
