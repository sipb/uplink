from dataclasses import dataclass
from dataclasses_json import dataclass_json
from twisted.web.resource import Resource
from twisted.web.server import Request
from synapse.module_api import ModuleApi
from synapse.module_api.errors import ConfigError

@dataclass_json
@dataclass
class Config:
    plain_text: str
    html: str = None
    skip_prefixes: tuple[str] = ()


class UplinkFirstLoginModule:
    def __init__(self, config: Config, api: ModuleApi):
        self.api = api
        self.api.register_account_validity_callbacks(
            on_user_registration=self.on_user_registration,
        )
        self.config = config

    @staticmethod
    def parse_config(config: dict) -> dict:
        try:
            return Config.from_dict(config)
        except Exception as e:
            raise ConfigError(f'{e}')

    async def on_user_registration(self, user: str) -> None:
        print(f'{user} registered!')

        for prefix in self.config.skip_prefixes:
            if user.startswith(prefix):
                print("skipping first login logic because user starts with", prefix)
                return

        with open('/tmp/uplink.log', 'a') as f:
            f.write(f'on_user_registration({user}) called\n')

        localpart = user[1:].split(':')[0]
        profile = await self.api.get_profile_for_user(localpart)

        event_content = {
            'msgtype': 'm.text',
            'body': self.config.plain_text \
                .format(
                    displayname=profile.display_name,
                    mxid=user,
                ),
        }
        if self.config.html is not None:
            event_content |= {
                'format': 'org.matrix.custom.html',
                'formatted_body': self.config.html \
                    .format(
                        displayname=profile.display_name,
                        mxid=user,
                    )
            }

        # Note: It relies on implementation details
        notices_manager = self.api._hs.get_server_notices_manager()

        # Create server notices room
        room_id = await notices_manager.get_or_create_notice_room_for_user(user)
        
        # Invite user to server notices room
        await notices_manager.maybe_invite_user_to_room(user, room_id)

        # Auto-join the user to the room
        await self.api.update_room_membership(user, user, room_id, 'join')

        # Disable URL previews
        # Note: It relies on implementation details and an undocumented
        # (https://github.com/matrix-org/matrix-spec/issues/394) event
        event = await self.api.create_and_send_event_into_room({
            'type': 'org.matrix.room.preview_urls',
            'room_id': room_id,
            'sender': notices_manager.server_notices_mxid,
            'content': {'disable': True},
            'state_key': '',
        })

        # Send server notice
        # The "correct" way would be to use the admin REST API
        event = await notices_manager.send_notice(
            user_id=user,
            event_content=event_content,
        )


