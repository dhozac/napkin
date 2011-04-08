#!/usr/bin/python -tt
# vim:set ts=4 sw=4 expandtab:
# 
# napkin - the core of the system
# Copyright (C) 2011 Daniel Hokka Zakrisson <daniel@hozac.com>
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import time
import logging
import threading
import napkin.helpers

helpers = napkin.helpers

class resource_ref:
    """A light-weight reference to a resource"""
    def __init__(self, c, n = None):
        """Create a new resource_ref based either on an object (one argument),
or a class and a name (two arguments)."""
        if isinstance(c, resource_ref):
            self._class = c._class
            self._name = c._name
        elif n is None:
            self._class = c.__class__
            self._name = c.name
        else:
            self._class = c
            self._name = n
    def __eq__(self, obj):
        if isinstance(obj, resource_ref):
            return self._class == obj._class and self._name == obj._name
        else:
            return self._class == obj.__class__ and self._name == obj.name
    def __ne__(self, obj):
        return not self.__eq__(obj)
    def __str__(self):
        return "%s(%s)" % (self._class.__name__, self._name.__repr__())
    def __repr__(self):
        return self.__str__()
    def __hash__(self):
        return hash(self._class) + hash(self._name)

class MonitorException(Exception):
    """A generic exception to throw for errors in monitors."""
    def __init__(self, obj, val, msg = None):
        self.obj = obj
        self.val = val
        self.msg = msg
    def __repr__(self):
        if self.msg is not None:
            return self.msg
        return "%s = %s" % (self.obj.name, self.val)
    def __str__(self):
        return self.__repr__()

class MonitorBelowMin(MonitorException):
    def __init__(self, obj, val, min):
        self.obj = obj
        self.val = val
        self.min = min
    def __repr__(self):
        return "%s: MonitorBelowMin: %s < %s" % (self.obj.name, self.val, self.min)
    def __str__(self):
        return self.__repr__()

class MonitorAboveMax(MonitorException):
    def __init__(self, obj, val, max):
        self.obj = obj
        self.val = val
        self.max = max
    def __repr__(self):
        return "%s: MonitorAboveMax: %s > %s" % (self.obj.name, self.val, self.max)
    def __str__(self):
        return self.__repr__()

