# for installation, see https://matrix-nio.readthedocs.io/en/latest/

from canvas_class import Class
from moira import MoiraAPI
import asyncio
import json
from nio import AsyncClient, MatrixRoom, RoomMessageText, RoomVisibility, RoomCreateError, RoomCreateResponse, Api, GetOpenIDTokenResponse
import requests # TODO: remove once this is handled from nio
import json # likewise

moira = MoiraAPI()

config = json.load(open('config.json', 'r'))

client = AsyncClient(config['homeserver'], config['username'])
client.access_token = config['token']

# I'll be doing it for the special case scenario because
# I'm not sure how we want setup for non-Canvas lists

# i.e. how do users choose if they want a space or normal room?
# how do we determine which mailing lists have opted in?
# who can create a channel for a given mailing list?
# who is allowed to turn a mailing list into a channel?
#   anyone if they are in a public and nonhidden list and admins otherwise?
#   something else?
# Also for classes, do we want them to be public so people can add themselves?

def class_channel_exists(canvas_class: Class|str):
    """
    Does a class channel exist for the given Canvas class?

    * canvas_class is the class name or Class
    """
    if isinstance(canvas_class, str):
        canvas_class = Class(canvas_class)
    # TODO: do this, define channel exists in general
    # https://matrix.org/docs/api/#get-/_matrix/client/v3/directory/room/-roomAlias-
    # client.room_resolve_alias
    # https://matrix.org/docs/api/#get-/_matrix/client/v3/directory/list/room/-roomId-
    # client.room_get_visibility

# TODO: this should be handled from nio
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


async def accept_identity_server_terms() -> requests.Response:
    # Get terms from https://matrix.org/_matrix/identity/v2/terms
    urls = ['https://matrix.org/legal/identity-server-privacy-notice-1']
    result = requests.post(
        url=f"https://{config['id_server']}/_matrix/identity/v2/terms",
        json={'user_accepts': urls},
        headers={'Authorization': f'Bearer {await get_id_access_token()}'},
    )
    return result


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
        classes = [str(c) for c in Class.get_list_from_mailing_lists(lists) if c.mailing_list.startswith('canvas-2023')]
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
        attributes = moira.list_attributes(list_name)
        members, invites = moira.get_members_of_list_by_type(list_name)
        # TODO: restore /home/rgabriel/.local/lib/python3.10/site-packages/nio.bak into nio when the PR is merged

        # How to get id_access_token for now? I don't think nio can interface with identity servers
        # first get token via await client.get_openid_token(config['username'])
        # curl -d '{"access_token": "TOKEN_GOES_HERE", "token_type": "Bearer", "matrix_server_name": "uplink.mit.edu", "expires_in": 60}' -H "Content-Type: application/json" "https://matrix.org/_matrix/identity/v2/account/register"
        response = await client.room_create(
            visibility=RoomVisibility.private if attributes['hiddenList'] or not attributes['publicList'] else RoomVisibility.public,
            alias=list_name,
            name=list_name, # For now
            topic=attributes['description'],
            invite=[f"@{member}:{config['server_name']}" for member in members],
            invite_3pid=[
                dict(
                    address=email,
                    id_access_token=await get_id_access_token(),
                    id_server=config['id_server'],
                    medium='email'
                )
                for email in invites
            ],
        )
        # TODO: everyone is invited whether they haven't logged into Uplink or not
        # if they haven't and then they join, do their invites appear?
        # Can invites be sent again or are they lost forever?
        # (FOR OWN USERS)
        print(response)
        if isinstance(response, RoomCreateResponse):
            await send_message('done!', 'm.notice')
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
        # TODO: also give room admin to the mailing list admins...
    if msg.startswith('!removealias') and event.sender == '@rgabriel:uplink.mit.edu':
        list_name = msg.split(' ')[1]
        response = await client.room_delete_alias(f'#{list_name}:uplink.mit.edu')
        await send_message(str(response), 'm.notice')
        

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
