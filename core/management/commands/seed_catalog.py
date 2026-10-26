import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from core.models import ComponentCategory, Processor, Motherboard, GraphicsCard, RamModule, PowerSupply, PcCase, Cooler


class Command(BaseCommand):
    help = "Заполнить каталог комплектующими из core/fixtures/components.json без перезаписи существующих записей."

    @transaction.atomic
    def handle(self, *args, **options):
        source = Path(__file__).resolve().parents[2] / "fixtures" / "components.json"
        try:
            catalog = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, ValueError, IndexError) as exc:
            raise CommandError(f"Не удалось прочитать каталог: {exc}") from exc
        models = {"cpu": Processor, "motherboard": Motherboard, "gpu": GraphicsCard,
                  "ram": RamModule, "psu": PowerSupply, "case": PcCase, "cooler": Cooler}
        count = 0
        for item in catalog["categories"]:
            values = dict(item)
            pk = values.pop("id")
            _, created = ComponentCategory.objects.get_or_create(pk=pk, defaults=values)
            count += created
        for item in catalog["components"]:
            values = dict(item)
            model = models[values.pop("category")]
            pk = values.pop("id")
            for field in ("supported_sockets", "supported_motherboard_formats"):
                if field in values:
                    parts = [value.strip() for value in values[field].split(",")]
                    if field == "supported_motherboard_formats" and any(p.startswith("E-ATX (") for p in parts):
                        values["spec_note"] = (values.get("spec_note", "") + " E-ATX: ширина платы до 285 мм.").strip()
                    values[field] = ["E-ATX" if p.startswith("E-ATX (") else p for p in parts]
            obj = model(**values, id=pk)
            obj.full_clean(validate_unique=False)
            _, created = model.objects.get_or_create(pk=pk, defaults=values)
            count += created
        self.stdout.write(self.style.SUCCESS(f"Добавлено записей: {count}"))
