import logging
import os
import random
import socket
import string
import threading
import requests
import time
import subprocess
import psycopg2
import pkgutil
import sys


import aria2p
import telegram.ext as tg
from dotenv import load_dotenv
from pyrogram import Client
from telegraph import Telegraph
from psycopg2 import Error
from megasdkrestclient import MegaSdkRestClient, errors as mega_err

import faulthandler
faulthandler.enable()

socket.setdefaulttimeout(600)

botStartTime = time.time()
if os.path.exists("log.txt"):
    with open("log.txt", "r+") as f:
        f.truncate(0)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("log.txt"), logging.StreamHandler()],
    level=logging.INFO,
)

LOGGER = logging.getLogger(__name__)

CONFIG_FILE_URL = os.environ.get('CONFIG_FILE_URL', None)
if CONFIG_FILE_URL is not None:
    res = requests.get(CONFIG_FILE_URL)
    if res.status_code == 200:
        with open('config.env', 'wb+') as f:
            f.write(res.content)
            f.close()
    else:
        logging.error(f"Failed to download config.env {res.status_code}")

load_dotenv("config.env")

Interval = []


def getConfig(name: str):
    return os.environ[name]


def mktable():
    try:
        conn = psycopg2.connect(DB_URI)
        cur = conn.cursor()
        sql = "CREATE TABLE users (uid bigint, sudo boolean DEFAULT FALSE);"
        cur.execute(sql)
        conn.commit()
        logging.info("Table Created!")
    except Error as e:
        logging.error(e)
        exit(1)

try:
    if bool(getConfig("_____REMOVE_THIS_LINE_____")):
        logging.error("The README.md file there to be read! Exiting now!")
        exit()
except KeyError:
    pass

aria2 = aria2p.API(
    aria2p.Client(
        host="http://localhost",
        port=6800,
        secret="",
    )
)

CWD = os.getcwd()
ariaconfig = pkgutil.get_data("bot", "data/aria.conf").decode()
dhtfile = pkgutil.get_data("bot", "data/dht.dat")
dht6file = pkgutil.get_data("bot", "data/dht6.dat")
with open("dht.dat", "wb+") as dht:
    dht.write(dhtfile)
with open("dht6.dat", "wb+") as dht6:
    dht6.write(dhtfile)
ariaconfig = ariaconfig.replace("/currentwd", str(CWD))
try:
    max_dl = getConfig("MAX_CONCURRENT_DOWNLOADS")
except KeyError:
    max_dl = "4"
tracker_list = requests.get("https://raw.githubusercontent.com/XIU2/TrackersListCollection/master/all_aria2.txt").text
ariaconfig += f"\nmax-concurrent-downloads={max_dl}\nbt-tracker={tracker_list}"
with open("aria.conf", "w+") as ariaconf:
    ariaconf.write(ariaconfig)
ARIA_CHILD_PROC = None
try:
    ARIA_CHILD_PROC = subprocess.Popen(["aria2c", f"--conf-path={CWD}/aria.conf"])
except FileNotFoundError:
    LOGGER.error("Please install Aria2c, Exiting..")
    sys.exit(0)
except OSError:
    LOGGER.error("Aria2c Binary might have got damaged, Please Check and reinstall..")
    sys.exit(0)
time.sleep(1)

DOWNLOAD_DIR = None
BOT_TOKEN = None

download_dict_lock = threading.Lock()
status_reply_dict_lock = threading.Lock()
# Key: update.effective_chat.id
# Value: telegram.Message
status_reply_dict = {}
# Key: update.message.message_id
# Value: An object of Status
download_dict = {}
# Stores list of users and chats the bot is authorized to use in
AUTHORIZED_CHATS = set()
SUDO_USERS = set()
AS_DOC_USERS = set()
AS_MEDIA_USERS = set()
if os.path.exists("authorized_chats.txt"):
    with open("authorized_chats.txt", "r+") as f:
        lines = f.readlines()
        for line in lines:
            #    LOGGER.info(line.split())
            AUTHORIZED_CHATS.add(int(line.split()[0]))
if os.path.exists('sudo_users.txt'):
    with open('sudo_users.txt', 'r+') as f:
        lines = f.readlines()
        for line in lines:
            SUDO_USERS.add(int(line.split()[0]))
try:
    achats = getConfig("AUTHORIZED_CHATS")
    achats = achats.split(" ")
    for chats in achats:
        AUTHORIZED_CHATS.add(int(chats))
except:
    pass
try:
    schats = getConfig('SUDO_USERS')
    schats = schats.split(" ")
    for chats in schats:
        SUDO_USERS.add(int(chats))
