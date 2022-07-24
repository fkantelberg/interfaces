import logging
import time
from threading import Thread

from odoo.service import server
from odoo.tools import config

from .client import MQTTRunner

_logger = logging.getLogger(__name__)

START_DELAY = 5


class MQTTRunnerThread(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.daemon = True
        self.runner = MQTTRunner()

    def run(self):
        # sleep a bit to let the workers start at ease
        time.sleep(START_DELAY)
        self.runner.run()

    def stop(self):
        self.runner.stop()


class WorkerMQTTRunner(server.Worker):
    """Jobrunner workers"""

    def __init__(self, multi):
        super().__init__(multi)
        self.watchdog_timeout = None
        self.runner = MQTTRunner()

    def sleep(self):
        pass

    def signal_handler(self, sig, frame):
        _logger.debug("WorkerMQTTRunner (%s) received signal %s", self.pid, sig)
        super().signal_handler(sig, frame)
        self.runner.stop()

    def process_work(self):
        _logger.debug("WorkerMQTTRunner (%s) starting up", self.pid)
        time.sleep(START_DELAY)
        self.runner.run()


runner_thread = None


def _start_runner_thread(server_type):
    global runner_thread
    if not config["stop_after_init"]:
        _logger.info("starting mqttrunner thread (in %s)", server_type)
        runner_thread = MQTTRunnerThread()
        runner_thread.start()


orig_prefork__init__ = server.PreforkServer.__init__
orig_prefork_process_spawn = server.PreforkServer.process_spawn
orig_prefork_worker_pop = server.PreforkServer.worker_pop
orig_threaded_start = server.ThreadedServer.start
orig_threaded_stop = server.ThreadedServer.stop


def prefork__init__(server, app):
    res = orig_prefork__init__(server, app)
    server.mqttrunner = {}
    return res


def prefork_process_spawn(server):
    orig_prefork_process_spawn(server)
    if not hasattr(server, "mqttrunner"):
        return

    if not server.mqttrunner:
        server.worker_spawn(WorkerMQTTRunner, server.mqttrunner)


def prefork_worker_pop(server, pid):
    res = orig_prefork_worker_pop(server, pid)
    if not hasattr(server, "mqttrunner"):
        return res

    if pid in server.mqttrunner:
        server.mqttrunner.pop(pid)
    return res


def threaded_start(server, stop=False):
    res = orig_threaded_start(server, stop=stop)
    if not stop:
        _start_runner_thread("threaded server")
    return res


def threaded_stop(server):
    global runner_thread
    if runner_thread:
        runner_thread.stop()

    res = orig_threaded_stop(server)
    if runner_thread:
        runner_thread.join()
        runner_thread = None
    return res


server.PreforkServer.__init__ = prefork__init__
server.PreforkServer.process_spawn = prefork_process_spawn
server.PreforkServer.worker_pop = prefork_worker_pop
server.ThreadedServer.start = threaded_start
server.ThreadedServer.stop = threaded_stop
