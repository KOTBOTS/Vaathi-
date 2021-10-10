import threading
from telegram.ext import CommandHandler
from bot import LOGGER, dispatcher
from bot.helper.mirror_utils.upload_utils import gdriveTools
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import auto_delete_message, sendMessage


def deletefile(update, context):
    msg_args = update.message.text.split(' ', maxsplit=1)
    reply_to = update.message.reply_to_message
    if len(msg_args) > 1:
        link = msg_args[1]
    elif reply_to is not None:
        reply_text = reply_to.text
        link = reply_text.split('\n')[0]
    else:
        link = None
    if link is not None:
        LOGGER.info(link)
        drive = gdriveTools.GoogleDriveHelper()
        msg = drive.deletefile(link)
        LOGGER.info(f"Delete Result: {msg}")
    else:
        msg = 'Send/reply to a GDrive link along with command!'
    reply_message = sendMessage(msg, context.bot, update)
    threading.Thread(target=auto_delete_message, args=(context.bot, update.message, reply_message)).start()


delete_handler = CommandHandler(
    command=BotCommands.deleteCommand,
    callback=deletefile,
    filters=CustomFilters.owner_filter | CustomFilters.sudo_user,
    run_async=True,
)
dispatcher.add_handler(delete_handler)
