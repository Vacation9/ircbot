from config import ADMINS, CHANNEL
import re
import os
from glob import glob
from lxml.html import parse
from urllib.request import urlopen, Request
from urllib.error import URLError
import json
import importlib
import imp
import time
import socket


class MyHandler():
    def __init__(self):
        self.ignored = []
        self.modules = self.loadmodules()
        self.abuselist = {}
        self.scorefile = os.path.dirname(__file__)+'/score'

    def loadmodules(self):
        modulemap = {}
        cmds = []
        for f in glob(os.path.dirname(__file__)+'/commands/*.py'):
            if os.access(f, os.X_OK):
                cmd = os.path.basename(f).split('.')[0]
                cmds.append(cmd)
        for cmd in cmds:
            modulemap[cmd] = importlib.import_module("commands."+cmd)
        return modulemap

    def ignore(self, c, nick):
        if nick in self.ignored:
            return
        self.ignored.append(nick)
        c.privmsg(CHANNEL,
                  "Now igoring %s." % nick)

    def abusecheck(self, c, e, limit):
        nick = e.source.nick
        if nick not in self.abuselist:
            self.abuselist[nick] = [time.time()]
        else:
            self.abuselist[nick].append(time.time())
        count = 0
        for x in self.abuselist[nick]:
            # 30 seconds - arbitrary cuttoff
            if (time.time() - x) < 30:
                count = count + 1
        if count > limit:
            c.privmsg(CHANNEL, "%s is a Bot Abuser" % nick)
            self.ignore(c, nick)
            return False
        return True

    def pubmsg(self, c, e):
        nick = e.source.nick
        msg = e.arguments[0].strip()
        if nick not in ADMINS:
            for nick in self.ignored:
                print("Ignoring!")
                return
        # is this a command?
        cmd = msg.split()[0]
        args = msg[len(cmd)+1:]
        if cmd[0] == '!':
            if cmd[1:] in self.modules:
                mod = self.modules[cmd[1:]]
                try:
                    if hasattr(mod, 'limit') and self.abusecheck(c, e, mod.limit):
                            mod.cmd(e, c, args)
                    else:
                            mod.cmd(e, c, args)
                except Exception as ex:
                    c.privmsg(CHANNEL, '%s: %s' % (type(ex), str(ex)))
                return

        #special commands
        if cmd[0] == '!':
            if cmd[1:] == 'help':
                cmdlist = self.modules.keys()
                cmdlist = ' !'.join([x for x in sorted(self.modules)])
                c.privmsg(CHANNEL, 'Commands: !' + cmdlist)
            # everything below this point requires admin
            if nick in ADMINS:
                if cmd[1:] == 'reload':
                    c.privmsg(CHANNEL, "Aye Aye Capt'n")
                    self.modules = self.loadmodules()
                    for x in self.modules.values():
                        imp.reload(x)
                    return
                elif cmd[1:] == 'cignore':
                    self.ignored = []
                    c.privmsg(CHANNEL, "Ignore list cleared.")
                elif cmd[1:] == 'ignore':
                    self.ignore(c, args)
                #FIXME: CHANNEL is hardcoded in config.py
                elif cmd[1:] == 'join':
                    c.join(args)
                    c.privmsg(args, "Joined at the request of " + nick)
                elif cmd[1:] == 'part':
                    c.privmsg(args, "Leaving at the request of " + nick)
                    c.part(args)
        # ++ and --
        match = re.search(r"([a-zA-Z0-9]+)(\+\+|--)", msg)
        if match:
            name = match.group(1).lower()
            if "+" in match.group(2):
                score = 1
                if name == nick:
                    c.privmsg(CHANNEL, nick +
                              ": No self promotion! You lose 10 points.")
                    score = -10
            else:
                score = -1
            if os.path.isfile(self.scorefile):
                scores = json.load(open(self.scorefile))
            else:
                scores = {}
            if name in scores:
                scores[name] += score
            else:
                scores[name] = score
            f = open(self.scorefile, "w")
            json.dump(scores, f)
            f.close()
            return

        # crazy regex to match urls
        match = re.match(r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»....]))", msg)
        if match:
            try:
                url = match.group(1)
                if not url.startswith('http'):
                    url = 'http://' + url
                # Wikipedia doesn't like the default User-Agent
                req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                t = parse(urlopen(req, timeout=2))
                c.privmsg(CHANNEL, t.find(".//title").text)
            except URLError as ex:
                # website does not exist
                if hasattr(ex.reason, 'errno') and ex.reason.errno == socket.EAI_NONAME:
                    return
                else:
                    c.privmsg(CHANNEL, '%s: %s' % (type(ex), str(ex)))
            # page does not contain a title
            except AttributeError:
                return
            except Exception as ex:
                    c.privmsg(CHANNEL, '%s: %s' % (type(ex), str(ex)))
        return
