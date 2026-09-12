# ============================================================
# BenShot By Zxyns
# ============================================================

import asyncio
import json
import os
import random
import time
import logging
import sys
import traceback
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from io import BytesIO
from typing import Dict, List, Optional, Set
import aiohttp
from aiohttp import ClientSession, TCPConnector, ClientTimeout
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from telegram.error import RetryAfter, TimedOut, NetworkError, Forbidden

# ==================== LOGGING ====================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

# ==================== HEALTH CHECK SERVER ====================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args):
        return

def run_health_check_server():
    server = HTTPServer(("0.0.0.0", 5000), HealthCheckHandler)
    server.serve_forever()

# ==================== CONNECTION POOL ====================
class ConnectionPool:
    def __init__(self, max_connections=50):
        self.max_connections = max_connections
        self.sessions = []
        self.available = []
        self.lock = asyncio.Lock()
        self.running = True
    async def start(self):
        for _ in range(self.max_connections):
            session = ClientSession(
                timeout=ClientTimeout(total=0.5),
                connector=TCPConnector(limit=100)
            )
            self.sessions.append(session)
            self.available.append(session)
        logger.info("✅ Connection Pool started")
    async def stop(self):
        self.running = False
        for session in self.sessions:
            await session.close()
    async def get_session(self):
        async with self.lock:
            while not self.available:
                await asyncio.sleep(0.0001)
            return self.available.pop()
    async def return_session(self, session):
        async with self.lock:
            self.available.append(session)

# ==================== CONFIG ====================
TOKENS = [
"8966737003:AAHtRcATawdxJSANmDSbjUKa9qhSAhayWFU" ,
"8473081376:AAHwGDCUgTrY1tlS7urrlzwU9htR0FT-4wM" ,
"8824291861:AAFYpZaV8j0_ARAOH34h8rhYWA6AmMvQJcE" ,
"8937229505:AAGOYyZdoiXVEv6aybN5fxJ7_R_cBTcKVq8" ,
"8907726550:AAEBiHIjcQPOcUcGXK5Pg_fA0Xzk-gxnhSI" ,
"8946646015:AAF7krV_tH6dL_w4hZweZ8AvLjSCHxCIPn8" ,
"8091275354:AAHsZO45bz6m2ctZCQSnQjEga1-TowUdMY8" ,
"8841569513:AAHNrFd7go1D0W9FIPizXQO13y_02BdMnVw" ,
"8807816791:AAE9NNGwUKXgnHa7Pwtd6yG4lgiBOFu2J28" ,
"8734612907:AAE_ktKyu0qsMhibP-gnmTbW6int8bdrtUM" ,
"8675702631:AAHohYK7t4ChWXQH6_9zxQSc3_dkbifVcBQ" ,
]

