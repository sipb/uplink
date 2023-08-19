"""
Synapse module that sends emails to users who have
not signed up to the homeserver.

Right now we are only sending emails when someone has
been invited to a new room, because 
"""

from dataclasses import dataclass
from dataclasses_json import dataclass_json
from twisted.web.resource import Resource
from twisted.web.server import Request
from synapse.module_api import ModuleApi
from synapse.events import EventBase
from synapse.types import StateMap
from synapse.module_api.errors import ConfigError
from pprint import pprint
import dns.resolver

BASE_URL = "https://matrix.mit.edu"
ROOM_BASE_URL = f"{BASE_URL}/#/room/"

# TODO: make template configurable
# uh while it would be nice to make it configurable I think there may be more
# hardcoded behavior based on our assumptions. Something else which would be nice
# is to write a blog post about how everything was put together.
@dataclass_json
@dataclass
class Config:
    pass

def kerb_exists(kerb):
    return True # TODO: revert this behavior!
    try:
        # should we check pobox instead?
        answers = dns.resolver.resolve(f'{kerb}.passwd.ns.athena.mit.edu', 'TXT')
        return True
    except dns.resolver.NXDOMAIN:
        return False

MATRIX_SPIEL_PLAIN = "Matrix is a free and open source messaging platform. You can chat on " \
    "your laptop by opening matrix.mit.edu on a web browser, or on your phone by downloading " \
    "the Element app and changing your server to matrix.mit.edu by clicking the \"Edit\" " \
    "button next to matrix.org."
MATRIX_SPIEL_HTML = MATRIX_SPIEL_PLAIN.replace("matrix.mit.edu", '<a href="https://matrix.mit.edu">matrix.mit.edu</a>', count=1)

ROOM_SPIEL = "A room is similar to a group chat or channel on other platforms."
SPACE_SPIEL = "A space is similar to a workspace or server on other platforms."

def make_email_subject(inviter_display_name: str, is_dm: bool, is_space: bool) -> str:
    if is_dm:
        return f"{inviter_display_name} has DMed you on Matrix"
    else:
        return f"You have been invited to a {'space' if is_space else 'room'} on Matrix"

def make_main_sentence(inviter: str, is_dm: bool, is_space: bool, room_name: str | None) -> str:
    if is_dm:
        return f"{inviter} has sent you a direct message on Matrix."
    else:
        room_type = 'space' if is_space else 'room'
        destination = f"the \"{room_name}\" {room_type}" if room_name is not None else f"a {room_type}"
        return f"{inviter} has invited you to {destination} on Matrix."

# TODO(important): we need a direct link to the room (room alias if available otherwise ID)

# TODO: make the button nice-looking
# example: https://www.litmus.com/blog/a-guide-to-bulletproof-buttons-in-email-design

def make_email_body_plain(inviter: str, is_dm: bool, is_space: bool, room_name: str | None) -> str:
    body = f"Hi,\n\n{make_main_sentence(inviter, is_dm, is_space, room_name)}"
    if not is_dm:
        body += f"\n\n{SPACE_SPIEL if is_space else ROOM_SPIEL}"
    body += f"\n\n{MATRIX_SPIEL_PLAIN}\n\nBest,\nThe SIPB Matrix maintainers"
    return body

def make_email_body_html(inviter: str, is_dm: bool, is_space: bool, room_name: str | None) -> str:
    body = f"Hi,<br/><br/>{make_main_sentence(inviter, is_dm, is_space, room_name)}"
    if not is_dm:
        body += f"<br/><br/>{SPACE_SPIEL if is_space else ROOM_SPIEL}"
    # TODO: add carrier pigeon image
    body += f"<br/><br/>{MATRIX_SPIEL_PLAIN}<br/><br/>Best,<br/>The SIPB Matrix maintainers"
    return body

def event_is_invite(event: EventBase) -> bool:
    return event.type == 'm.room.member' and event.content.get('membership') == 'invite'

def get_invited_user(event: EventBase) -> str:
    return event.state_key

def is_invitation_dm(event: EventBase) -> bool:
    return bool(event.content.get('is_direct'))

def get_username(mxid: str) -> str:
    localpart, homeserver = mxid[1:].split(':', maxsplit=1)
    return localpart

def room_is_space(state_events: StateMap[EventBase]):
    creation_event = state_events.get(('m.room.create', ''))
    if not creation_event:
        return False
    room_type = creation_event.content.get('type')
    return room_type == 'm.space'

def get_displayname(state_events: StateMap[EventBase], user: str):
    member_event = state_events.get(('m.room.member', user.lower()))
    if not member_event:
        return get_username(user)
    return member_event.content.get('displayname') or get_username(user)

def get_room_name(state_events: StateMap[EventBase]) -> str | None:
    name_event = state_events.get(('m.room.name', ''))
    if not name_event or not name_event.content.get('name'):
        return None
    return name_event.content.get('name')

class UplinkFutureUserEmailer:
    def __init__(self, config: Config, api: ModuleApi):
        self.api = api
        self.api.register_third_party_rules_callbacks(
            on_new_event=self.on_new_event,
        )
        self.config = config

    @staticmethod
    def parse_config(config: dict) -> dict:
        try:
            return Config.from_dict(config)
        except Exception as e:
            raise ConfigError(f'{e}')
    
    async def on_new_event(self, event: EventBase, state_events: StateMap):
        """
        Process room invites and send emails accordingly
        """
        # TODO: remove all of the logging

        if not event_is_invite(event):
            # We only care about invites
            return

        pprint(event)
        pprint(state_events)

        user = get_invited_user(event)

        if not self.api.is_mine(user):
            # We don't care about external users (receiver)
            print(f'receiver {user} not mine!')
            return

        if not self.api.is_mine(event.sender):
            # We don't care about external users (sender)
            # TODO: or do we?
            print(f'sender {event.sender} not mine!')
            return

        if await self.api.check_user_exists(user) is not None:
            # We only care about inexistent users
            print(f'user {user} already exists: {self.api.check_user_exists(user)}')
            return

        is_dm = is_invitation_dm(event)
        is_space = room_is_space(state_events)
        room_name = get_room_name(state_events)
        kerb = get_username(user)

        if not kerb_exists(kerb):
            print('Inexistent kerb!')
            return
        
        emailer = self.api._hs.get_send_email_handler()

        inviter = get_displayname(event.sender)

        email = f'{kerb}@mit.edu'
        print(f'sending email to {email}')
        await emailer.send_email(
            email_address=email,
            subject=make_email_subject(inviter, is_dm, is_space),
            app_name='SIPB Matrix',
            html=make_email_body_html(inviter, is_dm, is_space, room_name),
            text=make_email_body_plain(inviter, is_dm, is_space, room_name),
        )
        
