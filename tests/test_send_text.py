# coding: utf-8
import json

from flask import url_for

from tests.utils import cst, req, sleep


def test_email_pass(app, client):
    if not app.config.get('EMAIL_PASSWORD', ''):
        print("EMAIL_PASSWORD empty")
        return

    def check_pass(receivers=None, subject='Email from #scrapydweb', text=None):
        assert js['status'] == cst.OK
        assert js['result']['reason'] == 'Sent'
        assert js['result']['sender'] == app.config['FROM_ADDR']
        if receivers is not None:
            assert js['result']['receivers'] == receivers
        if subject is not None:
            assert js['result']['subject'] == subject
        if text is not None:
            assert js['result']['text'] == text
        assert js['when']
        sleep(5)

    # 'email'
    nos = ['debug', 'email_password']
    __, js = req(app, client, view='sendtext', kws=dict(opt='email'), nos=nos)
    check_pass(text='test')

    # 'email/<text>'
    text = 'test email text'
    __, js = req(app, client, view='sendtext', kws=dict(opt='email', text=text))
    check_pass(text=text)

    # 'email/<subject_channel>/<text>'
    text = 'test email subject text'
    subject_channel = text + ' #scrapydweb'
    kws = dict(opt='email', subject_channel=subject_channel, text=text)
    __, js = req(app, client, view='sendtext', kws=kws)
    check_pass(text=text, subject=subject_channel)

    # ?receivers=&subject=
    receivers = app.config['TO_ADDRS'] + ['my8100@gmail.com']
    text = 'test email text receivers and subject in query strings'
    subject = text + ' #scrapydweb'
    kws = dict(opt='email', text=text, receivers=';'.join(receivers), subject=subject)
    __, js = req(app, client, view='sendtext', kws=kws)
    check_pass(receivers=receivers, subject=subject, text=text)

    # post form
    receivers = ['my8100@gmail.com'] + app.config['TO_ADDRS']
    value = 'test email post form #scrapydweb'
    subject = value + ' #scrapydweb'
    # Cannot directly pass in a list type to the data, otherwise, only the first receiver could be recognized.
    data = dict(receivers=','.join(receivers), subject=subject, a=1, arg=value, Chinese=u'中文')
    __, js = req(app, client, view='sendtext', kws=dict(opt='email'), data=data)
    check_pass(receivers=receivers, subject=subject, text=None)
    data['a'] = str(data['a'])
    assert json.loads(js['result']['text']) == data

    # post json
    # requests.post('http://httpbin.org/post', data=dict(a=1, b=2)).json()
    # {'data': '',
     # 'form': {'a': '1', 'b': '2'},
     # 'headers': {'Content-Type': 'application/x-www-form-urlencoded',},
     # 'json': None,}
    # requests.post('http://httpbin.org/post', json=dict(a=1, b=2)).json()
    # {'data': '{"a": 1, "b": 2}',
     # 'form': {},
     # 'headers': {'Content-Type': 'application/json',},
     # 'json': {'a': 1, 'b': 2},}
    # https://stackoverflow.com/questions/10434599/get-the-data-received-in-a-flask-request
    # request.headers:
    # Content-Type: application/x-www-form-urlencoded
    # Content-Type: application/json
    # https://stackoverflow.com/questions/28836893/how-to-send-requests-with-jsons-in-unit-tests
    receivers = app.config['TO_ADDRS'] + ['my8100@gmail.com']
    value = 'test email post json #scrapydweb'
    subject = value + ' #scrapydweb'
    data = dict(receivers=receivers, subject=subject, b=2, arg=value, Chinese=u'中文')
    __, js = req(app, client, view='sendtext', kws=dict(opt='email'),
                 data=json.dumps(data), content_type='application/json')
    check_pass(receivers=receivers, subject=subject, text=None)
    assert json.loads(js['result']['text']) == data


def test_email_fail(app, client):
    app.config['EMAIL_PASSWORD'] = 'fakepassword'
    req(app, client, view='sendtext', kws=dict(opt='email'), jskws=dict(status=cst.ERROR),
        jskeys=['status', 'result', 'debug', 'when'], ins='email_password', nos='Sent')


