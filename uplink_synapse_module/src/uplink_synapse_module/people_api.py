from twisted.web.server import Request
from synapse.module_api import ModuleApi
from synapse.module_api.errors import ConfigError
from synapse.api.errors import HttpResponseException
from synapse.http.servlet import parse_json_object_from_request
from .util import AsyncResource, _wrap_for_html_exceptions, _return_json

# NOTE: It is possible that LDAP may be faster, e.g.:
# ldapsearch -LLL -h win.mit.edu -b "OU=users,OU=Moira,DC=WIN,DC=MIT,DC=EDU" "displayName=ga*" displayName cn
# It has Python bindings

# * 0m1.003s for People API
# * 0m0.718s for LDAP

# TODO: probably override if we wish to debug the header behavior
PEOPLE_API_ENDPOINT = 'https://mit-people-v3.cloudhub.io/people/v3/people'


class PeopleApiDirectoryResource(AsyncResource):
    client_id: str
    client_secret: str
    blocked_prefixes: list[str]

    def __init__(self, api: ModuleApi, client_id, client_secret, blocked_prefixes, enable_people_api):
        super().__init__()
        self.api = api
        self.client_id = client_id
        self.client_secret = client_secret
        # Hide ghosts
        self.blocked_prefixes = blocked_prefixes
        self.enable_people_api = enable_people_api

    # The actual endpoint is POST /_matrix/client/v3/user_directory/search
    # Served by https://github.com/matrix-org/synapse/blob/58f830511486271da72543dd20676b702bc52b2f/synapse/rest/client/user_directory.py#L32

    def should_search_people_api(self, search_term):
        """
        Determine if we should search the people API at all
        """
        if not self.enable_people_api:
            return False
        # searching just 3 letters is unreasonable, IMO.
        # it would result way too many results, and slow everything down
        return len(search_term) > 3
    
    def is_allowed_mxid(self, mxid: str):
        """
        check that a MXID is not blocked (i.e. not a ghost)
        """
        return not any(mxid.startswith(f'@{prefix}') for prefix in self.blocked_prefixes)

    async def find_names(self, search_query):
        """
        Make a query to the people API by name or whatever it accepts
        Return a list of tuples of (kerb, display name)
        """
        
        if not self.should_search_people_api(search_query):
            return []

        try:
            response = await self.api.http_client.get_json(
                PEOPLE_API_ENDPOINT,
                args={
                    'q': search_query,
                    'minimalData': 'true',
                },
                headers={
                    'client_id': [self.client_id],
                    'client_secret': [self.client_secret],
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

    # TODO: this would all be great except for the simple fact that
    # Element, at least on web, decides to re-sort the results returned by Synapse
    # so my ordering isn't actually respected

    @_wrap_for_html_exceptions
    async def async_render_POST(self, request: Request):
        requester = await self.api.get_user_by_req(request)
        user_id = requester.user.to_string()
        
        body = parse_json_object_from_request(request)
        search_term = body['search_term']

        # same behavior as regular Synapse
        limit = int(body.get("limit", 10))
        limit = max(min(limit, 50), 0)
        
        synapse_results_promise = self.api._hs.get_user_directory_handler().search_users(
            user_id,
            search_term,
            limit + 5, # search 5 more since we are removing bridged users
        )

        people_response = await self.find_names(search_term)

        synapse_response = await synapse_results_promise
        synapse_results = synapse_response['results']

        # local users who are not ghosts
        local_synapse_results = [
            result for result in synapse_results
            if self.api.is_mine(result['user_id'])
            and self.is_allowed_mxid(result['user_id'])
        ]
        # any user who does not belong to this homeserver
        remote_synapse_results = [
            result for result in synapse_results
            if not self.api.is_mine(result['uesr_id'])
        ]

        local_users_set = {result['user_id'] for result in local_synapse_results}

        # remove duplicates - only people who have not signed up
        # TODO: sort by relevance somehow
        people_results = [
            {'avatar_url': None, 'display_name': f'{name} - not signed up', 'user_id': self.api.get_qualified_user_id(kerb)}
            for kerb, name in people_response
            if self.api.get_qualified_user_id(kerb) not in local_users_set
        ]

        # Overall, we want the concatenation of
        # * first we prefer local users who have signed up
        # * next local users who have not signed up
        # * and finally, federated users
        matrix_results = local_synapse_results + people_results + remote_synapse_results

        limited = synapse_response['limited']
        if len(matrix_results) > limit:
            matrix_results = matrix_results[:limit]
            limited = True

        _return_json({
            'limited': limited,
            'results': matrix_results,
        }, request)


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
        _assert('enable' in config['people_api'], 'do you want to enable people api?')
        return config

    def __init__(self, config: dict, api: ModuleApi):
        self.api = api
        self.api.register_web_resource(
            path='/_synapse/client/people_api/search',
            resource=PeopleApiDirectoryResource(
                api=api,
                client_id=config['people_api']['client_id'],
                client_secret=config['people_api']['client_secret'],
                blocked_prefixes=config.get('blocked_prefixes', []),
                enable_people_api=config['people_api']['enable'],
            ),
        )

