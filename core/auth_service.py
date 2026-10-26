import hashlib
import json
import secrets
import uuid
from datetime import timedelta
from functools import wraps

import jwt
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import DatabaseError, transaction
from django.http import JsonResponse
from django.utils import timezone
from django.utils.crypto import salted_hmac
from .models import User, RefreshToken, LoginThrottle


class ApiError(Exception):
    def __init__(self, code, message, status=422, errors=None):
        self.code, self.message, self.status, self.errors = code, message, status, errors


def response_error(code, message, status, errors=None):
    payload = {"code": code, "message": message}
    if errors:
        payload["errors"] = errors
    return JsonResponse(payload, status=status)


def private_response(response):
    response["Cache-Control"] = "no-store"
    response["Pragma"] = "no-cache"
    return response


def endpoint(methods, authenticated=False):
    def decorate(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            try:
                if request.method not in methods:
                    result = response_error("METHOD_NOT_ALLOWED", "Метод не поддерживается.", 405)
                    result["Allow"] = ", ".join(methods)
                else:
                    if authenticated:
                        request.account_user, request.account_family = authenticate_access(request)
                    result = view(request, *args, **kwargs)
            except ApiError as exc:
                result = response_error(exc.code, exc.message, exc.status, exc.errors)
            except DatabaseError:
                result = response_error("DATABASE_UNAVAILABLE", "Сервис временно недоступен. Повторите попытку позже.", 503)
            return private_response(result)
        return wrapped
    return decorate


def read_json(request, allowed, required=()):
    if request.content_type != "application/json":
        raise ApiError("INVALID_JSON", "Ожидается JSON.", 400)
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        raise ApiError("INVALID_JSON", "Не удалось прочитать JSON.", 400)
    if not isinstance(data, dict):
        raise ApiError("INVALID_JSON", "Ожидается JSON-объект.", 400)
    if set(data) - set(allowed):
        raise ApiError("INVALID_FIELDS", "Запрос содержит неизвестные поля.")
    missing = set(required) - set(data)
    if missing:
        raise ApiError("INVALID_FIELDS", "Заполните обязательные поля.", errors={key: ["Обязательное поле."] for key in missing})
    return data


def user_data(user):
    return {"id": str(user.pk), "username": user.username, "email": user.email, "is_staff": user.is_staff}


def signing_key():
    return salted_hmac("pc-architect-access-v1", "access", secret=settings.SECRET_KEY, algorithm="sha256").hexdigest()


def access_token(user, family):
    now = timezone.now()
    return jwt.encode({
        "sub": str(user.pk), "sid": str(family), "jti": str(uuid.uuid4()), "token_type": "access",
        "iat": now, "nbf": now, "exp": now + timedelta(seconds=settings.AUTH_ACCESS_SECONDS),
        "iss": settings.AUTH_TOKEN_ISSUER, "aud": settings.AUTH_TOKEN_AUDIENCE,
    }, signing_key(), algorithm="HS256")


def authenticate_access(request):
    header = request.headers.get("Authorization", "")
    parts = header.split()
    if len(parts) != 2 or parts[0] != "Bearer":
        raise ApiError("UNAUTHENTICATED", "Войдите в учётную запись.", 401)
    try:
        claims = jwt.decode(parts[1], signing_key(), algorithms=["HS256"],
            issuer=settings.AUTH_TOKEN_ISSUER, audience=settings.AUTH_TOKEN_AUDIENCE,
            options={"require": ["sub", "sid", "jti", "token_type", "iat", "nbf", "exp", "iss", "aud"]})
        if claims["token_type"] != "access":
            raise ValueError
        user_id, family = uuid.UUID(claims["sub"]), uuid.UUID(claims["sid"])
    except (jwt.InvalidTokenError, ValueError, TypeError, AttributeError):
        raise ApiError("UNAUTHENTICATED", "Сеанс недействителен или истёк.", 401)
    user = User.objects.filter(pk=user_id, is_active=True).first()
    if user is None or not RefreshToken.objects.filter(user_id=user_id, family_id=family,
            used_at__isnull=True, revoked_at__isnull=True, expires_at__gt=timezone.now()).exists():
        raise ApiError("UNAUTHENTICATED", "Сеанс завершён. Войдите снова.", 401)
    return user, family


def refresh_hash(raw):
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_refresh(user, family=None, expires_at=None):
    raw = secrets.token_urlsafe(32)
    token = RefreshToken.objects.create(user=user, family_id=family or uuid.uuid4(),
        token_hash=refresh_hash(raw), expires_at=expires_at or timezone.now() + timedelta(days=settings.AUTH_REFRESH_DAYS))
    return token, raw


def revoke_family(family):
    RefreshToken.objects.filter(family_id=family, revoked_at__isnull=True).update(revoked_at=timezone.now())


def locked_cookie_token(request):
    # Lock the user before any token row: every operation on a family uses the same lock order.
    raw = request.COOKIES.get(settings.AUTH_REFRESH_COOKIE, "")
    if len(raw) != 43:
        return None
    found = RefreshToken.objects.filter(token_hash=refresh_hash(raw)).values("id", "user_id").first()
    if found is None:
        return None
    if not User.objects.select_for_update().filter(pk=found["user_id"]).exists():
        return None
    return RefreshToken.objects.select_for_update().select_related("user").filter(pk=found["id"]).first()


def token_response(request, token, raw):
    response = JsonResponse({"access_token": access_token(token.user, token.family_id),
        "token_type": "Bearer", "expires_in": settings.AUTH_ACCESS_SECONDS, "user": user_data(token.user)})
    response.set_cookie(settings.AUTH_REFRESH_COOKIE, raw,
        max_age=max(0, int((token.expires_at - timezone.now()).total_seconds())),
        httponly=True, secure=request.is_secure() or not settings.DEBUG, samesite="Strict", path="/api/auth/")
    return response


def clear_refresh_cookie(response, request):
    response.delete_cookie(settings.AUTH_REFRESH_COOKIE, path="/api/auth/", samesite="Strict")
    response.cookies[settings.AUTH_REFRESH_COOKIE]["httponly"] = True
    response.cookies[settings.AUTH_REFRESH_COOKIE]["secure"] = request.is_secure() or not settings.DEBUG
    return response


def login_with_limits(request, email, password):
    now = timezone.now()
    window = timedelta(seconds=settings.AUTH_LOGIN_WINDOW_SECONDS)
    keys = {
        refresh_hash("account:" + email): settings.AUTH_LOGIN_ACCOUNT_LIMIT,
        refresh_hash("ip:" + request.META.get("REMOTE_ADDR", "unknown")): settings.AUTH_LOGIN_IP_LIMIT,
    }
    with transaction.atomic():
        buckets = []
        for key in sorted(keys):
            LoginThrottle.objects.get_or_create(key=key, defaults={"window_started": now})
            bucket = LoginThrottle.objects.select_for_update().get(pk=key)
            if bucket.window_started + window <= now:
                bucket.failures, bucket.window_started = 0, now
                bucket.save(update_fields=["failures", "window_started"])
            buckets.append(bucket)
        if any(bucket.failures >= keys[bucket.pk] for bucket in buckets):
            return None, True
        user = User.objects.filter(email__iexact=email).first()
        valid = user.check_password(password) if user is not None else (make_password(password) and False)
        if user is None or not valid or not user.is_active:
            for bucket in buckets:
                bucket.failures += 1
                bucket.save(update_fields=["failures"])
            return None, False
        return user, False
