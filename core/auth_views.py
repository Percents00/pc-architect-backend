from django.conf import settings
from .auth_service import refresh_hash, authenticate_access
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import HttpResponse, JsonResponse
from django.middleware.csrf import get_token, rotate_token
from django.utils import timezone
from .models import User, RefreshToken
from .auth_service import (ApiError, endpoint, read_json, user_data, response_error, private_response,
    create_refresh, locked_cookie_token, revoke_family, token_response, clear_refresh_cookie, login_with_limits)


def csrf_failure(request, reason=""):
    return private_response(response_error("CSRF_FAILED", "Проверка запроса не пройдена. Обновите страницу и повторите действие.", 403))


@endpoint(["GET"])
def csrf(request):
    get_token(request)
    return HttpResponse(status=204)


@endpoint(["POST"])
def register(request):
    fields = ("username", "email", "password", "password_confirm")
    data = read_json(request, fields, fields)
    if any(not isinstance(data[key], str) for key in fields):
        raise ApiError("INVALID_FIELDS", "Поля регистрации должны быть строками.")
    username, email = data["username"].strip().lower(), data["email"].strip().lower()
    password = data["password"]
    if not 12 <= len(password) <= 128:
        raise ApiError("INVALID_FIELDS", "Проверьте пароль.", errors={"password": ["Пароль должен содержать от 12 до 128 символов."]})
    if password != data["password_confirm"]:
        raise ApiError("INVALID_FIELDS", "Пароли не совпадают.", errors={"password_confirm": ["Пароли не совпадают."]})
    errors = {}
    if User.objects.filter(username__iexact=username).exists():
        errors["username"] = ["Это имя пользователя уже занято."]
    if User.objects.filter(email__iexact=email).exists():
        errors["email"] = ["Этот email уже зарегистрирован."]
    if errors:
        raise ApiError("IDENTITY_EXISTS", "Имя пользователя или email уже заняты.", 409, errors)
    user = User(username=username, email=email)
    try:
        user.full_clean(exclude=["password"], validate_unique=False, validate_constraints=False)
        validate_password(password, user=user)
    except ValidationError as exc:
        errors = exc.message_dict if hasattr(exc, "message_dict") else {"password": exc.messages}
        raise ApiError("INVALID_FIELDS", "Проверьте данные регистрации.", errors=errors)
    user.set_password(password)
    try:
        with transaction.atomic():
            user.save()
    except IntegrityError:
        raise ApiError("IDENTITY_EXISTS", "Имя пользователя или email уже заняты.", 409)
    return JsonResponse({"user": user_data(user)}, status=201)


@endpoint(["POST"])
def login(request):
    data = read_json(request, ("email", "password"), ("email", "password"))
    if not isinstance(data["email"], str) or not isinstance(data["password"], str):
        raise ApiError("INVALID_FIELDS", "Email и пароль должны быть строками.")
    email, password = data["email"].strip().lower(), data["password"]
    if len(email) > 254 or not 1 <= len(password) <= 128:
        raise ApiError("INVALID_FIELDS", "Проверьте email и пароль.")
    user, limited = login_with_limits(request, email, password)
    if limited:
        result = response_error("TOO_MANY_ATTEMPTS", "Слишком много попыток входа. Повторите позже.", 429)
        result["Retry-After"] = "900"
        return result
    if user is None:
        raise ApiError("INVALID_CREDENTIALS", "Неверный email или пароль.", 401)
    with transaction.atomic():
        raw_cookie = request.COOKIES.get(settings.AUTH_REFRESH_COOKIE, "")
        old_user = RefreshToken.objects.filter(token_hash=refresh_hash(raw_cookie)).values_list("user_id", flat=True).first() if len(raw_cookie) == 43 else None
        locked = list(User.objects.select_for_update().filter(pk__in=[value for value in [user.pk, old_user] if value is not None]).order_by("id"))
        authenticated_id = user.pk
        user = next((item for item in locked if item.pk == authenticated_id), None)
        if user is None or not user.is_active:
            raise ApiError("INVALID_CREDENTIALS", "Неверный email или пароль.", 401)
        old = locked_cookie_token(request)
        if old is not None:
            revoke_family(old.family_id)
        token, raw = create_refresh(user)
    rotate_token(request)
    return token_response(request, token, raw)


@endpoint(["POST"])
def refresh(request):
    with transaction.atomic():
        old = locked_cookie_token(request)
        if old is None:
            valid = False
        elif old.used_at is not None or old.revoked_at is not None or old.expires_at <= timezone.now() or not old.user.is_active:
            revoke_family(old.family_id)
            valid = False
        else:
            old.used_at = timezone.now()
            old.save(update_fields=["used_at"])
            token, raw = create_refresh(old.user, old.family_id, old.expires_at)
            valid = True
    # Return after the transaction so revocations on rejected refreshes are committed.
    if not valid:
        return clear_refresh_cookie(response_error("UNAUTHENTICATED", "Сеанс завершён. Войдите снова.", 401), request)
    return token_response(request, token, raw)


@endpoint(["POST"])
def logout(request):
    with transaction.atomic():
        old = locked_cookie_token(request)
        if old is not None:
            revoke_family(old.family_id)
        elif request.headers.get("Authorization"):
            try:
                user, family = authenticate_access(request)
            except ApiError:
                pass
            else:
                User.objects.select_for_update().get(pk=user.pk)
                revoke_family(family)
    rotate_token(request)
    return clear_refresh_cookie(HttpResponse(status=204), request)


@endpoint(["GET"], authenticated=True)
def me(request):
    return JsonResponse(user_data(request.account_user))
