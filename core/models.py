import uuid
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.db import models
from django.db.models import Q, F
from django.db.models.functions import Lower


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=40, unique=True, validators=[RegexValidator(r"^[A-Za-z0-9_]{3,40}$")])
    email = models.EmailField(unique=True)

    class Meta:
        db_table = "users"
        constraints = [
            models.UniqueConstraint(Lower("username"), name="users_username_ci"),
            models.UniqueConstraint(Lower("email"), name="users_email_ci"),
        ]


class RefreshToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    family_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    token_hash = models.CharField(max_length=64, unique=True, validators=[RegexValidator(r"^[0-9a-f]{64}$")])
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "refresh_tokens"
        constraints = [models.CheckConstraint(condition=Q(expires_at__gt=F("created_at")), name="refresh_expiry")]


class ComponentCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    code_slug = models.SlugField(unique=True)
    icon_name = models.CharField(max_length=80, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "component_categories"
        ordering = ["display_order"]


class Component(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(ComponentCategory, on_delete=models.PROTECT)
    name = models.CharField(max_length=255)
    source_url = models.URLField(max_length=1000, blank=True)
    spec_note = models.TextField(blank=True)

    class Meta:
        abstract = True


class Processor(Component):
    socket = models.CharField(max_length=80)
    base_tdp = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    supported_memory_type = models.CharField(max_length=80)

    class Meta:
        db_table = "processors"
        constraints = [
            models.CheckConstraint(condition=Q(base_tdp__gt=0), name="processors_base_tdp_positive"),
        ]


class Motherboard(Component):
    socket = models.CharField(max_length=80)
    form_factor = models.CharField(max_length=80)
    ram_type = models.CharField(max_length=80)
    ram_slots_count = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        db_table = "motherboards"
        constraints = [
            models.CheckConstraint(condition=Q(ram_slots_count__gt=0), name="motherboards_ram_slots_count_positive"),
        ]


class GraphicsCard(Component):
    length_mm = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    tdp = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    recommended_psu_wattage = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        db_table = "graphics_cards"
        constraints = [
            models.CheckConstraint(condition=Q(length_mm__gt=0), name="graphics_cards_length_mm_positive"),
            models.CheckConstraint(condition=Q(tdp__gt=0), name="graphics_cards_tdp_positive"),
            models.CheckConstraint(condition=Q(recommended_psu_wattage__gt=0), name="graphics_cards_recommended_psu_wattage_positive"),
        ]


class RamModule(Component):
    memory_type = models.CharField(max_length=80)
    capacity_gb = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    height_mm = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        db_table = "ram_modules"
        constraints = [
            models.CheckConstraint(condition=Q(capacity_gb__gt=0), name="ram_modules_capacity_gb_positive"),
            models.CheckConstraint(condition=Q(height_mm__gt=0), name="ram_modules_height_mm_positive"),
        ]


class PowerSupply(Component):
    wattage = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    form_factor = models.CharField(max_length=80)
    efficiency_certificate = models.CharField(max_length=80)

    class Meta:
        db_table = "power_supplies"
        constraints = [
            models.CheckConstraint(condition=Q(wattage__gt=0), name="power_supplies_wattage_positive"),
        ]


class PcCase(Component):
    supported_motherboard_formats = ArrayField(models.CharField(max_length=80))
    max_gpu_length_mm = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    max_cooler_height_mm = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        db_table = "pc_cases"
        constraints = [
            models.CheckConstraint(condition=Q(max_gpu_length_mm__gt=0), name="pc_cases_max_gpu_length_mm_positive"),
            models.CheckConstraint(condition=Q(max_cooler_height_mm__gt=0), name="pc_cases_max_cooler_height_mm_positive"),
        ]


class Cooler(Component):
    max_tdp_dissipation = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    height_mm = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    supported_sockets = ArrayField(models.CharField(max_length=80))

    class Meta:
        db_table = "coolers"
        constraints = [
            models.CheckConstraint(condition=Q(max_tdp_dissipation__gt=0), name="coolers_max_tdp_dissipation_positive"),
            models.CheckConstraint(condition=Q(height_mm__gt=0), name="coolers_height_mm_positive"),
        ]


class PcBuild(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=120)
    description = models.CharField(max_length=2000, blank=True)
    is_public = models.BooleanField(default=False)
    share_slug = models.SlugField(max_length=64, unique=True, default=uuid.uuid4)
    is_compatible = models.BooleanField(default=False)
    total_tdp = models.PositiveSmallIntegerField(null=True, blank=True)
    cpu = models.ForeignKey(Processor, null=True, blank=True, on_delete=models.SET_NULL)
    motherboard = models.ForeignKey(Motherboard, null=True, blank=True, on_delete=models.SET_NULL)
    gpu = models.ForeignKey(GraphicsCard, null=True, blank=True, on_delete=models.SET_NULL)
    ram = models.ForeignKey(RamModule, null=True, blank=True, on_delete=models.SET_NULL)
    ram_count = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(16)])
    psu = models.ForeignKey(PowerSupply, null=True, blank=True, on_delete=models.SET_NULL)
    case = models.ForeignKey(PcCase, null=True, blank=True, on_delete=models.SET_NULL)
    cooler = models.ForeignKey(Cooler, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pc_builds"
        constraints = [models.CheckConstraint(
            condition=Q(ram__isnull=True, ram_count=0) | Q(ram__isnull=False, ram_count__gte=1, ram_count__lte=16),
            name="build_ram_count",
        )]


class BuildComment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    build = models.ForeignKey(PcBuild, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.CharField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "build_comments"


class Advertisement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    advertiser_name = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    image_path = models.CharField(max_length=500)
    target_url = models.URLField(max_length=1000, validators=[RegexValidator(r"^https://")])
    placement = models.CharField(max_length=20, choices=[("catalog", "Каталог"), ("public_build", "Сборка")])
    is_active = models.BooleanField(default=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()

    class Meta:
        db_table = "advertisements"
        constraints = [models.CheckConstraint(condition=Q(ends_at__gt=F("starts_at")), name="ad_period")]


class LoginThrottle(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    failures = models.PositiveSmallIntegerField(default=0)
    window_started = models.DateTimeField()

    class Meta:
        db_table = "login_throttle"
