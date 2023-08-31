"""
Interim implementation of student-only rooms.

Long-term we want to make a more general plug-in which also works
with Moira lists, servers, etc: https://github.com/sipb/uplink/issues/104
"""

from dataclasses import dataclass
from dataclasses_json import dataclass_json
from twisted.web.resource import Resource
from twisted.web.server import Request
from synapse.module_api import ModuleApi, NOT_SPAM
from synapse.module_api.errors import ConfigError, Codes


@dataclass_json
@dataclass
class Config:
    # Allow invited users to join
    allow_invited: bool = True


class UplinkStudentOnlyRooms:
    def __init__(self, config: Config, api: ModuleApi):
        self.api = api
        self.api.register_spam_checker_callbacks(
            user_may_join_room=self.user_may_join_room,
        )
        self.config = config

    @staticmethod
    def parse_config(config: dict) -> dict:
        try:
            return Config.from_dict(config)
        except Exception as e:
            raise ConfigError(f'{e}')
        
    async def get_affiliation(self, user: str) -> str | None:
        """
        Gets the affiliation of a user by MXID. Returns something like
        student@mit.edu or None if it cannot be found
        """
        # The function we're calling calls the DB directly (through a helper function).
        # Also relies on implementation details, but it also means we could use Synapse's
        # database to store our own stuff
        external_ids = await self.api._store.get_external_ids_by_user(user)
        for auth_provider, id in external_ids:
            if auth_provider == 'affiliation':
                return id.split('|')[0]

    async def is_mit_student(self, user: str) -> bool:
        affiliation = await self.get_affiliation(user)
        return affiliation == 'student@mit.edu'

    async def user_may_join_room(self, user: str, room: str, is_invited: bool):
        # Allow invited users to join if the config says so
        if self.config.allow_invited and is_invited:
            return NOT_SPAM
        if self.is_mit_student(user):
          return NOT_SPAM
        return Codes.FORBIDDEN
