# How to install and register:
# https://stackoverflow.com/questions/41535915/python-pip-install-from-local-dir
# i.e. sudo bin/pip install ~/uplink/
# https://matrix-org.github.io/synapse/latest/modules/index.html

# TODO: make sure what's on the server and here are consistent...

from twisted.web.resource import Resource
from twisted.web.server import Request
from synapse.module_api import ModuleApi
import json


class UplinkRegistrationResource(Resource):
    def render_GET(self, request: Request):
        with open('/tmp/uplink.log', 'a') as f:
            f.write(f'render_GET called, args: {json.dumps(request.args)}\n')
        request.setHeader(b"Content-Type", b"text/plain")
        return b'Error: Unexpected GET request!'

    def render_POST(self, request: Request):
        with open('/tmp/uplink.log', 'a') as f:
            f.write(f'render_POST called, args: {json.dumps(request.args)}\n')
        # TODO: save parameters and consent somewhere
        request.setResponseCode(307)
        # TODO: don't hardcode URL
        request.setHeader(b"Location", 'https://uplink.mit.edu/_synapse/client/new_user_consent')


class UplinkSynapseService:
    def __init__(self, config: dict, api: ModuleApi):
        self.api = api
        self.api.register_account_validity_callbacks(
            on_user_registration=self.on_user_registration,
        )
        self.api.register_web_resource(
            path='/_synapse/client/uplink/register',
            resource=UplinkRegistrationResource(),
        )

    async def on_user_registration(self, user: str) -> None:
        with open('/tmp/uplink.log', 'a') as f:
            f.write(f'on_user_registration({user}) called\n')
        # TODO: check if display name has changed
        # TODO: honor desired display name

