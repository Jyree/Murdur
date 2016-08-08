from tornado.ioloop import IOLoop
from tornado import gen
from tornado.httpclient import AsyncHTTPClient, HTTPError
import json
from sys import stdout, stderr, exit
from os import path, makedirs, listdir
import time
import re
from random import seed, choice, shuffle
import post_multipart
from urllib.parse import urlencode

BOT_TOKEN = 'token'
SAVE_DIR = './pics/'
BOARDS = [
    'h',
    'hc',
    'u',
    'd',
]

try:
    with open('stat.json', 'r') as f:
        statistics = json.loads(f.read())
except FileNotFoundError as e:
    statistics = dict()

seed()
logf = open('grabber.log', 'w')

# ------------------IMAGE GRUBBER------------------#


@gen.coroutine
def grab_img(b, fname):
    stderr.write('Start downloading %s\n' % (b + fname))

    try:
        resp = yield AsyncHTTPClient().fetch('http://i.4cdn.org/%s/%s' % (b, fname))
    except Exception as e:
        print('Proc_thread ', str(e), file=logf)
        stderr.write('%s ERROR\n' % (b + fname))
        return

    if(resp.error):
        stderr.write('%s ERROR\n' % (b + fname))
        return  # Fuck this image

    with open(path.join(SAVE_DIR, b + fname), 'wb') as fout:
        fout.write(resp.body)  # Saving downloaded file

    stderr.write('Finish downloading %s\n' % (b + fname))


@gen.coroutine
def proc_thread(thr, b):
    try:
        resp = yield AsyncHTTPClient().fetch('http://a.4cdn.org/%s/thread/%s.json' % (b, thr))
    except Exception as e:
        print('Proc_thread ', str(e), file=logf)
        return

    if(resp.error):
        return  # Fuck this thread

    js = json.loads(resp.body if isinstance(resp.body, str)
                    else resp.body.decode())['posts']
    for p in js:
        try:
            fname = str(p['tim']) + p['ext']
        except KeyError as e:
            continue

        if(path.isfile(path.join(SAVE_DIR, b + fname))):
            continue

        yield gen.Task(grab_img, b, fname)


@gen.coroutine
def proc_page(pg, b):
    for thread in pg["threads"]:
        yield gen.Task(proc_thread, thread['no'], b)


@gen.coroutine
def proc_board(b: str):
    try:
        response = yield AsyncHTTPClient().fetch('http://a.4cdn.org/%s/threads.json' % (b))
    except Exception as e:
        print('Proc_board %s' % (b), str(e), file=logf)
        return

    js = json.loads(response.body if isinstance(
        response.body, str) else response.body.decode())
    for page in js:
        yield gen.Task(proc_page, page, b)


@gen.engine
def grabber():
    while(True):
        shuffle(BOARDS)
        for b in BOARDS:
            yield gen.Task(proc_board, b)
        stderr.write('Grabber went to sleep\n')
        yield gen.Task(IOLoop.instance().add_timeout, time.time() + 24 * 60 * 60)

# ---------------TELEGRAM BOT---------------#


