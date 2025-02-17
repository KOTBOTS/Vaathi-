from time import sleep

from telegram.ext import CommandHandler

from bot import DOWNLOAD_DIR, dispatcher, download_dict, download_dict_lock
from bot.helper.ext_utils.bot_utils import MirrorStatus, getDownloadByGid
from bot.helper.ext_utils.fs_utils import clean_download
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import delete_all_messages, sendMessage


def cancel_mirror(update, context):
    args = update.message.text.split(" ", maxsplit=1)
    mirror_message = None
    if len(args) > 1:
        gid = args[1]
        dl = getDownloadByGid(gid)
        if not dl:
            sendMessage(f"GID: <code>{gid}</code> not found!", context.bot, update)
            return
        with download_dict_lock:
            keys = list(download_dict.keys())
        mirror_message = dl.message
    elif update.message.reply_to_message:
        mirror_message = update.message.reply_to_message
        with download_dict_lock:
            keys = list(download_dict.keys())
            dl = download_dict[mirror_message.message_id]
    if len(args) == 1 and (
        mirror_message is None or mirror_message.message_id not in keys
    ):
        if (
            BotCommands.MirrorCommand in update.message.text
            or BotCommands.TarMirrorCommand in update.message.text
            or BotCommands.UnzipMirrorCommand in mirror_message.text
        ):
            msg = "Mirror already have been cancelled!"
        else:
            msg = f"Please reply to the <code>/{BotCommands.MirrorCommand}</code> message which was used to start the download or <code>/{BotCommands.CancelMirror} GID</code> to cancel it!"
        sendMessage(msg, context.bot, update)
        return
    if dl.status() == MirrorStatus.STATUS_UPLOADING:
        sendMessage("Upload in Progress, Don't Cancel it!", context.bot, update)
        return
    elif dl.status() == MirrorStatus.STATUS_ARCHIVING:
        sendMessage("Archival in Progress, Don't Cancel it!", context.bot, update)
        return
    elif dl.status() == MirrorStatus.STATUS_SPLITTING:
        sendMessage("Splitting in Progress, Don't Cancel it!", context.bot, update)
        return
    elif dl.status() == MirrorStatus.STATUS_EXTRACTING:
        sendMessage("Extracting in Progress, Don't Cancel it!", context.bot, update)
        return
    else:
        dl.download().cancel_download()
    sleep(3)  # Wait a Second For Aria2 To free Resources.
    clean_download(f"{DOWNLOAD_DIR}{mirror_message.message_id}/")


def cancel_all(update, context):
    with download_dict_lock:
        count = 0
        for dlDetails in list(download_dict.values()):
            if dlDetails.status() in [
                MirrorStatus.STATUS_DOWNLOADING,
                MirrorStatus.STATUS_WAITING,
            ]:
                dlDetails.download().cancel_download()
                count += 1
    delete_all_messages()
    sendMessage(f"Cancelled {count} downloads!", context.bot, update)


cancel_mirror_handler = CommandHandler(
    BotCommands.CancelMirror,
    cancel_mirror,
    filters=(CustomFilters.authorized_chat | CustomFilters.authorized_user)
    & CustomFilters.mirror_owner_filter,
    run_async=True,
)
cancel_all_handler = CommandHandler(
    BotCommands.CancelAllCommand,
    cancel_all,
    filters=CustomFilters.owner_filter,
    run_async=True,
)
dispatcher.add_handler(cancel_all_handler)
dispatcher.add_handler(cancel_mirror_handler)
