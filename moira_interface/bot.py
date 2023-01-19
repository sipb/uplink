# for installation, see https://matrix-nio.readthedocs.io/en/latest/

from canvas_class import Class
from moira import MoiraAPI
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
    if list_name.startswith('canvas-'):
        return True
    else:
        return list_name in db['lists']


async def list_opt_in(list_name: str):
    """
    Opt in the Moira list `list_name` to have a room, by saving this fact
    """
    db.append('lists', list_name)


async def room_exists(alias: str):
    response = await client.room_resolve_alias(alias)
    if isinstance(response, RoomResolveAliasResponse):
        return True
    else:
        assert isinstance(response, RoomResolveAliasError)
        if response.status_code == 'M_NOT_FOUND':
            return False
        else:
            raise Exception(response)


# TODO: this should be handled from nio
# and fix this issue: https://github.com/poljar/matrix-nio/issues/375

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


async def invite_3pid_from_email_list(invites: list[str]):
    id_access_token = await get_id_access_token()
    return [dict(address=email,
                id_access_token=id_access_token,
                id_server=config['id_server'],
                medium='email')
            for email in invites]


async def create_list_room(list_name: str):
    """
    Creates a room corresponding to the given Moira list `list_name`
    """
    attributes = moira.list_attributes(list_name)
    members, invites = moira.get_members_of_list_by_type(list_name)
    # TODO: restore /home/rgabriel/.local/lib/python3.10/site-packages/nio.bak into nio when the PR (TBD) is merged
    # TODO: show a warning for hidden lists
    # "The list is hidden. Matrix currently does not offer a way of hiding members so that will not be honored. Are you sure?"
    response = await client.room_create(
        visibility=RoomVisibility.private if attributes['hiddenList'] or not attributes['publicList'] else RoomVisibility.public,
        alias=list_name,
        name=list_name,  # For now
        topic=attributes['description'],
        invite=[f"@{member}:{config['server_name']}" for member in members],
        invite_3pid=await invite_3pid_from_email_list(invites),
        preset=RoomPreset.trusted_private_chat, # this gives people perms (for now)
    )
    return response


async def sync_moira_permissions(list_name: str):
    """
    Sync moira permissions to Matrix permissions
    """
    # https://github.com/matrix-org/matrix-js-sdk/blob/185ded4ebc259d35f6c4c4945a68dba793703519/src/client.ts#L4089
    # https://matrix.org/docs/api/#put-/_matrix/client/v3/rooms/-roomId-/state/-eventType-/-stateKey-
    # https://spec.matrix.org/v1.5/client-server-api/#mroompower_levels
    # TODO: implement
    pass


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
    if msg.startswith('!myclasses'):
        lists = moira.user_lists('rgabriel')
        classes = [str(c) for c in Class.get_list_from_mailing_lists(
            lists) if c.mailing_list.startswith('canvas-2023')]
        await send_message('\n'.join(classes), 'm.notice')
    if msg.startswith('!listinfo'):
        list_name = msg.split(' ')[1]
        attributes = moira.list_attributes(list_name)
        await send_message(str(attributes), 'm.notice')
    # TODO: follow list access control stuff
    # and remove these commands which are just for debugging purposes
    if msg.startswith('!idtoken'):
        token = await get_id_access_token()
        print(token)
        await send_message(str(token))
    if msg.startswith('!acceptterms'):
        await send_message('on it!', 'm.notice')
        response = await accept_identity_server_terms()
        await send_message(f'{response} {response.content.decode()}', 'm.notice')
    if msg.startswith('!listmembers'):
        list_name = msg.split(' ')[1]
        members, invites = moira.get_members_of_list_by_type(list_name)
        await send_message('\n'.join(list(members) + list(invites)), 'm.notice')
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
