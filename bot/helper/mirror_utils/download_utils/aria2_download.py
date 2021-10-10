import threading
from time import sleep
from aria2p import API

from bot import aria2, download_dict_lock, STOP_DUPLICATE_MIRROR
from bot.helper.ext_utils.bot_utils import (
    LOGGER,
    download_dict,
    getDownloadByGid,
    is_magnet,
    new_thread,
)
from bot.helper.mirror_utils.status_utils.aria_download_status import AriaDownloadStatus
from bot.helper.telegram_helper.message_utils import *
from .download_helper import DownloadHelper
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper


class AriaDownloadHelper(DownloadHelper):
    def __init__(self):
        super().__init__()

    @new_thread
    def __onDownloadStarted(self, api, gid):
        if STOP_DUPLICATE_MIRROR:
            sleep(1)
            dl = getDownloadByGid(gid)
            download = aria2.get_download(gid)
            if STOP_DUPLICATE_MIRROR and dl is not None and not dl.getListener().isLeech:
                LOGGER.info('Checking File/Folder if already in Drive...')
                sname = aria2.get_download(gid).name
                if dl.getListener().isZip:
                    sname = sname + ".zip"
                if not dl.getListener().extract:
                    gdrive = GoogleDriveHelper()
                    smsg, button = gdrive.drive_list(sname, True)
                    if smsg:
                         dl.getListener().onDownloadError('File/Folder already available in Drive.\n\n')
                         aria2.remove([download], force=True)
                         sendMarkup("Here are the search results:", dl.getListener().bot, dl.getListener().update, button)
                         return
        update_all_messages()

    def __onDownloadComplete(self, api: API, gid):
        LOGGER.info(f"onDownloadComplete: {gid}")
        dl = getDownloadByGid(gid)
        download = api.get_download(gid)
        if download.followed_by_ids:
            new_gid = download.followed_by_ids[0]
            new_download = api.get_download(new_gid)
            if dl is None:
                dl = getDownloadByGid(new_gid)
            with download_dict_lock:
                download_dict[dl.uid()] = AriaDownloadStatus(new_gid, dl.getListener())
                if new_download.is_torrent:
                    download_dict[dl.uid()].is_torrent = True
            update_all_messages()
            LOGGER.info(f"Changed gid from {gid} to {new_gid}")
        elif dl:
            threading.Thread(target=dl.getListener().onDownloadComplete).start()

    @new_thread
    def __onDownloadPause(self, api, gid):
        LOGGER.info(f"onDownloadPause: {gid}")
        dl = getDownloadByGid(gid)
        dl.getListener().onDownloadError("Download stopped by user!")

    @new_thread
    def __onDownloadStopped(self, api, gid):
        LOGGER.info(f"onDownloadStop: {gid}")
        dl = getDownloadByGid(gid)
        if dl:
            dl.getListener().onDownloadError("Dead torrent!")

    @new_thread
    def __onDownloadError(self, api, gid):
        sleep(
            0.5
        )  # sleep for split second to ensure proper dl gid update from onDownloadComplete
        LOGGER.info(f"onDownloadError: {gid}")
        dl = getDownloadByGid(gid)
        download = api.get_download(gid)
        error = download.error_message
        LOGGER.info(f"Download Error: {error}")
        if dl:
            dl.getListener().onDownloadError(error)

    def start_listener(self):
        aria2.listen_to_notifications(
            threaded=True,
            on_download_start=self.__onDownloadStarted,
            on_download_error=self.__onDownloadError,
            on_download_pause=self.__onDownloadPause,
            on_download_stop=self.__onDownloadStopped,
            on_download_complete=self.__onDownloadComplete,
        )

    def add_download(self, link: str, path, listener, filename):
        if is_magnet(link):
            download = aria2.add_magnet(link, {"dir": path, "out": filename})
        else:
            download = aria2.add_uris([link], {"dir": path, "out": filename})
        if download.error_message:  # no need to proceed further at this point
            listener.onDownloadError(download.error_message)
            return
        with download_dict_lock:
            download_dict[listener.uid] = AriaDownloadStatus(download.gid, listener)
            LOGGER.info(f"Started: {download.gid} DIR:{download.dir} ")
