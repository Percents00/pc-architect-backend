import django.contrib.auth.models
import django.contrib.postgres.fields
import django.core.validators
import django.db.models.deletion
import django.db.models.functions.text
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='ComponentCategory',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=120)),
                ('code_slug', models.SlugField(unique=True)),
                ('icon_name', models.CharField(blank=True, max_length=80)),
                ('display_order', models.PositiveSmallIntegerField(default=0)),
            ],
            options={
                'db_table': 'component_categories',
                'ordering': ['display_order'],
            },
        ),
        migrations.CreateModel(
            name='User',
            fields=[
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('first_name', models.CharField(blank=True, max_length=150, verbose_name='first name')),
                ('last_name', models.CharField(blank=True, max_length=150, verbose_name='last name')),
                ('is_staff', models.BooleanField(default=False, help_text='Designates whether the user can log into this admin site.', verbose_name='staff status')),
                ('is_active', models.BooleanField(default=True, help_text='Designates whether this user should be treated as active. Unselect this instead of deleting accounts.', verbose_name='active')),
                ('date_joined', models.DateTimeField(default=django.utils.timezone.now, verbose_name='date joined')),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('username', models.CharField(max_length=40, unique=True, validators=[django.core.validators.RegexValidator('^[A-Za-z0-9_]{3,40}$')])),
                ('email', models.EmailField(max_length=254, unique=True)),
                ('groups', models.ManyToManyField(blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', related_name='user_set', related_query_name='user', to='auth.group', verbose_name='groups')),
                ('user_permissions', models.ManyToManyField(blank=True, help_text='Specific permissions for this user.', related_name='user_set', related_query_name='user', to='auth.permission', verbose_name='user permissions')),
            ],
            options={
                'db_table': 'users',
            },
            managers=[
                ('objects', django.contrib.auth.models.UserManager()),
            ],
        ),
        migrations.CreateModel(
            name='Advertisement',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('advertiser_name', models.CharField(max_length=255)),
                ('title', models.CharField(max_length=255)),
                ('image_path', models.CharField(max_length=500)),
                ('target_url', models.URLField(max_length=1000, validators=[django.core.validators.RegexValidator('^https://')])),
                ('placement', models.CharField(choices=[('catalog', 'Каталог'), ('public_build', 'Сборка')], max_length=20)),
                ('is_active', models.BooleanField(default=True)),
                ('starts_at', models.DateTimeField()),
                ('ends_at', models.DateTimeField()),
            ],
            options={
                'db_table': 'advertisements',
                'constraints': [models.CheckConstraint(condition=models.Q(('ends_at__gt', models.F('starts_at'))), name='ad_period')],
            },
        ),
        migrations.CreateModel(
            name='Cooler',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('source_url', models.URLField(blank=True, max_length=1000)),
                ('spec_note', models.TextField(blank=True)),
                ('max_tdp_dissipation', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ('height_mm', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ('supported_sockets', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=80), size=None)),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.componentcategory')),
            ],
            options={
                'db_table': 'coolers',
            },
        ),
        migrations.CreateModel(
            name='GraphicsCard',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('source_url', models.URLField(blank=True, max_length=1000)),
                ('spec_note', models.TextField(blank=True)),
                ('length_mm', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ('tdp', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ('recommended_psu_wattage', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.componentcategory')),
            ],
            options={
                'db_table': 'graphics_cards',
            },
        ),
        migrations.CreateModel(
            name='Motherboard',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('source_url', models.URLField(blank=True, max_length=1000)),
                ('spec_note', models.TextField(blank=True)),
                ('socket', models.CharField(max_length=80)),
                ('form_factor', models.CharField(max_length=80)),
                ('ram_type', models.CharField(max_length=80)),
                ('ram_slots_count', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.componentcategory')),
            ],
            options={
                'db_table': 'motherboards',
            },
        ),
        migrations.CreateModel(
            name='PcBuild',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=120)),
                ('description', models.CharField(blank=True, max_length=2000)),
                ('is_public', models.BooleanField(default=False)),
                ('share_slug', models.SlugField(default=uuid.uuid4, max_length=64, unique=True)),
                ('is_compatible', models.BooleanField(default=False)),
                ('total_tdp', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('ram_count', models.PositiveSmallIntegerField(default=0, validators=[django.core.validators.MaxValueValidator(16)])),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('cooler', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.cooler')),
                ('gpu', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.graphicscard')),
                ('motherboard', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.motherboard')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'pc_builds',
            },
        ),
        migrations.CreateModel(
            name='BuildComment',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('content', models.CharField(max_length=2000)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('build', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.pcbuild')),
            ],
            options={
                'db_table': 'build_comments',
            },
        ),
        migrations.CreateModel(
            name='PcCase',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('source_url', models.URLField(blank=True, max_length=1000)),
                ('spec_note', models.TextField(blank=True)),
                ('supported_motherboard_formats', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=80), size=None)),
                ('max_gpu_length_mm', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ('max_cooler_height_mm', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.componentcategory')),
            ],
            options={
                'db_table': 'pc_cases',
            },
        ),
        migrations.AddField(
            model_name='pcbuild',
            name='case',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.pccase'),
        ),
        migrations.CreateModel(
            name='PowerSupply',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('source_url', models.URLField(blank=True, max_length=1000)),
                ('spec_note', models.TextField(blank=True)),
                ('wattage', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ('form_factor', models.CharField(max_length=80)),
                ('efficiency_certificate', models.CharField(max_length=80)),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.componentcategory')),
            ],
            options={
                'db_table': 'power_supplies',
            },
        ),
        migrations.AddField(
            model_name='pcbuild',
            name='psu',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.powersupply'),
        ),
        migrations.CreateModel(
            name='Processor',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('source_url', models.URLField(blank=True, max_length=1000)),
                ('spec_note', models.TextField(blank=True)),
                ('socket', models.CharField(max_length=80)),
                ('base_tdp', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ('supported_memory_type', models.CharField(max_length=80)),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.componentcategory')),
            ],
            options={
                'db_table': 'processors',
            },
        ),
        migrations.AddField(
            model_name='pcbuild',
            name='cpu',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.processor'),
        ),
        migrations.CreateModel(
            name='RamModule',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('source_url', models.URLField(blank=True, max_length=1000)),
                ('spec_note', models.TextField(blank=True)),
                ('memory_type', models.CharField(max_length=80)),
                ('capacity_gb', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ('height_mm', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.componentcategory')),
            ],
            options={
                'db_table': 'ram_modules',
            },
        ),
        migrations.AddField(
            model_name='pcbuild',
            name='ram',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.rammodule'),
        ),
        migrations.CreateModel(
            name='RefreshToken',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('family_id', models.UUIDField(db_index=True, default=uuid.uuid4)),
                ('token_hash', models.CharField(max_length=64, unique=True, validators=[django.core.validators.RegexValidator('^[0-9a-f]{64}$')])),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField()),
                ('used_at', models.DateTimeField(blank=True, null=True)),
                ('revoked_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'refresh_tokens',
            },
        ),
        migrations.AddConstraint(
            model_name='user',
            constraint=models.UniqueConstraint(django.db.models.functions.text.Lower('username'), name='users_username_ci'),
        ),
        migrations.AddConstraint(
            model_name='user',
            constraint=models.UniqueConstraint(django.db.models.functions.text.Lower('email'), name='users_email_ci'),
        ),
        migrations.AddConstraint(
            model_name='cooler',
            constraint=models.CheckConstraint(condition=models.Q(('max_tdp_dissipation__gt', 0)), name='coolers_max_tdp_dissipation_positive'),
        ),
        migrations.AddConstraint(
            model_name='cooler',
            constraint=models.CheckConstraint(condition=models.Q(('height_mm__gt', 0)), name='coolers_height_mm_positive'),
        ),
        migrations.AddConstraint(
            model_name='graphicscard',
            constraint=models.CheckConstraint(condition=models.Q(('length_mm__gt', 0)), name='graphics_cards_length_mm_positive'),
        ),
        migrations.AddConstraint(
            model_name='graphicscard',
            constraint=models.CheckConstraint(condition=models.Q(('tdp__gt', 0)), name='graphics_cards_tdp_positive'),
        ),
        migrations.AddConstraint(
            model_name='graphicscard',
            constraint=models.CheckConstraint(condition=models.Q(('recommended_psu_wattage__gt', 0)), name='graphics_cards_recommended_psu_wattage_positive'),
        ),
        migrations.AddConstraint(
            model_name='motherboard',
            constraint=models.CheckConstraint(condition=models.Q(('ram_slots_count__gt', 0)), name='motherboards_ram_slots_count_positive'),
        ),
        migrations.AddConstraint(
            model_name='pccase',
            constraint=models.CheckConstraint(condition=models.Q(('max_gpu_length_mm__gt', 0)), name='pc_cases_max_gpu_length_mm_positive'),
        ),
        migrations.AddConstraint(
            model_name='pccase',
            constraint=models.CheckConstraint(condition=models.Q(('max_cooler_height_mm__gt', 0)), name='pc_cases_max_cooler_height_mm_positive'),
        ),
        migrations.AddConstraint(
            model_name='powersupply',
            constraint=models.CheckConstraint(condition=models.Q(('wattage__gt', 0)), name='power_supplies_wattage_positive'),
        ),
        migrations.AddConstraint(
            model_name='processor',
            constraint=models.CheckConstraint(condition=models.Q(('base_tdp__gt', 0)), name='processors_base_tdp_positive'),
        ),
        migrations.AddConstraint(
            model_name='rammodule',
            constraint=models.CheckConstraint(condition=models.Q(('capacity_gb__gt', 0)), name='ram_modules_capacity_gb_positive'),
        ),
        migrations.AddConstraint(
            model_name='rammodule',
            constraint=models.CheckConstraint(condition=models.Q(('height_mm__gt', 0)), name='ram_modules_height_mm_positive'),
        ),
        migrations.AddConstraint(
            model_name='pcbuild',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('ram__isnull', True), ('ram_count', 0)), models.Q(('ram__isnull', False), ('ram_count__gte', 1), ('ram_count__lte', 16)), _connector='OR'), name='build_ram_count'),
        ),
        migrations.AddConstraint(
            model_name='refreshtoken',
            constraint=models.CheckConstraint(condition=models.Q(('expires_at__gt', models.F('created_at'))), name='refresh_expiry'),
        ),
    ]
