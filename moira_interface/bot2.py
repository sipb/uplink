import simplematrixbotlib as botlib
import json
from nio import RoomVisibility, MatrixRoom, RoomPreset, RoomMessage

prefs = json.load(open('prefs.json', 'r'))

creds = botlib.Creds(
    homeserver=prefs['homeserver'],
    username=prefs['username'],
    access_token=prefs['token'],
    session_stored_file='session.txt'
)

config = botlib.Config()
config.join_on_invite = True

bot = botlib.Bot(creds)

@bot.listener.on_message_event
async def commands(room: MatrixRoom, message: RoomMessage):
    match = botlib.MessageMatch(room, message, bot, prefs['prefix'])
    if match.is_not_from_this_bot() and match.prefix():
        if match.command("echo"):
            message = " ".join(arg for arg in match.args())
            await bot.api.send_text_message(room.room_id, message)
        if match.command("createroom"):
            if len(match.args()) != 3:
                await bot.api.send_text_message(room.room_id, 'Usage: createroom alias name topic', 'm.notice')
                return
            alias, name, topic = match.args()
            await bot.async_client.room_create(
                visibility=RoomVisibility.private,
                alias=alias,
                name=name,
                topic=topic,
                federate=False, # TODO: for now?
                preset=RoomPreset.public_chat,
                invite=[message.sender], # for moira lists this would be everyone
            )
        if match.command("joinroom"):
            room_id = match.args()[0]
            await bot.async_client.room_invite(room_id, message.sender)

bot.run()
