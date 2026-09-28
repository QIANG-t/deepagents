"""Explicit HTTP contract check against the isolated inventree-spike server.

Run with the container's /home/inventree/data/env/bin/python manage.py shell.
Creates one owned analysis task for the pre-existing BO-9001 fixture.
"""

import json
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from django.contrib.auth.models import User
from django.middleware.csrf import get_token
from django.test import Client, RequestFactory

from build.models import Build
from inventree_procurement_plugin.models import ProcurementTask


assert os.environ.get('INVENTREE_SITE_URL') == 'http://127.0.0.1:18080'
build = Build.objects.get(reference='BO-9001')
reader = User.objects.get(username='spike_build_reader')
denied = User.objects.get(username='spike_build_denied')
other = User.objects.get(username='spike_owner')
base = '/plugin/inventree_procurement/'


def session_headers(user, csrf=False):
    client = Client()
    client.force_login(user)
    cookies = [f"sessionid={client.cookies['sessionid'].value}"]
    headers = {'Host': '127.0.0.1:18080'}
    if csrf:
        request = RequestFactory().get('/')
        token = get_token(request)
        cookies.append(f"csrftoken={request.META['CSRF_COOKIE']}")
        headers['X-CSRFToken'] = token
    headers['Cookie'] = '; '.join(cookies)
    return headers


def http(method, path, headers=None, payload=None):
    data = None if payload is None else json.dumps(payload).encode('utf-8')
    req_headers = dict(headers or {'Host': '127.0.0.1:18080'})
    if data is not None:
        req_headers['Content-Type'] = 'application/json'
    request = Request(
        'http://127.0.0.1:8000' + path, data=data, method=method,
        headers=req_headers,
    )
    try:
        with urlopen(request, timeout=30) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        body = error.read()
        try:
            return error.code, json.loads(body)
        except ValueError:
            return error.code, body.decode('utf-8')[:120]


reader_headers = session_headers(reader, csrf=True)
denied_headers = session_headers(denied, csrf=True)
other_headers = session_headers(other)
payload = {'build_ids': [build.pk]}

checks = {
    'anonymous_health': http('GET', base + 'health/'),
    'anonymous_tasks': http('GET', base + 'tasks/'),
    'anonymous_post': http('POST', base + 'tasks/', payload=payload),
    'no_csrf_post': http('POST', base + 'tasks/', headers=session_headers(reader), payload=payload),
    'denied_post': http('POST', base + 'tasks/', headers=denied_headers, payload=payload),
    'denied_tasks': http('GET', base + 'tasks/', headers=denied_headers),
}
for name, (status, body) in checks.items():
    print(name, status, json.dumps(body if isinstance(body, dict) else str(body)[:80]))
assert [checks[name][0] for name in checks] == [401, 401, 401, 403, 403, 403]

status, created = http('POST', base + 'tasks/', headers=reader_headers, payload=payload)
print('create', status, json.dumps(created, default=str))
assert status == 201, created
task_id = created['task']['id']
assert created['task']['status'] == 'analyzed'
assert created['task']['build_ids'] == [build.pk]

status, detail = http('GET', base + f'tasks/{task_id}/', headers=reader_headers)
assert status == 200 and detail['task']['id'] == task_id
status, response = http('GET', base + f'tasks/{task_id}/preview/', headers=reader_headers)
assert status == 200, response
preview = response['preview']
lines = preview['lines']
part = preview['parts'][0]
assert [line['required'] for line in lines] == ['4.00000', '6.00000'], lines
assert [line['outstanding'] for line in lines] == ['4.00000', '6.00000'], lines
assert part['selected_build_outstanding'] == '10.00000', part
assert part['available_stock']['value'] == '5.00000', part
assert part['preliminary_shortage']['value'] == '5.00000', part
assert part['build_line_ids'] == [line['build_line_id'] for line in lines]
assert part['available_stock']['source']['build_context_id'] == build.pk
assert part['available_stock']['location_assumption']['build_take_from_id'] == build.take_from_id
assert preview['warnings'] and part['preliminary_shortage']['warning']
assert response['snapshot_digest'] == created['task']['snapshot_digest']
print('preview', status, json.dumps(response, default=str))

for name, headers in [('anonymous', None), ('denied', denied_headers), ('other_owner', other_headers)]:
    result = http('GET', base + f'tasks/{task_id}/preview/', headers=headers)
    print('preview_' + name, result[0], json.dumps(result[1] if isinstance(result[1], dict) else str(result[1])[:80]))
    # Owner masking runs before business permission checks on detail URLs.
    assert result[0] == {'anonymous': 401, 'denied': 404, 'other_owner': 404}[name]

assert ProcurementTask.objects.get(pk=task_id).preview == preview
print('task_id', task_id)
