from django.db.models.signals import pre_delete
from django.dispatch import receiver
from .models import Processor, Motherboard, GraphicsCard, RamModule, PowerSupply, PcCase, Cooler, PcBuild


COMPONENT_SLOTS = {
    Processor: "cpu", Motherboard: "motherboard", GraphicsCard: "gpu",
    RamModule: "ram", PowerSupply: "psu", PcCase: "case", Cooler: "cooler",
}


@receiver(pre_delete)
def clear_deleted_component(sender, instance, using, **kwargs):
    slot = COMPONENT_SLOTS.get(sender)
    if slot is None:
        return
    from django.utils import timezone
    changes = {slot: None, "is_compatible": False, "total_tdp": None, "updated_at": timezone.now()}
    if slot == "ram":
        changes["ram_count"] = 0
    PcBuild.objects.using(using).filter(**{slot: instance}).update(**changes)
