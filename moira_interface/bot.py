# for installation, see https://matrix-nio.readthedocs.io/en/latest/

from canvas_class import Class
from moira import MoiraAPI
import asyncio
import json
from nio import AsyncClient, MatrixRoom, RoomMessageText, RoomVisibility, RoomCreateError, RoomCreateResponse, Api

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
    if msg.startswith('!listmitmembers'):
        list_name = msg.split(' ')[1]
        members = moira.get_all_mit_members_of_list(list_name)
        await send_message('\n'.join(members), 'm.notice')
    if msg.startswith('!createlistroom'):
        list_name = msg.split(' ')[1]
        await send_message(f'Creating room for list {list_name}', 'm.notice')
        attributes = moira.list_attributes(list_name)
        members = moira.get_all_mit_members_of_list(list_name)
        response = await client.room_create(
            visibility=RoomVisibility.private if attributes['hiddenList'] or not attributes['publicList'] else RoomVisibility.public,
            alias=list_name,
            name=list_name, # For now
            topic=attributes['description'],
            invite=[f'@{member}:uplink.mit.edu' for member in members], # Hardcoded for now (TODO: fix)
        )
        # TODO: everyone is invited whether they haven't logged into Uplink or not
        # if they haven't and then they join, do their invites appear?
        # Can invites be sent again or are they lost forever?

        # Ohhh matrix defines invite_3pid (would need pull request to matrix-nio)
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
