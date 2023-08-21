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
from .util import kerb_exists, get_username

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

MATRIX_SPIEL_BASE = "Matrix is a free and open source messaging platform. You can chat on " \
    "your laptop by opening {link} on a web browser, or on your phone by downloading " \
    "the {element} app and changing your server to matrix.mit.edu by clicking the \"Edit\" " \
    "button next to matrix.org."
MATRIX_SPIEL_PLAIN = MATRIX_SPIEL_BASE.format(link='https://matrix.mit.edu', element='Element')
MATRIX_SPIEL_HTML = MATRIX_SPIEL_BASE.format(
    link='<a href="https://matrix.mit.edu" target="_blank" rel="noopener">matrix.mit.edu</a>',
    element='<a href="https://matrix.mit.edu/mobile_guide/" target="_blank" rel="noopener"><img src="https://matrix.mit.edu/media/QJGdSyYMSrCJjSKylDEqjfIz" alt="element icon">Element</a>',
)

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

def make_email_body_plain(inviter: str, is_dm: bool, is_space: bool, room_name: str | None, room_link: str) -> str:
    body = f"Hi,\n\n{make_main_sentence(inviter, is_dm, is_space, room_name)}"
    if not is_dm:
        body += f"\n\n{SPACE_SPIEL if is_space else ROOM_SPIEL}"
    body += f"\n\n{MATRIX_SPIEL_PLAIN}\n\nBest,\nThe SIPB Matrix maintainers"
    return body

def make_email_body_html(inviter: str, is_dm: bool, is_space: bool, room_name: str | None, room_link: str) -> str:
    what_to_join = room_name or "Matrix"
    body = f"Hi,<br/><br/>{make_main_sentence(inviter, is_dm, is_space, room_name)}" \
        f"<br/><br/>{make_button(room_link, f'Join {what_to_join} now!', '#007a61')}"
    if not is_dm:
        body += f"<br/>{SPACE_SPIEL if is_space else ROOM_SPIEL}"
    body += f"<br/><br/>{MATRIX_SPIEL_HTML}<br/><br/>Best,<br/>The SIPB Matrix maintainers" \
        '<br/><img src="https://matrix.mit.edu/pigeon.png" width="134" height="169">'
    return body

def make_button(href, content, color='#1F7F4C'):
    # https://www.litmus.com/blog/a-guide-to-bulletproof-buttons-in-email-design/
    # There are several to try
    return f'<table border="0" cellspacing="0" cellpadding="0"><tr><td style="padding: 12px 18px 12px 18px; border-radius:5px; background-color:{color};" align="center"><a rel="noopener" target="_blank" href="{href}" target="_blank" style="font-size: 16px; font-weight: bold; color: #ffffff; text-decoration: none; display: inline-block;">{content}</a></td></tr></table>'

def event_is_invite(event: EventBase) -> bool:
    return event.type == 'm.room.member' and event.content.get('membership') == 'invite'

def get_invited_user(event: EventBase) -> str:
    return event.state_key

def is_invitation_dm(event: EventBase) -> bool:
    return bool(event.content.get('is_direct'))

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

def id_or_canonical_alias(event: EventBase, state_events: StateMap[EventBase]):
    alias_event = state_events.get(('m.room.canonical_alias', ''))
    if not alias_event or not alias_event.content.get('alias'):
        return event.room_id
    else:
        return alias_event.content.get('alias')

def make_room_permalink(room_id_or_alias):
    return f'{ROOM_BASE_URL}{room_id_or_alias}'

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

        if not event_is_invite(event):
            # We only care about invites
            return

        print("Found an invite!")

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

        inviter = get_displayname(state_events, event.sender)
        room_link = make_room_permalink(id_or_canonical_alias(event, state_events))

        email = f'{kerb}@mit.edu'
        emailer = self.api._hs.get_send_email_handler()
        await emailer.send_email(
            email_address=email,
            subject=make_email_subject(inviter, is_dm, is_space),
            app_name='SIPB Matrix',
            html=make_email_body_html(inviter, is_dm, is_space, room_name, room_link),
            text=make_email_body_plain(inviter, is_dm, is_space, room_name, room_link),
        )
        
