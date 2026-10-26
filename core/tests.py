from io import StringIO
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from .models import User, ComponentCategory, Processor, Motherboard, GraphicsCard, RamModule, PowerSupply, PcCase, Cooler, PcBuild, BuildComment


class DatabaseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog", stdout=StringIO())
        cls.user = User.objects.create_user(username="Tester", email="tester@example.test", password="example-password")

    def test_seed_is_repeatable_and_preserves_existing_data(self):
        cpu = Processor.objects.first()
        cpu.name = "Changed name"
        cpu.save()
        call_command("seed_catalog", stdout=StringIO())
        self.assertEqual(ComponentCategory.objects.count(), 7)
        for model in [Processor, Motherboard, GraphicsCard, RamModule, PowerSupply, PcCase, Cooler]:
            self.assertEqual(model.objects.count(), 3)
        cpu.refresh_from_db()
        self.assertEqual(cpu.name, "Changed name")
        self.assertTrue(self.user.check_password("example-password"))

    def test_case_insensitive_identity(self):
        for username, email in [("tester", "other@example.test"), ("Other", "TESTER@example.test")]:
            with self.assertRaises(IntegrityError), transaction.atomic():
                User.objects.create_user(username=username, email=email)

    def test_ram_deletion_preserves_build_and_clears_slot(self):
        ram = RamModule.objects.first()
        build = PcBuild.objects.create(user=self.user, title="Test", ram=ram, ram_count=2, is_compatible=True)
        RamModule.objects.filter(pk=ram.pk).delete()
        build.refresh_from_db()
        self.assertIsNone(build.ram_id)
        self.assertEqual(build.ram_count, 0)
        self.assertFalse(build.is_compatible)
        BuildComment.objects.create(build=build, user=self.user, content="Test")
        build.delete()
        self.assertEqual(BuildComment.objects.count(), 0)

    def test_numeric_constraints_and_category_protection(self):
        cpu = Processor.objects.first()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Processor.objects.filter(pk=cpu.pk).update(base_tdp=0)
        with self.assertRaises(IntegrityError), transaction.atomic():
            PcBuild.objects.create(user=self.user, title="Invalid", ram_count=2)
        with self.assertRaises(ProtectedError):
            cpu.category.delete()


class CatalogApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog", stdout=StringIO())

    def test_categories_and_paginated_components(self):
        categories = self.client.get("/api/categories/").json()["items"]
        self.assertEqual(len(categories), 7)
        self.assertEqual(categories[0]["code_slug"], "cpu")
        first = self.client.get("/api/components/").json()
        second = self.client.get("/api/components/?page=2").json()
        self.assertEqual(first["total"], 21)
        self.assertEqual(len(first["items"]), 20)
        self.assertEqual(len(second["items"]), 1)
        ids = [item["id"] for item in first["items"] + second["items"]]
        self.assertEqual(len(set(ids)), 21)
        self.assertTrue(all("category" in item and "category_id" in item for item in first["items"]))

    def test_search_filters_and_details_read_database(self):
        cpu = Processor.objects.first()
        cpu.name = "Unique database processor"
        cpu.save()
        response = self.client.get("/api/components/", {"category": "cpu", "q": "database"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 1)
        self.assertEqual(response.json()["items"][0]["id"], str(cpu.pk))
        detail = self.client.get(f"/api/components/{cpu.pk}/").json()
        self.assertEqual(detail["name"], "Unique database processor")
        self.assertEqual(detail["socket"], cpu.socket)
        case = PcCase.objects.first()
        self.assertIsInstance(self.client.get(f"/api/components/{case.pk}/").json()["supported_motherboard_formats"], list)

    def test_bad_parameters_and_missing_component(self):
        for params in [{"category": "unknown"}, {"page": "oops"}, {"page": "0"},
                       {"page_size": "101"}, {"page_size": "0"}, {"unknown": "x"}]:
            response = self.client.get("/api/components/", params)
            self.assertEqual(response.status_code, 422)
            self.assertIn("code", response.json())
        for identifier in ["invalid", "00000000-0000-0000-0000-000000000000"]:
            self.assertEqual(self.client.get(f"/api/components/{identifier}/").status_code, 404)
        self.assertEqual(self.client.post("/api/components/").status_code, 405)

    def test_database_failure_returns_safe_error(self):
        from unittest.mock import patch
        from django.db import OperationalError
        with patch("core.views.ComponentCategory.objects.order_by", side_effect=OperationalError("secret connection details")):
            response = self.client.get("/api/categories/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "DATABASE_UNAVAILABLE")
        self.assertNotIn("secret", response.content.decode())

    def test_only_frontend_files_are_served(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from django.test import override_settings
        with TemporaryDirectory() as directory, override_settings(FRONTEND_DIR=directory):
            root = Path(directory)
            content = b"<!doctype html><title>Frontend</title>"
            (root / "index.html").write_bytes(content)
            for name in ["style.css", "app.js", "auth.js", "compatibility.js"]:
                file = root / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text("frontend asset", encoding="utf-8")
                response = self.client.get("/" + name)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(b"".join(response.streaming_content), b"frontend asset")
            response = self.client.get("/")
            self.assertEqual(b"".join(response.streaming_content), content)
            for url in ["/backend/config/settings.py", "/data/components.js", "/data/builds.js", "/docs/database.md", "/core/fixtures/components.json"]:
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_api_and_catalog_seed_do_not_require_frontend(self):
        from tempfile import TemporaryDirectory
        from django.test import override_settings
        with TemporaryDirectory() as directory, override_settings(FRONTEND_DIR=directory):
            call_command("seed_catalog", stdout=StringIO())
            self.assertEqual(self.client.get("/api/categories/").status_code, 200)
            self.assertEqual(self.client.get("/api/components/").json()["total"], 21)
            self.assertEqual(self.client.get("/").status_code, 503)
            self.assertEqual(self.client.get("/app.js").status_code, 404)
