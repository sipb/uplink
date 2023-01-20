from mit_moira import Moira
from canvas_class import Class

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

# TODO: submit PRs to original package
# Set limit to 0 for infinite results
# Use kwargs instead of args on calls for readability
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


    @staticmethod
    def normalize_kerberos(user_string):
        """
        Turn a kerberos string into a normal kerb username without any suffixes
        """
        # Credit: old/mailing_list_csv_to_json.py
        if "/" in user_string:
            kerb, extension = user_string.split("/")
            if extension=="root@ATHENA.MIT.EDU":
                return kerb
        else:
            kerb, extension = user_string.split("@")
            if extension=="ATHENA.MIT.EDU" or extension=="MIT.EDU":
                return kerb


    def get_members_of_list_by_type(self, name: str):
        """
        Gets each person in a given mailing list `name`.
        Returns a tuple of 2 sets, first the kerbs of MIT members, and second the external email addresses
        """
    
        members = self.get_all_members_of_list(name, True)
        mit_members = set() # instead of list, to prevent duplicates
        external_members = set()

        for user_type, user_string in ((member.type, member.member) for member in members):
            if user_type=="USER":
                mit_members.add(user_string)
            elif user_type=="KERBEROS":
                mit_members.add(self.normalize_kerberos(user_string))
            elif user_type=="STRING":
                if "@" in user_string and "<devnull" not in user_string and \
                        " removed " not in user_string and " " not in user_string:
                    external_members.add(user_string)
        return mit_members, external_members


class MoiraList:
    """
    A moira mailing list. Properties are loaded from demand and cached
    to avoid making excessive calls to Moira APIs.

    Because instances should be short-lived, there if something changes on the
    Moira side, once it's cached, it will not change here.
    """

    def __init__(self, list_name: str):
        self.list_name = list_name
        self._moira = MoiraAPI()
        self._attributes = None
        self._members_by_type = None
        self._owners = None
        self._membership_administrators = None

    def __repr__(self):
        return f'MoiraList("{self.list_name}")'

    @property
    def attributes(self):
        if self._attributes is None:
            self._attributes = self._moira.list_attributes(self.list_name)
        return self._attributes

    @property
    def description(self):
        return self.attributes['description']
    
    @property
    def is_public(self):
        return self.attributes['publicList']

    @property
    def is_hidden(self):
        return self.attributes['hiddenList']

    @property
    def members_by_type(self):
        """
        Get members of this list
        Returns a tuple of 2 sets, first the kerbs of MIT members, and second the external email addresses
        """
        if self._members_by_type is None:
            self._members_by_type = self._moira.get_members_of_list_by_type(self.list_name)
        return self._members_by_type

    @property
    def mit_members(self):
        return self.members_by_type[0]

    @property
    def external_members(self):
        return self.members_by_type[1]

    def _expand_members(self, moira_type: str, moira_name: str):
        """
        Get a list of users from the given type and name
        """
        if moira_type == 'NONE':
            return set()
        elif moira_type == 'USER':
            return {moira_name}
        elif moira_type == 'KERBEROS':
            return {self._moira.normalize_kerberos(moira_name)}
        else:
            assert moira_type == 'LIST'
            return MoiraList(moira_name).mit_members
    
    @property
    def owners(self):
        if self._owners is None:
            self._owners = self._expand_members(self.attributes['aceType'], self.attributes['aceName'])
        return self._owners

    @property
    def membership_administrators(self):
        if self._membership_administrators is None:
            self._membership_administrators = self._expand_members(self.attributes['memaceType'], self.attributes['memaceName'])
        return self._membership_administrators
    
    @property
    def is_class(self):
        answer = self.list_name.startswith('canvas-')
        if answer:
            self.canvas_class = Class(self.list_name)
        return answer

    def get_matrix_room_name(self) -> str:
        """
        Generate a display name for the room corresponding to this list
        (list name, in the case of classes, a nicer string is returned)
        """
        if self.is_class:
            return self.canvas_class.get_room_name()
        else:
            return self.list_name
    
    def get_matrix_room_alias(self) -> str:
        """
        Generate an alias for the room corresponding to this list
        (list name, in the case of canvas classes, it's stripped to be less lengthy)
        """
        if self.is_class:
            return self.canvas_class.get_room_alias()
        else:
            return self.list_name

    def get_matrix_room_description(self) -> str:
        """
        Generate a description for the room corresponding to this list
        (class name or list description)
        """
        if self.is_class and self.canvas_class.full_name:
            return self.canvas_class.full_name
        else:
            return self.description

