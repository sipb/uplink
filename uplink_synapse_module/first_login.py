from twisted.web.resource import Resource
from twisted.web.server import Request
from synapse.module_api import ModuleApi

class UplinkFirstLoginModule:
    def __init__(self, config: dict, api: ModuleApi):
        self.api = api
        self.api.register_account_validity_callbacks(
            on_user_registration=self.on_user_registration,
        )

    async def on_user_registration(self, user: str) -> None:
        with open('/tmp/uplink.log', 'a') as f:
            f.write(f'on_user_registration({user}) called\n')