class manifest:
    instance = None
    def __init__(self):
        manifest.instance = self
        self.resources = {}
        self.order = []
        self.report_data = {}
        self.monitors = []
        self.wlock = threading.RLock()
        self.rlock = threading.RLock()
        self.has_wlock = False

    def add(self, obj):
        k = resource_ref(obj)
        if k in self.resources:
            raise KeyError("%s is already a registered resource" % k)
        self.resources[k] = obj
        return k

    def __contains__(self, obj):
        return resource_ref(obj) in self.resources

    def get(self, k):
        return self.resources[resource_ref(k)]

    def __iter__(self):
        if not self.order:
            res = [k for k in self.resources if not isinstance(self.resources[k], monitor)]
            for i in res:
                self.resources[i].rafter = self.resources[i].after
            for i in res:
                for j in self.resources[i].before:
                    self.resources[j].rafter.append(i)
            n = len(res)
            self.order = []
            for i in res:
                if not self.resources[i].rafter:
                    self.order.append(i)
                    n = n - 1
            pn = n + 1
            while n > 0 and pn > n:
                for i in res:
                    if i in self.order:
                        continue
                    done = True
                    for j in self.resources[i].rafter:
                        if j not in self.order:
                            done = False
                            break
                    if done:
                        self.order.append(i)
                        n = n - 1
                        pn = n
                time.sleep(1)
        for i in self.order:
            yield self.resources[i]

    def run(self):
        self.get_rlock()
        for i in self:
            r = i.pre()
            if r:
                logging.info(r)
        for i in self:
            if not i.can_run():
                continue
            try:
                r = i.run()
                if r:
                    logging.info(r)
            except:
                logging.exception("%s: run failed" % i.name)
        for i in self:
            r = i.post()
            if r:
                logging.info(r)
        self.unlock()
    def clear(self):
        self.resources.clear()
        self.order = []

    def str_resource(self, obj):
        if isinstance(obj, monitor):
            return repr(obj) + ".schedule()\n"
        elif obj.subscribed:
            ret = repr(obj) + ".subscribe("
            ret += repr(obj.subscribed[0][0])
            if obj.subscribed[0][1]:
                ret += ", " + repr(obj.subscribed[0][1])
            ret += ")\n"
            return ret
        else:
            return repr(obj) + ".add()\n"
    def __str__(self):
        ret = ""
        if self.order:
            for i in self.order:
                ret += self.str_resource(self.resources[i])
        for k in self.resources:
            if k not in self.order:
                ret += self.str_resource(self.resources[k])
        return ret
    def __repr__(self):
        return self.__str__()

    def add_schedule(self, obj):
        k = resource_ref(obj)
        do_schedule = True
        for i in self.monitors:
            if k == i['key']:
                do_schedule = False
                break
        k = self.add(obj)
        if do_schedule:
            self.schedule(k, obj)
    def schedule(self, k, obj):
        new = int(time.time()) + obj.interval
        d = {'time': new, 'key': k}
        for i in range(0, len(self.monitors)):
            if new < self.monitors[i]['time']:
                self.monitors.insert(i, d)
                return
        self.monitors.append(d)
    def monitor(self):
        self.report_data.clear()
        if len(self.monitors) == 0:
            return
        self.get_rlock()
        curtime = int(time.time())
        logging.debug("running monitors at %d:\n%s" % (curtime, self.monitors))
        while self.monitors[0]['time'] <= curtime:
            d = self.monitors.pop(0)
            try:
                i = self.resources[d['key']]
            except KeyError:
                # Deleted monitor
                continue
            try:
                val = i.run()
            except MonitorException:
                t = sys.exc_info()[0]
                e = sys.exc_info()[1]
                logging.warning("%s: %s" % (d['key'], e))
                i.notify_subscribers(t, e)
                val = e.val
            except:
                logging.exception("unknown exception from %s" % d['key'])
                continue
            if val is not None:
                self.report(i, val)
            self.schedule(d['key'], i)
        self.unlock()
    def get_delay(self):
        if len(self.monitors) > 0:
            time_left = self.monitors[0]['time'] - time.time()
            if time_left < 0:
                time_left = 0
        else:
            time_left = None
        return time_left
    def report(self, obj, val):
        self.report_data[(obj.__class__.__name__, obj.name)] = val
    def get_report(self):
        return self.report_data
    def clear_monitor(self):
        self.report_data.clear()
        self.monitors = []

    def read(self, filename):
        self.get_wlock()
        self.clear()
        napkin.helpers.execfile(filename)
        self.unlock()

    def get_rlock(self):
        logging.debug("Thread %s: acquiring read lock" % threading.current_thread().ident)
        self.rlock.acquire()
        logging.debug("Thread %s: acquired!" % threading.current_thread().ident)
    def get_wlock(self):
        logging.debug("Thread %s: acquiring write lock" % threading.current_thread().ident)
        self.wlock.acquire()
        self.rlock.acquire()
        self.has_wlock = True
        logging.debug("Thread %s: acquired!" % threading.current_thread().ident)
    def unlock(self):
        logging.debug("Thread %s: releasing locks" % threading.current_thread().ident)
        if self.has_wlock:
            self.has_wlock = False
            self.wlock.release()
        self.rlock.release()

