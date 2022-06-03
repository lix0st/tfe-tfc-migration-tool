"""
Module for Terraform Enterprise/Cloud Migration Worker: Teams.
"""
import os
from .base_worker import TFCMigratorBaseWorker

TFE_WS_SOURCE = os.getenv("TFE_WS_SOURCE", "")

class TeamsWorker(TFCMigratorBaseWorker):
    """
    A class to represent the worker that will migrate all teams from one
    TFC/E org to another TFC/E org.
    """

    _api_module_used = "teams"
    _required_entitlements = ["teams"]

    def migrate_all(self):
        """
        Function to migrate all teams from one TFC/E org to another TFC/E org.
        """

        self._logger.info("Migrating teams...")

        teams_map = {}
        target_teams_data = {}
        source_teams = []

        if TFE_WS_SOURCE:
            # Migrate only teams that are configured in team access for the workspace
            source_workspace_team_filters = [
                {
                    "keys": ["workspace", "id"],
                    "value": self._api_source.workspaces.show(workspace_name=TFE_WS_SOURCE)["data"]["id"]
                }
            ]

            # Pull teams
            source_workspace_teams = self._api_source.team_access.list(\
                filters=source_workspace_team_filters)["data"]

            for source_workspace_team in source_workspace_teams:
                team = self._api_source.teams.show(source_workspace_team["relationships"]["team"]["data"]["id"])["data"]
                source_teams.append(team)

        else:

            # Fetch teams from existing org
            source_teams = self._api_source.teams.list_all()["data"]

        target_teams = self._api_target.teams.list_all()["data"]

        for target_team in target_teams:
            target_teams_data[target_team["attributes"]["name"]] = target_team["id"]

        new_org_owners_team_id = None

        for source_team in source_teams:
            if source_team["attributes"]["name"] == "owners":
                new_org_owners_team_id = source_team["id"]
                break

        for source_team in source_teams:
            source_team_name = source_team["attributes"]["name"]

            if source_team_name in target_teams_data:
                teams_map[source_team["id"]] = target_teams_data[source_team_name]
                self._logger.info("Team: %s, exists. Skipped.", source_team_name)
                continue

            if source_team_name == "owners":
                # No need to create a team, it's the owners team
                teams_map[source_team["id"]] = new_org_owners_team_id
            else:
                # Build the new team payload
                new_team_payload = {
                    "data": {
                        "type": "teams",
                        "attributes": {
                            "name": source_team_name,
                            "organization-access": {
                                "manage-workspaces": \
                                    source_team["attributes"]\
                                        ["organization-access"]["manage-workspaces"],
                                "manage-policies": \
                                    source_team["attributes"]\
                                        ["organization-access"]["manage-policies"],
                                "manage-vcs-settings": \
                                    source_team["attributes"]\
                                        ["organization-access"]["manage-vcs-settings"]
                            }
                        }
                    }
                }

                # Create team in the target org
                new_team = self._api_target.teams.create(new_team_payload)
                self._logger.info("Team %s, created.", source_team_name)

                # Build Team ID Map
                teams_map[source_team["id"]] = new_team["data"]["id"]

        self._logger.info("Teams migrated.")

        return teams_map


    def delete_all_from_target(self):
        """
        Function to delete all teams from the target TFC/E org.
        """

        self._logger.info("Deleting teams...")

        teams = self._api_target.teams.list()["data"]
        if teams:
            for team in teams:
                team_name = team["attributes"]["name"]
                if team_name != "owners":
                    self._api_target.teams.destroy(team["id"])
                    self._logger.info("Team: %s deleted.", team_name)

        self._logger.info("Teams deleted.")