except:
    pass
try:
    BOT_TOKEN = getConfig("BOT_TOKEN")
    parent_id = getConfig("GDRIVE_FOLDER_ID")
    DOWNLOAD_DIR = getConfig("DOWNLOAD_DIR")
    if not DOWNLOAD_DIR.endswith("/"):
        DOWNLOAD_DIR = DOWNLOAD_DIR + "/"
    DOWNLOAD_STATUS_UPDATE_INTERVAL = int(getConfig("DOWNLOAD_STATUS_UPDATE_INTERVAL"))
    OWNER_ID = int(getConfig("OWNER_ID"))
    AUTO_DELETE_MESSAGE_DURATION = int(getConfig("AUTO_DELETE_MESSAGE_DURATION"))
    TELEGRAM_API = getConfig("TELEGRAM_API")
    TELEGRAM_HASH = getConfig("TELEGRAM_HASH")
except KeyError:
    LOGGER.error("One or more env variables missing! Exiting now")
    exit(1)
try:
    DB_URI = getConfig('DATABASE_URL')
    if len(DB_URI) == 0:
        raise KeyError
except KeyError:
    DB_URI = None
if DB_URI is not None:
    try:
        conn = psycopg2.connect(DB_URI)
        cur = conn.cursor()
        sql = "SELECT * from users;"
        cur.execute(sql)
        rows = cur.fetchall()  # returns a list ==> (uid, sudo)
        for row in rows:
            AUTHORIZED_CHATS.add(row[0])
            if row[1]:
                SUDO_USERS.add(row[0])
    except Error as e:
        if 'relation "users" does not exist' in str(e):
            mktable()
        else:
            LOGGER.error(e)
            exit(1)
    finally:
        cur.close()
        conn.close()

LOGGER.info("Generating USER_SESSION_STRING")
app = Client(
    ":memory:", api_id=int(TELEGRAM_API), api_hash=TELEGRAM_HASH, bot_token=BOT_TOKEN
)

# Generate Telegraph Token
sname = "".join(random.SystemRandom().choices(string.ascii_letters, k=8))
LOGGER.info("Generating Telegraph Token using '" + sname + "' name")
telegraph = Telegraph()
telegraph.create_account(short_name=sname)
telegraph_token = telegraph.get_access_token()
LOGGER.info("Telegraph Token Generated: '" + telegraph_token + "'")

try:
    MEGA_KEY = getConfig("MEGA_KEY")
except KeyError:
    MEGA_KEY = None
    LOGGER.info("MEGA API KEY NOT AVAILABLE")
MEGA_CHILD_PROC = None
if MEGA_KEY is not None:
    try:
        MEGA_CHILD_PROC = subprocess.Popen(["megasdkrest", "--apikey", MEGA_KEY])
    except FileNotFoundError:
        LOGGER.error("Please install Megasdkrest Binary, Exiting..")
        sys.exit(0)
    except OSError:
        LOGGER.error("Megasdkrest Binary might have got damaged, Please Check ..")
        sys.exit(0)
    time.sleep(3)
    mega_client = MegaSdkRestClient("http://localhost:6090")
    try:
        MEGA_USERNAME = getConfig("MEGA_USERNAME")
        MEGA_PASSWORD = getConfig("MEGA_PASSWORD")
        if len(MEGA_USERNAME) > 0 and len(MEGA_PASSWORD) > 0:
            try:
                mega_client.login(MEGA_USERNAME, MEGA_PASSWORD)
            except mega_err.MegaSdkRestClientException as e:
                logging.error(e.message["message"])
                exit(0)
        else:
            LOGGER.info("Mega API KEY provided but credentials not provided. Starting Mega in anonymous mode!")
            MEGA_USERNAME = None
            MEGA_PASSWORD = None
    except KeyError:
        LOGGER.info("Mega API KEY provided but credentials not provided. Starting Mega in anonymous mode!")
        MEGA_USERNAME = None
        MEGA_PASSWORD = None
else:
    MEGA_USERNAME = None
    MEGA_PASSWORD = None
try:
    INDEX_URL = getConfig("INDEX_URL")
    if len(INDEX_URL) == 0:
        INDEX_URL = None
except KeyError:
    INDEX_URL = None
try:
    BUTTON_THREE_NAME = getConfig("BUTTON_THREE_NAME")
    BUTTON_THREE_URL = getConfig("BUTTON_THREE_URL")
    if len(BUTTON_THREE_NAME) == 0 or len(BUTTON_THREE_URL) == 0:
        raise KeyError
except KeyError:
    BUTTON_THREE_NAME = None
    BUTTON_THREE_URL = None
