import uuid
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from .models import PcBuild
from .views import COMPONENT_MODELS
from .auth_service import ApiError, endpoint, read_json


SLOTS = ("cpu", "motherboard", "gpu", "ram", "psu", "case", "cooler")
FIELDS = ("title", "description", "ram_count") + tuple(slot + "_id" for slot in SLOTS)


def serialize(build):
    return {"id": str(build.pk), "title": build.title, "description": build.description,
        "selection": {**{slot + "_id": str(getattr(build, slot + "_id")) if getattr(build, slot + "_id") else None for slot in SLOTS}, "ram_count": build.ram_count},
        "created_at": build.created_at, "updated_at": build.updated_at}


def clean_build(data, build=None):
    values = {}
    for field, limit in [("title", 120), ("description", 2000)]:
        value = data.get(field, getattr(build, field) if build else ("Моя сборка ПК" if field == "title" else ""))
        if not isinstance(value, str) or len(value) > limit or (field == "title" and not value.strip()):
            raise ApiError("INVALID_FIELDS", "Проверьте название и описание сборки.")
        values[field] = value.strip() if field == "title" else value
    for slot in SLOTS:
        field = slot + "_id"
        value = data.get(field, getattr(build, field) if build else None)
        if value is not None:
            try:
                value = uuid.UUID(str(value))
            except (ValueError, TypeError):
                raise ApiError("INVALID_COMPONENT", "Некорректный ID комплектующего.")
            if not COMPONENT_MODELS[slot].objects.filter(pk=value).exists():
                raise ApiError("INVALID_COMPONENT", "Комплектующее отсутствует или относится к другой категории.")
        values[field] = value
    count = data.get("ram_count", build.ram_count if build else 0)
    if type(count) is not int or not 0 <= count <= 16 or (values["ram_id"] is None and count != 0) or (values["ram_id"] is not None and count == 0):
        raise ApiError("INVALID_FIELDS", "Без RAM количество модулей равно 0, с RAM — от 1 до 16.")
    values["ram_count"] = count
    return values


@endpoint(["GET", "POST"], authenticated=True)
def builds(request):
    if request.method == "POST":
        data = read_json(request, FIELDS, ("title",))
        with transaction.atomic():
            build = PcBuild.objects.create(user=request.account_user, **clean_build(data))
        return JsonResponse(serialize(build), status=201)
    try:
        page, size = int(request.GET.get("page", "1")), int(request.GET.get("page_size", "20"))
        if page < 1 or not 1 <= size <= 100:
            raise ValueError
    except ValueError:
        raise ApiError("INVALID_PAGINATION", "Некорректная страница списка.")
    queryset = PcBuild.objects.filter(user=request.account_user).order_by("-updated_at", "id")
    return JsonResponse({"items": [serialize(item) for item in queryset[(page - 1) * size:page * size]], "total": queryset.count(), "page": page, "page_size": size})


@endpoint(["GET", "PATCH", "DELETE"], authenticated=True)
def build_detail(request, build_id):
    try:
        identifier = uuid.UUID(build_id)
    except ValueError:
        raise ApiError("NOT_FOUND", "Сборка не найдена.", 404)
    with transaction.atomic():
        build = PcBuild.objects.select_for_update().filter(pk=identifier, user=request.account_user).first()
        if build is None:
            raise ApiError("NOT_FOUND", "Сборка не найдена.", 404)
        if request.method == "DELETE":
            build.delete()
            return HttpResponse(status=204)
        if request.method == "PATCH":
            data = read_json(request, FIELDS)
            for key, value in clean_build(data, build).items():
                setattr(build, key, value)
            build.is_public, build.is_compatible, build.total_tdp = False, False, None
            build.save()
        return JsonResponse(serialize(build))