def test_slack_pass(app, client):
    if not app.config['SLACK_TOKEN']:
        print("SLACK_TOKEN unset")
        return

    def check_pass(text=None, channel=app.config['SLACK_CHANNEL']):  # general -> "channel": "CLX124N0Z",
        assert js['url'] == 'https://slack.com/api/chat.postMessage?channel=%s' % channel
        assert js['status_code'] == 200
        assert js['status'] == cst.OK
        assert js['result']['ok'] == True
        if text is not None:
            assert js['result']['message']['text'] == text
        assert js['when']

    # 'slack'
    nos = ['debug', 'token', 'error', 'tip']
    __, js = req(app, client, view='sendtext', kws=dict(opt='slack'), nos=nos)
    check_pass('test')
    channel_general = js['result']['channel']

    # 'slack/<text>'
    text = 'test slack text'
    __, js = req(app, client, view='sendtext', kws=dict(opt='slack', text=text))
    check_pass(text)

    # 'slack/<subject_channel>/<text>'
    channel = 'random'  # random -> "channel": "CLRUUNCCT"
    text = 'test slack channel %s and text' % channel
    kws = dict(opt='slack', subject_channel=channel, text=text)
    __, js = req(app, client, view='sendtext', kws=kws)
    check_pass(text, channel)
    channel_random = js['result']['channel']
    assert channel_random != channel_general

    # post form and channel in query string
    channel = 'random'
    value = "slack post form and channel %s in query string" % channel
    data = dict(a=1, arg=value, Chinese=u'中文')
    __, js = req(app, client, view='sendtext', kws=dict(opt='slack', channel=channel), data=data)
    check_pass(channel=channel)
    data['a'] = str(data['a'])
    assert json.loads(js['result']['message']['text']) == data
    assert js['result']['channel'] == channel_random

    # post json
    channel = 'random'
    value = "slack post json and channel %s in data" % channel
    data = dict(channel=channel, b=2, arg=value, Chinese=u'中文')
    __, js = req(app, client, view='sendtext', kws=dict(opt='slack'),
                data=json.dumps(data), content_type='application/json')
    check_pass(channel=channel)
    assert json.loads(js['result']['message']['text']) == data
    assert js['result']['channel'] == channel_random


def test_slack_fail(app, client):
    kws = dict(opt='slack')
    jskeys = ['url', 'status_code', 'status', 'result', 'debug', 'tip', 'when']

    def check_fail(channel=None, status_code=None, result=None):
        assert js['status'] == 'error'
        if channel is not None:
            assert js['url'] == "https://slack.com/api/chat.postMessage?channel=%s" % channel
        if status_code is not None:
            assert js['status_code'] == status_code
        if result is not None:
            assert js['result'] == result
        assert js['tip']
        assert js['when']

    # SLACK_TOKEN unset
    token = app.config['SLACK_TOKEN']
    app.config['SLACK_TOKEN'] = ''
    __, js = req(app, client, view='sendtext', kws=kws)
    check_fail(result='The SLACK_TOKEN option is unset')

    if not token:
        return
    else:
        app.config['SLACK_TOKEN'] = token

    # SLACK_CHANNEL invalid
    channel = app.config['SLACK_CHANNEL']
    fakechannel = 'fakechannel'
    app.config['SLACK_CHANNEL'] = fakechannel
    __, js = req(app, client, view='sendtext', kws=kws, jskeys=jskeys)
    check_fail(status_code=200, channel=fakechannel, result={'error': 'channel_not_found', 'ok': False})
    assert js['debug'] == {'channel': fakechannel, 'text': 'test', 'token': app.config['SLACK_TOKEN']}
    app.config['SLACK_CHANNEL'] = channel

    # SLACK_TOKEN invalid
    faketoken = 'faketoken'
    app.config['SLACK_TOKEN'] = faketoken
    __, js = req(app, client, view='sendtext', kws=kws, jskeys=jskeys)
    check_fail(status_code=200, channel=app.config['SLACK_CHANNEL'], result={'error': 'invalid_auth', 'ok': False})
    assert js['debug'] == {'channel': app.config['SLACK_CHANNEL'], 'text': 'test', 'token': faketoken}


