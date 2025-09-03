import pytest
from django.contrib.auth import get_user_model
from commerce.models import LegalEntity, MembershipRequest, LegalEntityCreationRequest, LegalEntityMembership

pytestmark = pytest.mark.django_db


def _staff(client, db):
    U = get_user_model()
    u = U.objects.create_user(username="staff", password="pass", is_staff=True)
    client.force_login(u)
    return u


def test_admin_membership_approve_reject(client, db):
    u = _staff(client, db)
    user2 = get_user_model().objects.create_user(username="u2", password="pass")
    le = LegalEntity.objects.create(name="LE1", inn="5408131553", bik="044525225", checking_account="40702810900000000003")
    mr = MembershipRequest.objects.create(applicant=user2, legal_entity=le)
    # JWT for staff user
    from rest_framework_simplejwt.tokens import AccessToken
    token = str(AccessToken.for_user(u))
    client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    r1 = client.post(f"/api/commerce/admin/membership-requests/{mr.id}/approve/")
    assert r1.status_code == 200
    r2 = client.post(f"/api/commerce/admin/membership-requests/{mr.id}/reject/")
    # second change should be 400 as already processed
    assert r2.status_code == 400


def test_admin_entity_create_approve_reject(client, db):
    u = _staff(client, db)
    user2 = get_user_model().objects.create_user(username="u3", password="pass")
    cr = LegalEntityCreationRequest.objects.create(applicant=user2, name="N", inn="7707083893", bik="044525225", checking_account="40702810900000000001")
    from rest_framework_simplejwt.tokens import AccessToken
    token = str(AccessToken.for_user(u))
    client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    r1 = client.post(f"/api/commerce/admin/entity-creation-requests/{cr.id}/approve/")
    assert r1.status_code == 200
    r2 = client.post(f"/api/commerce/admin/entity-creation-requests/{cr.id}/reject/")
    assert r2.status_code == 400
