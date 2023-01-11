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

    # TODO: accept input from above command instead of re-calling the function
    # or make the above function return a special class with a method to do this (better)
    # TODO: also add another method to the class to get email addresses (filter by valid email address)
    def get_all_mit_members_of_list(self, name: str):
        members = self.get_all_members_of_list(name, True)
        mit_members = set() # instead of list, to prevent duplicates
        
        # Copied from old/mailing_list_csv_to_json.py
        for user_type, user_string in ((member.type, member.member) for member in members):
            if user_type=="USER":
                mit_members.add(user_string)
            elif user_type=="KERBEROS":
                if "/" in user_string:
                    kerb, extension = user_string.split("/")
                    if extension=="root@ATHENA.MIT.EDU":
                        mit_members.add(kerb)
                else:
                    kerb, extension = user_string.split("@")
                    if extension=="ATHENA.MIT.EDU" or extension=="MIT.EDU":
                        mit_members.add(kerb)
        return mit_members