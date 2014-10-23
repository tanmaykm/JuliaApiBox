#! /usr/bin/env python

import random
import string

import tornado.ioloop
import tornado.web
import tornado.auth
import docker

from zmq.eventloop import ioloop

from jbapi_util import read_config, CloudHelper, LoggerMixin
from db.db_base import JBoxDB
from db.user_v2 import JBoxUserV2
from handlers.handler_base import JBApiHandler
from handlers.main import MainHandler
from jbapi_container import JBApiContainer


class JBApi(LoggerMixin):
    cfg = None

    def __init__(self):
        cfg = JBApi.cfg = read_config()
        dckr = docker.Client()
        cloud_cfg = cfg['cloud_host']

        JBApiHandler.configure(cfg)

        JBoxDB.configure(cfg)
        if 'jbox_users_v2' in cloud_cfg:
            JBoxUserV2.NAME = cloud_cfg['jbox_users_v2']

        CloudHelper.configure(has_s3=cloud_cfg['s3'],
                              has_dynamodb=cloud_cfg['dynamodb'],
                              has_cloudwatch=cloud_cfg['cloudwatch'],
                              has_autoscale=cloud_cfg['autoscale'],
                              has_route53=cloud_cfg['route53'],
                              scale_up_at_load=cloud_cfg['scale_up_at_load'],
                              scale_up_policy=cloud_cfg['scale_up_policy'],
                              autoscale_group=cloud_cfg['autoscale_group'],
                              route53_domain=cloud_cfg['route53_domain'],
                              region=cloud_cfg['region'],
                              install_id=cloud_cfg['install_id'])

        JBApiContainer.configure(dckr, cfg['docker_image_pfx'],
                                 cfg['mem_limit'], cfg['cpu_limit'], cfg['numlocalmax'])

        self.application = tornado.web.Application([
            (r"/api/.*", MainHandler)
        ])
        self.application.settings["cookie_secret"] = self.get_cookie_secret()
        self.application.settings["google_oauth"] = cfg["google_oauth"]
        self.application.listen(cfg["port"])

        self.ioloop = ioloop.IOLoop.instance()

        # run container maintainence every 5 minutes
        run_interval = 5 * 60 * 1000
        self.log_info("Container maintenance every " + str(run_interval / (60 * 1000)) + " minutes")
        self.ct = ioloop.PeriodicCallback(JBApi.do_housekeeping, run_interval, self.ioloop)

    @staticmethod
    def get_cookie_secret():
        secret = []
        secret_chars = string.ascii_uppercase + string.digits
        while len(secret) < 32:
            secret.append(random.choice(secret_chars))
        return ''.join(secret)

    def run(self):
        JBApiContainer.publish_container_stats()
        JBApiContainer.refresh_container_list()
        self.ct.start()
        self.ioloop.start()

    @staticmethod
    def do_housekeeping():
        JBApiContainer.maintain()
        if JBApi.cfg['cloud_host']['scale_down'] and (JBApiContainer.num_active() == 0) and \
                (JBApiContainer.num_stopped() == 0) and CloudHelper.should_terminate():
            JBApi.log_info("terminating to scale down")
            CloudHelper.terminate_instance()


if __name__ == "__main__":
    ioloop.install()
    JBApi().run()
