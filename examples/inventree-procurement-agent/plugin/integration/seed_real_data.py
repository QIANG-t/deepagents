"""Explicit, idempotent fixture for the isolated inventree-spike instance.

Run through ``manage.py shell < seed_real_data.py`` in the spike container.
This script refuses other site URLs and writes only labelled test records.
"""

import json
import os
from decimal import Decimal
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from django.contrib.auth.models import Group, User
from django.test import Client

from build.models import Build
from order.models import PurchaseOrder
from part.models import BomItem, Part
from stock.models import StockItem, StockLocation
from stock.status_codes import StockStatus
from users.models import RuleSet, UserProfile
from users.permissions import check_user_permission, check_user_role


assert os.environ.get('INVENTREE_SITE_URL') == 'http://127.0.0.1:18080', (
    'Run only in inventree-spike at 127.0.0.1:18080'
)


def upsert(model, lookup, values):
    obj, _ = model.objects.get_or_create(**lookup, defaults=values)
    for key, value in values.items():
        setattr(obj, key, value)
    obj.save()
    return obj


source = upsert(StockLocation, {'name': 'SPIKE-SOURCE'}, {'external': False})
other = upsert(StockLocation, {'name': 'SPIKE-OTHER'}, {'external': False})
assembly = upsert(
    Part,
    {'IPN': 'SPIKE-ASM-001'},
    {'name': 'Spike assembly', 'assembly': True, 'component': False, 'active': True},
)
component = upsert(
    Part,
    {'IPN': 'SPIKE-COMP-001'},
    {
        'name': 'Spike shared component',
        'assembly': False,
        'component': True,
        'purchaseable': True,
        'active': True,
    },
)

for reference, quantity in [('SPIKE-A', 2), ('SPIKE-B', 3)]:
    upsert(
        BomItem,
        {'part': assembly, 'sub_part': component, 'reference': reference},
        {'raw_amount': str(quantity), 'quantity': Decimal(quantity)},
    )

build = upsert(
    Build,
    {'reference': 'BO-9001'},
    {'part': assembly, 'quantity': 2, 'take_from': source, 'title': 'Spike fixture'},
)
# manage.py shell can skip the post-save hook which normally creates these lines.
# This method guards existing (build, bom_item) pairs, so reruns stay idempotent.
build.create_build_line_items()
for location, batch, quantity, status in [
    (source, 'SPIKE-IN', 5, StockStatus.OK.value),
    (other, 'SPIKE-OUT', 7, StockStatus.OK.value),
    (source, 'SPIKE-QUARANTINED', 11, StockStatus.QUARANTINED.value),
]:
    upsert(
        StockItem,
        {'part': component, 'location': location, 'batch': batch},
        {'quantity': Decimal(quantity), 'status': status},
    )

reader_group, _ = Group.objects.get_or_create(name='SPIKE-BUILD-VIEW')
rule, _ = RuleSet.objects.get_or_create(group=reader_group, name='build')
rule.can_view = True
rule.save()

reader, _ = User.objects.get_or_create(username='spike_build_reader')
denied, _ = User.objects.get_or_create(username='spike_build_denied')
for user in [reader, denied]:
    UserProfile.objects.get_or_create(user=user)
    user.is_active = True
    user.is_staff = False
    user.is_superuser = False
    user.set_unusable_password()
    user.save()
reader.groups.set([reader_group])
denied.groups.clear()


def http_get(user, path):
    client = Client()
    client.force_login(user)
    cookie = client.cookies['sessionid'].value
    req = Request(
        'http://127.0.0.1:8000' + path,
        headers={'Host': '127.0.0.1:18080', 'Cookie': f'sessionid={cookie}'},
    )
    try:
        with urlopen(req, timeout=20) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, error.read().decode('utf-8')[:200]


paths = {
    'build': f'/api/build/{build.pk}/',
    'lines': f'/api/build/line/?build={build.pk}',
    'line_detail': f'/api/build/line/{build.build_lines.order_by("pk").first().pk}/',
    'stock': f'/api/stock/?part={component.pk}&include_variants=false',
    'part': f'/api/part/{component.pk}/',
    'requirements': f'/api/part/{component.pk}/requirements/',
}
print(
    'fixture_ids',
    json.dumps(
        {
            'build': build.pk,
            'assembly': assembly.pk,
            'component': component.pk,
            'source': source.pk,
            'other': other.pk,
            'lines': list(
                build.build_lines.order_by('bom_item__reference').values_list(
                    'pk', 'bom_item__reference', 'quantity'
                )
            ),
        },
        default=str,
    ),
)
print(
    'line_methods',
    json.dumps(
        [
            {
                'pk': line.pk,
                'part': line.part.pk,
                'quantity': str(line.quantity),
                'allocated_quantity': str(line.allocated_quantity()),
                'unallocated_quantity': str(line.unallocated_quantity()),
            }
            for line in build.build_lines.order_by('bom_item__reference')
        ]
    ),
)
for user in [reader, denied]:
    print(
        'permissions',
        user.username,
        json.dumps(
            {
                'build_view_role': check_user_role(user, 'build', 'view'),
                'build_view_model': check_user_permission(user, Build, 'view'),
                'build_view_django': user.has_perm('build.view_build'),
                'part_view_model': check_user_permission(user, Part, 'view'),
                'stock_view_model': check_user_permission(user, StockItem, 'view'),
                'purchase_add_model': check_user_permission(user, PurchaseOrder, 'add'),
            }
        ),
    )
    for name, path in paths.items():
        status, data = http_get(user, path)
        if isinstance(data, dict) and status == 200:
            data = {key: data.get(key) for key in ['pk', 'reference', 'part', 'quantity', 'take_from', 'total_in_stock', 'available_stock', 'total_stock', 'unallocated_stock', 'required_for_build_orders', 'allocated', 'bom_item', 'build'] if key in data}
        elif isinstance(data, list) and status == 200:
            if name == 'lines':
                data = [
                    {key: item.get(key) for key in ['pk', 'build', 'bom_item', 'part', 'reference', 'quantity', 'allocated', 'available_stock']}
                    for item in data
                ]
            elif name == 'stock':
                data = [
                    {key: item.get(key) for key in ['pk', 'part', 'location', 'quantity', 'status', 'in_stock']}
                    for item in data
                ]
        print('http', user.username, name, status, json.dumps(data, default=str))
