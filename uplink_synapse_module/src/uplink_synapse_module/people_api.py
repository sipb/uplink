from twisted.web.resource import Resource
from twisted.web.server import Request
from synapse.module_api import ModuleApi
import json
from synapse.http.servlet import parse_json_object_from_request

# NOTE: It is possible that LDAP may be faster, e.g.:
# ldapsearch -LLL -h win.mit.edu -b "OU=users,OU=Moira,DC=WIN,DC=MIT,DC=EDU" "displayName=ga*" displayName cn
# It has Python bindings

# * 0m1.003s for People API
# * 0m0.718s for LDAP

PEOPLE_API_ENDPOINT = 'https://mit-people-v3.cloudhub.io/people/v3/people'

class PeopleApiDirectoryResource(Resource):
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
        
        response = await self.api.http_client.get_json(
            PEOPLE_API_ENDPOINT,
            args={
                'q': search_query,
                'minimalData': True,
            },
            headers={
                'client_id': self.client_id,
                'client_secret': self.client_secret,
            }
        )

        results = response['items']
        return [
            # Yes, it says "keberos". That is what the API says.
            (result['keberosId'], result['displayName']) for result in results
        ]

    def render_GET(self, request: Request):
        # This get request shall be for debugging, because only POST is used
        request.setHeader(b"Content-Type", b"text/plain")
        request.args['q']
        return f"{request.args}".encode()

    def render_POST(self, request: Request):
        # TODO: Get authenticated user
        self.api.get_user_by_req(request)
        
        # TODO: since this is a wrapper, it should call the actual synapse endpoint
        # (or api call directly)
        self.api._hs.get_user_directory_handler().search_users(
            # ...
        )

        # TODO: remember element sends one request for every keystroke,
        # determine when to search the MIT directory, smartly

        request.setHeader(b"Content-Type", b"text/plain")
        body = parse_json_object_from_request(request)
        search_term = body['search_term']
        limit = body.get('limit') # number of results to give
        results = self.find_names(search_term)
        limited = False
        # apply limit
        if limit and len(results) > limit:
            results = results[:limit]
        matrix_results = [
            # TODO: this assumes everyone does set their username to their kerb, which is actually true right now
            {'avatar_url': None, 'display_name': name, 'user_id': self.api.get_qualified_user_id(kerb)}
            for kerb, name in results
        ]

        # TODO: if this user directory shows people who haven't signed up
        # it is important to make sure they get emails
        

        return json.dumps({
            'limited': limited,
            'results': matrix_results,
        }).encode()

class PeopleApiSynapseService:
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
