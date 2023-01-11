from canvas_class import Class
from moira import MoiraAPI
import asyncio
import json
from nio import AsyncClient, MatrixRoom, RoomMessageText

# structure from https://github.com/git-bruh/matrix-discord-bridge/blob/main/bridge/bridge.py
# TODO: that bot uses the logging package to log things

class MatrixClient(AsyncClient):
    def __init__(self, *args, **kwargs):
        token = kwargs.pop('token')
        super().__init__(*args, **kwargs)
        self.access_token = token
        self.listen = False # idk what this does
        self.ready = asyncio.Event()
        self.loop = asyncio.get_event_loop()
        self.add_callbacks()

    def add_callbacks(self):
        callbacks = Callbacks(self)
        self.add_event_callback(callbacks.message_callback, RoomMessageText)


# better than my first closure attempt since we persist some state, I think...
class Callbacks:
    def __init__(self, client):
        self.client = client

    async def message_callback(self, room: MatrixRoom, event: RoomMessageText):
        message = event.body
        client = self.client
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

async def main():
    config = json.load(open('config.json', 'r'))
    client = MatrixClient(config['homeserver'], config['username'], token=config['token'])
    
    # This is the part that I missed. First it syncs
    # NOTE: I think this is the main key
    await client.sync(full_state=True)

    # Then it continues...
    retry = 2
    while True:
        try:
            client.ready.set()
            client.listen = True

            print("Client ready!")

            await client.sync_forever(timeout=30000, full_state=True)
        except Exception:
            print(f"Unknown exception occured, retrying in {retry} seconds...")

            # Clear "ready" status.
            client.ready.clear()

            await client.close()
            await asyncio.sleep(retry)

            client.listen = False
        finally:
            if client.listen:
                await client.close()
                return False

if __name__ == "__main__":
    asyncio.run(main())