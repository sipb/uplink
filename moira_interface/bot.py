# for installation, see https://matrix-nio.readthedocs.io/en/latest/

from canvas_class import Class
from moira import MoiraAPI
import asyncio
import json
from nio import AsyncClient, MatrixRoom, RoomMessageText

config = json.load(open('config.json', 'r'))

client = AsyncClient(config['homeserver'], config['username'])
client.access_token = config['token']

async def message_callback(room: MatrixRoom, event: RoomMessageText) -> None:
    # ignore messages from self
    print(f'{event.sender=} {client.user=}')
    if (event.sender == client.user):
        return
    print(
        f"Message received in room {room.display_name}\n"
        f"{room.user_name(event.sender)} | {event.body}"
    )
    if (event.body.startswith('!ping')):
        # how to reply? not as straightforward as the js library
        await client.room_send(
            room.room_id,
            message_type='m.room.message',
            content={'msgtype': 'm.notice', 'body': 'Pong!'}
        )

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

asyncio.get_event_loop().run_until_complete(main())

# moira = MoiraAPI()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