# Should be tested before test_telegram_pass() since flags are stored in metadata
def test_telegram_fail(app, client):
    kws = dict(opt='telegram')

    def check_fail(status_code=None, result=None):
        assert js['status'] == 'error'
        if status_code is not None:
            assert js['status_code'] == status_code
            assert js['url']
        if result is not None:
            assert js['result'] == result
        assert js['tip']
        assert js['when']

    # TELEGRAM_TOKEN unset
    token = app.config['TELEGRAM_TOKEN']
    app.config['TELEGRAM_TOKEN'] = ''
    __, js = req(app, client, view='sendtext', kws=kws)
    check_fail(result="The TELEGRAM_TOKEN option is unset")

    if not (token and app.config['ENABLE_TELEGRAM_ALERT']) :
        return
    else:
        app.config['TELEGRAM_TOKEN'] = token

    # TELEGRAM_TOKEN invalid
    faketoken = 'faketoken'
    app.config['TELEGRAM_TOKEN'] = faketoken
    __, js = req(app, client, view='sendtext', kws=kws)
    check_fail(status_code=404, result=dict(description="Not Found", error_code=404, ok=False))
    assert js['debug'] == dict(text='test', token=faketoken)

    faketoken_ = token + '_'
    app.config['TELEGRAM_TOKEN'] = faketoken_
    __, js = req(app, client, view='sendtext', kws=kws)
    check_fail(status_code=401, result=dict(description="Unauthorized", error_code=401, ok=False))
    assert js['debug'] == dict(text='test', token=faketoken_)

    app.config['TELEGRAM_TOKEN'] = token

    # __test_telegram_chat_id_none
    kws_ = dict(kws)
    kws_['__test_telegram_chat_id_none'] = 'True'
    __, js = req(app, client, view='sendtext', kws=kws_)
    check_fail(status_code=None, result=None)
    assert "initiate or update conversations" in js['result']
    assert js['debug'] == {'text': 'test', 'token': token}
    assert js['tip']

    # __test_telegram_chat_not_found, see test_telegram_pass()


def test_telegram_pass(app, client):
    if not (app.config['TELEGRAM_TOKEN'] and app.config['ENABLE_TELEGRAM_ALERT']):
        print("ENABLE_TELEGRAM_ALERT False or TELEGRAM_TOKEN unset")
        return

    def check_pass(text=None):
        assert 'https://api.telegram.org/bot%s' % app.config['TELEGRAM_TOKEN'] in js['url']
        assert js['status_code'] == 200
        assert js['status'] == cst.OK
        assert js['result']['ok'] == True
        if text is not None:
            assert js['result']['result']['text'] == text
        assert js['when']

    # 'telegram' | 'tg'
    nos = ['debug', 'token', 'error', 'tip']
    __, js = req(app, client, view='sendtext', kws=dict(opt='telegram'), nos=nos)
    check_pass('test')
    __, js = req(app, client, view='sendtext', kws=dict(opt='tg'), nos=nos)
    check_pass('test')

    # 'tg/<text>'
    text = 'test tg text'
    __, js = req(app, client, view='sendtext', kws=dict(opt='tg', text=text))
    check_pass(text)

    # post form
    value = "tg post form"
    data = dict(a=1, arg=value, Chinese=u'中文')
    __, js = req(app, client, view='sendtext', kws=dict(opt='tg'), data=data)
    check_pass()
    data['a'] = str(data['a'])
    assert json.loads(js['result']['result']['text']) == data

    # post json
    value = "tg post json"
    data = dict(b=2, arg=value, Chinese=u'中文')
    __, js = req(app, client, view='sendtext', kws=dict(opt='tg'),
                data=json.dumps(data), content_type='application/json')
    check_pass()
    assert json.loads(js['result']['result']['text']) == data

    # __test_telegram_chat_not_found -> Resetting telegram_chat_id
    kws = dict(opt='telegram')
    kws['__test_telegram_chat_not_found'] = 'True'
    __, js = req(app, client, view='sendtext', kws=kws)
    check_pass('test')
