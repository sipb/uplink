"""
Interim implementation of student-only rooms.

Long-term we want to make a more general plug-in which also works
with Moira lists, servers, etc: https://github.com/sipb/uplink/issues/104

oh important note HMMMM. This only works for our own users, not for federated users
People can still join from other homeservers.
"""

from dataclasses import dataclass
from dataclasses_json import dataclass_json
from twisted.web.resource import Resource
from twisted.web.server import Request
from synapse.module_api import ModuleApi, NOT_SPAM
from synapse.module_api.errors import ConfigError, Codes

EVENT_NAME = 'edu.mit.sipb.student_only'

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
        # Also relies on implementation details, but it also means we could in theory also use
        # Synapse's database to store our own stuff without abusing the external ID mapping
        external_ids = await self.api._store.get_external_ids_by_user(user)
        for auth_provider, id in external_ids:
            if auth_provider == 'affiliation':
                # The second half is superfluous and only exists because we are hacking
                # the external ID system to store affiliations when it's not what it
                # was made for (requires unique values since it is for logging in)
                return id.split('|')[0]

    async def is_mit_student(self, user: str) -> bool:
        affiliation = await self.get_affiliation(user)
        print(f"[uplink_synapse_module] {user}'s affiliation is {affiliation}")
        return affiliation == 'student@mit.edu'

    async def user_may_join_room(self, user: str, room: str, is_invited: bool):
        # We are choosing to use the empty string as state key since we don't need one
        event_key = (EVENT_NAME, '')
        # This callback doesn't directly give us the room state,
        # but we can retrieve it
        state = await self.api.get_room_state(room, [event_key])
        if event_key not in state:
            # We only care about rooms which are explicitly declared as student-only
            return NOT_SPAM
        
        print("[uplink_synapse_module] user_may_join_room called on", user, "and", room)
        # Allow invited users to join if the config says so
        if self.config.allow_invited and is_invited:
            print("[uplink_synapse_module]", "user was invited, accepting")
            return NOT_SPAM
        if await self.is_mit_student(user):
          return NOT_SPAM
        
        return Codes.FORBIDDEN
    
    # TODO user_may_invite to reflect the same behavior
    # since we have allow_invited to true, right now we don't care about this case
    # (inviting anyone is allowed since they can accept the invite)
    # and we might as well just build the general-case module