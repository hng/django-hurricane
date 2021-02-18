import tornado.web
from django.conf import settings
from django.core.management.base import SystemCheckError
from django.core.wsgi import get_wsgi_application
from django.db import OperationalError, connection

from hurricane.metrics import RequestQueueLengthMetric, ResponseTimeAverageMetric
from hurricane.server.wsgi import HurricaneWSGIContainer
from hurricane.metrics import StartupTimeMetric


class DjangoHandler(tornado.web.RequestHandler):
    def initialize(self):
        self.django = HurricaneWSGIContainer(self, get_wsgi_application())

    def prepare(self) -> None:
        self.django(self.request)
        self._finished = True
        self._log()
        self.on_finish()


class DjangoProbeHandler(tornado.web.RequestHandler):
    """
    Parent class for all specific probe handlers.
    """

    def compute_etag(self):
        return None

    def set_extra_headers(self, path):
        self.set_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")

    def _check(self):
        pass

    def get(self):
        self._check()

    def post(self):
        self._check()


class DjangoLivenessHandler(DjangoProbeHandler):
    """
    This handler runs with every call to the probe endpoint which is supposed to be used
    with Kubernetes 'Liveness Probes'. The DjangoCheckHandler calls Django's Check Framework which
    can be used to determine the application's health state during its operation.
    """

    def initialize(self, check_handler):
        self.check = check_handler

    def _check(self):
        if StartupTimeMetric.get():
            try:
                self.check()
                if settings.DATABASES:
                    # once a connection has been established, this will be successful
                    # (even if the connection is gone later on)
                    connection.ensure_connection()
            except SystemCheckError as e:
                if settings.DEBUG:
                    self.write("django check error: " + str(e))
                else:
                    self.write("check error")
                self.set_status(500)
            except OperationalError as e:
                if settings.DEBUG:
                    self.write("django database error: " + str(e))
                else:
                    self.write("db error")
                self.set_status(500)
            else:
                if response_average_time := ResponseTimeAverageMetric.get():
                    self.write(
                        f"Average response time: {response_average_time:.2f}ms Request "
                        f"queue size: {RequestQueueLengthMetric.get()} Rx"
                    )
                else:
                    self.write("alive")
        else:
            self.set_status(400)


class DjangoReadinessHandler(DjangoProbeHandler):
    """
    This handler runs with every call to the probe endpoint which is supposed to be used
    with Kubernetes 'Readiness Probes'. The DjangoCheckHandler calls Django's Check Framework which
    can be used to determine the application's health state during its operation.
    """

    def initialize(self, req_queue_len):
        self.request_queue_length = req_queue_len

    def _check(self):
        if StartupTimeMetric.get():
            if RequestQueueLengthMetric.get() > self.request_queue_length:
                self.set_status(400)
            else:
                self.set_status(200)
        else:
            self.set_status(400)


class DjangoStartupHandler(DjangoProbeHandler):
    """
    This handler runs with every call to the probe endpoint which is supposed to be used with Kubernetes
    'Startup Probes'. It returns 400 response for post and get requests, if StartupTimeMetric is not set, what means
    that the application is still in the startup phase. As soon as StartupTimeMetric is set, this handler returns 200
    response upon request, which indicates, that startup phase is finished and Kubernetes can now poll
    liveness/readiness probes.
    """

    def _check(self):
        if StartupTimeMetric.get():
            self.write(f"Startup was finished {StartupTimeMetric.get()}")
            self.set_status(200)
        else:
            self.set_status(400)