OWNER_ID = 8895537848
SUDO_FILE = "sudo_users.json"
PFP_FOLDER = "pfps"
TARGET_PHOTO_FOLDER = "target_photos"
for folder in [PFP_FOLDER, TARGET_PHOTO_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# ==================== GLOBAL STATE ====================
SUDO_USERS = {OWNER_ID}
TARGETS = {}
GAME_OVER_PFP = {}
ACTIVE_TASKS = defaultdict(dict)
BASE_DELAY = 0.0000001
ULTRA_MAX_MODE = True
AUTO_FLOOD_BYPASS = True
REFRESH_COUNTER = 0
start_time = time.time()

BOT_DEFAULT_COOLDOWN = 0.0   # effectively no delay
bot_data = {token: {
    'cooldown': BOT_DEFAULT_COOLDOWN,
    'last_send': 0,
    'healthy': True,
    'fail_count': 0,
    'last_health_check': 0,
    'flood_wait_until': 0,
    'skip_until': 0,
    'restart_needed': False,
    'bot_id': None,
} for token in TOKENS}

SLIDE_TARGETS = defaultdict(set)
SLIDE_ABUSE_MAP = defaultdict(dict)

def load_sudo():
    global SUDO_USERS
    if os.path.exists(SUDO_FILE):
        with open(SUDO_FILE, 'r') as f:
            SUDO_USERS = set(json.load(f))
load_sudo()

def save_sudo():
    with open(SUDO_FILE, 'w') as f:
        json.dump(list(SUDO_USERS), f)

# ==================== EMOJIS & TEMPLATES ====================
ALL_SINGLE_EMOJIS = [
    '❤️','🧡','💛','💚','💙','💜','🖤','🤍','🤎','💗','💓','💖','💕','💘','💝','💟','♡','❤️‍🔥','❤️🩹', '⌚', '📱', '📲', '💻', '⌨️', '🖥️', '🖨️', '🖱️', '🖲️', '🕹️', '🗜️', '💽', '💾', '💿', '📀', '📼', '📷', '📸', '📹', '🎥', '📽️', '🎞️', '📞', '☎️', '📟', '📠', '📺', '📻', '🎙️', '🎚️', '🎛️', '🧭', '⏱️', '⏲️', '⏰', '🕰️', '⌛', '⏳', '📡', '🔋', '🔌', '💡', '🔦', '🕯️', '🪔', '🧯', '🛢️', '💸', '💵', '💴', '💶', '💷', '🪙', '💰', '💳', '💎', '⚖️', '🧰', '🔧', '🔨', '⚒️', '🛠️', '⛏️', '🪚', '🔩', '⚙️', '🪤', '🧱', '🪨', '🛖', '🧲', '🔫', '💣', '🧨', '🛡️', '🧪', '🔬', '🔭', '📡', '💉', '🧬', '🪣', '🔗', '⚔️', '🛡️', '🚬', '⚰️', '🪦', '⚱️', '🏺', '🔮', '📿', '🧿', '💈', '⚗️', '🔭', '🗡️', '💊', '🩸', '🫀', '🫁', '🧠', '🦠', '🧫', '🧬', '🌡️', '🪠', '🧹', '🪥', '🧺', '🪣', '🚽', '🚰', '🚿', '🛁', '🛀', '🧼', '🧽', '🪒', '🔑', '🗝️', '🚪', '🪑', '🛋️', '🛏️', '🛌', '🧸', '🪆', '🖼️', '🎁', '🎈', '🎏', '🎀', '🪄', '🪅', '🎊', '🎉', '🎎', '🏮', '🎐', '🧧', '✉️', '📩', '📨', '📧', '💌', '📥', '📤', '📦', '🏷️', '🪧', '📪', '📫', '📬', '📭', '📮', '📜', '📃', '📄', '📑', '📊', '📈', '📉', '🗒️', '🗓️', '📆', '📅', '🗑️', '🗃️', '🗳️', '🗄️', '📋', '📁', '📂', '🗂️', '🗞️', '📰', '📓', '📔', '📒', '📕', '📗', '📘', '📙', '📚', '🔖', '🧷', '🔗', '📎', '🖇️', '📐', '📏', '🧮', '📌', '📍', '✂️', '🖊️', '🖋️', '✒️', '🖌️', '🖍️', '📝', '🩷', '🔍', '🔎', '🔏', '🔐', '🔒', '🔓'    '😀', '😃', '😄', '😁', '😆', '😅', '🤣', '😂', '🙂', '🙃',
    '😉', '😊', '😇', '🥰', '😍', '🤩', '😘', '😗', '😚', '😙',
    '😋', '😛', '😜', '🤪', '😝', '🤑', '🤗', '🤭', '🤫', '🤔',
    '🤐', '🤨', '😐', '😑', '😶', '😏', '😒', '🙄', '😬', '🤥',
    '😌', '😔', '😪', '🤤', '😴', '😷', '🤒', '🤕', '🤢', '🤮',
    '🤧', '🥵', '🥶', '🥴', '😵', '🤯', '🤠', '🥳', '😎', '🤓',
    '🧐', '😕', '😟', '🙁', '😮', '😯', '😲', '😳', '🥺', '😦',
    '😧', '😨', '😰', '😥', '😢', '😭', '😱', '😖', '😣', '😞',
    '😓', '😩', '😫', '🥱', '😤', '😡', '😠', '🤬', '😈', '👿',
    '💀', '☠️', '💩', '🤡', '👹', '👺', '👻', '👽', '👾', '🤖',
    '😺', '😸', '😹', '😻', '😼', '😽', '🙀', '😿', '😾', '👋',
    '🤚', '🖐️', '✋', '🖖', '👌', '🤌', '🤏', '✌️', '🤞', '🫰',
    '🤟', '🤘', '🤙', '👈', '👉', '👆', '🖕', '👇', '☝️', '👍',
    '👎', '✊', '👊', '🤛', '🤜', '👏', '🙌', '👐', '🤲', '🤝',
    '🙏', '✍️', '💅', '🤳', '💪', '🦾', '🦿', '🦵', '🦶', '👂',
    '🦻', '👃', '🧠', '🫀', '🫁', '🦷', '🦴', '👀', '👁️', '👅',
    '👄', '💋', '🩸', '👶', '👧', '🧒', '👦', '👩', '🧑', '👨',
    '👩‍🦱', '🧑‍🦱', '👨‍🦱', '👩‍🦰', '🧑‍🦰', '👨‍🦰', '👱‍♀️', '👱', '👱‍♂️', '👩‍🦳',
    '🧑‍🦳', '👨‍🦳', '👩‍🦲', '🧑‍🦲', '👨‍🦲', '🧔‍♀️', '🧔', '🧔‍♂️', '👵', '🧓',
    '👴', '👲', '👳‍♀️', '👳', '👳‍♂️', '🧕', '👮‍♀️', '👮', '👮‍♂️', '👷‍♀️',
    '👷', '👷‍♂️', '💂‍♀️', '💂', '💂‍♂️', '🕵️‍♀️', '🕵️', '🕵️‍♂️', '👩‍⚕️', '🧑‍⚕️',
    '👨‍⚕️', '👩‍🌾', '🧑‍🌾', '👨‍🌾', '👩‍🍳', '🧑‍🍳', '👨‍🍳', '👩‍🎓', '🧑‍🎓', '👨‍🎓',
    '👩‍🎤', '🧑‍🎤', '👨‍🎤', '👩‍🏫', '🧑‍🏫', '👨‍🏫', '👩‍💻', '🧑‍💻', '👨‍💻', '👩‍💼',
    '🧑‍💼', '👨‍💼', '👩‍🔧', '🧑‍🔧', '👨‍🔧', '👩‍🔬', '🧑‍🔬', '👨‍🔬', '👩‍🎨', '🧑‍🎨',
    '👨‍🎨', '👩‍🚒', '🧑‍🚒', '👨‍🚒', '👩‍✈️', '🧑‍✈️', '👨‍✈️', '👩‍🚀', '🧑‍🚀', '👨‍🚀',
    '👩‍⚖️', '🧑‍⚖️', '👨‍⚖️', '👰‍♀️', '👰', '👰‍♂️', '🤵‍♀️', '🤵', '🤵‍♂️', '👸',
    '🤴', '🥷', '🦸‍♀️', '🦸', '🦸‍♂️', '🦹‍♀️', '🦹', '🦹‍♂️', '🧟‍♀️', '🧟',
    '🧟‍♂️', '🧞‍♀️', '🧞', '🧞‍♂️', '🧜‍♀️', '🧜', '🧜‍♂️', '🧚‍♀️', '🧚', '🧚‍♂️',
    '🧛‍♀️', '🧛', '🧛‍♂️', '🧜‍♀️', '🧝‍♀️', '🧝', '🧝‍♂️', '🧌', '💆‍♀️', '💆',
    '💆‍♂️', '💇‍♀️', '💇', '💇‍♂️', '🚶‍♀️', '🚶', '🚶‍♂️', '🧍‍♀️', '🧍', '🧍‍♂️',
    '🧎‍♀️', '🧎', '🧎‍♂️', '🏃‍♀️', '🏃', '🏃‍♂️', '💃', '🕺', '🕴️', '👯‍♀️',
    '👯', '👯‍♂️', '🧖‍♀️', '🧖', '🧖‍♂️', '🧘‍♀️', '🧘', '🧘‍♂️', '🐶', '🐱',
    '🐭', '🐹', '🐰', '🦊', '🐻', '🐼', '🐨', '🐯', '🦁', '🐮',
    '🐷', '🐽', '🐸', '🐵', '🙈', '🙉', '🙊', '🐒', '🐔', '🐧',
    '🐦', '🐤', '🐣', '🐥', '🦆', '🦅', '🦉', '🦇', '🐺', '🐗',
    '🐴', '🦄', '🐝', '🪱', '🐛', '🦋', '🐌', '🐞', '🐜', '🪰',
    '🪲', '蟑', '🕷️', '🕸️', '🦂', '🦟', '🪰', '🪱', '🐢', '🐍',
    '🦎', '🦖', '🦕', '🐙', '🦑', '🦐', '🦞', '🦀', '🪸', '🐠',
    '🐟', '🐬', '🐳', '🐋', '🦈', '🐊', '🐅', '🐆', '🦓', '🦍',
    '🦧', '🐘', '🦛', '👺', '🐪', '🐫', '🦒', '🦘', '🐃', '🐂',
    '🐄', '🐎', '🐖', '🐏', '🐑', '🐐', '🦌', '🐕', '🐩', '🦮',
    '🐕‍🦺', '🐈', '🐈‍⬛', '🪶', '🐓', '🦃', '🦤', '🦚', '🦜', '🦢',
    '🦩', '🕊️', '🐇', '🦝', '👹', '🦨', '🦡', '🦫', '🦦', '🦥',
    '🦔', '🦧', '🐾', '🐉', '🐲', '🌵', '🎄', '🌲', '🌳', '🌴',
    '🪵', '🌱', '🌿', '☘️', '🍀', '🎍', '🎋', '🍃', '🍂', '🍁',
    '🍄', '🐚', '🪨', '🌾', '💐', '🌷', '🌹', '🥀', '🌺', '🌸',
    '🌼', '🌻', '🌞', '🌝', '🌛', '🌜', '🌕', '🌖', '🌗', '🌘',
    '🌑', '🌒', '🌓', '🌔', '🌙', '🌎', '🌍', '🌏', '🪐', '💫',
    '⭐', '🌟', '✨', '⚡', '☄️', '💥', '🔥', '🌪️', '🌈', '☀️',
    '🌤️', '⛅', '🌥️', '☁️', '🌦️', '🌧️', '⛈️', '🌩️', '🌨️', '❄️',
    '☃️', '⛄', '🌬️', '💨', '💧', '💦', '☔', '☂️', '🌊', '🌫️'
]

ALL_FLAG_EMOJIS = [
    '🇦🇫','🇦🇽','🇦🇱','🇩🇿','🇦🇸','🇦🇩','🇦🇴','🇦🇮','🇦🇶','🇦🇬','🇦🇷','🇦🇲','🇦🇼','🇦🇺','🇦🇹','🇦🇿','🇧🇸','🇧🇭','🇧🇩','🇧🇧','🇧🇾','🇧🇪','🇧🇿','🇧🇯','🇧🇲','🇧🇹','🇧🇴','🇧🇦','🇧🇼','🇧🇷','🇮🇴','🇻🇬','🇧🇳','🇧🇬','🇧🇫','🇧🇮','🇰🇭','🇨🇲','🇨🇦','🇮🇨','🇨🇻','🇧🇶','🇰🇾','🇨🇫','🇹🇩','🇨🇱','🇨🇳','🇨🇽','🇨🇨','🇨🇴','🇰🇲','🇨🇬','🇨🇩','🇨🇰','🇨🇷','🇨🇮','🇭🇷','🇨🇺','🇨🇼','🇨🇾','🇨🇿','🇩🇰','🇩🇯','🇩🇲','🇩🇴','🇪🇨','🇪🇬','🇸🇻','🇬🇶','🇪🇷','🇪🇪','🇪🇹','🇪🇺','🇫🇰','🇫🇴','🇫🇯','🇫🇮','🇫🇷','🇬🇫','🇵🇫','🇹🇫','🇬🇦','🇬🇲','🇬🇪','🇩🇪','🇬🇭','🇬🇮','🇬🇷','🇬🇱','🇬🇩','🇬🇵','🇬🇺','🇬🇹','🇬🇬','🇬🇳','🇬🇼','🇬🇾','🇭🇹','🇭🇳','🇭🇰','🇭🇺','🇮🇸','🇮🇳','🇮🇩','🇮🇷','🇮🇶','🇮🇪','🇮🇲','🇮🇱','🇮🇹','🇯🇲','🇯🇵','🇯🇪','🇯🇴','🇰🇿','🇰🇪','🇰🇮','🇽🇰','🇰🇼','🇰🇬','🇱🇦','🇱🇻','🇱🇧','🇱🇸','🇱🇷','🇱🇾','🇱🇮','🇱🇹','🇱🇺','🇲🇴','🇲🇰','🇲🇬','🇲🇼','🇲🇾','🇲🇻','🇲🇱','🇲🇹','🇲🇭','🇲🇶','🇲🇷','🇲🇺','🇾🇹','🇲🇽','🇫🇲','🇲🇩','🇲🇨','🇲🇳','🇲🇪','🇲🇸','🇲🇦','🇲🇿','🇲🇲','🇳🇦','🇳🇷','🇳🇵','🇳🇱','🇳🇨','🇳🇿','🇳🇮','🇳🇪','🇳🇬','🇳🇺','🇳🇫','🇰🇵','🇲🇵','🇳🇴','🇴🇲','🇵🇰','🇵🇼','🇵🇸','🇵🇦','🇵🇬','🇵🇾','🇵🇪','🇵🇭','🇵🇳','🇵🇱','🇵🇹','🇵🇷','🇶🇦','🇷🇪','🇷🇴','🇷🇺','🇷🇼','🇧🇱','🇸🇭','🇰🇳','🇱🇨','🇵🇲','🇻🇨','🇼🇸','🇸🇲','🇸🇹','🇸🇦','🇸🇳','🇷🇸','🇸🇨','🇸🇱','🇸🇬','🇸🇽','🇸🇰','🇸🇮','🇬🇸','🇸🇧','🇸🇴','🇿🇦','🇬🇸','🇰🇷','🇸🇸','🇪🇸','🇱🇰','🇸🇩','🇸🇷','🇸🇯','🇸🇿','🇸🇪','🇨🇭','🇸🇾','🇹🇼','🇹🇯','🇹🇿','🇹🇭','🇹🇱','🇹🇬','🇹🇰','🇹🇴','🇹🇹','🇹🇳','🇹🇷','🇹🇲','🇹🇨','🇹🇻','🇺🇬','🇺🇦','🇦🇪','🇬🇧','🇺🇸','🇻🇮','🇺🇾','🇺🇿','🇻🇺','🇻🇦','🇻🇪','🇻🇳','🇼🇫','🇪🇭','🇾🇪','🇿🇲','🇿🇼',
    '🏴󠁧󠁢󠁥󠁮󠁧󠁿', '🏴󠁧󠁢󠁳󠁣󠁴󠁿', '🏴󠁧󠁢󠁷󠁬󠁳󠁿',
]

ALL_WATER_EMOJIS = [
        '😀', '😃', '😄', '😁', '😆', '😅', '🤣', '😂', '🙂', '🙃',
    '😉', '😊', '😇', '🥰', '😍', '🤩', '😘', '😗', '😚', '😙',
    '😋', '😛', '😜', '🤪', '😝', '🤑', '🤗', '🤭', '🤫', '🤔',
    '🤐', '🤨', '😐', '😑', '😶', '😏', '😒', '🙄', '😬', '🤥',
    '😌', '😔', '😪', '🤤', '😴', '😷', '🤒', '🤕', '🤢', '🤮'
, '💧', '💦', '🌊', '🌊', '🧊', '🫧', '🐳', '🐋', '🐬', '🦭', '🐟', '🐠', '🐡', '🦈', '🐙', '🐚', '🪸', '🦖', '🦞', '🦐', '🦑', '🪼', '🛶', '⛵', '🚤', '🛥️', '⛴️', '🛳️', '🚢', '⚓', '🛟', '🌊', '💧', '💦', '🚰', '🚿', '🛁', '🛀',
]

ALL_HEART_EMOJIS = ['❤️','🧡','💛','💚','💙','💜','🖤','🤍','🤎']

# ==================== NC WORDS ====================
NC1_WORD = "TMKC !¡"
NC2_WORD = "🌎Ҳҷ🪐" * 80
NC3_WORD = "Ҳҷ💟Ҳҷ✨Ҳҷ💎Ҳҷ🍥Ҳҷ🧊Ҳҷ🕊️" * 70 + " TERI MA RAND"
NC4_WORD = "🚫🚫😂🚫💙💙💙🚫🚫🚫💙💙💙😂🚫 " * 20 + "RAND KE BACHHE"

ZXYNNC_WORD = "ZXYN KO BAAP BOL RUNDYKE BACCHE"
STORMNC_WORD = "STORM KO BAAP BOL RUNDYK BACCHE"
CODEZXYNNC_WORD = "CODEZXYN KO BAAP BOL RUNDYK BACCHE"

# ==================== SLIDE ABUSES ====================
SLIDE1_ABUSES = [
    "ʙʜᴏꜱᴅɪᴋᴇ 🖕",
    "ᴍᴀᴅᴀʀᴄʜᴏᴅ 🤬",
    "ʙᴇʜᴇɴᴄʜᴏᴅ 🖕",
    "ᴄʜᴜᴛɪʏᴀ ꜱᴀᴀʟᴀ 🤡",
    "ɢᴀɴᴅᴜ ɪɴꜱᴀᴀɴ 💩",
    "ʀᴀɴᴅɪ ᴋᴇ ʙᴀᴄᴄʜᴇ 🖕",
    "ʟᴏᴅᴜ ʙʜᴀᴅᴡᴇ 😡",
    "ᴛᴇʀɪ ᴍᴀᴀ ᴋɪ ᴄʜᴜᴛ 🖕",
    "ʜᴀʀᴀᴍᴢᴀᴅᴀ ᴋᴀʜɪɴ ᴋᴀ 🤬",
    "ᴋᴀᴍɪɴᴇ ᴋᴜᴛᴛᴇ 🐕",
    "ʜɪᴊᴅᴇ ᴋɪ ᴀᴜʟᴀᴅ 🎭",
    "ᴀᴘɴɪ ᴀᴜᴋᴀᴛ ᴍᴇɪɴ ʀᴇʜ ʙʜᴀᴅᴡᴇ 🖕",
    "ɢᴀᴀɴᴅ ᴍᴀʀᴀ ᴄʜᴜᴘ ᴄʜᴀᴀᴘ 🍑",
    "ʟᴀᴜᴅᴇ ᴋᴇ ʙᴀᴀʟ 🥢",
    "ᴄʜɪɴᴀʟ ᴋɪ ᴀᴜʟᴀᴀᴅ 🤬",
    "ᴊʜᴀᴛᴜꜱ ꜱᴀᴀʟᴀ 🖕",
    "ʙʜᴀᴅᴡᴀ ᴋᴀʜɪɴ ᴋᴀ 🤡",
    "ᴛᴇʀɪ ʙᴇʜᴀɴ ᴋᴏ ʟᴏᴅᴀ 🖕",
    "ᴍᴀᴀ ᴋᴇ ʟᴀᴜᴅᴇ 🤬",
    "ᴄʜᴏᴏᴛ ᴋᴇ ʙᴀᴀʟ 💩",
    "ᴛᴜᴍʜᴀʀɪ ᴀᴜᴋᴀᴛ ɴᴀʜɪ ʜᴀɪ 🖕",
    "ᴍᴀᴀ ᴋɪ ᴄʜᴜᴛ ᴛᴇʀɪ 🤬",
    "ʟᴏᴅᴜ ɪɴꜱᴀᴀɴ 🤡",
    "ɢᴀɴᴅᴜ ʜᴀɪ ᴛᴜ 💩",
    "ᴄʜᴜᴛɪʏᴀ ʜᴀɪ ᴋʏᴀ 🖕",
    "ᴀᴘɴɪ ᴍᴀᴀ ᴋᴏ ᴅᴇᴋʜ 👁️",
    "ᴘᴀᴘᴀ ꜱᴇ ᴘᴏᴏᴄʜ 🧔",
    "ʜɪᴊᴅᴀ ʜᴀɪ ᴛᴜ 🎭",
    "ᴛᴇʀɪ ᴍᴀᴀ ʀᴀɴᴅɪ 🤬",
    "ꜱᴀʟᴀ ᴋᴜᴛᴛᴀ 🐕",
]

SLIDE3_ROASTS = [
    "ʙʜᴏꜱᴅɪᴋᴇ ᴛᴇʀɪ ᴀᴜᴋᴀᴛ ᴇᴋ ᴋᴏᴜᴅɪ ᴋɪ ʙʜɪ ɴᴀʜɪ ʜᴀɪ, ᴍᴀᴀ ᴋɪ ᴄʜᴜᴛ ᴛᴇʀɪ ɢᴀᴀɴᴅ ᴍᴀʀᴀ ᴄʜᴜᴘ ᴄʜᴀᴀᴘ! 🖕🤬",
    "ᴍᴀᴅᴀʀᴄʜᴏᴅ ᴛᴜ ᴘᴇᴅᴀ ʜɪ ɢᴀʟᴛɪ ꜱᴇ ʜᴜᴀ ᴛʜᴀ, ᴀᴘɴɪ ᴍᴀᴀ ᴋᴏ ᴅᴇᴋʜ ᴋᴀʀ ᴅᴏᴏʙ ᴍᴀʀ ʟᴏᴅᴜ ɪɴꜱᴀᴀɴ! 🤡💧",
    "ʙᴇʜᴇɴᴄʜᴏᴅ ᴋʜᴜᴅ ᴋᴏ ᴋᴏɪ ᴛᴏᴘ ꜱᴀᴍᴀᴊʜᴛᴀ ʜᴀɪ ᴋʏᴀ, ᴛᴇʀɪ ᴏᴏᴋᴀᴛ ʙʜᴀɪʏᴀ ʙʜɪᴋᴀʀɪ ᴊᴀɪꜱɪ ʜᴀɪ! 🚷🏚️",
    "ᴄʜᴜᴛɪʏᴀ ꜱᴀᴀʟᴀ ʜᴀʀ ᴊᴀɢᴀh ʙᴇɪᴢᴢᴀᴛ ʜᴏᴛᴀ ʜᴀɪ, ɢᴀɴᴅᴜ ʜᴀɪ ᴛᴜ ꜱᴀʀᴇ-ᴀᴀᴍ ʙʜᴀᴅᴡᴀ! 💩🗑️",
    "ʀᴀɴᴅɪ ᴋᴇ ʙᴀᴄᴄʜᴇ ᴛᴇʀɪ ᴢᴜʙᴀᴀɴ ʙᴀʜᴜᴛ ᴄʜᴀʟᴛɪ ʜᴀɪ, ᴀᴜᴋᴀᴛ ᴍᴇɪɴ ʀᴇʜ ɴᴀʜɪ ᴛᴏ ʟᴏᴅᴀ ᴍɪʟᴇɢᴀ! 🔪⛓️",
    "ʟᴏᴅᴜ ʙʜᴀᵈᴡᴇ ᴛᴇʀᴀ ᴋᴏɪ ᴡᴀᴊᴏᴏᴅ ʜɪ ɴᴀʜɪ ʜᴀɪ, ꜱᴀʟᴀ ᴋᴜᴛᴛᴀ ʙʜɪ ᴛᴜᴊʜꜱᴇ ᴢʏᴀᴅᴀ ɪᴢᴢᴀᴛ ᴘᴀᴛᴀ ʜᴀɪ! 🐕❌",
    "ᴛᴇʀɪ ᴍᴀᴀ ᴋɪ ᴄʜᴜᴛ ᴍᴀᴀʀᴜ ʙʜᴏꜱᴅɪᴋᴇ, ᴛᴜᴍʜᴀʀɪ ᴋʜᴀᴀɴᴅᴀᴀɴ ᴋɪ ᴀᴜᴋᴀᴛ ᴇᴋ ʀᴜᴘᴀʏᴇ ᴋɪ ʙʜɪ ɴᴀʜɪ! 💸📉",
    "ʜᴀʀᴀᴍᴢᴀᴅᴀ ᴋᴀʜɪɴ ᴋᴀ ᴍᴜꜰᴛ ᴋᴀ ʀᴏᴛɪ ᴛᴏᴅᴛᴀ ʜᴀɪ, ᴀᴘɴᴇ ᴘᴀᴘᴀ ꜱᴇ ᴘᴏᴏᴄʜ ᴋɪ ᴛᴇʀɪ ᴀᴜᴋᴀᴛ ᴋʏᴀ ʜᴀɪ! 🧔💸",
    "ᴋᴀᴍɪɴᴇ ᴋᴜᴛᴛᴇ ᴛᴇʀɪ ꜱʜᴀᴋʟ ᴅᴇᴋʜ ᴋᴀʀ ᴜʟᴛɪ ᴀᴀᴛɪ ʜᴀɪ, ʜɪᴊᴅᴀ ʜᴀɪ ᴛᴜ ᴘᴜʀᴀ ᴋᴀ ᴘᴜʀᴀ! 🎭🤮",
    "ɢᴀᴀɴᴅ ᴍᴀʀᴀ ᴄʜᴜᴘ ᴄʜᴀᴀᴘ ʟᴏᴅᴜ, ᴀᴜᴋᴀᴛ ꜱᴇ ʙᴀᴀᴅʜ ʙᴏʟᴇɢᴀ ᴛᴏ ᴍᴀᴀ ᴄʜᴏᴅ ᴅᴜɴɢᴀ ᴛᴇʀɪ! 🖕🔥",
    "ʟᴀᴜᴅᴇ ᴋᴇ ʙᴀᴀʟ ᴋʜᴜᴅ ᴋᴏ ᴅᴏɴ ꜱᴀᴍᴀᴊʜᴛᴀ ʜᴀɪ, ᴏᴏᴋᴀᴛ ᴛᴇʀɪ ɢᴀʟʟɪ ᴋᴇ ᴋᴜᴛᴛᴇ ᴊᴀɪꜱɪ ʙʜɪ ɴᴀʜɪ! 🐕🐾",
    "ᴄʜɪɴᴀʟ ᴋɪ ᴀᴜʟᴀᴀᴅ ꜱᴀᴀʟᴀ ʀᴀᴀᴛ ʙʜᴀʀ ʙʜᴏᴋᴛᴀ ʜᴀɪ, ꜱᴜʙᴀʜ ʜᴏᴛᴇ ʜɪ ʙʜɪᴋ ᴍᴀᴀɢɴᴇ ʟᴀɢᴛᴀ ʜᴀɪ! 🏴‍☠️🥣",
    "ᴊʜᴀᴛᴜꜱ ꜱᴀᴀʟᴀ ᴀᴋᴀᴅ ᴀɪꜱɪ ᴅɪᴋʜᴀᴛᴀ ʜᴀɪ ᴊᴀɪꜱᴇ ᴀᴍʙᴀɴɪ ᴋᴀ ʙᴀᴀᴘ ʜᴏ, ᴀᴜᴋᴀᴛ ᴅᴇᴋʜɪ ʜᴀɪ ᴀᴘɴɪ? 🤡📉",
    "ᴛᴇʀɪ ʙᴇʜᴀɴ ᴋᴏ ʟᴏᴅᴀ ᴍᴇʀᴀ, ᴛᴜ ᴀᴜʀ ᴛᴇʀᴀ ᴘOor family ᴇᴋ ɴᴏ. ᴋᴇ ʙʜɪᴋᴀʀɪ ʜᴀɪɴ! 👨‍👩‍👦🚷",
    "ᴍᴀᴀ ᴋᴇ ʟᴀᴜᴅᴇ ᴛᴇʀɪ ᴘᴇᴀᴄʜ ᴘʜᴀᴀᴅ ᴅᴜɴɢᴀ, ᴀᴜᴋᴀᴛ ᴍᴇɪɴ ʀᴇʜ ɴᴀʜɪ ᴛᴏ ɢᴀᴀɴᴅ ᴍᴀ ᴊᴀʏᴇɢɪ! 🍑💥",
]

# ==================== SPAM TEMPLATES ====================
SPAM2_TEMPLATE = "{target} 𝐓𝐄𝐑𝐈 𝐌𝐀𝐀 {heart} 𝐊𝐈 𝐂𝐇𝐎𝐎𝐓 𝐌𝐀𝐀𝐑𝐔 《{heart}》〰 " * 25
SPAM3_TEMPLATE = "{target}  𝐏𝐈𝐋𝐋𝐄 𝐂𝐇𝐔𝐃 {flag} 𝐈𝐒 𝐂𝐎𝐔𝐍𝐓𝐑𝐘 𝐌𝐄 《{flag}》〰 " * 25

# ==================== ANI_NC_LINES & GLITCH_NC_LINES ====================
ANI_NC_LINES = [
    "{target} Tᴇʀɪ ᴍꫝ 🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳🐳 Wʜꫝʟᴇ ᴄʜᴏᴅᴇɢꫝ 👀",
    "{target} Tᴇʀɪ ᴍꫝ 🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬🐬 Dᴏʟᴘʜɪɴ ᴄʜᴏᴅᴇɢꫝ 👀",
    "{target} Tᴇʀɪ ᴍꫝ 🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄🦄 Uɴɪᴄᴏʀɴ ᴄʜᴏᴅᴇɢꫝ 👀",
    "{target} Tᴇʀɪ ᴍꫝ 🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎🦎 Lɪᴢꫝʀᴅ ᴄʜᴏᴅᴇɢꫝ 👀",
    "{target} Tᴇʀɪ ᴍꫝ 🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉🐉 Dʀꫝɢᴏɴ ᴄʜᴏᴅᴇɢꫝ 👀",
    "{target} Tᴇʀɪ ᴍꫝ 🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼🐼 Pꫝɴᴅꫝ ᴄʜᴏᴅᴇɢꫝ 👀",
    "{target} Tᴇʀɪ ᴍꫝ 🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒🐒 Mᴏɴᴋᴇʏ ᴄʜᴏᴅᴇɢꫝ 👀",
    "{target} Tᴇʀɪ ᴍꫝ 🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍🐍 Sɴꫝᴋᴇ ᴄʜᴏᴅᴇɢꫝ 👀",
    "{target} Tᴇʀɪ ᴍꫝ 🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙🐙 Oᴄᴛᴏᴘꪊs ᴄʜᴏᴅᴇɢꫝ 👀",
    "{target} Tᴇʀɪ ᴍꫝ 🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩🦩 Fʟꫝᴍɪɴɢᴏ ᴄʜᴏᴅᴇɢꫝ 👀",
    "{target} Tᴇʀɪ ᴍꫝ 🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇🦇 ʙꫝᴛ ᴄʜᴏᴅᴇɢꫝ 👀",
    "{target} Tᴇʀɪ ᴍꫝ 🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔🦔 Pᴏʀᴄꪊᴘɪɴᴇ ᴄʜᴏᴅᴇɢꫝ 👀",
    "{target} Tᴇʀɪ ᴍꫝ 🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜🦜 Pꫝʀʀᴏᴛ ᴄʜᴏᴅᴇɢꫝ 👀",
    "{target} Tᴇʀɪ ᴍꫝ 🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼🪼Jᴇʟʟʏғɪsʜ ᴄʜᴏᴅᴇɢꫝ 👀",    "{target} Tᴇʀɪ ᴍꫝ 🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖🦖 T-Rᴇx ᴄʜᴏᴅᴇɢꫝ 👀",
    "{target} Tᴇʀɪ ᴍꫝ 🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈🦈 Sʜꫝʀᴋ ᴄʜᴏᴅᴇɢꫝ 👀",
    "{target} Tᴇʀɪ ᴍꫝ 🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅🐅 Tɪɢᴇʀ ᴄʜᴏᴅᴇɢꫝ 👀",
    "{target} Tᴇʀɪ ᴍꫝ 🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁🦁 Lɪᴏɴ ᴄʜᴏᴅᴇɢꫝ 👀",
    "{target} Tᴇʀɪ ᴍꫝ 🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍🦍 Gᴏʀɪʟʟꫝ ᴄʜᴏᴅᴇɢꫝ 👀",
    "{target} Tᴇʀɪ ᴍꫝ 🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘🐘 Eʟᴇᴘʜꫝɴᴛ ᴄʜᴏᴅᴇɢꫝ 👀",
    "{target} Tᴇʀɪ ᴍꫝ 🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪🐪 Cꫝᴍᴇʟ ᴄʜᴏᴅᴇɢꫝ 👀",
    "{target} Tᴇʀɪ ᴍꫝ 🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂🦂 Sᴄᴏʀᴘɪᴏɴ ᴄʜᴏᴅᴇɢꫝ 👀",
    "{target} Tᴇʀɪ ᴍꫝ 🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅🦅 Eꫝɢʟᴇ ᴄʜᴏᴅᴇɢꫝ 👀",
    "{target} Tᴇʀɪ ᴍꫝ 🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺🐺 Wᴏʟғ ᴄʜᴏᴅᴇɢꫝ 👀",
    "{target} Tᴇʀɪ ᴍꫝ 🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆🐆 Lᴇᴏᴘꫝʀᴅ ᴄʜᴏᴅᴇɢꫝ 👀",
    "{target} Tᴇʀɪ ᴍꫝ 🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊🐊 Cʀᴏᴄᴏᴅɪʟᴇ ᴄʜᴏᴅᴇɢꫝ 👀",
    "{target} Tᴇʀɪ ᴍꫝ 🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏🦏 Rʜɪɴᴏ ᴄʜᴏᴅᴇɢꫝ 👀",
    "{target} Tᴇʀɪ ᴍꫝ 🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🇯🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓🦓 Zᴇʙʀꫝ ᴄʜᴏᴅᴇɢꫝ 👀"
]

GLITCH_NC_LINES = [
    "{target}𒄆꧅𒄆\n꧅𒄆꧅𒄆꧅𒄆\n꧅𒄆꧅𒄆꧅𒄆\n꧅𒄆꧅𒄆꧅𒄆\n꧅𒄆꧅𒄆꧅𒄆\n꧅𒄆꧅𒄆꧅𒄆\n꧅𒄆꧅𒄆꧅𒄆\n꧅𒄆꧅𒄆꧅𒄆\n꧅𒄆꧅𒄆꧅𒄆\n꧅𒄆꧅𒄆꧅𒄆\n꧅𒄆꧅𒄆꧅𒄆\n꧅𒄆꧅𒄆꧅𒄆\n꧅𒄆꧅𒄆꧅𒄆\n꧅𒄆꧅𒄆꧅𒄆\n꧅𒄆꧅𒄆꧅𒄆\n꧅𒄆꧅𒄆꧅𒄆\n꧅𒄆꧅𒄆꧅𒄆\n꧅𒄆꧅𒄆꧅𒄆",
    "{target}҈꧅҉\n꧅҈҉꧅҈҉꧅\n꧅҈҉꧅҈҉꧅\n꧅҈҉꧅҈҉꧅\n꧅҈҉꧅҈҉꧅\n꧅҈҉꧅҈҉꧅\n꧅҈҉꧅҈҉꧅\n꧅҈҉꧅҈҉꧅\n꧅҈҉꧅҈҉꧅\n꧅҈҉꧅҈҉꧅\n꧅҈҉꧅҈҉꧅\n꧅҈҉꧅҈҉꧅\n꧅҈҉꧅҈҉꧅\n꧅҈҉꧅҈҉꧅\n꧅҈҉꧅҈҉꧅\n꧅҈҉꧅҈҉꧅\n꧅҈҉꧅҈҉꧅\n꧅҈҉꧅҈҉꧅",
    "{target}𒐫꧅𒐫\n꧅𒐫𒐫꧅𒐫𒐫꧅\n꧅𒐫𒐫꧅𒐫𒐫꧅\n꧅𒐫𒐫꧅𒐫𒐫꧅\n꧅𒐫𒐫꧅𒐫𒐫꧅\n꧅𒐫𒐫꧅𒐫𒐫꧅\n꧅𒐫𒐫꧅𒐫𒐫꧅\n꧅𒐫𒐫꧅𒐫𒐫꧅\n꧅𒐫𒐫꧅𒐫𒐫꧅\n꧅𒐫𒐫꧅𒐫𒐫꧅\n꧅𒐫𒐫꧅𒐫𒐫꧅\n꧅𒐫𒐫꧅𒐫𒐫꧅\n꧅𒐫𒐫꧅𒐫𒐫꧅\n꧅𒐫𒐫꧅𒐫𒐫꧅\n꧅𒐫𒐫꧅𒐫𒐫꧅\n꧅𒐫𒐫꧅𒐫𒐫꧅\n꧅𒐫𒐫꧅𒐫𒐫꧅\n꧅𒐫𒐫꧅𒐫𒐫꧅",
    "{target}꧅꧅꧅\n꧅꧅꧅꧅꧅꧅\n꧅꧅꧅꧅꧅꧅\n꧅꧅꧅꧅꧅꧅\n꧅꧅꧅꧅꧅꧅\n꧅꧅꧅꧅꧅꧅\n꧅꧅꧅꧅꧅꧅\n꧅꧅꧅꧅꧅꧅\n꧅꧅꧅꧅꧅꧅\n꧅꧅꧅꧅꧅꧅\n꧅꧅꧅꧅꧅꧅\n꧅꧅꧅꧅꧅꧅\n꧅꧅꧅꧅꧅꧅\n꧅꧅꧅꧅꧅꧅\n꧅꧅꧅꧅꧅꧅\n꧅꧅꧅꧅꧅꧅\n꧅꧅꧅꧅꧅꧅\n꧅꧅꧅꧅꧅꧅",
    "{target}𒄆҈꧅\n꧅𒄆҉꧅𒐫꧅𒄆\n꧅𒄆҉꧅𒐫꧅𒄆\n꧅𒄆҉꧅𒐫꧅𒄆\n꧅𒄆҉꧅𒐫꧅𒄆\n꧅𒄆҉꧅𒐫꧅𒄆\n꧅𒄆҉꧅𒐫꧅𒄆\n꧅𒄆҉꧅𒐫꧅𒄆\n꧅𒄆҉꧅𒐫꧅𒄆\n꧅𒄆҉꧅𒐫꧅𒄆\n꧅𒄆҉꧅𒐫꧅𒄆\n꧅𒄆҉꧅𒐫꧅𒄆\n꧅𒄆҉꧅𒐫꧅𒄆\n꧅𒄆҉꧅𒐫꧅𒄆\n꧅𒄆҉꧅𒐫꧅𒄆\n꧅𒄆҉꧅𒐫꧅𒄆\n꧅𒄆҉꧅𒐫꧅𒄆\n꧅𒄆҉꧅𒐫꧅𒄆",
    "{target}꧅҉꧅\n҉꧅҉꧅҉꧅҉\n҉꧅҉꧅҉꧅҉\n҉꧅҉꧅҉꧅҉\n҉꧅҉꧅҉꧅҉\n҉꧅҉꧅҉꧅҉\n҉꧅҉꧅҉꧅҉\n҉꧅҉꧅҉꧅҉\n҉꧅҉꧅҉꧅҉\n҉꧅҉꧅҉꧅҉\n҉꧅҉꧅҉꧅҉\n҉꧅҉꧅҉꧅҉\n҉꧅҉꧅҉꧅҉\n҉꧅҉꧅҉꧅҉\n҉꧅҉꧅҉꧅҉\n҉꧅҉꧅҉꧅҉\n҉꧅҉꧅҉꧅҉\n҉꧅҉꧅҉꧅҉",
    "{target}𒐫҈𒐫\n҈𒐫҈𒐫҈𒐫\n҈𒐫҈𒐫҈𒐫\n҈𒐫҈𒐫҈𒐫\n҈𒐫҈𒐫҈𒐫\n҈𒐫҈𒐫҈𒐫\n҈𒐫҈𒐫҈𒐫\n҈𒐫҈𒐫҈𒐫\n҈𒐫҈𒐫҈𒐫\n҈𒐫҈𒐫҈𒐫\n҈𒐫҈𒐫҈𒐫\n҈𒐫҈𒐫҈𒐫\n҈𒐫҈𒐫҈𒐫\n҈𒐫҈𒐫҈𒐫\n҈𒐫҈𒐫҈𒐫\n҈𒐫҈𒐫҈𒐫\n҈𒐫҈𒐫҈𒐫\n҈𒐫҈𒐫҈𒐫",
    "{target}꧅𒐫꧅\n𒐫꧅𒐫꧅𒐫꧅\n𒐫꧅𒐫꧅𒐫꧅\n𒐫꧅𒐫꧅𒐫꧅\n𒐫꧅𒐫꧅𒐫꧅\n𒐫꧅𒐫꧅𒐫꧅\n𒐫꧅𒐫꧅𒐫꧅\n𒐫꧅𒐫꧅𒐫꧅\n𒐫꧅𒐫꧅𒐫꧅\n𒐫꧅𒐫꧅𒐫꧅\n𒐫꧅𒐫꧅𒐫꧅\n𒐫꧅𒐫꧅𒐫꧅\n𒐫꧅𒐫꧅𒐫꧅\n𒐫꧅𒐫꧅𒐫꧅\n𒐫꧅𒐫꧅𒐫꧅\n𒐫꧅𒐫꧅𒐫꧅\n𒐫꧅𒐫꧅𒐫꧅\n𒐫꧅𒐫꧅𒐫꧅",
    "{target}҈꧅҈\n꧅҈꧅҈꧅҈\n꧅҈꧅҈꧅҈\n꧅҈꧅҈꧅҈\n꧅҈꧅҈꧅҈\n꧅҈꧅҈꧅҈\n꧅҈꧅҈꧅҈\n꧅҈꧅҈꧅҈\n꧅҈꧅҈꧅҈\n꧅҈꧅҈꧅҈\n꧅҈꧅҈꧅҈\n꧅҈꧅҈꧅҈\n꧅҈꧅҈꧅҈\n꧅҈꧅҈꧅҈\n꧅҈꧅҈꧅҈\n꧅҈꧅҈꧅҈\n꧅҈꧅҈꧅҈\n꧅҈꧅҈꧅҈",
    "{target}𒄆𒐫҈\n𒐫҈𒄆𒐫҈𒄆\n𒐫҈𒄆𒐫҈𒄆\n𒐫҈𒄆𒐫҈𒄆\n𒐫҈𒄆𒐫҈𒄆\n𒐫҈𒄆𒐫҈𒄆\n𒐫҈𒄆𒐫҈𒄆\n𒐫҈𒄆𒐫҈𒄆\n𒐫҈𒄆𒐫҈𒄆\n𒐫҈𒄆𒐫҈𒄆\n𒐫҈𒄆𒐫҈𒄆\n𒐫҈𒄆𒐫҈𒄆\n𒐫҈𒄆𒐫҈𒄆\n𒐫҈𒄆𒐫҈𒄆\n𒐫҈𒄆𒐫҈𒄆\n𒐫҈𒄆𒐫҈𒄆\n𒐫҈𒄆𒐫҈𒄆\n𒐫҈𒄆𒐫҈𒄆"
]

# ==================== HELPER FUNCTIONS ====================
def smallcaps(text: str) -> str:
    mapping = {
        'a':'ᴀ','b':'ʙ','c':'ᴄ','d':'ᴅ','e':'ᴇ','f':'ꜰ','g':'ɢ','h':'ʜ','i':'ɪ','j':'ᴊ',
        'k':'ᴋ','l':'ʟ','m':'ᴍ','n':'ɴ','o':'ᴏ','p':'ᴘ','q':'ǫ','r':'ʀ','s':'ꜱ','t':'ᴛ',
        'u':'ᴜ','v':'ᴠ','w':'ᴡ','x':'x','y':'ʏ','z':'ᴢ'
    }
    return ''.join(mapping.get(c.lower(), c) for c in text)

def random_emoji(lst):
    return random.choice(lst)

def emoji_reply(text, emoji="🚀"):
    return f"{emoji} {text}"

async def stop_task(chat_id, task_key):
    if chat_id in ACTIVE_TASKS and task_key in ACTIVE_TASKS[chat_id]:
        old = ACTIVE_TASKS[chat_id][task_key]
        if old.get('main_task'):
            old['main_task'].cancel()
        for bt in old.get('bot_tasks', []):
            bt.cancel()
        del ACTIVE_TASKS[chat_id][task_key]
        return True
    return False

async def stop_all_tasks(chat_id):
    SLIDE_TARGETS.pop(chat_id, None)
    SLIDE_ABUSE_MAP.pop(chat_id, None)
    if chat_id in ACTIVE_TASKS:
        for attack_data in ACTIVE_TASKS[chat_id].values():
            if attack_data.get('main_task'):
                attack_data['main_task'].cancel()
            for bt in attack_data.get('bot_tasks', []):
                bt.cancel()
        ACTIVE_TASKS[chat_id].clear()
        return True
    return False

def get_target(chat_id):
    return TARGETS.get(chat_id, "TARGET")

# ==================== DECORATORS ====================
def only_sudo(func):
    async def wrapper(update, context):
        if not update.effective_user or update.effective_user.id not in SUDO_USERS:
            if update.message:
                await update.message.reply_text(emoji_reply(smallcaps("CAN I FUCK YOUR MOM 🥺"), "😍"))
            return
        return await func(update, context)
    return wrapper

def only_owner(func):
    async def wrapper(update, context):
        if not update.effective_user or update.effective_user.id != OWNER_ID:
            if update.message:
                await update.message.reply_text(emoji_reply(smallcaps("only owner can use this."), "⛔"))
            return
        return await func(update, context)
    return wrapper

# ==================== CONNECTION POOL ====================
connection_pool = ConnectionPool()

# ==================== HEALTH MONITOR ====================
async def health_check_bot(token: str) -> bool:
    session = await connection_pool.get_session()
    try:
        url = f"https://api.telegram.org/bot{token}/getMe"
        async with session.get(url, timeout=0.5) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get('ok', False)
            return False
    except:
        return False
    finally:
        await connection_pool.return_session(session)

async def health_monitor():
    while True:
        for token in TOKENS:
            now = time.time()
            if now - bot_data[token]['last_health_check'] >= 0.01:
                healthy = await health_check_bot(token)
                bot_data[token]['healthy'] = healthy
                bot_data[token]['last_health_check'] = now
                if healthy:
                    bot_data[token]['fail_count'] = 0
                else:
                    bot_data[token]['fail_count'] += 1
                    if bot_data[token]['fail_count'] > 10:
                        bot_data[token]['skip_until'] = now + 10
        await asyncio.sleep(0.01)

# ==================== API CALLS ====================
async def set_title_via_api(token: str, chat_id: int, title: str) -> bool:
    session = await connection_pool.get_session()
    try:
        url = f"https://api.telegram.org/bot{token}/setChatTitle"
        payload = {"chat_id": chat_id, "title": title[:255]}
        async with session.post(url, json=payload, timeout=0.5) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get('ok', False)
            return False
    except Exception as e:
        bot_data[token]['restart_needed'] = True
        if isinstance(e, RetryAfter):
            wait = e.retry_after if hasattr(e, 'retry_after') else 30
            bot_data[token]['flood_wait_until'] = time.time() + wait
            logger.warning(f"Bot {token[:10]}... FloodWait {wait}s – restart")
        elif isinstance(e, Forbidden):
            bot_data[token]['skip_until'] = time.time() + 10
            logger.warning(f"Bot {token[:10]}... Forbidden – restart")
        else:
            bot_data[token]['skip_until'] = time.time() + 5
            logger.warning(f"Bot {token[:10]}... Other error: {e} – restart")
        return False
    finally:
        await connection_pool.return_session(session)

async def send_message_via_api(token: str, chat_id: int, text: str) -> bool:
    session = await connection_pool.get_session()
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text}
        async with session.post(url, json=payload, timeout=0.5) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get('ok', False)
            return False
    except Exception as e:
        bot_data[token]['restart_needed'] = True
        if isinstance(e, RetryAfter):
            wait = e.retry_after if hasattr(e, 'retry_after') else 30
            bot_data[token]['flood_wait_until'] = time.time() + wait
            logger.warning(f"Bot {token[:10]}... FloodWait {wait}s – restart")
        elif isinstance(e, Forbidden):
            bot_data[token]['skip_until'] = time.time() + 10
            logger.warning(f"Bot {token[:10]}... Forbidden – restart")
        else:
            bot_data[token]['skip_until'] = time.time() + 5
            logger.warning(f"Bot {token[:10]}... Other error: {e} – restart")
        return False
    finally:
        await connection_pool.return_session(session)

