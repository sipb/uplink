from mit_moira import Moira

# TODO: submit PRs to original package
# Set limit to 0 for infinite results
# Use kwargs instead of args on calls for readability

class ListMember:
    list: str
    member: str
    type: str

    def __init__(self, list, member, type):
        self.list = list
        self.member = member
        assert type in ['USER', 'LIST', 'STRING', 'KERBEROS']
        self.type = type
    
    @staticmethod
    def from_json(json):
        return ListMember(json['list'], json['member'], json['type'])
    
    def __repr__(self):
        return f'ListMember("{self.list}", "{self.member}", "{self.type}")'

class MoiraAPI(Moira):
    def __init__(self):
        super().__init__('personal.cert', 'personal.key')

    def get_all_members_of_list(self, name: str, recurse=True):
        dicts = self.client.service.getListMembership(
            listName=name,
            memberType='', # no limit either. I'd leave blank but zeep refuses
            recursiveSearch=recurse,
            maxReturnCount=0, # no limit
            proxyID=self.proxy_id,
        )
        return [ListMember.from_json(json) for json in dicts]

    # TODO: implement some parsing as in mailing_list_csv_to_json.py
    # (Parse kerberos principals and the like and turn them all into kerbs)