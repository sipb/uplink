# for installation, see https://matrix-nio.readthedocs.io/en/latest/

from canvas_class import Class
from moira import MoiraAPI, MoiraList
import asyncio
import json
from nio import AsyncClient, MatrixRoom, RoomMessageText, RoomVisibility, RoomCreateError, RoomCreateResponse, Api, GetOpenIDTokenResponse, RoomPreset, RoomResolveAliasResponse, RoomResolveAliasError
import requests  # TODO: remove once this is handled from nio
import json  # likewise
from database import Database

moira = MoiraAPI()
config = json.load(open('config.json', 'r'))
db = Database()

client = AsyncClient(config['homeserver'], config['username'])
client.access_token = config['token']

async def list_is_opted_in(list_name: str):
    """
    Has the Moira list `list_name` opted to have a room?
    If yes, this means the room with alias `list_name` exists or should be created
    """
    if list_name.startswith('canvas-') and list_name.endswith('-st'):
        return True
    else:
        return list_name in db['lists']


async def room_exists(alias: str):
    """
    Does the room with given alias `alias` exist in our homeserver?
    """
    if ':' not in alias:
        alias = f"#{alias}:{config['server_name']}"
    response = await client.room_resolve_alias(alias)
    if isinstance(response, RoomResolveAliasResponse):
        return True
    else:
        assert isinstance(response, RoomResolveAliasError)
        if response.status_code == 'M_NOT_FOUND':
            return False
        else:
            raise Exception(response)


def username_from_localpart(localpart: str):
    return f"@{localpart}:{config['server_name']}"


def generate_power_levels_for_list(l: MoiraList) -> dict:
    """
    Generate a m.room.power_levels event based on the moira list permissions

    This function is called on room creation when overriding the power levels or when syncing from the list
    """
    # How to send a state event: https://matrix.org/docs/api/#put-/_matrix/client/v3/rooms/-roomId-/state/-eventType-/-stateKey-

    # Help, I think I am overthinking things considering I am considering lists with memacl
    # because not even webmoira lets you set that
    # It would be nice to make a nicer WebMoira client tho...
    
    return {
        # This is a power_levels event, as defined in the spec:
        # https://spec.matrix.org/v1.5/client-server-api/#mroompower_levels
        "type": "m.room.power_levels",

        "content": {
            # The default power level for a user to have is 0
            "users_default": 0,

            # For moira lists, 50 should mean memacl, and 100 owner
            "users": {username_from_localpart(u): 100 for u in l.owners}
                   | {username_from_localpart(u): 50 for u in l.membership_administrators}
                   | {config['username']: 100}, # bot itself should have permissions (TODO unless it's not required for appservice)

            # These are the power levels required to send specific types of events            
            "events": {
                "m.room.name": 50,
                "m.room.power_levels": 100,
                "m.room.history_visibility": 100,
                "m.room.canonical_alias": 100,
                "m.room.avatar": 50, # *room* avatar
                "m.room.tombstone": 100,
                "m.room.server_acl": 100,
                "m.room.encryption": 50,
                "m.room.pinned_events": 0, # anyone can pin!
                "m.room.join_rules": 50,
            },
            "ban": 100,
            "kick": 50,
            "redact": 100,
            "invite": 0 if l.is_public else 50,

            # The default power level required to send a message event other than specified above is 0
            "events_default": 0,

            # The default power level required to send a state event other than specified above is 0
            "state_default": 50,
        },
    }
    