# ==================== ROUND‑ROBIN DISPATCHER ====================
async def nc_dispatcher(chat_id, attack_type, make_title_func):
    bot_index = 0
    while True:
        if chat_id not in ACTIVE_TASKS or attack_type not in ACTIVE_TASKS[chat_id]:
            break
        token = TOKENS[bot_index]
        bot_index = (bot_index + 1) % len(TOKENS)

        now = time.time()
        if not bot_data[token]['healthy'] or now < bot_data[token]['skip_until']:
            continue
        if now < bot_data[token]['flood_wait_until']:
            continue
        if now - bot_data[token]['last_send'] < bot_data[token]['cooldown']:
            continue

        title = make_title_func(token)
        if title is None:
            continue

        success = await set_title_via_api(token, chat_id, title)
        bot_data[token]['last_send'] = time.time()

        if bot_data[token]['restart_needed']:
            bot_data[token]['restart_needed'] = False
            bot_data[token]['cooldown'] = 0.0
            bot_data[token]['flood_wait_until'] = 0
            bot_data[token]['skip_until'] = 0
            continue

        if success:
            if bot_data[token]['cooldown'] > 0.0:
                bot_data[token]['cooldown'] = max(0.0, bot_data[token]['cooldown'] * 0.99)
        else:
            bot_data[token]['cooldown'] = min(5.0, bot_data[token]['cooldown'] * 1.1)