try:
    BUTTON_FOUR_NAME = getConfig("BUTTON_FOUR_NAME")
    BUTTON_FOUR_URL = getConfig("BUTTON_FOUR_URL")
    if len(BUTTON_FOUR_NAME) == 0 or len(BUTTON_FOUR_URL) == 0:
        raise KeyError
except KeyError:
    BUTTON_FOUR_NAME = None
    BUTTON_FOUR_URL = None
try:
    BUTTON_FIVE_NAME = getConfig("BUTTON_FIVE_NAME")
    BUTTON_FIVE_URL = getConfig("BUTTON_FIVE_URL")
    if len(BUTTON_FIVE_NAME) == 0 or len(BUTTON_FIVE_URL) == 0:
        raise KeyError
except KeyError:
    BUTTON_FIVE_NAME = None
    BUTTON_FIVE_URL = None
try:
    IS_TEAM_DRIVE = getConfig("IS_TEAM_DRIVE")
    IS_TEAM_DRIVE = IS_TEAM_DRIVE.lower() == "true"
except KeyError:
    IS_TEAM_DRIVE = False

try:
    USE_SERVICE_ACCOUNTS = getConfig("USE_SERVICE_ACCOUNTS")
    USE_SERVICE_ACCOUNTS = USE_SERVICE_ACCOUNTS.lower() == "true"
except KeyError:
    USE_SERVICE_ACCOUNTS = False

try:
    BLOCK_MEGA_LINKS = getConfig("BLOCK_MEGA_LINKS")
    BLOCK_MEGA_LINKS = BLOCK_MEGA_LINKS.lower() == "true"
except KeyError:
    BLOCK_MEGA_LINKS = False

try:
    SHORTENER = getConfig("SHORTENER")
    SHORTENER_API = getConfig("SHORTENER_API")
    if len(SHORTENER) == 0 or len(SHORTENER_API) == 0:
        raise KeyError
except KeyError:
    SHORTENER = None
    SHORTENER_API = None

try:
    IGNORE_PENDING_REQUESTS = getConfig("IGNORE_PENDING_REQUESTS")
    IGNORE_PENDING_REQUESTS = IGNORE_PENDING_REQUESTS.lower() == 'true'
except KeyError:
    IGNORE_PENDING_REQUESTS = False
try:
    TOKEN_PICKLE_URL = getConfig('TOKEN_PICKLE_URL')
    if len(TOKEN_PICKLE_URL) == 0:
        TOKEN_PICKLE_URL = None
    else:
        res = requests.get(TOKEN_PICKLE_URL)
        if res.status_code == 200:
            with open('token.pickle', 'wb+') as f:
                f.write(res.content)
                f.close()
        else:
            logging.error(f"Failed to download token.pickle {res.status_code}")
            raise KeyError
except KeyError:
    pass
try:
    ACCOUNTS_ZIP_URL = getConfig('ACCOUNTS_ZIP_URL')
    if len(ACCOUNTS_ZIP_URL) == 0:
        ACCOUNTS_ZIP_URL = None
    else:
        res = requests.get(ACCOUNTS_ZIP_URL)
        if res.status_code == 200:
            with open('accounts.zip', 'wb+') as f:
                f.write(res.content)
                f.close()
        else:
            logging.error(f"Failed to download accounts.zip {res.status_code}")
            raise KeyError
        subprocess.run(["unzip", "-q", "-o", "accounts.zip"])
        os.remove("accounts.zip")
except KeyError:
    pass

try:
    STOP_DUPLICATE_MIRROR = getConfig('STOP_DUPLICATE_MIRROR')
    if STOP_DUPLICATE_MIRROR.lower() == 'true':
        STOP_DUPLICATE_MIRROR = True
    else:
        STOP_DUPLICATE_MIRROR = False
except KeyError:
    STOP_DUPLICATE_MIRROR = False
    
try:
    AS_DOCUMENT = getConfig('AS_DOCUMENT')
    AS_DOCUMENT = AS_DOCUMENT.lower() == 'true'
except KeyError:
    AS_DOCUMENT = False    
try:
    TG_SPLIT_SIZE = getConfig('TG_SPLIT_SIZE')
    if len(TG_SPLIT_SIZE) == 0 or int(TG_SPLIT_SIZE) > 2097152000:
        raise KeyError
    else:
        TG_SPLIT_SIZE = int(TG_SPLIT_SIZE)
except KeyError:
    TG_SPLIT_SIZE = 2097152000

updater = tg.Updater(token=BOT_TOKEN)
bot = updater.bot
dispatcher = updater.dispatcher
