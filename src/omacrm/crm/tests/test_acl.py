from djmoney.money import Money
from django.test import TestCase

from omacrm.core.services.acl import AccessLevel, AclService
from omacrm.core.models import Role, Team, TeamUser, User
from omacrm.crm.models import Account


class CrmAclTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("owner", "owner@example.com", "pw")
        self.other = User.objects.create_user("other", "other@example.com", "pw")
        self.role = Role.objects.create(
            name="Owner",
            data={
                "Account": {
                    "read": AccessLevel.OWN,
                    "edit": AccessLevel.OWN,
                    "create": AccessLevel.YES,
                    "delete": AccessLevel.NO,
                }
            },
        )
        self.user.roles.add(self.role)
        self.own = Account.objects.create(name="Own Account", assigned_user=self.user)
        self.foreign = Account.objects.create(
            name="Foreign Account", assigned_user=self.other
        )

    def test_own_scoping(self):
        queryset = AclService.scope_queryset(self.user, "Account", Account.objects.all())
        self.assertIn(self.own, queryset)
        self.assertNotIn(self.foreign, queryset)
        self.assertTrue(AclService.check(self.user, "Account", "edit", self.own))
        self.assertFalse(AclService.check(self.user, "Account", "edit", self.foreign))

    def test_team_scoping(self):
        team_role = Role.objects.create(
            name="Team", data={"Account": {"read": AccessLevel.TEAM}}
        )
        team = Team.objects.create(name="Sales")
        team.roles.add(team_role)
        TeamUser.objects.create(team=team, user=self.user)
        self.foreign.teams.add(team)
        queryset = AclService.scope_queryset(self.user, "Account", Account.objects.all())
        self.assertIn(self.foreign, queryset)

    def test_no_delete_permission(self):
        self.assertFalse(
            AclService.check(self.user, "Account", "delete", self.own)
        )
