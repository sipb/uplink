from twisted.web.resource import Resource
from twisted.web.server import Request
from synapse.module_api import ModuleApi
import requests # TODO: use twisted instead, synchronous bad
import json
from synapse.http.servlet import parse_json_object_from_request

PEOPLE_API_ENDPOINT = 'https://mit-people-v3.cloudhub.io/people/v3/people'

class PeopleApiDirectoryResource(Resource):
    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret

    # The actual endpoint is POST /_matrix/client/v3/user_directory/search

    def find_names(self, search_query):
        """
        Make a query to the people API by name or whatever it accepts
        Return a list of tuples of (kerb, display name)
        """
        # TODO: please for the love of everything do not use requests
        # use twisted and make sure it is asynchronous/consistent to the type
        # of requests synapse makes
        response = requests.get(PEOPLE_API_ENDPOINT, params={
            'q': search_query,
            'minimalData': True,
        }, headers={
            'client_id': self.client_id,
            'client_secret': self.client_secret,
        })
        assert response.status_code == 200
        results = json.loads(response.content.decode())['items']
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
        # TODO: check authentication
        # TODO: remember element sends one request for every keystroke,
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
            # TODO: don't hardcode, and remember to change to matrix.mit.edu (ideally read the config to know)
            {'avatar_url': None, 'display_name': name, 'user_id': f'@{kerb}:uplink.mit.edu'}
            for kerb, name in results
        ]
        return json.dumps({
            'limited': limited,
            'results': matrix_results,
        }).encode()

class UplinkSynapseService:
    def __init__(self, config: dict, api: ModuleApi):
        self.api = api
        self.api.register_web_resource(
            path='/_synapse/client/people_api/search',
            resource=PeopleApiDirectoryResource(
                client_id=config['people_api']['client_id'],
                client_secret=config['people_api']['client_secret'],
            ),
        )