class resource:
    metaproperties = {
        'name': {},
        'ensure': {'default': 'present'},
        'requires': {'alias': 'after'},
        'before': {'type': [resource_ref], 'default': []},
        'after': {'type': [resource_ref], 'default': []},
    }
    def convert_value(self, t, v):
        if isinstance(t, (list, tuple)) or t == list or t == tuple:
            if not isinstance(v, (list, tuple)):
                v = [v]
            nv = []
            if len(t) == 0:
                t[0] = str
            for i in v:
                nv.append(self.convert_value(t[0], i))
        elif t == bool:
            if isinstance(v, (str, unicode)):
                vl = v.lower()
                if vl == "true" or vl == "1" or vl == "yes":
                    nv = True
                elif vl == "false" or vl == "0" or vl == "no":
                    nv = False
                else:
                    raise ValueError("%s is not a valid boolean value" % v)
            else:
                nv = bool(v)
        else:
            nv = t(v)
        return nv
    def __init__(self, *args, **kwargs):
        self.before = []
        self.after = []
        self.subscribed = []
        self.manifest = manifest.instance
        self.success = False
        if len(kwargs) == 0 and len(args) == 1:
            # Resource reference
            self.name = args[0]
            return
        for i in kwargs:
            prop = None
            if i in self.properties:
                prop = self.properties[i]
            elif i in self.metaproperties:
                prop = self.metaproperties[i]
            else:
                raise TypeError("unexpected keyword argument %s" % (i))
            val = kwargs[i]
            if 'alias' in prop:
                i = prop['alias']
                if i in self.properties:
                    prop = self.properties[i]
                elif i in self.metaproperties:
                    prop = self.metaproperties[i]
                else:
                    raise TypeError("unknown alias %s" % (i))
            if 'type' in prop:
                val = self.convert_value(prop['type'], val)
            setattr(self, i, val)
        if not hasattr(self, 'name'):
            if hasattr(self, 'def_name') and hasattr(self, self.def_name):
                setattr(self, 'name', getattr(self, self.def_name))
            elif len(args) > 0:
                self.name = args[0]
                if hasattr(self, 'def_name'):
                    setattr(self, self.def_name, args[0])
            else:
                raise TypeError("missing required argument name")
        for j in (self.properties, self.metaproperties):
            for i in j:
                prop = j[i]
                if not hasattr(self, i):
                    if 'required' in prop and prop['required']:
                        raise TypeError("missing required argument %s" % (i))
                    if 'default' in prop:
                        setattr(self, i, prop['default'])
    def add(self):
        if isinstance(self, monitor):
            raise TypeError("%s is a monitor and cannot be .add()ed, try .schedule() instead")
        self.manifest.add(self)
    def pre(self):
        pass
    def run(self):
        r = getattr(self, 'ensure_' + self.ensure, None)
        if r is None:
            raise TypeError("unknown ensure value %s" % self.ensure)
        return r()
    def post(self):
        pass
    def subscribe(self, obj, t=None):
        k = resource_ref(obj)
        self.after.append(k)
        self.add()
        self.subscribed.append((k, t))
        if isinstance(obj, monitor):
            self.manifest.get(k).subscribers.append((self, t))
    def notify_subscribers(self, t=None):
        self.notification = t
    def can_run(self):
        for i in self.after:
            if not self.manifest.get(i).success:
                return False
        if len(self.subscribed) > 0:
            for i in self.subscribed:
                obj = self.manifest.get(i[0])
                if hasattr(obj, 'notification') and (obj.notification == i[1] or i[1] is None):
                    return True
            return False
        return True
    def __str__(self):
        ret = self.__class__.__name__ + "("
        for i in (self.metaproperties, self.properties):
            for j in i:
                prop = i[j]
                if hasattr(self, j):
                    v = getattr(self, j)
                    if 'default' not in prop or v != prop['default']:
                        ret += "%s=%s, " % (j, getattr(self, j).__repr__())
        ret = ret[:-2] + ")"
        return ret
    def __repr__(self):
        return self.__str__()

class monitor(resource):
    metaproperties = resource.metaproperties.copy()
    metaproperties.update({
        'interval': {'required': True, 'type': int},
        'min': {},
        'max': {},
    })
    def __init__(self, *args, **kwargs):
        resource.__init__(self, *args, **kwargs)
        self.subscribers = []
    def schedule(self):
        self.manifest.add_schedule(self)
    def run(self):
        val = self.fetch()
        if hasattr(self, 'min') and val < self.min:
            raise MonitorBelowMin(self, val, self.min)
        if hasattr(self, 'max') and val > self.max:
            raise MonitorAboveMax(self, val, self.max)
        return val
    def notify_subscribers(self, t, e):
        for i in self.subscribers:
            if i[1] == t.__name__:
                logging.debug("running rectifier for %s %s: %s" % (resource_ref(self), t.__name__, resource_ref(i[0])))
                i[0].run()
