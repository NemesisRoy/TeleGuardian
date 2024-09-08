import os
import logging
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from telethon.tl.functions.contacts import BlockRequest
from pymongo import MongoClient
from telethon.sessions import StringSession

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Your Telegram API credentials from environment variables
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')
bot_token = os.getenv('BOT_TOKEN')
bot_owner_id = 7279627904

# Use the session string from environment variable
session_string = os.getenv('TELEGRAM_SESSION_STRING')

# Initialize the Telegram client with the bot token
client = TelegramClient(StringSession(session_string), api_id, api_hash)

# MongoDB Atlas connection from environment variable
mongo_uri = os.getenv('MONGODB_URI')
mongo_client = MongoClient(mongo_uri)
db = mongo_client['test']  # Replace 'test' with your actual database name
approved_users_collection = db['approved_users']

# Spam protection settings
MAX_UNAPPROVED_MESSAGES = 5
user_message_count = {}
approved_users = set()  # Set to store approved users

# Path to the GIF file
video_or_gif_path = 'https://i.postimg.cc/fWgdYxf8/21970003.gif'  # Change this to your actual file path

async def main():
    # Start the client with the session string
    await client.start()

    # Load approved users from MongoDB at startup (synchronous iteration)
    for user in approved_users_collection.find():
        approved_users.add(user['user_id'])
        logger.info(f"Loaded approved user: {user['username']} (ID: {user['user_id']})")

    logger.info("Approved users loaded from MongoDB.")


# Dictionary to keep track of messages sent by the bot (store message IDs per user)
bot_messages = {}

@client.on(events.NewMessage(incoming=True))
async def handle_pm(event):
    chat_id = event.chat_id
    sender = await event.get_sender()

    # Ignore messages from groups, channels, bots, and your own saved messages
    if event.is_group or event.is_channel or sender.bot or event.is_self:
        return

    # If the user is approved, allow the messages
    if sender.id in approved_users:
        return

    # Track the user's messages
    if sender.id not in user_message_count:
        user_message_count[sender.id] = 1

        # Send a professional-looking message with video/GIF and store the message ID
        gif_message = await client.send_file(
            sender.id,
            video_or_gif_path,
            caption=("👋 **Greetings, Stranger!**\n\n"
                     "I am **ITACHI**, the Digital Guardian of Niraj's Realm. 🥷⛩️\n\n"
                     "He's currently OFF doing Digital Detox 🧘🏻\n\n"
                     "Don't spam, else you'll be hit with Amaterasu!🌀⚡\n\n"
                     "~ SAYONARA 🍂")
        )

        # Store the message ID in the bot_messages dictionary
        bot_messages[sender.id] = [gif_message.id]

    else:
        # Increment the message count for the user
        user_message_count[sender.id] += 1

        # Warn the user if they are close to the limit
        if user_message_count[sender.id] == MAX_UNAPPROVED_MESSAGES - 1:
            warning_message = await event.reply(
                "Huh, You DUMB!😒\n"
                "One more msg & you'll be under my Genjutsu!🤧"
            )
            # Store the warning message ID in the bot_messages dictionary
            bot_messages[sender.id].append(warning_message.id)

    # Check if the user has sent more than the allowed number of messages
    if user_message_count[sender.id] >= MAX_UNAPPROVED_MESSAGES:
        # Block the user
        await client(BlockRequest(id=sender.id))

        # Send a final notice before blocking and store the message ID
        final_message = await client.send_message(
            sender.id,
            "~ BAKA 🤡"
        )
        bot_messages[sender.id].append(final_message.id)

@client.on(events.NewMessage(pattern='!approve'))
async def approve_user(event):
    sender = await event.get_sender()

    # Only the bot owner can approve users
    if sender.id == int(bot_owner_id):
        if event.is_reply:
            reply_message = await event.get_reply_message()
            user_to_approve = await reply_message.get_sender()

            # Add the user to the approved list
            approved_users.add(user_to_approve.id)
            approved_users_collection.update_one(
                {'user_id': user_to_approve.id},
                {'$set': {'user_id': user_to_approve.id, 'username': user_to_approve.username}},
                upsert=True
            )
            approval_message = await event.respond(f"User {user_to_approve.username} approved to message you.")

            # Track the approval message ID
            if user_to_approve.id in bot_messages:
                bot_messages[user_to_approve.id].append(approval_message.id)
            else:
                bot_messages[user_to_approve.id] = [approval_message.id]

            # Delete the bot's previous messages for this user (GIF, warnings, etc.)
            if user_to_approve.id in bot_messages:
                for message_id in bot_messages[user_to_approve.id]:
                    await client.delete_messages(user_to_approve.id, message_id)

                # Clear the stored messages after deleting them
                del bot_messages[user_to_approve.id]
        else:
            await event.respond("Reply to a user's message with !approve to approve them.")
    else:
        await event.respond("You don't have permission to use this command.")


@client.on(events.NewMessage(pattern='!disapprove'))
async def disapprove_user(event):
    sender = await event.get_sender()
    
    # Check if the sender is the bot owner
    if sender.id == bot_owner_id:
        if event.is_reply:
            reply_message = await event.get_reply_message()
            user_to_disapprove = await reply_message.get_sender()

            # Remove user from approved list
            approved_users.discard(user_to_disapprove.id)
            approved_users_collection.delete_one({'user_id': user_to_disapprove.id})
            await event.respond(f"User {user_to_disapprove.username} disapproved from messaging you.")
        else:
            await event.respond("Reply to a user's message with !disapprove to disapprove them.")
    else:
        await event.respond("You don't have permission to use this command.")

# Start the Telegram client
with client:
    client.loop.run_until_complete(main())
    client.run_until_disconnected()