async def create_list_room(list_name: str, sync_moira_permissions=True, caller=None) -> RoomCreateResponse | RoomCreateError:
    """
    Creates a room corresponding to the given Moira list `list_name`, and opts it in 

    If `sync_moira_permissions` is true, the permissions on the Matrix room will reflect
    the permissions of the mailing list, otherwise, it will be closer to a traditional group
    chat (i.e. RoomPreset.trusted_private_chat)

    `caller` is the name of the person who invoked the creation of the room (full username)
    This is required with hidden lists because members are added lazily instead of all at once
    to try to comply with the property.

    Returns the result of client.room_create (RoomCreateResponse on success)
    """
    async def invite_3pid_from_email_list(invites: list[str]):
        if not invites:
            return None
        id_access_token = await get_id_access_token()
        return [dict(address=email,
                    id_access_token=id_access_token,
                    id_server=config['id_server'],
                    medium='email')
                for email in invites]

    l = MoiraList(list_name)
    assert not (l.is_hidden and caller is None), \
        'if the mailing list is hidden, ' + \
        'you MUST set invites_override to the room creator or any other initial member list, ' + \
        'to avoid leaking too much of the member list'
    response = await client.room_create(
        visibility=RoomVisibility.private if l.is_hidden or not l.is_public else RoomVisibility.public,
        alias=l.get_matrix_room_alias(),
        name=l.get_matrix_room_name(),
        topic=l.get_matrix_room_description(),
        invite=[caller] if l.is_hidden else [username_from_localpart(member) for member in l.mit_members],
        invite_3pid=await invite_3pid_from_email_list(l.external_members),
        preset=RoomPreset.private_chat if sync_moira_permissions else RoomPreset.trusted_private_chat,
        power_level_override=generate_power_levels_for_list(l) if sync_moira_permissions else None,
    )
    if isinstance(response, RoomCreateResponse):
        db.append('lists', list_name)
    return response


# TODO: exception handling
# for instance, currently crashes if you try to create a list room for a list that doesn't exist
async def message_callback(room: MatrixRoom, event: RoomMessageText) -> None:
    async def send_message(msg, type='m.text'):
        await client.room_send(
            room.room_id,
            message_type='m.room.message',
            content={'msgtype': type, 'body': msg}
        )
    # ignore messages from self
    if event.sender == client.user:
        return
    msg = event.body
    if msg.startswith('!ping'):
        await send_message('Pong!')
    if msg.startswith('!createlistroom'):
        list_name = msg.split(' ')[1]
        await send_message(f'Creating room for list {list_name}', 'm.notice')
        response = await create_list_room(list_name)
        print(response)
        if isinstance(response, RoomCreateResponse):
            await send_message('room has been created!', 'm.notice')
        else:
            assert isinstance(response, RoomCreateError)
            if response.status_code == 'M_ROOM_IN_USE':
                await send_message('Room already exists')
            elif response.message == 'Cannot invite so many users at once':
                # TODO: recreate and manually add one by one
                # Or get rid of ratelimiting for this user
                await send_message('handling large mailing lists is not yet implemented')
            else:
                await send_message(f'There was an error creating the room for list {list_name}')
                await send_message(str(response), 'm.notice')
    if msg.startswith('!removealias') and event.sender == '@rgabriel:uplink.mit.edu':
        list_name = msg.split(' ')[1]
        response = await client.room_delete_alias(f'#{list_name}:uplink.mit.edu')
        await send_message(str(response), 'm.notice')
    if msg.startswith('!roomexists'):
        try:
            alias = msg.split(' ')[1]
            await send_message('Yes' if await room_exists(alias) else 'No')
        except Exception as e:
            await send_message(f'{e}', 'm.notice')


# TODO: this should be handled from nio
# and fix this issue: https://github.com/poljar/matrix-nio/issues/375
# currently manually editing the site-package to add missing parameter

async def get_id_access_token() -> str:
    url = f"https://{config['id_server']}/_matrix/identity/v2/account/register"
    token = await client.get_openid_token(config['username'])
    assert isinstance(token, GetOpenIDTokenResponse)
    result = requests.post(url, json=dict(
        access_token=token.access_token,
        token_type="Bearer",
        matrix_server_name=config['server_name'],
        expires_in=token.expires_in,
    ))
    return json.loads(result.content)['access_token']


# You just have to call this function once, so I'm not calling it from any part of the code
async def accept_identity_server_terms() -> requests.Response:
    # Get terms from https://matrix.org/_matrix/identity/v2/terms
    urls = ['https://matrix.org/legal/identity-server-privacy-notice-1']
    result = requests.post(
        url=f"https://{config['id_server']}/_matrix/identity/v2/terms",
        json={'user_accepts': urls},
        headers={'Authorization': f'Bearer {await get_id_access_token()}'},
    )
    return result


async def main() -> None:
    # This line is important, so it doesn't reply to old messages on restart...
    # Another option seems to be to use the `since` parameter
    # Since I see commands as something immediate, if the bot wasn't running for whatever reason
    # they are now irrelevant and people will run the commands again if needed
    # This is what I expect from Discord bots
    # From testing, it doesn't seem perfect, but it's probably good enough
    await client.sync(full_state=True)

    client.add_event_callback(message_callback, RoomMessageText)
    await client.sync_forever(timeout=30000)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
