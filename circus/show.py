# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
import errno
import time

from circus.fly import Fly
from circus import logger


class Show(object):

    def __init__(self, name, cmd, num_flies, warmup_delay, working_dir,
                 shell, uid=None, gid=None):
        self.name = name
        self.num_flies = num_flies
        self.warmup_delay = warmup_delay
        self.cmd = cmd
        self._fly_counter = 0
        self.working_dir = working_dir
        self.flies = {}
        self.shell = shell
        self.uid = uid
        self.gid = gid

    def __len__(self):
        return len(self.flies)

    def reap_flies(self):
        for wid, fly in self.flies.items():
            if fly.poll() is not None:
                self.flies.pop(wid)

    def manage_flies(self):
        if len(self.flies.keys()) < self.num_flies:
            self.spawn_flies()

        flies = self.flies.keys()
        flies.sort()
        while len(flies) > self.num_flies:
            wid = flies.pop(0)
            fly = self.flies.pop(wid)
            self.kill_fly(fly)

    def spawn_flies(self):
        for i in range(self.num_flies - len(self.flies.keys())):
            self.spawn_fly()
            time.sleep(self.warmup_delay)

    def spawn_fly(self):
        self._fly_counter += 1
        fly = Fly(self._fly_counter, self.cmd, self.working_dir, self.shell,
                  self.uid, self.gid)
        logger.info('running %s fly [pid %d]' % (self.name, fly.pid))
        self.flies[self._fly_counter] = fly

    # TODO: we should manage more flies here.
    def kill_fly(self, fly):
        logger.info("kill fly %s" % fly.pid)
        fly.terminate()

    def kill_flies(self):
        for wid in self.flies.keys():
            try:
                fly = self.flies.pop(wid)
                self.kill_fly(fly)
            except OSError, e:
                if e.errno != errno.ESRCH:
                    raise

    #################
    # show commands #
    #################

    def handle_flies(self, *args):
        return ",".join([str(wid) for wid in self.flies.keys()])

    def handle_numflies(self, *args):
        return str(self.num_flies)

    def handle_quit(self, *args):
        if len(args) > 0:
            wid = int(args[0])
            if wid in self.flies:
                try:
                    fly =  fly = self.flies.pop(wid)
                    self.kill_fly(fly)
                    return "ok"
                except OSError, e:
                    if e.errno != errno.ESRCH:
                        raise
            else:
                return "error: fly '%s' not found" % wid
        else:
            self.kill_flies()
            self.num_flies = 0
            return "ok"

    def handle_reload(self, *args):
        for i in range(self.num_flies):
            self.spawn_fly()
        self.manage_flies()
        return "ok"

    handle_hup = handle_reload

    def handle_ttin(self, *args):
        self.num_flies += 1
        self.manage_flies()
        return str(self.num_flies)

    def handle_ttou(self, *args):
        self.num_flies -= 1
        self.manage_flies()
        return str(self.num_flies)