# ---------- Title generation functions ----------
def make_nc_title(token, target, frame_left, frame_right, emoji_set, word):
    emoji = random_emoji(emoji_set)
    return f"{frame_left}{emoji}{frame_right} {target} {word} {frame_left}{emoji}{frame_right}"[:255]

def make_nc5_title(token, target):
    heart = random_emoji(ALL_SINGLE_EMOJIS)
    base = "Ⱂ«Ⱂ«Ⱂ«"
    title = f"〔 {target} 〕"
    while len(title) + len(base) + 1 < 255:
        title += base + random_emoji(ALL_SINGLE_EMOJIS)
    return title[:255]

def make_ani_title(token, target):
    line = random.choice(ANI_NC_LINES)
    return line.format(target=target)[:255]

def make_glitch_title(token, target):
    line = random.choice(GLITCH_NC_LINES)
    return line.format(target=target)[:255]

# ==================== ATTACK STARTER ====================
def start_nc_attack(chat_id, attack_type, title_maker_func):
    if chat_id in ACTIVE_TASKS and attack_type in ACTIVE_TASKS[chat_id]:
        old = ACTIVE_TASKS[chat_id][attack_type]
        if old.get('main_task'):
            old['main_task'].cancel()
        for bt in old.get('bot_tasks', []):
            bt.cancel()
        del ACTIVE_TASKS[chat_id][attack_type]

    async def dispatcher_wrapper():
        try:
            await nc_dispatcher(chat_id, attack_type, title_maker_func)
        except asyncio.CancelledError:
            pass
    main_task = asyncio.create_task(dispatcher_wrapper())
    ACTIVE_TASKS[chat_id][attack_type] = {
        'main_task': main_task,
        'bot_tasks': [main_task]
    }
    return main_task

