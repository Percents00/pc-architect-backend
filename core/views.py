from functools import wraps
from pathlib import Path
import uuid

from django.conf import settings
from django.db import DatabaseError
from django.http import FileResponse, JsonResponse, Http404, HttpResponse
from django.views.decorators.http import require_GET
from .models import ComponentCategory, Processor, Motherboard, GraphicsCard, RamModule, PowerSupply, PcCase, Cooler


COMPONENT_MODELS = {
    "cpu": Processor, "motherboard": Motherboard, "gpu": GraphicsCard,
    "ram": RamModule, "psu": PowerSupply, "case": PcCase, "cooler": Cooler,
}
ASSETS = {
    "auth.js": "text/javascript",
    "style.css": "text/css",
    "app.js": "text/javascript",
    "compatibility.js": "text/javascript",
}


@require_GET
def index(request):
    try:
        stream = (Path(settings.FRONTEND_DIR) / "index.html").open("rb")
    except FileNotFoundError:
        return HttpResponse("Не найден фронтенд. Разместите репозиторий frontend рядом с backend или задайте FRONTEND_DIR.", status=503, content_type="text/plain; charset=utf-8")
    return FileResponse(stream, content_type="text/html; charset=utf-8")


@require_GET
def asset(request, name):
    if name not in ASSETS:
        raise Http404
    try:
        stream = (Path(settings.FRONTEND_DIR) / name).open("rb")
    except FileNotFoundError:
        raise Http404
    return FileResponse(stream, content_type=ASSETS[name] + "; charset=utf-8")


def error(code, message, status):
    return JsonResponse({"code": code, "message": message}, status=status)


def catalog_endpoint(view):
    @require_GET
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except DatabaseError:
            return error("DATABASE_UNAVAILABLE", "Каталог временно недоступен. Повторите попытку позже.", 503)
    return wrapped


@catalog_endpoint
def categories(request):
    fields = ("id", "name", "code_slug", "icon_name", "display_order")
    return JsonResponse({"items": list(ComponentCategory.objects.order_by("display_order", "id").values(*fields))})


@catalog_endpoint
def components(request):
    unsupported = set(request.GET) - {"category", "q", "page", "page_size"}
    if unsupported:
        return error("INVALID_FILTER", "Неподдерживаемые параметры: " + ", ".join(sorted(unsupported)), 422)
    category = request.GET.get("category", "")
    if category and category not in COMPONENT_MODELS:
        return error("INVALID_CATEGORY", "Неизвестная категория комплектующих.", 422)
    try:
        page = int(request.GET.get("page", "1"))
        page_size = int(request.GET.get("page_size", "20"))
        if page < 1 or not 1 <= page_size <= 100:
            raise ValueError
    except ValueError:
        return error("INVALID_PAGINATION", "page должен быть положительным, page_size — от 1 до 100.", 422)

    query = request.GET.get("q", "").strip()
    items = []
    for code, model in COMPONENT_MODELS.items():
        if category and category != code:
            continue
        queryset = model.objects.order_by("name", "id")
        if query:
            queryset = queryset.filter(name__icontains=query)
        items.extend({**item, "category": code} for item in queryset.values())
    start = (page - 1) * page_size
    return JsonResponse({"items": items[start:start + page_size], "total": len(items), "page": page, "page_size": page_size})


@catalog_endpoint
def component_detail(request, component_id):
    try:
        identifier = uuid.UUID(component_id)
    except ValueError:
        return error("NOT_FOUND", "Комплектующее не найдено.", 404)
    for code, model in COMPONENT_MODELS.items():
        item = model.objects.filter(pk=identifier).values().first()
        if item is not None:
            return JsonResponse({**item, "category": code})
    return error("NOT_FOUND", "Комплектующее не найдено.", 404)
