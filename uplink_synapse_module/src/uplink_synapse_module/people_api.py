from twisted.web.resource import Resource
from twisted.web.server import NOT_DONE_YET, Request
from synapse.module_api import ModuleApi
from synapse.module_api.errors import ConfigError
from synapse.api.errors import HttpResponseException
import json
from synapse.http.servlet import parse_json_object_from_request
from synapse.module_api import run_in_background


# NOTE: It is possible that LDAP may be faster, e.g.:
# ldapsearch -LLL -h win.mit.edu -b "OU=users,OU=Moira,DC=WIN,DC=MIT,DC=EDU" "displayName=ga*" displayName cn
# It has Python bindings

# * 0m1.003s for People API
# * 0m0.718s for LDAP

PEOPLE_API_ENDPOINT = 'https://mit-people-v3.cloudhub.io/people/v3/people'

class AsyncResource(Resource):
    """
    Extends twisted.web.Resource to add support for async_render_X methods
    
    Stolen from https://github.com/matrix-org/matrix-synapse-saml-mozilla

    IDK why it's the default
    """

    def render(self, request: Request):
        method = request.method.decode("ascii")
        m = getattr(self, "async_render_" + method, None)
        if not m and method == "HEAD":
            m = getattr(self, "async_render_GET", None)
        if not m:
            return super().render(request)

        async def run():
            with request.processing():
                return await m(request)

        run_in_background(run)
        return NOT_DONE_YET


class PeopleApiDirectoryResource(AsyncResource):
    def __init__(self, api: ModuleApi, client_id, client_secret):
        self.api = api
        self.client_id = client_id
        self.client_secret = client_secret

    # The actual endpoint is POST /_matrix/client/v3/user_directory/search
    # Served by https://github.com/matrix-org/synapse/blob/58f830511486271da72543dd20676b702bc52b2f/synapse/rest/client/user_directory.py#L32

    async def find_names(self, search_query):
        """
        Make a query to the people API by name or whatever it accepts
        Return a list of tuples of (kerb, display name)
        """
        
        # TODO: fix - this gives a 403
        b'{ "error": "multiple_clients", "description": "there are more than one client_id or client_secret" }'
        # as if you sent the header duplicated

        try:
            response = await self.api.http_client.get_json(
                PEOPLE_API_ENDPOINT,
                args={
                    'q': search_query,
                    'minimalData': 'true',
                },
                headers={
                    'client_id': self.client_id,
                    'client_secret': self.client_secret,
                }
            )
        except HttpResponseException as e:
            print(e.msg)
            print(e.response)
            print(e.headers)
            return []
        except Exception as e:
            from pprint import pprint
            pprint(e)
            return []

        results = response['items']
        return [
            # Yes, it says "keberos". That is what the API says.
            (result['keberosId'], result['displayName']) for result in results
        ]

    def render_GET(self, request: Request):
        # This get request shall be for debugging, because only POST is used
        request.setHeader(b"Content-Type", b"text/plain")
        return f"{request.args}".encode()

    async def async_render_POST(self, request: Request):
        requester = await self.api.get_user_by_req(request)
        print(requester)
        
        request.setHeader(b"Content-Type", b"text/plain")
        body = parse_json_object_from_request(request)
        search_term = body['search_term']
        limit = body.get('limit') or 50 # number of results to give
        
        # TODO: this gives a sqlite error?!
        # probably just do the HTTP request tbh
        # like this doesn't look supported lol
        synapse_results_promise = self.api._hs.get_user_directory_handler().search_users(
            requester.user,
            search_term,
            limit,
        )

        # TODO: remember element sends one request for every keystroke,
        # determine when to search the MIT directory, smartly

        people_results = await self.find_names(search_term)
        limited = False
        # apply limit - TODO this is wrong, the combined list must respect the limit
        if limit and len(people_results) > limit:
            people_results = people_results[:limit]

        synapse_results = await synapse_results_promise

        # TODO: combine smartly - use the limit
        matrix_results = [
            # TODO: this assumes everyone does set their username to their kerb, which is actually true right now
            {'avatar_url': None, 'display_name': name, 'user_id': self.api.get_qualified_user_id(kerb)}
            for kerb, name in people_results
        ] + synapse_results

        # TODO: if this user directory shows people who haven't signed up
        # it is important to make sure they get emails
        
        _return_json({
            'limited': limited,
            'results': matrix_results,
        })

class PeopleApiSynapseService:
    @staticmethod
    def parse_config(config: dict) -> dict: 
        def _assert(b, msg='invalid config'):
            if not b:
                raise ConfigError(msg)

        _assert('people_api' in config, 'Config not given (people_api missing)')
        _assert(isinstance(config['people_api'], dict), 'people_api must be a dict')
        _assert('client_id' in config['people_api'], 'client_id missing')
        _assert('client_secret' in config['people_api'], 'client_secret missing')
        return config

    def __init__(self, config: dict, api: ModuleApi):
        self.api = api
        self.api.register_web_resource(
            path='/_synapse/client/people_api/search',
            resource=PeopleApiDirectoryResource(
                api=api,
                client_id=config['people_api']['client_id'],
                client_secret=config['people_api']['client_secret'],
            ),
        )


def _return_json(json_obj, request: Request):
    """
    Returns JSON via an AsyncResource. Stolen from the same repo.
    """

    json_bytes = json.dumps(json_obj).encode("utf-8")

    request.setHeader(b"Content-Type", b"application/json")
    request.setHeader(b"Content-Length", b"%d" % (len(json_bytes),))
    request.setHeader(b"Cache-Control", b"no-cache, no-store, must-revalidate")
    request.setHeader(b"Access-Control-Allow-Origin", b"*")
    request.setHeader(
        b"Access-Control-Allow-Methods", b"GET, POST, PUT, DELETE, OPTIONS"
    )
    request.setHeader(
        b"Access-Control-Allow-Headers",
        b"Origin, X-Requested-With, Content-Type, Accept, Authorization",
    )
    request.write(json_bytes)
    try:
        request.finish()
    except RuntimeError as e:
        print("[uplink_synapse_module] Connection disconnected before response was written: %r", e)