# ==================== COMMAND HANDLERS ====================
@only_sudo
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = smallcaps("""
╔═══━━━─── 🌙 𝐙𝐱𝐘𝐧 𝐔𝐋𝐓𝐑𝐀 𝐕𝟑.𝟎 ⚡ ───━━━═══╗
              𓆩 𝐁𝐎𝐓 𝐂𝐎𝐍𝐓𝐑𝐎𝐋 𝐏𝐀𝐍𝐄𝐋 𓆪
╚═══━━━────────────────────━━━═══╝

        ⚡ 𝐏𝐎𝐖𝐄𝐑𝐄𝐃 𝐁𝐘 𝐙𝐗𝐘𝐍 ⚡
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

╭━━〔 ⚔️ 𝐍𝐎𝐑𝐓𝐇 〕━━╮
┃ ✦ .nc1   ✦ .nc2   ✦ .nc3
┃ ✦ .nc4   ✦ .nc5   ✦ .aninc
┃ ✦ .glitchnc
╰━━━━━━━━━━━━━━━━━━━━╯

╭━━〔 🛡️ 𝐁𝐑𝐎𝐓𝐇𝐄𝐑𝐇𝐎𝐎𝐃 〕━━╮
┃ ✦ .zxynnc   ✦ .stormnc   ✦ .Codezxynnc
╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯

╭━━〔 🌊 𝐒𝐋𝐈𝐃𝐄 〕━━╮
┃ ✦ .slide1   ✦ .slide2   ✦ .slide3
╰━━━━━━━━━━━━━━━━━━━━╯

╭━━〔 👑 𝐂𝐎𝐑𝐄 〕━━╮
┃ ✦ .addsudo    ✦ .delsudo
┃ ✦ .listsudo   ✦ .showbots
┃ ✦ .changebotname
╰━━━━━━━━━━━━━━━━━━╯

╭━━〔 💥 𝐂𝐇𝐀𝐎𝐒 〕━━╮
┃ ✦ .spam1   ✦ .spam2   ✦ .spam3
┃ ✦ .setpfp   ✦ .pfploop
╰━━━━━━━━━━━━━━━━━━━╯

╭━━〔 ⚙️ 𝐍𝐄𝐔𝐑𝐀𝐋 〕━━╮
┃ ✦ .delaync      ✦ .delayspam
┃ ✦ .delaypfp     ✦ .autofloodbypass
┃ ✦ .refreshall   ✦ .ultramax
┃ ✦ .status       ✦ .delays
┃ ✦ .delay <type> <sec>
┃ ✦ .ultraspeed
╰━━━━━━━━━━━━━━━━━━━╯

╭━━〔 🛑 𝐊𝐈𝐋𝐋 〕━━╮
┃ ✦ .stopall      ✦ .stopslide1
┃ ✦ .stopnc1      ✦ .stopnc2
┃ ✦ .stopnc3      ✦ .stopnc4
┃ ✦ .stopnc5      ✦ .stopaninc
┃ ✦ .stopglitchnc
╰━━━━━━━━━━━━━━━━━━╯

╭━━〔 💀 𝐃𝐄𝐀𝐓𝐇 〕━━╮
┃ ✦ .gameover   ✦ .settarget
┃ ✦ .showtarget
╰━━━━━━━━━━━━━━━━━━━╯

╭━━〔 🤖 𝐀𝐃𝐌𝐈𝐍 〕━━╮
┃ ✦ .add   ✦ .prm [ᴄᴏᴜɴᴛ]
╰━━━━━━━━━━━━━━━━━━╯

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✨ 𝐔𝐒𝐀𝐆𝐄  ➜  .<𝐂𝐎𝐌𝐌𝐀𝐍𝐃>  /  /<𝐂𝐎𝐌𝐌𝐀𝐍𝐃>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
)
    await update.message.reply_text(emoji_reply(text, "🔥"))

# ---------- NC commands ----------
async def start_nc(update, context, nc_type):
    chat_id = get_chat_id(update)
    args = context.args
    target = get_target(chat_id)
    if args:
        target = " ".join(args)
        TARGETS[chat_id] = target

    attack_type = f"nc_{nc_type}"
    if nc_type == "nc1":
        def maker(token):
            return make_nc_title(token, target, "〔", "〕", ALL_SINGLE_EMOJIS, NC1_WORD)
    elif nc_type == "nc2":
        def maker(token):
            return make_nc_title(token, target, "𓊈", "𓊉", ALL_FLAG_EMOJIS, NC2_WORD)
    elif nc_type == "nc3":
        def maker(token):
            return make_nc_title(token, target, "𓊆", "𓊇", ALL_WATER_EMOJIS, NC3_WORD)
    elif nc_type == "nc4":
        def maker(token):
            return make_nc_title(token, target, "ᅠ", "ᅠ", ALL_SINGLE_EMOJIS, NC4_WORD)
    else:
        return

    start_nc_attack(chat_id, attack_type, maker)
    await update.message.reply_text(emoji_reply(smallcaps(f"{nc_type} 𝐄XECUTE 𝐎n {target} 🌸 𝐎PERATED 𝐁Y 𝐙xʏɴ (𝐙xʏɴ 𝐒ᴡᴏʀᴅ 100x)"), "🚀"))

@only_sudo
async def nc1(update, context): await start_nc(update, context, "nc1")
@only_sudo
async def nc2(update, context): await start_nc(update, context, "nc2")
@only_sudo
async def nc3(update, context): await start_nc(update, context, "nc3")
@only_sudo
async def nc4(update, context): await start_nc(update, context, "nc4")

@only_sudo
async def nc5(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = get_chat_id(update)
    args = context.args
    target = get_target(chat_id)
    if args:
        target = " ".join(args)
        TARGETS[chat_id] = target
    attack_type = "nc_nc5"
    start_nc_attack(chat_id, attack_type, lambda token: make_nc5_title(token, target))
    await update.message.reply_text(emoji_reply(smallcaps(f"nc5 𝐄XECUTE 𝐎n {target} 🌸 𝐎PERATED 𝐁Y 𝐙xʏɴ (𝐙xʏɴ 𝐒ᴡᴏʀᴅ 100x)"), "🚀"))

@only_sudo
async def aninc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = get_chat_id(update)
    args = context.args
    target = get_target(chat_id)
    if args:
        target = " ".join(args)
        TARGETS[chat_id] = target
    attack_type = "nc_aninc"
    start_nc_attack(chat_id, attack_type, lambda token: make_ani_title(token, target))
    await update.message.reply_text(emoji_reply(smallcaps(f"aninc 𝐄XECUTE 𝐎n {target} 🌸 𝐎PERATED 𝐁Y 𝐙xʏɴ (𝐙xʏɴ 𝐒ᴡᴏʀᴅ 100x)"), "🐾"))

@only_sudo
async def glitchnc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = get_chat_id(update)
    args = context.args
    target = get_target(chat_id)
    if args:
        target = " ".join(args)
        TARGETS[chat_id] = target
    attack_type = "nc_glitchnc"
    start_nc_attack(chat_id, attack_type, lambda token: make_glitch_title(token, target))
    await update.message.reply_text(emoji_reply(smallcaps(f"glitchnc 𝐄XECUTE 𝐎n {target} 🌸 𝐎PERATED 𝐁Y 𝐙xʏɴ (𝐙xʏɴ 𝐒ᴡᴏʀᴅ 100x)"), "🌀"))

# ---------- Homie NC ----------
async def start_homie_nc(update, context, homie_type):
    global ULTRA_MAX_MODE, AUTO_FLOOD_BYPASS
    chat_id = get_chat_id(update)
    args = context.args
    target = get_target(chat_id)
    if args:
        target = " ".join(args)
        TARGETS[chat_id] = target
    ULTRA_MAX_MODE = True
    AUTO_FLOOD_BYPASS = True
    attack_type = f"homie_{homie_type}"
    if homie_type == "zxynnc":
        word = ZXYNNC_WORD
    elif homie_type == "stormnc":
        word = STORMNC_WORD
    elif homie_type == "Codezxynnc":
        word = CODEZXYNNC_WORD
    else:
        return
    start_nc_attack(chat_id, attack_type, lambda token: make_nc_title(token, target, "《", "》", ALL_SINGLE_EMOJIS, word))
    await update.message.reply_text(emoji_reply(smallcaps(f"{homie_type} started on {target} (round‑robin 100x)"), "⚡"))

@only_sudo
async def zxynnc(update, context): await start_homie_nc(update, context, "zxynnc")
@only_sudo
async def stormnc(update, context): await start_homie_nc(update, context, "stormnc")
@only_sudo
async def Codezxynnc(update, context): await start_homie_nc(update, context, "Codezxynnc")

# ---------- Slide ----------
@only_sudo
async def slide1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_slide(update, context, "slide1")

@only_sudo
async def slide2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_slide(update, context, "slide2")

@only_sudo
async def slide3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_slide(update, context, "slide3")

async def start_slide(update, context, slide_type):
    chat_id = get_chat_id(update)
    if not update.message.reply_to_message:
        await update.message.reply_text(emoji_reply(smallcaps("𝐁hosad 𝐏appu 𝐑eply 𝐃e 𝐔ser 𝐊o ."), "⚠️"))
        return
    target_user = update.message.reply_to_message.from_user
    user_id = target_user.id

    if user_id in SLIDE_TARGETS[chat_id]:
        SLIDE_TARGETS[chat_id].remove(user_id)
        SLIDE_ABUSE_MAP[chat_id].pop(user_id, None)

    if slide_type == "slide1":
        abuses = SLIDE1_ABUSES
    elif slide_type == "slide2":
        args = context.args
        if not args:
            await update.message.reply_text(emoji_reply(smallcaps("𝐌ALIK 𝐓EXT 𝐊E 𝐒ATH USE KRO"), "⚠️"))
            return
        custom_text = " ".join(args)
        abuses = [custom_text]
    elif slide_type == "slide3":
        abuses = SLIDE3_ROASTS
    else:
        return

    SLIDE_TARGETS[chat_id].add(user_id)
    SLIDE_ABUSE_MAP[chat_id][user_id] = abuses
    await stop_task(chat_id, f"slide_{slide_type}")
    await update.message.reply_text(emoji_reply(smallcaps(f"{slide_type} 𝐄XECUTE 𝐎n  🌸  {target_user.first_name} – will reply to every future message"), "💥"))

async def slide_reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.from_user:
        return
    chat_id = update.effective_chat.id
    user_id = update.message.from_user.id
    if user_id in SLIDE_TARGETS.get(chat_id, set()):
        abuses = SLIDE_ABUSE_MAP.get(chat_id, {}).get(user_id)
        if abuses:
            text = random.choice(abuses)
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_to_message_id=update.message.message_id
                )
            except Exception as e:
                logger.error(f"Slide reply error: {e}")

# ---------- Spam (using old per-bot workers, but cooldown=0) ----------
async def bot_worker_spam(token, chat_id, spam_type, spam_texts, target):
    while True:
        if chat_id not in ACTIVE_TASKS or f"spam_{spam_type}" not in ACTIVE_TASKS[chat_id]:
            break
        now = time.time()
        if not bot_data[token]['healthy'] or now < bot_data[token]['skip_until']:
            await asyncio.sleep(0.0001)
            continue
        if now < bot_data[token]['flood_wait_until']:
            await asyncio.sleep(0.0001)
            continue
        if now - bot_data[token]['last_send'] < bot_data[token]['cooldown']:
            await asyncio.sleep(0)
            continue
        if spam_type == "spam2":
            heart = random_emoji(ALL_HEART_EMOJIS)
            text = SPAM2_TEMPLATE.format(target=target, heart=heart)
        elif spam_type == "spam3":
            flag = random_emoji(ALL_FLAG_EMOJIS)
            text = SPAM3_TEMPLATE.format(target=target, flag=flag)
        else:
            text = random.choice(spam_texts)
        success = await send_message_via_api(token, chat_id, text)
        bot_data[token]['last_send'] = time.time()
        if bot_data[token]['restart_needed']:
            bot_data[token]['restart_needed'] = False
            bot_data[token]['cooldown'] = 0.0
            bot_data[token]['flood_wait_until'] = 0
            bot_data[token]['skip_until'] = 0
            break
        if success:
            if bot_data[token]['cooldown'] > 0.0:
                bot_data[token]['cooldown'] = max(0.0, bot_data[token]['cooldown'] * 0.99)
        else:
            bot_data[token]['cooldown'] = min(5.0, bot_data[token]['cooldown'] * 1.1)
        await asyncio.sleep(0)

def start_attack(chat_id, attack_type, worker_func, *args):
    if chat_id in ACTIVE_TASKS and attack_type in ACTIVE_TASKS[chat_id]:
        old = ACTIVE_TASKS[chat_id][attack_type]
        if old.get('main_task'):
            old['main_task'].cancel()
        for bt in old.get('bot_tasks', []):
            bt.cancel()
        del ACTIVE_TASKS[chat_id][attack_type]

    bot_tasks = []
    for token in TOKENS:
        async def wrapper(token=token):
            while True:
                if chat_id not in ACTIVE_TASKS or attack_type not in ACTIVE_TASKS[chat_id]:
                    break
                try:
                    await worker_func(token, chat_id, *args)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Worker for {token[:10]}... crashed: {e}")
                if chat_id in ACTIVE_TASKS and attack_type in ACTIVE_TASKS[chat_id]:
                    bot_data[token]['restart_needed'] = False
                    bot_data[token]['cooldown'] = 0.0
                    bot_data[token]['flood_wait_until'] = 0
                    bot_data[token]['skip_until'] = 0
                    await asyncio.sleep(0.001)
        task = asyncio.create_task(wrapper())
        bot_tasks.append(task)

    async def main_wrapper():
        try:
            await asyncio.gather(*bot_tasks, return_exceptions=True)
        except asyncio.CancelledError:
            for t in bot_tasks:
                t.cancel()
            await asyncio.gather(*bot_tasks, return_exceptions=True)
            raise
    main_task = asyncio.create_task(main_wrapper())
    ACTIVE_TASKS[chat_id][attack_type] = {
        'main_task': main_task,
        'bot_tasks': bot_tasks
    }
    return main_task

async def start_spam(update, context, spam_type):
    chat_id = get_chat_id(update)
    target = get_target(chat_id)
    args = context.args

    if spam_type == "spam1":
        if not args:
            await update.message.reply_text(emoji_reply(smallcaps("𝐩𝐫𝐨𝐯𝐢𝐝𝐞 𝐭𝐞𝐱𝐭 𝐭𝐨 𝐬𝐩𝐚𝐦"), "⚠️"))
            return
        text = " ".join(args)
        spam_texts = [text]
    elif spam_type == "spam2":
        if args:
            target = " ".join(args)
            TARGETS[chat_id] = target
        heart = random_emoji(ALL_HEART_EMOJIS)
        spam_texts = [SPAM2_TEMPLATE.format(target=target, heart=heart)]
    elif spam_type == "spam3":
        if args:
            target = " ".join(args)
            TARGETS[chat_id] = target
        flag = random_emoji(ALL_FLAG_EMOJIS)
        spam_texts = [SPAM3_TEMPLATE.format(target=target, flag=flag)]
    else:
        return

    attack_type = f"spam_{spam_type}"
    start_attack(chat_id, attack_type, bot_worker_spam, spam_type, spam_texts, target)
    await update.message.reply_text(emoji_reply(smallcaps(f"{spam_type} started on {target} (0.0s cooldown)"), "💬"))

@only_sudo
async def spam1(update, context): await start_spam(update, context, "spam1")
@only_sudo
async def spam2(update, context): await start_spam(update, context, "spam2")
@only_sudo
async def spam3(update, context): await start_spam(update, context, "spam3")

# ---------- PFP ----------
@only_sudo
async def setpfp(update, context):
    chat_id = get_chat_id(update)
    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        await update.message.reply_text(emoji_reply(smallcaps("𝐑𝐄𝐏𝐋𝐘 𝐎𝐍 𝐈𝐌𝐀𝐆𝐄 "), "⚠️"))
        return
    photo = update.message.reply_to_message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    data = await file.download_as_bytearray()
    GAME_OVER_PFP[chat_id] = data
    path = os.path.join(TARGET_PHOTO_FOLDER, f"{chat_id}.jpg")
    with open(path, 'wb') as f:
        f.write(data)
    await update.message.reply_text(emoji_reply(smallcaps("𝐌𝐄𝐇𝐊𝐀𝐀 𝐋𝐀𝐃𝐋𝐄 𝐃𝐎𝐍𝐄 𝐇𝐄"), "✅"))

@only_sudo
async def pfploop(update, context):
    chat_id = get_chat_id(update)
    pfp_files = [f for f in os.listdir(PFP_FOLDER) if f.lower().endswith(('.jpg','.jpeg','.png','.gif'))]
    if not pfp_files:
        await update.message.reply_text(emoji_reply(smallcaps("𝐌𝐄𝐇𝐊𝐀 𝐋𝐀𝐃𝐋𝐄 𝐙xʏɴ 𝐊 𝐇𝐀𝐓𝐄𝐑𝐒 𝐋𝐏 "), "⚠️"))
        return

    await stop_task(chat_id, "pfploop")
    async def pfp_loop():
        i = 0
        while True:
            if chat_id not in ACTIVE_TASKS or "pfploop" not in ACTIVE_TASKS[chat_id]:
                break
            try:
                img_path = os.path.join(PFP_FOLDER, pfp_files[i % len(pfp_files)])
                with open(img_path, 'rb') as f:
                    await context.bot.set_chat_photo(chat_id, photo=f)
                i += 1
                await asyncio.sleep(0.0001)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"pfp_loop error: {e}")
                await asyncio.sleep(0.0001)
    task = asyncio.create_task(pfp_loop())
    ACTIVE_TASKS[chat_id]["pfploop"] = {'main_task': task, 'bot_tasks': [task]}
    await update.message.reply_text(emoji_reply(smallcaps("𝐏𝐅𝐏 𝐋𝐎𝐎𝐏 𝐀𝐂𝐓𝐈𝐕𝐄 💀"), "🖼️"))

# ---------- Bot Management ----------
@only_sudo
async def showbots(update, context):
    await update.message.reply_text(emoji_reply(smallcaps(f"bots: {', '.join([t[:10]+'...' for t in TOKENS])}"), "🤖"))

@only_sudo
async def changebotname(update, context):
    await update.message.reply_text(emoji_reply(smallcaps("𝐁𝐇𝐊𝐊 𝐁𝐒𝐃𝐊"), "ℹ️"))

# ---------- Sudo ----------
@only_owner
async def addsudo(update, context):
    if not update.message.reply_to_message:
        await update.message.reply_text(emoji_reply(smallcaps("𝐁hosad 𝐏appu 𝐑eply 𝐃e 𝐔ser 𝐊o"), "⚠️"))
        return
    uid = update.message.reply_to_message.from_user.id
    SUDO_USERS.add(uid)
    save_sudo()
    await update.message.reply_text(emoji_reply(smallcaps(f"𝐙xʏɴ 𝐤𝐚 𝐠𝐮𝐥𝐚𝐦 {uid} 𝐚𝐝𝐝𝐞𝐝 𝐭𝐨 𝐬𝐮𝐝𝐨 🌟❤️‍🔥"), "✅"))

@only_owner
async def delsudo(update, context):
    if not update.message.reply_to_message:
        await update.message.reply_text(emoji_reply(smallcaps("𝐁hosad 𝐏appu 𝐑eply 𝐃e 𝐔ser 𝐊o"), "⚠️"))
        return
    uid = update.message.reply_to_message.from_user.id
    SUDO_USERS.discard(uid)
    save_sudo()
    await update.message.reply_text(emoji_reply(smallcaps(f"𝐭𝐦𝐤𝐜 𝐢𝐬𝐢 𝐥𝐲𝐤 𝐡 𝐭𝐮 {uid} 𝐜𝐚𝐫𝐞𝐟𝐮𝐥𝐥𝐲 𝐫𝐞𝐦𝐨𝐯𝐞𝐝 𝐟𝐫𝐦 𝐬𝐮𝐝𝐨 🍷"), "🗑️"))

@only_sudo
async def listsudo(update, context):
    await update.message.reply_text(emoji_reply(smallcaps(f"sudoku users: {', '.join(map(str, SUDO_USERS))}"), "👑"))

# ---------- Engine ----------
@only_sudo
async def delaync(update, context):
    if not context.args:
        await update.message.reply_text(emoji_reply(smallcaps("𝐔sage: .𝐃elaync <𝐒econds>"), "ℹ️"))
        return
    try:
        val = float(context.args[0])
        await update.message.reply_text(emoji_reply(smallcaps(f"𝐍𝐂 𝐃𝐄𝐋𝐀𝐘 𝐒𝐄𝐓 𝐓𝐎 {val}s (note: round‑robin override)"), "✅"))
    except:
        await update.message.reply_text(emoji_reply(smallcaps("𝐈𝐍𝐕𝐀𝐋𝐈𝐃 𝐍𝐔𝐌𝐁𝐄𝐑"), "❌"))

@only_sudo
async def delayspam(update, context):
    if not context.args:
        await update.message.reply_text(emoji_reply(smallcaps("usage: .delayspam <seconds>"), "ℹ️"))
        return
    try:
        val = float(context.args[0])
        await update.message.reply_text(emoji_reply(smallcaps(f"spam delay set to {val}s (note: cooldown=0 override)"), "✅"))
    except:
        await update.message.reply_text(emoji_reply(smallcaps("invalid number"), "❌"))

@only_sudo
async def delaypfp(update, context):
    if not context.args:
        await update.message.reply_text(emoji_reply(smallcaps("usage: .delaypfp <seconds>"), "ℹ️"))
        return
    try:
        val = float(context.args[0])
        await update.message.reply_text(emoji_reply(smallcaps(f"pfp delay set to {val}s (note: 0.0001s default)"), "✅"))
    except:
        await update.message.reply_text(emoji_reply(smallcaps("invalid number"), "❌"))

@only_sudo
async def delay_cmd(update, context):
    if len(context.args) < 2:
        await update.message.reply_text(emoji_reply(smallcaps("usage: .delay <type> <seconds>\ntypes: nc, spam, pfp, ultra"), "ℹ️"))
        return
    typ = context.args[0].lower()
    try:
        val = float(context.args[1])
        if val < 0:
            raise ValueError
        await update.message.reply_text(emoji_reply(smallcaps(f"{typ} delay set to {val}s (note: override)"), "✅"))
    except ValueError:
        await update.message.reply_text(emoji_reply(smallcaps("invalid number"), "❌"))

@only_sudo
async def delays_cmd(update, context):
    msg = f"""
current delay settings:
• NC round‑robin: no artificial delay (cooldown 0)
• Spam cooldown: 0 (max speed)
• PFP loop: 0.0001s
• Health check: every 0.01s
• Auto-restart delay: 0.001s
"""
    await update.message.reply_text(emoji_reply(smallcaps(msg), "📊"))

@only_sudo
async def ultramax_cmd(update, context):
    global ULTRA_MAX_MODE
    ULTRA_MAX_MODE = not ULTRA_MAX_MODE
    await update.message.reply_text(emoji_reply(smallcaps(f"ULTRA MAX mode: {'ON' if ULTRA_MAX_MODE else 'OFF'}"), "⚡"))

@only_sudo
async def autofloodbypass(update, context):
    global AUTO_FLOOD_BYPASS
    AUTO_FLOOD_BYPASS = not AUTO_FLOOD_BYPASS
    await update.message.reply_text(emoji_reply(smallcaps(f"auto flood bypass: {'ON' if AUTO_FLOOD_BYPASS else 'OFF'}"), "🛡️"))

@only_sudo
async def refreshall(update, context):
    global REFRESH_COUNTER
    REFRESH_COUNTER += 1
    await update.message.reply_text(emoji_reply(smallcaps(f"refreshed all (counter {REFRESH_COUNTER})"), "🔄"))

@only_sudo
async def status_cmd(update, context):
    chat_id = get_chat_id(update)
    uptime = time.time() - start_time
    active = list(ACTIVE_TASKS.get(chat_id, {}).keys())
    target = get_target(chat_id)
    healthy_count = sum(1 for t in TOKENS if bot_data[t]['healthy'])
    flooded_count = sum(1 for t in TOKENS if time.time() < bot_data[t]['flood_wait_until'])
    text = smallcaps(f"""
status for chat {chat_id}
target: {target}
active tasks: {', '.join(active) if active else 'none'}
ultra max: {'on' if ULTRA_MAX_MODE else 'off'}
auto flood bypass: {'on' if AUTO_FLOOD_BYPASS else 'off'}
uptime: {int(uptime//3600)}h {int((uptime%3600)//60)}m
Healthy bots: {healthy_count}/{len(TOKENS)}
Flooded (skipped): {flooded_count}
NC round‑robin cooldown: 0 (max speed)
""")
    await update.message.reply_text(emoji_reply(text, "📈"))

# ---------- Stop ----------
@only_sudo
async def stopall(update, context):
    chat_id = get_chat_id(update)
    await stop_all_tasks(chat_id)
    await update.message.reply_text(emoji_reply(smallcaps("system purged – target matrix cleared"), "🛑"))

@only_sudo
async def stopslide1(update, context):
    chat_id = get_chat_id(update)
    SLIDE_TARGETS.pop(chat_id, None)
    SLIDE_ABUSE_MAP.pop(chat_id, None)
    if await stop_task(chat_id, "slide_slide1"):
        await update.message.reply_text(emoji_reply(smallcaps("slide matrix terminated"), "🛑"))
    else:
        await update.message.reply_text(emoji_reply(smallcaps("slide matrix terminated (targets wiped)"), "🛑"))

@only_sudo
async def stopnc1(update, context):
    chat_id = get_chat_id(update)
    if await stop_task(chat_id, "nc_nc1"):
        await update.message.reply_text(emoji_reply(smallcaps("alpha protocol killed"), "🛑"))
    else:
        await update.message.reply_text(emoji_reply(smallcaps("alpha protocol offline"), "ℹ️"))

@only_sudo
async def stopnc2(update, context):
    chat_id = get_chat_id(update)
    if await stop_task(chat_id, "nc_nc2"):
        await update.message.reply_text(emoji_reply(smallcaps("beta protocol killed"), "🛑"))
    else:
        await update.message.reply_text(emoji_reply(smallcaps("beta protocol offline"), "ℹ️"))

@only_sudo
async def stopnc3(update, context):
    chat_id = get_chat_id(update)
    if await stop_task(chat_id, "nc_nc3"):
        await update.message.reply_text(emoji_reply(smallcaps("gamma protocol killed"), "🛑"))
    else:
        await update.message.reply_text(emoji_reply(smallcaps("gamma protocol offline"), "ℹ️"))

@only_sudo
async def stopnc4(update, context):
    chat_id = get_chat_id(update)
    if await stop_task(chat_id, "nc_nc4"):
        await update.message.reply_text(emoji_reply(smallcaps("delta protocol killed"), "🛑"))
    else:
        await update.message.reply_text(emoji_reply(smallcaps("delta protocol offline"), "ℹ️"))

@only_sudo
async def stopnc5(update, context):
    chat_id = get_chat_id(update)
    if await stop_task(chat_id, "nc_nc5"):
        await update.message.reply_text(emoji_reply(smallcaps("omega protocol killed"), "🛑"))
    else:
        await update.message.reply_text(emoji_reply(smallcaps("omega protocol offline"), "ℹ️"))

@only_sudo
async def stopaninc(update, context):
    chat_id = get_chat_id(update)
    if await stop_task(chat_id, "nc_aninc"):
        await update.message.reply_text(emoji_reply(smallcaps("beast mode severed"), "🛑"))
    else:
        await update.message.reply_text(emoji_reply(smallcaps("beast mode offline"), "ℹ️"))

@only_sudo
async def stopglitchnc(update, context):
    chat_id = get_chat_id(update)
    if await stop_task(chat_id, "nc_glitchnc"):
        await update.message.reply_text(emoji_reply(smallcaps("matrix glitch neutralized"), "🛑"))
    else:
        await update.message.reply_text(emoji_reply(smallcaps("matrix glitch offline"), "ℹ️"))

@only_sudo
async def stopzxynnc(update, context):
    chat_id = get_chat_id(update)
    if await stop_task(chat_id, "homie_zxynnc"):
        await update.message.reply_text(emoji_reply(smallcaps("zxyn syndicate eliminated"), "🛑"))
    else:
        await update.message.reply_text(emoji_reply(smallcaps("zxyn syndicate offline"), "ℹ️"))

@only_sudo
async def stopstormnc(update, context):
    chat_id = get_chat_id(update)
    if await stop_task(chat_id, "homie_stormnc"):
        await update.message.reply_text(emoji_reply(smallcaps("storm empire suppressed"), "🛑"))
    else:
        await update.message.reply_text(emoji_reply(smallcaps("storm empire offline"), "ℹ️"))

@only_sudo
async def stopCodezxynnc(update, context):
    chat_id = get_chat_id(update)
    if await stop_task(chat_id, "homie_Codezxynnc"):
        await update.message.reply_text(emoji_reply(smallcaps("shadow realm closed"), "🛑"))
    else:
        await update.message.reply_text(emoji_reply(smallcaps("shadow realm offline"), "ℹ️"))

# ---------- Gameover ----------
@only_sudo
async def gameover(update, context):
    chat_id = get_chat_id(update)
    target = get_target(chat_id)
    await stop_all_tasks(chat_id)

    pfp_data = GAME_OVER_PFP.get(chat_id)
    if pfp_data:
        try:
            await context.bot.set_chat_photo(chat_id, photo=BytesIO(pfp_data))
        except Exception as e:
            logger.error(f"set gameover pfp error: {e}")

    ist = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist).strftime("%I:%M:%S %p")
    group_title = update.effective_chat.title or "Unknown Group"
    uptime = time.time() - start_time
    uptime_str = f"{int(uptime//3600)}h {int((uptime%3600)//60)}m {int(uptime%60)}s"
    heart = random_emoji(ALL_HEART_EMOJIS)

    msg = f"""
    "<b>🔥 𝙂𝘼𝙈𝙀 𝙊𝓥𝑬𝑹 𝑩𝒀 𝒁𝑿𝒀𝑵 🔥</b>\n"
    "\n"
    "<b>🎯 Target:</b> <code>{target}</code>\n"
    "<b>📛 Group:</b> <code>{group_title}</code>\n"
    "<b>🕒 IST Time:</b> <code>{now_ist}</code>\n"
    "<b>⏱️ Uptime:</b> <code>{uptime_str}</code>\n"
    "\n"
    "<code>{target} 𑁍ࠬܓ{heart} ᴛᴇʀɪ ᴍᴀ ᴋɪ ᴄʜʜᴏᴏᴛ ᴍᴇɪɴ ʙᴏᴍʙ 𝜗𝜚⋆₊ 𝕫𝕏𝕐ℕ ᴋᴀ ʟᴀᴜᴅᴀ ˚₊· ‌➳❥</code>\n"
    "\n"
    "<b>⚠️ 𝙆𝑴𝑱𝑶𝑹 𝑲𝑰𝑫𝑬 𝘈𝑩 𝑩𝑯𝑨𝑾 𝑵𝒀𝒀 𝑴𝑰𝑳𝑬𝑮𝑨 ⚠️</b>"
)
"""
    await update.message.reply_text(msg, parse_mode="HTML")

# ---------- Target ----------
@only_sudo
async def settarget(update, context):
    chat_id = get_chat_id(update)
    if not context.args:
        await update.message.reply_text(emoji_reply(smallcaps("usage: .settarget <name>"), "ℹ️"))
        return
    target = " ".join(context.args)
    TARGETS[chat_id] = target
    await update.message.reply_text(emoji_reply(smallcaps(f"target set to {target}"), "🎯"))

@only_sudo
async def showtarget(update, context):
    chat_id = get_chat_id(update)
    target = get_target(chat_id)
    await update.message.reply_text(emoji_reply(smallcaps(f"current target: {target}"), "🎯"))

# ---------- Add & Prm ----------
async def get_bot_id(token: str) -> Optional[int]:
    session = await connection_pool.get_session()
    try:
        url = f"https://api.telegram.org/bot{token}/getMe"
        async with session.get(url, timeout=0.5) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data.get('ok'):
                    return data['result']['id']
    except:
        pass
    finally:
        await connection_pool.return_session(session)
    return None

async def promote_bot(token: str, chat_id: int, user_id: int) -> bool:
    session = await connection_pool.get_session()
    try:
        url = f"https://api.telegram.org/bot{token}/promoteChatMember"
        payload = {
            "chat_id": chat_id,
            "user_id": user_id,
            "can_change_info": True,
            "can_post_messages": True,
            "can_edit_messages": True,
            "can_delete_messages": True,
            "can_invite_users": True,
            "can_restrict_members": True,
            "can_pin_messages": True,
            "can_promote_members": True,
            "can_manage_chat": True,
            "can_manage_voice_chats": True,
        }
        async with session.post(url, json=payload, timeout=0.5) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get('ok', False)
            return False
    except Exception as e:
        logger.error(f"Promote error for {token[:10]}: {e}")
        return False
    finally:
        await connection_pool.return_session(session)

@only_sudo
async def add_all_bots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = get_chat_id(update)
    bot_ids = []
    for token in TOKENS:
        if bot_data[token]['bot_id'] is None:
            bot_id = await get_bot_id(token)
            if bot_id:
                bot_data[token]['bot_id'] = bot_id
        if bot_data[token]['bot_id']:
            bot_ids.append((token, bot_data[token]['bot_id']))

    if not bot_ids:
        await update.message.reply_text(emoji_reply(smallcaps("Failed to fetch bot IDs"), "❌"))
        return

    promoted = 0
    for token, bot_id in bot_ids:
        if await promote_bot(token, chat_id, bot_id):
            promoted += 1
            await asyncio.sleep(0.05)
    await update.message.reply_text(emoji_reply(smallcaps(f"Promoted {promoted} bots as admins"), "✅"))

@only_sudo
async def promote_n_bots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = get_chat_id(update)
    count = 10
    if context.args:
        try:
            count = int(context.args[0])
        except ValueError:
            await update.message.reply_text(emoji_reply(smallcaps("Invalid count, using 10"), "ℹ️"))
            count = 10
    bot_ids = []
    for token in TOKENS:
        if bot_data[token]['bot_id'] is None:
            bot_id = await get_bot_id(token)
            if bot_id:
                bot_data[token]['bot_id'] = bot_id
        if bot_data[token]['bot_id']:
            bot_ids.append((token, bot_data[token]['bot_id']))

    if not bot_ids:
        await update.message.reply_text(emoji_reply(smallcaps("Failed to fetch bot IDs"), "❌"))
        return

    count = min(count, len(bot_ids))
    promoted = 0
    for token, bot_id in bot_ids[:count]:
        if await promote_bot(token, chat_id, bot_id):
            promoted += 1
            await asyncio.sleep(0.05)
    await update.message.reply_text(emoji_reply(smallcaps(f"Promoted {promoted} bots as admins"), "✅"))

def get_chat_id(update):
    return update.effective_chat.id

# ==================== DOT COMMAND HANDLER ====================
async def dot_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    if not text.startswith('.'):
        return
    parts = text.split()
    cmd = parts[0][1:].lower()
    args = parts[1:]
    context.args = args

    handlers = {
        'menu': start_cmd, 'start': start_cmd, 'storm': start_cmd,
        'nc1': nc1, 'nc2': nc2, 'nc3': nc3, 'nc4': nc4, 'nc5': nc5,
        'aninc': aninc, 'glitchnc': glitchnc,
        'zxynnc': zxynnc, 'stormnc': stormnc, 'Codezxynnc': Codezxynnc,
        'slide1': slide1, 'slide2': slide2, 'slide3': slide3,
        'spam1': spam1, 'spam2': spam2, 'spam3': spam3,
        'setpfp': setpfp, 'pfploop': pfploop,
        'addsudo': addsudo, 'delsudo': delsudo, 'listsudo': listsudo,
        'showbots': showbots, 'changebotname': changebotname,
        'delaync': delaync, 'delayspam': delayspam, 'delaypfp': delaypfp,
        'delay': delay_cmd, 'delays': delays_cmd,
        'ultramax': ultramax_cmd,
        'autofloodbypass': autofloodbypass,
        'refreshall': refreshall,
        'status': status_cmd,
        'stopall': stopall,
        'stopslide1': stopslide1,
        'stopnc1': stopnc1, 'stopnc2': stopnc2, 'stopnc3': stopnc3, 'stopnc4': stopnc4, 'stopnc5': stopnc5,
        'stopaninc': stopaninc, 'stopglitchnc': stopglitchnc,
        'stopzxynnc': stopzxynnc, 'stopstormnc': stopstormnc, 'stopCodezxynnc': stopCodezxynnc,
        'gameover': gameover,
        'settarget': settarget, 'showtarget': showtarget,
        'add': add_all_bots,
        'prm': promote_n_bots,
    }

    handler = handlers.get(cmd)
    if handler:
        await handler(update, context)
    else:
        await update.message.reply_text(emoji_reply(smallcaps("RUNDYKE .storm type krr 😝"), "🩵"))

# ==================== TELEGRAM APP BUILDER ====================
def build_app(token):
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("menu", start_cmd))
    app.add_handler(CommandHandler("storm", start_cmd))
    app.add_handler(CommandHandler("nc1", nc1))
    app.add_handler(CommandHandler("nc2", nc2))
    app.add_handler(CommandHandler("nc3", nc3))
    app.add_handler(CommandHandler("nc4", nc4))
    app.add_handler(CommandHandler("nc5", nc5))
    app.add_handler(CommandHandler("aninc", aninc))
    app.add_handler(CommandHandler("glitchnc", glitchnc))
    app.add_handler(CommandHandler("zxynnc", zxynnc))
    app.add_handler(CommandHandler("stormnc", stormnc))
    app.add_handler(CommandHandler("Codezxynnc", Codezxynnc))
    app.add_handler(CommandHandler("slide1", slide1))
    app.add_handler(CommandHandler("slide2", slide2))
    app.add_handler(CommandHandler("slide3", slide3))
    app.add_handler(CommandHandler("spam1", spam1))
    app.add_handler(CommandHandler("spam2", spam2))
    app.add_handler(CommandHandler("spam3", spam3))
    app.add_handler(CommandHandler("setpfp", setpfp))
    app.add_handler(CommandHandler("pfploop", pfploop))
    app.add_handler(CommandHandler("addsudo", addsudo))
    app.add_handler(CommandHandler("delsudo", delsudo))
    app.add_handler(CommandHandler("listsudo", listsudo))
    app.add_handler(CommandHandler("showbots", showbots))
    app.add_handler(CommandHandler("changebotname", changebotname))
    app.add_handler(CommandHandler("delaync", delaync))
    app.add_handler(CommandHandler("delayspam", delayspam))
    app.add_handler(CommandHandler("delaypfp", delaypfp))
    app.add_handler(CommandHandler("delay", delay_cmd))
    app.add_handler(CommandHandler("delays", delays_cmd))
    app.add_handler(CommandHandler("ultramax", ultramax_cmd))
    app.add_handler(CommandHandler("autofloodbypass", autofloodbypass))
    app.add_handler(CommandHandler("refreshall", refreshall))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("stopall", stopall))
    app.add_handler(CommandHandler("stopslide1", stopslide1))
    app.add_handler(CommandHandler("stopnc1", stopnc1))
    app.add_handler(CommandHandler("stopnc2", stopnc2))
    app.add_handler(CommandHandler("stopnc3", stopnc3))
    app.add_handler(CommandHandler("stopnc4", stopnc4))
    app.add_handler(CommandHandler("stopnc5", stopnc5))
    app.add_handler(CommandHandler("stopaninc", stopaninc))
    app.add_handler(CommandHandler("stopglitchnc", stopglitchnc))
    app.add_handler(CommandHandler("stopzxynnc", stopzxynnc))
    app.add_handler(CommandHandler("stopstormnc", stopstormnc))
    app.add_handler(CommandHandler("stopCodezxynnc", stopCodezxynnc))
    app.add_handler(CommandHandler("gameover", gameover))
    app.add_handler(CommandHandler("settarget", settarget))
    app.add_handler(CommandHandler("showtarget", showtarget))
    app.add_handler(CommandHandler("add", add_all_bots))
    app.add_handler(CommandHandler("prm", promote_n_bots))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^\.\w+'), dot_command_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, slide_reply_handler))
    app.add_error_handler(error_handler)
    return app

async def error_handler(update, context):
    logger.error(f"Update {update} caused error {context.error}")

# ==================== MAIN ====================
apps = []
bots = []

async def run_bots():
    global apps, bots, start_time
    health_thread = threading.Thread(target=run_health_check_server, daemon=True)
    health_thread.start()
    logger.info("Health check server running on port 5000")
    await connection_pool.start()
    asyncio.create_task(health_monitor())

    for token in TOKENS:
        if "TOKEN" in token:
            logger.warning(f"Placeholder token found: {token}. Replace with real token.")
        try:
            app = build_app(token)
            apps.append(app)
            bots.append(app.bot)
        except Exception as e:
            logger.error(f"Failed to build app for token {token[:10]}...: {e}")

    if not apps:
        logger.error("No valid bots to start.")
        return

    for app in apps:
        await app.initialize()
        await app.start()
        await app.updater.start_polling()

    start_time = time.time()
    logger.info(f"{len(apps)} STORM ALL BOT ONLINE 💚👈🏻 @s1rstorm")
    logger.info("USE .storm FOR HELP MENU")
    logger.info("⚡ GOD KING LEVEL SPEED (ROUND‑ROBIN 100x)")
    logger.info("⚡ ITS TIME TO FUCK YOUR HATERS")
    logger.info("⚡ STORM BHAGWAN EY")

    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass
    finally:
        for app in apps:
            await app.updater.stop()
            await app.stop()
            await app.shutdown()
        await connection_pool.stop()
        logger.info("𝐅𝐔𝐂𝐊 𝐎𝐅 𝐀𝐋𝐋 𝐁𝐎𝐓𝐒🌟")

if __name__ == "__main__":
    try:
        asyncio.run(run_bots())
    except KeyboardInterrupt:
        logger.info("Interrupted.")
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}")
        traceback.print_exc()