@gen.coroutine
def send_new(msg):
    chat_id = msg['message']['chat']['id']
    username = msg['message']['from']['username']

    if(not '%s:%s' % (chat_id, username) in statistics.keys()):
        statistics['%s:%s' % (chat_id, username)] = 0
    statistics['%s:%s' % (chat_id, username)] += 1

    while(True):
        print('start sending to %s' % (username), file=stderr)
        fname = path.join(SAVE_DIR, choice(listdir(SAVE_DIR)))
        ext = fname[-4:]

        try:
            with open(fname, 'rb') as fin:
                if(ext == 'jpeg' or ext == '.png' or ext == '.jpg'):
                    # post('https://api.telegram.org/bot%s/sendPhoto' % BOT_TOKEN,
                    #         files={'photo': fin})
                    #         data={'chat_id': chat_id, 'disable_notification': True},
                    resp = yield post_multipart.posturl('https://api.telegram.org/bot%s/sendPhoto' % BOT_TOKEN,
                                                        [('chat_id', chat_id),
                                                         ('disable_notification', True)],
                                                        [('photo', path.basename(fname), fin.read())])
                elif(ext == '.gif'):
                    # post('https://api.telegram.org/bot%s/sendDocument' % BOT_TOKEN,
                    #         data={'chat_id': chat_id, 'disable_notification': True},
                    #         files={'document': fin})
                    resp = yield post_multipart.posturl('https://api.telegram.org/bot%s/sendDocument' % BOT_TOKEN,
                                                        [('chat_id', chat_id),
                                                         ('disable_notification', True)],
                                                        [('document', path.basename(fname), fin.read())])
                elif(ext == 'webm'):
                    # post('https://api.telegram.org/bot%s/sendVideo' % BOT_TOKEN,
                    #         data={'chat_id': chat_id, 'disable_notification': True},
                    #         files={'video': fin})
                    resp = yield post_multipart.posturl('https://api.telegram.org/bot%s/sendVideo' % BOT_TOKEN,
                                                        [('chat_id', chat_id),
                                                         ('disable_notification', True)],
                                                        [('video', path.basename(fname), fin.read())])
        except Exception as e:
            print('Error occured: ', e, file=stderr)
            continue

        print('finishing sending to %s' % (username), file=stderr)
        break


@gen.coroutine
def send_help(msg):
    yield send_message(msg['message']['chat']['id'], 'Use \\new to request pic!')


@gen.coroutine
def send_start(msg):
    pass  # Duck the start


@gen.coroutine
def send_message(chat_id, txt):
    params = urlencode({'chat_id': chat_id, 'text': txt})
    yield AsyncHTTPClient().fetch('https://api.telegram.org/bot%s/sendMessage?%s' % (BOT_TOKEN, params))


@gen.coroutine
def multi_send(msg):
    txt = msg['message']['text'][4:]  # /new...
    chat_id = msg['message']['chat']['id']

    res = 0
    for c in txt:
        if(not c.isdigit()):
            break
        res *= 10
        res += int(c)
    if(res > 50):
        yield send_message(chat_id, 'Too many porn pics you want. Go to hell should you')
        return
    for _ in range(res):
        yield send_new(msg)


mp = (
    (r'^/new\d+.*$', multi_send),
    (r'^/new.*$', send_new),
    (r'^/help$', send_help),
    (r'^/start$', send_start),
)


@gen.coroutine
def proc_message(msg):
    try:
        text = msg['message']['text']
        for rec in mp:
            if(re.match(rec[0], text)):
                yield gen.Task(rec[1], msg)
                break
    except KeyError as e:
        return


@gen.engine
def telegram_bot():
    try:
        with open('last', 'r') as f:
            l = int(f.readline())
    except FileNotFoundError:
        l = 0  # No messages retrieved yet

    while(True):
        try:
            resp = yield AsyncHTTPClient().fetch('https://api.telegram.org/bot%s/getUpdates?offset=%i' % (BOT_TOKEN, l + 1))
        except Exception as e:
            print('telegram bot ', e, file=logf)
            continue

        js = json.loads(resp.body if isinstance(resp.body, str)
                        else resp.body.decode())['result']

        if(len(js) == 0):
            continue

        for message in js:
            yield gen.Task(proc_message, message)

        l = js[-1]['update_id']
        with open('last', 'w') as f:
            f.write(str(l))

        with open('stat.json', 'w') as f:
            f.write(json.dumps(statistics))


if __name__ == '__main__':
    try:
        makedirs(SAVE_DIR)
    except Exception as e:
        pass
    IOLoop.instance().spawn_callback(grabber)
    IOLoop.instance().spawn_callback(telegram_bot)
    IOLoop.instance().start()

logf.close()
