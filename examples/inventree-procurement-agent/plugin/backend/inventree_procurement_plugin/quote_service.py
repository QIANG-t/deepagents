"""Permission-checked SupplierPart facts for quote comparison."""

from .service import BusinessReadDenied


class SupplierPartMissing(LookupError):
    """The selected SupplierPart does not exist or belongs to another Part."""


def check_supplier_read_permissions(user: object) -> None:
    """Require current access to suppliers, supplier parts, and price breaks."""
    from company.models import Company, SupplierPart, SupplierPriceBreak
    from users.permissions import check_user_permission

    for model in (Company, SupplierPart, SupplierPriceBreak):
        if not check_user_permission(user, model, "view"):
            raise BusinessReadDenied("Supplier and supplier pricing view permissions are required")


def supplier_part_snapshot(user: object, supplier_part_id: int, preview: dict) -> dict:
    """Read supplier facts only after all current model permissions pass."""
    from company.models import SupplierPart, SupplierPriceBreak

    check_supplier_read_permissions(user)
    allowed_part_ids = {part["part_id"] for part in preview.get("parts", [])}
    try:
        supplier_part = SupplierPart.objects.select_related("supplier", "part").get(pk=supplier_part_id)
    except SupplierPart.DoesNotExist as error:
        raise SupplierPartMissing("SupplierPart was not found") from error
    if supplier_part.part_id not in allowed_part_ids:
        raise SupplierPartMissing("SupplierPart is not linked to the analyzed Part")
    pricebreaks = SupplierPriceBreak.objects.filter(part_id=supplier_part_id).order_by("quantity", "pk")
    return {
        "supplier_part_id": supplier_part.pk,
        "part_id": supplier_part.part_id,
        "part_units": supplier_part.part.units,
        "supplier_name": supplier_part.supplier.name,
        "sku": supplier_part.SKU,
        "pack_quantity_native": (str(supplier_part.pack_quantity_native)
                                 if supplier_part.pack_quantity_native is not None else None),
        "pricebreaks": [{"quantity": str(row.quantity),
                         "price": str(row.price.amount) if row.price is not None else None,
                         "currency": str(row.price_currency) if row.price is not None else None}
                        for row in pricebreaks],
    }
