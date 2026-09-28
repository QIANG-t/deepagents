"""Seed a labelled supplier quote fixture in the isolated inventree-spike DB.

Run with ``manage.py shell < seed_quote_fixture.py`` in the spike container.
The quote text is synthetic and never stored as an InvenTree purchase order.
"""

import os

from djmoney.money import Money

from company.models import Company, SupplierPart, SupplierPriceBreak
from part.models import Part


if os.environ.get('INVENTREE_SITE_URL') != 'http://127.0.0.1:18080':
    raise RuntimeError('This script runs only in the isolated inventree-spike instance')

component = Part.objects.get(IPN='SPIKE-COMP-001')
supplier, _ = Company.objects.get_or_create(
    name='SPIKE Quote Supplier',
    defaults={'is_supplier': True},
)
if not supplier.is_supplier:
    supplier.is_supplier = True
    supplier.save(update_fields=['is_supplier'])

supplier_part, _ = SupplierPart.objects.get_or_create(
    part=component,
    supplier=supplier,
    SKU='SPIKE-QUOTE-001',
    defaults={'pack_quantity': '5', 'active': True},
)
if supplier_part.pack_quantity != '5' or not supplier_part.active:
    supplier_part.pack_quantity = '5'
    supplier_part.active = True
    supplier_part.save()

price_break, _ = SupplierPriceBreak.objects.get_or_create(
    part=supplier_part,
    quantity=1,
    defaults={'price': Money('10.00', 'USD')},
)
if price_break.price != Money('10.00', 'USD'):
    price_break.price = Money('10.00', 'USD')
    price_break.save()

print('supplier_part_id', supplier_part.pk)
print('supplier_name', supplier.name)
print('component_ipn', component.IPN)
print('pack_quantity_native', supplier_part.pack_quantity_native)
print('price_break', str(price_break.price), 'at_quantity', price_break.quantity)
