import abc
import asyncio
import logging
from typing import Dict, NoReturn, Optional, Tuple, List

from aiogram import Bot

from .types import ChatsType, MarkupType, ChatIdType
from .exceptions import RunningError


class BaseBroadcaster(abc.ABC):
    running = []

    def __init__(
            self,
            chats: ChatsType,
            args: Optional[Dict] = None,
            disable_notification: Optional[bool] = None,
            disable_web_page_preview: Optional[bool] = None,
            reply_to_message_id: Optional[int] = None,
            allow_sending_without_reply: Optional[bool] = None,
            reply_markup: MarkupType = None,
            bot: Optional[Bot] = None,
            bot_token: Optional[str] = None,
            timeout: float = 0.02,
            logger=__name__,
    ):
        self._setup_chats(chats, args)
        self.disable_notification = disable_notification
        self.disable_web_page_preview = disable_web_page_preview
        self.reply_to_message_id = reply_to_message_id
        self.allow_sending_without_reply = allow_sending_without_reply
        self.reply_markup = reply_markup
        self._setup_bot(bot, bot_token)
        self.timeout = timeout

        if not isinstance(logger, logging.Logger):
            logger = logging.getLogger(logger)

        self.logger = logger

        self._id = len(BaseBroadcaster.running)
        self._is_running = False
        self._successful = []
        self._failure = []

    def __str__(self):
        attributes = [
            ('id', self._id),
            ('is_running', self._is_running),
        ]
        if self._is_running:
            attributes.append(('progress', f'{len(self.successful)}/{len(self.chats)}'))
        attributes = '; '.join((f'{key}={str(value)}' for key, value in attributes))
        return f'<{self.__class__.__name__}({attributes})>'

    @property
    def successful(self):
        if not self._is_running:
            raise RunningError(self._is_running)
        else:
            return self._successful

    def _setup_bot(
            self,
            bot: Optional[Bot] = None,
            token: Optional[str] = None,
    ) -> Bot:
        if not (bot or token):
            bot = Bot.get_current()
            if bot:
                self.bot = bot
            else:
                raise AttributeError('You should either pass a bot instance or a token')
        if bot and token:
            raise AttributeError('You can’t pass both bot and token')
        if bot:
            self.bot = bot
        elif token:
            bot = Bot(token=token)
            self.bot = bot
        return bot

    def _setup_chats(self, chats: ChatsType, args: Optional[Dict] = None):
        if isinstance(chats, int) or isinstance(chats, str):
            self.chats = [{'chat_id': chats, **args}]
        elif isinstance(chats, list):
            if all([
                isinstance(chat, int) or isinstance(chat, str)
                for chat in chats
            ]):
                self.chats = [
                    {'chat_id': chat, **args} for chat in chats
                ]
            elif all([
                isinstance(chat, dict)
                for chat in chats
            ]):
                if not all([chat.get('chat_id') for chat in chats]):
                    raise ValueError('Not all dictionaries have the "chat_id" key')
                if not self._chek_identical_keys(dicts=chats):
                    raise ValueError('Not all dictionaries have identical keys')
                self.chats = [
                    {'chat_id': chat.pop('chat_id'), **chat, **args}
                    for chat in chats if chat.get('chat_id', None)
                ]
        else:
            raise AttributeError(f'argument chats: expected {ChatsType}, got "{type(chats)}"')

    @staticmethod
    def _chek_identical_keys(dicts: List) -> bool:
        for d in dicts[1:]:
            if not sorted(d.keys()) == sorted(dicts[0].keys()):
                return False
        return True

    @staticmethod
    def _parse_args(chat: Dict) -> Tuple[ChatIdType, dict]:
        chat_id = chat.get('chat_id')
        text_args = chat
        return chat_id, text_args

    @abc.abstractmethod
    async def send(
            self,
            chat_id: ChatIdType,
            chat_args: dict,
    ) -> bool:
        pass

    async def run(self) -> NoReturn:
        self._is_running = True
        BaseBroadcaster.running.append(self)
        for chat in self.chats:
            logging.info(str(self))
            chat_id, chat_args = self._parse_args(chat)
            if await self.send(chat_id=chat_id, chat_args=chat_args):
                self._successful.append(chat_id)
            else:
                self._failure.append(chat)
            await asyncio.sleep(self.timeout)
        self._is_running = False
        BaseBroadcaster.running.remove(self)
        logging.info(f'{len(self._successful)}/{len(self.chats)} messages were sent out')

    async def close_bot(self):
        logging.warning('GOODBYE')
        await self.bot.session.close()
