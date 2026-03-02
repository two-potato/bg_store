from django.db import migrations, models


def seed_and_migrate(apps, schema_editor):
    MembershipRole = apps.get_model('commerce', 'MembershipRole')
    RequestStatus = apps.get_model('commerce', 'RequestStatus')
    LegalEntityMembership = apps.get_model('commerce', 'LegalEntityMembership')
    MembershipRequest = apps.get_model('commerce', 'MembershipRequest')
    LegalEntityCreationRequest = apps.get_model('commerce', 'LegalEntityCreationRequest')

    roles = {
        'owner': 'Владелец',
        'admin': 'Админ',
        'manager': 'Менеджер',
        'viewer': 'Наблюдатель',
    }
    statuses = {
        'pending': 'На рассмотрении',
        'approved': 'Одобрено',
        'rejected': 'Отклонено',
    }
    for code, name in roles.items():
        MembershipRole.objects.get_or_create(code=code, defaults={'name': name})
    for code, name in statuses.items():
        RequestStatus.objects.get_or_create(code=code, defaults={'name': name})

    # Migrate membership roles
    for m in LegalEntityMembership.objects.all():
        # Old schema had a char field 'role'
        code = getattr(m, 'role', None)
        if code:
            role = MembershipRole.objects.get(code=code)
            setattr(m, 'role_new', role)
            m.save(update_fields=['role_new'])

    # Migrate request statuses
    for mr in MembershipRequest.objects.all():
        code = getattr(mr, 'status', None)
        if code:
            st = RequestStatus.objects.get(code=code)
            setattr(mr, 'status_new', st)
            mr.save(update_fields=['status_new'])
    for cr in LegalEntityCreationRequest.objects.all():
        code = getattr(cr, 'status', None)
        if code:
            st = RequestStatus.objects.get(code=code)
            setattr(cr, 'status_new', st)
            cr.save(update_fields=['status_new'])


class Migration(migrations.Migration):
    dependencies = [
        ('commerce', '0004_legalentity_members'),
    ]

    operations = [
        migrations.CreateModel(
            name='MembershipRole',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('code', models.CharField(max_length=32, unique=True)),
                ('name', models.CharField(max_length=64)),
            ],
        ),
        migrations.CreateModel(
            name='RequestStatus',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('code', models.CharField(max_length=32, unique=True)),
                ('name', models.CharField(max_length=64)),
            ],
        ),
        # Add new fields alongside old
        migrations.AddField(
            model_name='legalentitymembership',
            name='role_new',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.PROTECT, to='commerce.membershiprole'),
        ),
        migrations.AddField(
            model_name='membershiprequest',
            name='status_new',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.PROTECT, to='commerce.requeststatus'),
        ),
        migrations.AddField(
            model_name='legalentitycreationrequest',
            name='status_new',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.PROTECT, to='commerce.requeststatus'),
        ),
        migrations.RunPython(seed_and_migrate, migrations.RunPython.noop),
        # Drop old char fields
        migrations.RemoveField(
            model_name='legalentitymembership',
            name='role',
        ),
        migrations.RemoveField(
            model_name='membershiprequest',
            name='status',
        ),
        migrations.RemoveField(
            model_name='legalentitycreationrequest',
            name='status',
        ),
        # Rename new to final names
        migrations.RenameField(
            model_name='legalentitymembership',
            old_name='role_new',
            new_name='role',
        ),
        migrations.RenameField(
            model_name='membershiprequest',
            old_name='status_new',
            new_name='status',
        ),
        migrations.RenameField(
            model_name='legalentitycreationrequest',
            old_name='status_new',
            new_name='status',
        ),
    ]
