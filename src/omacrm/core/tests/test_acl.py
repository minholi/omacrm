from django.test import TestCase

from omacrm.core.models import Role, Team, TeamUser, User
from omacrm.core.services.acl import AccessLevel, AclService


class AclServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("u1", "u1@example.com", "pw")
        self.role = Role.objects.create(
            name="Sales",
            data={"Team": {"read": AccessLevel.OWN, "edit": AccessLevel.NO}},
        )
        self.user.roles.add(self.role)
        self.team = Team.objects.create(name="Team A")

    def test_superuser_has_full_access(self):
        superuser = User.objects.create_superuser("root", "root@example.com", "pw")
        self.assertEqual(AclService.level(superuser, "Team"), AccessLevel.YES)
        self.assertTrue(AclService.check(superuser, "Team", "delete"))
        self.assertEqual(AclService.forbidden_fields(superuser, "Team"), set())

    def test_default_level_without_roles(self):
        other = User.objects.create_user("u2", "u2@example.com", "pw")
        self.assertEqual(AclService.level(other, "Team"), AccessLevel.NO)
        self.assertEqual(AclService.level(other, "Unknown"), AccessLevel.ALL)

    def test_role_levels(self):
        self.assertEqual(AclService.level(self.user, "Team", "read"), AccessLevel.OWN)
        self.assertEqual(AclService.level(self.user, "Team", "edit"), AccessLevel.NO)
        self.assertFalse(AclService.check(self.user, "Team", "edit"))

    def test_highest_level_wins_across_team_roles(self):
        team_role = Role.objects.create(
            name="Team role", data={"Team": {"read": AccessLevel.TEAM}}
        )
        self.team.roles.add(team_role)
        TeamUser.objects.create(team=self.team, user=self.user)
        self.assertEqual(AclService.level(self.user, "Team", "read"), AccessLevel.TEAM)

    def test_field_level_acl(self):
        user = User.objects.create_user("u3", "u3@example.com", "pw")
        role = Role.objects.create(
            name="Restricted",
            data={"Team": {"read": AccessLevel.ALL}},
            field_data={"Team": {"description": AccessLevel.NO}},
        )
        user.roles.add(role)
        self.assertFalse(AclService.check_field(user, "Team", "description", "read"))
        self.assertTrue(AclService.check_field(user, "Team", "name", "read"))

    def test_scope_queryset_levels(self):
        no_access = User.objects.create_user("u4", "u4@example.com", "pw")
        self.assertEqual(AclService.scope_queryset(no_access, "Team", Team.objects.all()).count(), 0)

        full_access_user = User.objects.create_user("u5", "u5@example.com", "pw")
        full_role = Role.objects.create(
            name="Full", data={"Team": {"read": AccessLevel.ALL}}
        )
        full_access_user.roles.add(full_role)
        self.assertEqual(
            AclService.scope_queryset(full_access_user, "Team", Team.objects.all()).count(),
            Team.objects.count(),
        )
