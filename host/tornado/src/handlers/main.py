import tornado.web
from handlers.handler_base import JBApiHandler
from jbapi_container import JBAsyncApi, JBApiContainer


class MainHandler(JBApiHandler):
    @tornado.web.asynchronous
    def post(self):
        uri = self.request.uri
        self.log_debug("called with uri: " + uri)

        comps = filter(bool, uri.split('/'))
        if (len(comps) < 3) or (comps[0] != 'api'):
            self.send_error(status_code=404)
            return

        api_name = comps[1]
        cmd = comps[2]
        args = comps[3:]
        vargs = self.request.arguments

        self.log_debug("calling service:" + api_name +
                       ". cmd:" + cmd +
                       " num args:" + str(len(args)) +
                       " num vargs:" + str(len(vargs)))
        JBApiContainer.ensure_container_available(api_name)
        JBAsyncApi.send_recv(api_name, cmd, args=args, vargs=vargs, on_recv=self.on_recv, on_timeout=self.on_timeout)

    def on_recv(self, msg):
        self.log_debug("responding for " + self.request.uri)
        self.log_info("response: [" + str(msg) + "]")
        self.write(str(msg))
        self.finish()

    def on_timeout(self):
        self.log_error("timed out serving " + self.request.uri)
        self.send_error(status_code=408)

    def get(self):
        return self.post()

    def is_valid_api(self, api_name):
        return api_name in self.config("api_names", [])
