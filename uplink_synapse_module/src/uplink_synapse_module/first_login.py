from twisted.web.resource import Resource
from twisted.web.server import Request
from synapse.module_api import ModuleApi
from synapse.module_api.errors import ConfigError

class UplinkFirstLoginModule:
    def __init__(self, config: dict, api: ModuleApi):
        self.api = api
        self.api.register_account_validity_callbacks(
            on_user_registration=self.on_user_registration,
        )
        self.config = config

    @staticmethod
    def parse_config(config: dict) -> dict:
        def _assert(b, msg='invalid config'):
            if not b:
                raise ConfigError(msg)
        _assert('plain_text' in config, 'You must specify a welcome message.')
        return config

    async def on_user_registration(self, user: str) -> None:
        print(f'{user} registered!')
        with open('/tmp/uplink.log', 'a') as f:
            f.write(f'on_user_registration({user}) called\n')

        localpart = user[1:].split(':')[0]
        profile = await self.api.get_profile_for_user(localpart)

        event_content = {
            'msgtype': 'm.text',
            'body': self.config['plain_text'] \
                .format(
                    displayname=profile.display_name,
                    mxid=user,
                ),
        }
        if 'html' in self.config:
            event_content |= {
                'format': 'org.matrix.custom.html',
                'formatted_body': self.config['html'] \
                    .format(
                        displayname=profile.display_name,
                        mxid=user,
                    )
            }

        # Send server notice
        # Note: It relies on implementation details
        # The "correct" way would be to use the admin REST API
        event = await self.api._hs.get_server_notices_manager().send_notice(
            user_id=user,
            event_content=event_content,
        )


        # Disable URL previews
        # Note: It relies on implementation details and an undocumented
        # (https://github.com/matrix-org/matrix-spec/issues/394) account data
        # TODO: this does not work for some odd reason! however calling this directly works
        res = await self.api._hs.get_account_data_handler().add_account_data_to_room(
            user_id=user,
            room_id=event.room_id,
            account_data_type='org.matrix.room.preview_urls',
            content={'disable': True},
        )

        print("done adding account data?", res)


