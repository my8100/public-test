# coding: utf-8
import os
import re

from flask import request

from ...utils.send_email import send_email
from ..baseview import BaseView


metadata = dict(
    telegram_authorized=False,
    telegram_bot_username=None,
    telegram_chat_id=None,
    telegram_chat_username=None
)


class SendTextView(BaseView):
    slack_help = 'https://api.slack.com/methods/chat.postMessage'
    telegram_help = 'https://core.telegram.org/bots#6-botfather'

    def __init__(self):
        super(SendTextView, self).__init__()

        self.opt = self.view_args['opt']
        self.opt = 'telegram' if self.opt == 'tg' else self.opt
        # https://stackoverflow.com/questions/10434599/get-the-data-received-in-a-flask-request
        # request.values: combined args and form, preferring args if keys overlap
        self.form = request.json or request.form

        if self.opt == 'email':
            self.subject_channel = (self.view_args['subject_channel']
                                  or request.args.get('subject', None)
                                  or self.form.get('subject', self.EMAIL_SUBJECT))
            # request.json['receivers'] could be a list type instead of a string type
            receivers = re.findall(r'[^\s"\',;\[\]]+@[^\s"\',;\[\]]+',
                                   request.args.get('receivers', '') or str(self.form.get('receivers', '')))
            self.EMAIL_KWARGS['to_addrs'] = receivers or self.TO_ADDRS
        elif self.opt == 'slack':
            self.subject_channel = (self.view_args['subject_channel']
                                  or request.args.get('channel', None)
                                  or self.form.get('channel', self.SLACK_CHANNEL))  # 'general'
        else:
            self.subject_channel = None
        self.logger.debug('subject_channel: %s', self.subject_channel)

        self.text = self.view_args['text'] or request.args.get('text', None)
        if not self.text:
            self.text = self.json_dumps(self.form) if self.form else 'test'
        self.logger.debug('text: %s', self.text)

        self.js = {}
        self.tested = False # For test only

    def dispatch_request(self, **kwargs):
        if self.opt == 'email':
            self.send_email()
        elif self.opt == 'slack':
            self.send_slack()
            if self.js.setdefault('status', self.ERROR) != self.OK:
                if self.SLACK_TOKEN:
                    self.js['debug'] = dict(token=self.SLACK_TOKEN, channel=self.subject_channel, text=self.text)
                self.js['tip'] = "See %s for help." % self.slack_help
                self.logger.error("Fail to send text via Slack:\n%s", self.js)
        elif self.opt == 'telegram':
            self.send_telegram()
            if self.js.setdefault('status', self.ERROR) != self.OK:
                if self.TELEGRAM_TOKEN:
                    self.js['debug'] = dict(token=self.TELEGRAM_TOKEN, text=self.text)
                self.js['tip'] = "See %s for help." % self.telegram_help
                self.logger.error("Fail to send text via Telegram:\n%s", self.js)
        self.js['when'] = self.get_now_string(True)
        return self.json_dumps(self.js, as_response=True)

    def send_email(self):
        self.EMAIL_KWARGS['subject'] = self.subject_channel
        self.EMAIL_KWARGS['content'] = self.text
        result, reason = send_email(**self.EMAIL_KWARGS)
        if result:
            self.js = dict(status=self.OK,
                           result=dict(reason=reason, sender=self.EMAIL_KWARGS['from_addr'],
                                       receivers=self.EMAIL_KWARGS['to_addrs'],
                                       subject=self.subject_channel, text=self.text))
        else:
            self.js = dict(status=self.ERROR, result=dict(reason=reason), debug=self.EMAIL_KWARGS)

    def send_slack(self):
        if not self.SLACK_TOKEN:
            self.js = dict(status=self.ERROR, result="The SLACK_TOKEN option is unset")
            return
        url = 'https://slack.com/api/chat.postMessage?channel=%s' % self.subject_channel
        data = dict(
            token=self.SLACK_TOKEN,
            text=self.text
        )
        status_code, js = self.make_request(url, data=data, check_status=False)
        for key in ['auth', 'status', 'status_code', 'url', 'when']:
            js.pop(key, None)
        self.js = dict(url=url, status_code=status_code, result=js)
        # {"ok":false,"error":"invalid_auth"}
        # {"ok":false,"error":"channel_not_found"}
        # {"ok":false,"error":"no_text"}
        if js.get('ok', False):
            self.logger.debug("Sent to %s via Slack", js.get('message', {}).get('username', ''))
            self.js['status'] = self.OK
        else:
            self.js['status'] = self.ERROR

    def check_telegram_auth(self, js):
        # {"ok":false,"error_code":401,"description":"Unauthorized"}
        # botfaketoken: {'ok': False, 'error_code': 404, 'description': 'Not Found'}
        status_code = js.pop('status_code')
        if (status_code == -1
            or js.get('error_code', 0) in [401, 404]
            or js.get('description', '') in ['Unauthorized', 'Not Found']):
            metadata['telegram_authorized'] = False
            for key in ['auth', 'status', 'when']:
                js.pop(key, None)
            self.js = dict(url=js.pop('url'), status_code=status_code, status=self.ERROR, result=js)
        elif status_code == 200:
            metadata['telegram_authorized'] = True
            self.js = {}

    def set_telegram_bot_username(self):
        if metadata['telegram_bot_username'] is None:
            url = 'https://api.telegram.org/bot%s/getme' % self.TELEGRAM_TOKEN
            status_code, js = self.make_request(url, check_status=False)
            self.check_telegram_auth(js)
            if not metadata['telegram_authorized']:
                return
            metadata['telegram_bot_username'] = js.get('result', {}).get('username', None)
            self.logger.info("telegram_bot_username: %s", metadata['telegram_bot_username'])

    def set_telegram_chat_id(self):
        # For test only
        if request.args.get('__test_telegram_chat_id_none', 'False') == 'True':
            metadata['telegram_chat_id'] = None
        # For test only
        if request.args.get('__test_telegram_chat_not_found', 'False') == 'True' and not self.tested:
            metadata['telegram_chat_id'] = 'fake_chat_id'
            self.tested = True
            return
        if metadata['telegram_chat_id'] is None:
            url = 'https://api.telegram.org/bot%s/getUpdates' % self.TELEGRAM_TOKEN
            status_code, js = self.make_request(url, check_status=False)
            self.check_telegram_auth(js)
            if not metadata['telegram_authorized']:
                return
            # {"ok":true,"result":[]}
            # For test only
            if request.args.get('__test_telegram_chat_id_none', 'False') == 'True':
                js['result'] = []
            if js.get('result', []):
                metadata['telegram_chat_id'] = js['result'][-1]['message']['chat']['id']
                try:
                    first_name = js['result'][-1]['message']['chat']['first_name']
                    last_name = js['result'][-1]['message']['chat']['last_name']
                except KeyError:
                    first_name = last_name = ''
                metadata['telegram_chat_username'] = ' '.join([first_name, last_name])
                self.logger.info("telegram_chat_id: %s", metadata['telegram_chat_id'])
                self.logger.info("telegram_chat_username: %s", metadata['telegram_chat_username'])

    def send_telegram(self):
        if not self.TELEGRAM_TOKEN:
            self.js = dict(status=self.ERROR, result="The TELEGRAM_TOKEN option is unset")
            return
        self.set_telegram_bot_username()
        self.set_telegram_chat_id()
        if not metadata['telegram_authorized']:
            return
        if metadata['telegram_chat_id'] is None:
            if metadata['telegram_bot_username'] is None:
                link = '`telegram.me/<bot_username>`'
            else:
                link = 'telegram.me/%s' % metadata['telegram_bot_username']
            result = ("You should initiate or update conversations with %s first, "
                      "see %s for help.") % (link, self.telegram_help)
            self.js = dict(status=self.ERROR, result=result)
            return

        url = 'https://api.telegram.org/bot%s/sendMessage?chat_id=%s' % (
            self.TELEGRAM_TOKEN, metadata['telegram_chat_id'])
        status_code, js = self.make_request(url, data=dict(text=self.text), check_status=False)

        for key in ['auth', 'status', 'status_code', 'url', 'when']:
            js.pop(key, None)
        self.js = dict(url=url, status_code=status_code, result=js)

        # {"ok":false,"error_code":400,"description":"Bad Request: chat not found"}
        if "chat not found" in js.get('description', ''):
            self.logger.warning("Resetting telegram_chat_id")
            metadata['telegram_chat_id'] = None
            self.send_telegram()
        elif js.get('ok', False):
            self.logger.debug("Sent to %s via Telegram", metadata['telegram_chat_username'])
            self.js['status'] = self.OK
        else:
            self.js['status'] = self.ERROR
