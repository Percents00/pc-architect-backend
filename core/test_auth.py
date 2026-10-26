import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import jwt
from django.conf import settings
from django.db import close_old_connections, connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from .auth_service import refresh_hash, signing_key
from .models import User, RefreshToken, PcBuild, RamModule


PASSWORD = "Cedar#47!River$92"


def client():
    result = Client(enforce_csrf_checks=True)
    result.get("/api/auth/csrf/")
    return result


def send(browser, path, data=None, method="post", token=None, **kwargs):
    headers = {"HTTP_X_CSRFTOKEN": browser.cookies["csrftoken"].value}
    if token:
        headers["HTTP_AUTHORIZATION"] = "Bearer " + token
    headers.update(kwargs)
    return getattr(browser, method)(path, data=json.dumps(data or {}), content_type="application/json", **headers)


def sign_in(browser, email="owner@example.test"):
    return send(browser, "/api/auth/login/", {"email": email, "password": PASSWORD})


class AuthTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="owner", email="owner@example.test", password=PASSWORD)

    def setUp(self):
        self.browser = client()

    def me(self, access):
        return self.browser.get("/api/auth/me/", HTTP_AUTHORIZATION="Bearer " + access)

    def test_registration_normalizes_and_hashes_without_logging_in(self):
        data = {"username": " New_User ", "email": " NEW@example.test ", "password": PASSWORD, "password_confirm": PASSWORD}
        response = send(self.browser, "/api/auth/register/", data)
        self.assertEqual(response.status_code, 201)
        created = User.objects.get(username="new_user")
        self.assertEqual(created.email, "new@example.test")
        self.assertTrue(created.check_password(PASSWORD))
        self.assertNotEqual(created.password, PASSWORD)
        self.assertNotIn(PASSWORD, response.content.decode())
        self.assertNotIn(settings.AUTH_REFRESH_COOKIE, response.cookies)
        self.assertEqual(response["Cache-Control"], "no-store")
        duplicate = send(self.browser, "/api/auth/register/", data)
        self.assertEqual(duplicate.status_code, 409)

    def test_registration_validation(self):
        base = {"username": "newuser", "email": "new@example.test", "password": PASSWORD, "password_confirm": PASSWORD}
        for change in [{"username": "xx"}, {"email": "invalid"}, {"password_confirm": "different"},
                       {"password": "123456789012", "password_confirm": "123456789012"},
                       {"password": "x" * 129, "password_confirm": "x" * 129}, {"is_staff": True}]:
            with self.subTest(change=tuple(change)):
                self.assertEqual(send(self.browser, "/api/auth/register/", {**base, **change}).status_code, 422)

    def test_auth_mutations_require_csrf_and_reject_foreign_origin(self):
        bare = Client(enforce_csrf_checks=True)
        for route in ["register", "login", "refresh", "logout"]:
            response = bare.post(f"/api/auth/{route}/", data="{}", content_type="application/json")
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()["code"], "CSRF_FAILED")
        sign_in(self.browser)
        self.assertEqual(send(self.browser, "/api/auth/refresh/", HTTP_ORIGIN="https://evil.example").status_code, 403)

    def test_login_cookie_and_access_claims(self):
        with override_settings(DEBUG=True):
            response = sign_in(self.browser)
        self.assertEqual(response.status_code, 200)
        cookie = response.cookies[settings.AUTH_REFRESH_COOKIE]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Strict")
        self.assertEqual(cookie["path"], "/api/auth/")
        self.assertFalse(cookie["secure"])
        self.assertNotIn("refresh_token", response.json())
        stored = RefreshToken.objects.get(token_hash=refresh_hash(cookie.value))
        self.assertNotEqual(stored.token_hash, cookie.value)
        access = response.json()["access_token"]
        claims = jwt.decode(access, signing_key(), algorithms=["HS256"], audience=settings.AUTH_TOKEN_AUDIENCE, issuer=settings.AUTH_TOKEN_ISSUER)
        self.assertEqual(claims["sub"], str(self.user.pk))
        self.assertEqual(claims["exp"] - claims["iat"], 900)
        self.assertEqual(self.me(access).status_code, 200)
        self.assertNotIn("password", self.me(access).json())
        self.assertEqual(self.me(access)["Cache-Control"], "no-store")

    def test_refresh_cookie_is_secure_over_https(self):
        response = send(self.browser, "/api/auth/login/", {"email": self.user.email, "password": PASSWORD}, secure=True, HTTP_ORIGIN="https://testserver")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.cookies[settings.AUTH_REFRESH_COOKIE]["secure"])

    def test_rotation_preserves_absolute_expiry_and_reuse_revokes_family(self):
        login = sign_in(self.browser)
        old_raw = self.browser.cookies[settings.AUTH_REFRESH_COOKIE].value
        old = RefreshToken.objects.get(token_hash=refresh_hash(old_raw))
        response = send(self.browser, "/api/auth/refresh/")
        self.assertEqual(response.status_code, 200)
        new_raw = self.browser.cookies[settings.AUTH_REFRESH_COOKIE].value
        self.assertNotEqual(new_raw, old_raw)
        replacement = RefreshToken.objects.get(token_hash=refresh_hash(new_raw))
        old.refresh_from_db()
        self.assertIsNotNone(old.used_at)
        self.assertEqual(old.family_id, replacement.family_id)
        self.assertEqual(old.expires_at, replacement.expires_at)
        self.browser.cookies[settings.AUTH_REFRESH_COOKIE] = old_raw
        self.assertEqual(send(self.browser, "/api/auth/refresh/").status_code, 401)
        self.assertFalse(RefreshToken.objects.filter(family_id=old.family_id, revoked_at__isnull=True).exists())
        self.browser.cookies[settings.AUTH_REFRESH_COOKIE] = new_raw
        self.assertEqual(send(self.browser, "/api/auth/refresh/").status_code, 401)
        self.assertEqual(self.me(login.json()["access_token"]).status_code, 401)
        self.assertEqual(self.me(response.json()["access_token"]).status_code, 401)

    def test_logout_revokes_access_and_refresh_only_for_current_session(self):
        first = sign_in(self.browser).json()["access_token"]
        old_raw = self.browser.cookies[settings.AUTH_REFRESH_COOKIE].value
        other_browser = client()
        second = sign_in(other_browser).json()["access_token"]
        response = send(self.browser, "/api/auth/logout/")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.cookies[settings.AUTH_REFRESH_COOKIE]["max-age"], 0)
        self.assertEqual(self.me(first).status_code, 401)
        self.assertEqual(other_browser.get("/api/auth/me/", HTTP_AUTHORIZATION="Bearer " + second).status_code, 200)
        self.browser.cookies[settings.AUTH_REFRESH_COOKIE] = old_raw
        self.assertEqual(send(self.browser, "/api/auth/refresh/").status_code, 401)
        self.assertEqual(send(self.browser, "/api/auth/logout/").status_code, 204)

    def test_logout_can_revoke_with_access_when_cookie_is_missing(self):
        access = sign_in(self.browser).json()["access_token"]
        del self.browser.cookies[settings.AUTH_REFRESH_COOKIE]
        self.assertEqual(send(self.browser, "/api/auth/logout/", token=access).status_code, 204)
        self.assertEqual(self.me(access).status_code, 401)

    def test_expired_refresh_and_inactive_user(self):
        sign_in(self.browser)
        token = RefreshToken.objects.get(user=self.user)
        RefreshToken.objects.filter(pk=token.pk).update(created_at=timezone.now() - timedelta(days=31), expires_at=timezone.now() - timedelta(days=1))
        self.assertEqual(send(self.browser, "/api/auth/refresh/").status_code, 401)
        response = sign_in(self.browser)
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.me(response.json()["access_token"]).status_code, 401)
        self.assertEqual(send(self.browser, "/api/auth/refresh/").status_code, 401)
        self.assertEqual(sign_in(self.browser).status_code, 401)

    def test_access_rejects_expiry_bad_signature_claims_and_algorithm(self):
        original = sign_in(self.browser).json()["access_token"]
        claims = jwt.decode(original, options={"verify_signature": False})
        now = int(timezone.now().timestamp())
        variants = [
            (claims, "different-key-not-authorized-00000000000000000000", "HS256"),
            ({**claims, "exp": now - 1, "iat": now - 1000, "nbf": now - 1000}, signing_key(), "HS256"),
            ({**claims, "aud": "other-app"}, signing_key(), "HS256"),
            ({**claims, "iss": "other-server"}, signing_key(), "HS256"),
            ({**claims, "token_type": "refresh"}, signing_key(), "HS256"),
            (claims, "", "none"),
        ]
        for payload, key, algorithm in variants:
            self.assertEqual(self.me(jwt.encode(payload, key, algorithm=algorithm)).status_code, 401)
        missing = dict(claims)
        missing.pop("exp")
        self.assertEqual(self.me(jwt.encode(missing, signing_key(), algorithm="HS256")).status_code, 401)

    @override_settings(AUTH_LOGIN_ACCOUNT_LIMIT=2, AUTH_LOGIN_IP_LIMIT=100)
    def test_login_failures_are_limited_and_generic(self):
        wrong = {"email": self.user.email, "password": "wrong"}
        self.assertEqual(send(self.browser, "/api/auth/login/", wrong).status_code, 401)
        self.assertEqual(send(self.browser, "/api/auth/login/", wrong).status_code, 401)
        self.assertEqual(sign_in(self.browser).status_code, 429)
        missing = send(self.browser, "/api/auth/login/", {"email": "missing@example.test", "password": "wrong"})
        self.assertEqual(missing.json()["message"], "Неверный email или пароль.")

    def test_secret_and_public_routes_are_not_exposed(self):
        for path in ["/backend/.django-secret-key", "/.django-secret-key", "/api/public/builds/", "/api/public/builds/anything/"]:
            response = self.browser.get(path)
            self.assertEqual(response.status_code, 404)
            self.assertNotIn(settings.SECRET_KEY, response.content.decode())


class PrivateBuildTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="owner", email="owner@example.test", password=PASSWORD)
        cls.other = User.objects.create_user(username="other", email="other@example.test", password=PASSWORD)

    def setUp(self):
        self.browser = client()
        self.access = sign_in(self.browser).json()["access_token"]

    def test_private_build_create_read_update_delete(self):
        response = send(self.browser, "/api/builds/", {"title": "Мой ПК"}, token=self.access)
        self.assertEqual(response.status_code, 201)
        identifier = response.json()["id"]
        self.assertFalse(PcBuild.objects.get(pk=identifier).is_public)
        path = f"/api/builds/{identifier}/"
        own = self.browser.get("/api/builds/", HTTP_AUTHORIZATION="Bearer " + self.access)
        self.assertEqual(own.json()["total"], 1)
        self.assertEqual(own["Cache-Control"], "no-store")
        changed = send(self.browser, path, {"title": "Обновлённый ПК"}, method="patch", token=self.access)
        self.assertEqual(changed.json()["title"], "Обновлённый ПК")
        self.assertEqual(send(self.browser, path, method="delete", token=self.access).status_code, 204)
        self.assertFalse(PcBuild.objects.filter(pk=identifier).exists())

    def test_foreign_build_is_hidden_and_ownership_cannot_be_overridden(self):
        other_build = PcBuild.objects.create(user=self.other, title="Private")
        path = f"/api/builds/{other_build.pk}/"
        self.assertEqual(self.browser.get(path, HTTP_AUTHORIZATION="Bearer " + self.access).status_code, 404)
        self.assertEqual(send(self.browser, path, {"title": "Changed"}, method="patch", token=self.access).status_code, 404)
        self.assertEqual(send(self.browser, path, method="delete", token=self.access).status_code, 404)
        self.assertEqual(self.browser.get("/api/builds/", HTTP_AUTHORIZATION="Bearer " + self.access).json()["total"], 0)
        for extra in [{"user_id": str(self.other.pk)}, {"is_public": True}, {"is_compatible": True}]:
            self.assertEqual(send(self.browser, "/api/builds/", {"title": "Test", **extra}, token=self.access).status_code, 422)

    def test_mutations_require_both_access_and_csrf(self):
        bare = Client(enforce_csrf_checks=True)
        response = bare.post("/api/builds/", data='{"title":"Test"}', content_type="application/json", HTTP_AUTHORIZATION="Bearer " + self.access)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(send(self.browser, "/api/builds/", {"title": "Test"}).status_code, 401)
        self.assertEqual(send(self.browser, "/api/builds/", {"title": "Test", "ram_count": 1}, token=self.access).status_code, 422)
        self.assertEqual(send(self.browser, "/api/builds/", {"title": "Test", "ram_count": True}, token=self.access).status_code, 422)


class ConcurrentRefreshTests(TransactionTestCase):
    def test_concurrent_replay_revokes_entire_family_without_deadlock(self):
        User.objects.create_user(username="owner", email="owner@example.test", password=PASSWORD)
        original = client()
        signed = sign_in(original)
        raw = original.cookies[settings.AUTH_REFRESH_COOKIE].value
        browsers = [client(), client()]
        for browser in browsers:
            browser.cookies[settings.AUTH_REFRESH_COOKIE] = raw
        barrier = Barrier(2)

        def attempt(browser):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return send(browser, "/api/auth/refresh/").status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = sorted(pool.map(attempt, browsers))
        self.assertEqual(statuses, [200, 401])
        self.assertFalse(RefreshToken.objects.filter(revoked_at__isnull=True).exists())
        self.assertEqual(original.get("/api/auth/me/", HTTP_AUTHORIZATION="Bearer " + signed.json()["access_token"]).status_code, 401)
