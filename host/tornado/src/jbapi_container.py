import time
import multiprocessing
import zmq
import isodate
import psutil
import json

from datetime import timedelta
from zmq.devices.basedevice import ThreadDevice
from zmq.eventloop import ioloop, zmqstream

from jbapi_util import LoggerMixin, CloudHelper, unique_container_name, continer_name_prefix
from db.api_spec import JBoxApiSpec


class JBApiQueue(LoggerMixin):
    BUFFER_SZ = 20
    QUEUES = {}

    def __init__(self, api_name):
        self.api_name = api_name
        self.num_outstanding = 0
        self.mean_outstanding = 0
        self.qdev = qdev = ThreadDevice(zmq.QUEUE, zmq.XREP, zmq.XREQ)

        spec = JBoxApiSpec(api_name)
        bind_pfx = "tcp://" + CloudHelper.instance_private_ip()

        endpt_in = bind_pfx + str(':') + str(spec.get_endpoint_in())
        endpt_out = bind_pfx + str(':') + str(spec.get_endpoint_out())
        self.endpoints = endpt_in, endpt_out

        timeout_secs = spec.get_timeout_secs()
        self.timeout = timedelta(seconds=timeout_secs) if timeout_secs is not None else None

        self.cmd = spec.get_cmd()
        self.image_name = spec.get_image_name()

        qdev.bind_in(endpt_in)
        qdev.bind_out(endpt_out)

        qdev.setsockopt_in(zmq.SNDHWM, JBApiQueue.BUFFER_SZ)
        qdev.setsockopt_out(zmq.RCVHWM, JBApiQueue.BUFFER_SZ)
        qdev.setsockopt_in(zmq.RCVHWM, JBApiQueue.BUFFER_SZ)
        qdev.setsockopt_out(zmq.SNDHWM, JBApiQueue.BUFFER_SZ)
        qdev.start()

        JBApiQueue.QUEUES[api_name] = self
        self.log_debug("Created " + self.debug_str())

    def debug_str(self):
        return "Queue %s (%s, %s). outstanding: %g, %g" % (self.api_name, self.get_endpoint_in(), self.get_endpoint_out(), self.num_outstanding, self.mean_outstanding)

    def get_endpoint_in(self):
        return self.endpoints[0]

    def get_endpoint_out(self):
        return self.endpoints[1]

    def get_timeout(self):
        return self.timeout

    def get_command(self):
        return self.cmd

    def get_image_name(self):
        return self.image_name

    @staticmethod
    def get_queue(api_name, alloc=True):
        if api_name in JBApiQueue.QUEUES:
            return JBApiQueue.QUEUES[api_name]
        elif alloc:
            return JBApiQueue(api_name)
        return None

    @staticmethod
    def allocate_random_endpoints():
        ctx = zmq.Context.instance()
        binder = ctx.socket(zmq.REQ)
        bind_pfx = "tcp://" + CloudHelper.instance_private_ip()
        port_in = binder.bind_to_random_port(bind_pfx)
        port_out = binder.bind_to_random_port(bind_pfx)
        binder.close()
        time.sleep(0.25)

        endpoint_in = bind_pfx + str(':') + str(port_in)
        endpoint_out = bind_pfx + str(':') + str(port_out)

        return endpoint_in, endpoint_out

    def incr_outstanding(self, num):
        self.num_outstanding += num
        self.mean_outstanding = (1.0 * self.mean_outstanding + self.num_outstanding) / 2


class JBAsyncApi(LoggerMixin):
    ASYNC_APIS = {}
    DEFAULT_TIMEOUT = timedelta(seconds=30)
    MAX_CONNS = 2
    CMD_TERMINATE = ":terminate"

    def __init__(self, api_name):
        self.queue = JBApiQueue.get_queue(api_name)
        ctx = zmq.Context.instance()
        self.api_name = api_name
        self.sock = ctx.socket(zmq.REQ)
        self.sock.connect(self.queue.get_endpoint_in())
        self.has_errors = False
        self.timeout_callback = None
        self.timeout = self.queue.get_timeout()
        if self.timeout is None:
            self.timeout = JBAsyncApi.DEFAULT_TIMEOUT

        if api_name in JBAsyncApi.ASYNC_APIS:
            JBAsyncApi.ASYNC_APIS[api_name].append(self)
        else:
            JBAsyncApi.ASYNC_APIS[api_name] = [self]

        self.log_debug("Created " + self.debug_str())

    def debug_str(self):
        return "AsyncApi %s. dflt timeout:%s" % (self.api_name, str(self.timeout))

    @staticmethod
    def _get_async_api(api_name):
        if not ((api_name in JBAsyncApi.ASYNC_APIS) and (len(JBAsyncApi.ASYNC_APIS[api_name]) > 0)):
            JBAsyncApi(api_name)
        return JBAsyncApi.ASYNC_APIS[api_name].pop()

    def _release(self):
        self.queue.incr_outstanding(-1)
        cache = JBAsyncApi.ASYNC_APIS[self.api_name]
        if not self.has_errors and (len(cache) < JBAsyncApi.MAX_CONNS):
            cache.append(self)

    def _send_recv(self, send_data, on_recv, on_timeout, timeout=None):
        stream = zmqstream.ZMQStream(self.sock)
        loop = ioloop.IOLoop.instance()
        if timeout is None:
            timeout = self.timeout

        def _on_timeout():
            JBAsyncApi.log_debug("timed out : " + self.debug_str())
            self.has_errors = True
            self.timeout_callback = None
            stream.stop_on_recv()
            stream.close()
            self._release()
            if on_timeout is not None:
                on_timeout()

        def _on_recv(msg):
            JBAsyncApi.log_debug("message received : " + self.debug_str())
            if self.timeout_callback is not None:
                loop.remove_timeout(self.timeout_callback)
                self.timeout_callback = None
            stream.stop_on_recv()
            self._release()
            if on_recv is not None:
                on_recv(msg)

        self.log_debug(self.debug_str() + ". making call with timeout: " + str(timeout))
        self.timeout_callback = loop.add_timeout(timeout, _on_timeout)
        stream.on_recv(_on_recv)
        self.queue.incr_outstanding(1)
        self.sock.send(send_data)

    @staticmethod
    def send_recv(api_name, cmd, args=None, vargs=None, on_recv=None, on_timeout=None, timeout=None):
        send_data = JBAsyncApi.make_req(cmd, args=args, vargs=vargs)
        api = JBAsyncApi._get_async_api(api_name)
        api.log_debug(api.debug_str() + ". calling " + cmd)
        api._send_recv(send_data, on_recv, on_timeout, timeout)

    @staticmethod
    def send_terminate_msg(api_name):
        JBAsyncApi.send_recv(api_name, JBAsyncApi.CMD_TERMINATE)

    @staticmethod
    def make_req(cmd, args=None, vargs=None):
        req = {'cmd': cmd}
        if (args is not None) and (len(args) > 0):
            req['args'] = args
        if (vargs is not None) and (len(vargs) > 0):
            req['vargs'] = vargs

        return json.dumps(req)


class JBApiContainer(LoggerMixin):
    # keep shellinabox for troubleshooting
    CONTAINER_PORT_BINDINGS = {4200: ('127.0.0.1',)}
    HOST_VOLUMES = None
    DCKR = None
    DCKR_IMAGE_PFX = None
    MEM_LIMIT = None

    # By default all groups have 1024 shares.
    # A group with 100 shares will get a ~10% portion of the CPU time (https://wiki.archlinux.org/index.php/Cgroups)
    CPU_LIMIT = 1024
    PORTS = [4200]
    LOCAL_TZ_OFFSET = 0
    MAX_CONTAINERS = 0
    INITIAL_DISK_USED_PCT = None
    LAST_CPU_PCT = None

    API_CONTAINERS = {}
    DESIRED_CONTAINER_COUNTS = {}

    def __init__(self, dockid):
        self.dockid = dockid
        self.props = None
        self.dbgstr = None
        self.host_ports = None

    def refresh(self):
        self.props = None
        self.dbgstr = None

    def get_props(self):
        if self.props is None:
            self.props = JBApiContainer.DCKR.inspect_container(self.dockid)
        return self.props

    def get_cpu_allocated(self):
        props = self.get_props()
        cpu_shares = props['Config']['CpuShares']
        num_cpus = multiprocessing.cpu_count()
        return max(1, int(num_cpus * cpu_shares / 1024))

    def get_memory_allocated(self):
        props = self.get_props()
        mem = props['Config']['Memory']
        if mem > 0:
            return mem
        return psutil.virtual_memory().total

    def debug_str(self):
        if self.dbgstr is None:
            self.dbgstr = "JBApiContainer id=" + str(self.dockid) + ", name=" + str(self.get_name())
        return self.dbgstr

    def get_name(self):
        props = self.get_props()
        return props['Name'] if ('Name' in props) else None

    def get_api_name(self):
        if self.get_name() is None:
            return None
        parts = self.get_name().split('_')
        if len(parts) != 3:
            return None
        return parts[1]

    def get_image_names(self):
        props = self.get_props()
        img_id = props['Image']
        for img in JBApiContainer.DCKR.images():
            if img['Id'] == img_id:
                return img['RepoTags']
        return []

    @staticmethod
    def configure(dckr, image_pfx, mem_limit, cpu_limit, max_containers):
        JBApiContainer.DCKR = dckr
        JBApiContainer.DCKR_IMAGE_PFX = image_pfx
        JBApiContainer.MEM_LIMIT = mem_limit
        JBApiContainer.CPU_LIMIT = cpu_limit
        JBApiContainer.LOCAL_TZ_OFFSET = JBApiContainer.local_time_offset()
        JBApiContainer.MAX_CONTAINERS = max_containers

    @staticmethod
    def get_image_name(api_name):
        return JBApiContainer.DCKR_IMAGE_PFX + '_' + api_name

    @staticmethod
    def ensure_container_available(api_name):
        if (api_name in JBApiContainer.API_CONTAINERS) and (len(JBApiContainer.API_CONTAINERS[api_name]) > 0):
            JBApiContainer.log_debug("container already up for " + api_name + ". count: " + repr(len(JBApiContainer.API_CONTAINERS[api_name])))
            return
        JBApiContainer.create_new(api_name)

    @staticmethod
    def create_new(api_name):
        container_name = unique_container_name(api_name)
        queue = JBApiQueue.get_queue(api_name)
        env = {
            "JBAPI_NAME": api_name,
            "JBAPI_QUEUE": queue.get_endpoint_out(),
            "JBAPI_CMD": queue.get_command()
        }
        image_name = queue.get_image_name()
        if image_name is None:
            image_name = JBApiContainer.get_image_name(api_name)
        jsonobj = JBApiContainer.DCKR.create_container(image_name,
                                                       detach=True,
                                                       mem_limit=JBApiContainer.MEM_LIMIT,
                                                       cpu_shares=JBApiContainer.CPU_LIMIT,
                                                       ports=JBApiContainer.PORTS,
                                                       environment=env,
                                                       hostname='juliabox',
                                                       name=container_name)
        dockid = jsonobj["Id"]
        cont = JBApiContainer(dockid)
        JBApiContainer.log_info("Created " + cont.debug_str())
        cont.start(api_name)
        JBApiContainer.publish_container_stats()
        return cont

    @staticmethod
    def publish_container_stats():
        """ Publish custom cloudwatch statistics. Used for status monitoring and auto scaling. """
        nactive = JBApiContainer.num_active()
        CloudHelper.publish_stats("NumActiveContainers", "Count", nactive)

        curr_cpu_used_pct = psutil.cpu_percent()
        last_cpu_used_pct = curr_cpu_used_pct if JBApiContainer.LAST_CPU_PCT is None else JBApiContainer.LAST_CPU_PCT
        JBApiContainer.LAST_CPU_PCT = curr_cpu_used_pct
        cpu_used_pct = int((curr_cpu_used_pct + last_cpu_used_pct)/2)

        mem_used_pct = psutil.virtual_memory().percent
        CloudHelper.publish_stats("MemUsed", "Percent", mem_used_pct)

        disk_used_pct = 0
        for x in psutil.disk_partitions():
            try:
                disk_used_pct = max(psutil.disk_usage(x.mountpoint).percent, disk_used_pct)
            except:
                pass
        if JBApiContainer.INITIAL_DISK_USED_PCT is None:
            JBApiContainer.INITIAL_DISK_USED_PCT = disk_used_pct
        disk_used_pct = max(0, (disk_used_pct - JBApiContainer.INITIAL_DISK_USED_PCT))
        CloudHelper.publish_stats("DiskUsed", "Percent", disk_used_pct)

        cont_load_pct = min(100, max(0, nactive * 100 / JBApiContainer.MAX_CONTAINERS))
        CloudHelper.publish_stats("ContainersUsed", "Percent", cont_load_pct)

        overall_load_pct = max(cont_load_pct, disk_used_pct, mem_used_pct, cpu_used_pct)
        CloudHelper.publish_stats("Load", "Percent", overall_load_pct)

    @staticmethod
    def calc_desired_container_counts():
        for api_name in JBApiContainer.API_CONTAINERS:
            queue = JBApiQueue.get_queue(api_name, alloc=False)
            if queue is None:
                JBApiContainer.DESIRED_CONTAINER_COUNTS[api_name] = 0
                continue

            desired = JBApiContainer.DESIRED_CONTAINER_COUNTS[api_name]
            JBApiContainer.log_debug("calculating desired capacity with " + queue.debug_str() + ". current desired: " + str(desired))
            if queue.mean_outstanding > 1:
                incr = int(queue.mean_outstanding)
                desired += incr
            elif queue.mean_outstanding < 0.01:  # approx 5 polls where 0 q length was found
                desired = 0
            elif queue.mean_outstanding < 0.5:  # nothing is queued when eman is 1/3
                if desired > 1:
                    desired -= 1
            JBApiContainer.DESIRED_CONTAINER_COUNTS[api_name] = desired
            JBApiContainer.log_debug("calculating desired capacity with " + queue.debug_str() + ". final desired: " + str(desired))

            if queue.num_outstanding == 0:
                queue.incr_outstanding(0)   # recalculate mean if no requests are coming

    @staticmethod
    def refresh_container_list():
        JBApiContainer.API_CONTAINERS = {}

        for c in JBApiContainer.DCKR.containers(all=True):
            cont = JBApiContainer(c['Id'])
            if not (cont.is_running() or cont.is_restarting()):
                cont.delete()
                continue

            api_name = cont.get_api_name()
            if api_name is None:
                continue

            JBApiContainer.register_api_container(api_name, cont.dockid)

    @staticmethod
    def maintain():
        """
        For each API type, maintain a desired capacity calculated based on number of outstanding requests.
        """
        JBApiContainer.log_info("Starting container maintenance...")
        JBApiContainer.refresh_container_list()
        JBApiContainer.publish_container_stats()
        JBApiContainer.calc_desired_container_counts()

        for (api_name, clist) in JBApiContainer.API_CONTAINERS.iteritems():
            ndiff = len(clist) - JBApiContainer.DESIRED_CONTAINER_COUNTS[api_name]

            # terminate if in excess
            # TODO: this does not handle non-responsive containers yet
            while ndiff > 0:
                JBAsyncApi.send_terminate_msg(api_name)
                ndiff -= 1

            # launch if more required
            while ndiff < 0:
                JBApiContainer.create_new(api_name)
                ndiff += 1

        JBApiContainer.log_info("Finished container maintenance.")

    @staticmethod
    def num_active():
        active_containers = JBApiContainer.DCKR.containers(all=False)
        return len(active_containers)

    @staticmethod
    def num_stopped():
        all_containers = JBApiContainer.DCKR.containers(all=True)
        return len(all_containers) - JBApiContainer.num_active()

    @staticmethod
    def get_by_name(name):
        nname = "/" + unicode(name)

        for c in JBApiContainer.DCKR.containers(all=True):
            if ('Names' in c) and (c['Names'] is not None) and (c['Names'][0] == nname):
                return JBApiContainer(c['Id'])
        return None

    @staticmethod
    def get_by_api(api_name):
        nname = continer_name_prefix(api_name)

        api_containers = []
        for c in JBApiContainer.DCKR.containers(all=True):
            if ('Names' in c) and (c['Names'] is not None) and (c['Names'][0]).startswith(nname):
                api_containers.append(JBApiContainer(c['Id']))
        return api_containers

    @staticmethod
    def parse_iso_time(tm):
        if tm is not None:
            tm = isodate.parse_datetime(tm)
        return tm

    @staticmethod
    def local_time_offset():
        """Return offset of local zone from GMT"""
        if time.localtime().tm_isdst and time.daylight:
            return time.altzone
        else:
            return time.timezone

    def is_running(self):
        props = self.get_props()
        state = props['State']
        return state['Running'] if 'Running' in state else False

    def is_restarting(self):
        props = self.get_props()
        state = props['State']
        return state['Restarting'] if 'Restarting' in state else False

    def time_started(self):
        props = self.get_props()
        return JBApiContainer.parse_iso_time(props['State']['StartedAt'])

    def time_finished(self):
        props = self.get_props()
        return JBApiContainer.parse_iso_time(props['State']['FinishedAt'])

    def time_created(self):
        props = self.get_props()
        return JBApiContainer.parse_iso_time(props['Created'])

    def stop(self):
        JBApiContainer.log_info("Stopping " + self.debug_str())
        self.refresh()
        if self.is_running():
            JBApiContainer.DCKR.stop(self.dockid, timeout=5)
            self.refresh()
            JBApiContainer.log_info("Stopped " + self.debug_str())
        else:
            JBApiContainer.log_info("Already stopped or restarting" + self.debug_str())

    @staticmethod
    def register_api_container(api_name, container_id):
        clist = JBApiContainer.API_CONTAINERS[api_name] if api_name in JBApiContainer.API_CONTAINERS else []
        clist.append(container_id)
        JBApiContainer.API_CONTAINERS[api_name] = clist
        if api_name not in JBApiContainer.DESIRED_CONTAINER_COUNTS:
            JBApiContainer.DESIRED_CONTAINER_COUNTS[api_name] = 1
        JBApiContainer.log_info("Registered " + container_id)

    @staticmethod
    def deregister_api_container(api_name, container_id):
        clist = JBApiContainer.API_CONTAINERS[api_name] if api_name in JBApiContainer.API_CONTAINERS else []
        if container_id in clist:
            clist.remove(container_id)
        JBApiContainer.API_CONTAINERS[api_name] = clist
        JBApiContainer.log_info("Deregistered " + container_id)

    def start(self, api_name):
        self.refresh()
        JBApiContainer.log_info("Starting " + self.debug_str())
        if self.is_running() or self.is_restarting():
            JBApiContainer.log_info("Already started " + self.debug_str())
            return

        JBApiContainer.DCKR.start(self.dockid, port_bindings=JBApiContainer.CONTAINER_PORT_BINDINGS)
        self.refresh()
        JBApiContainer.log_info("Started " + self.debug_str())
        JBApiContainer.register_api_container(api_name, self.get_name())

    def restart(self):
        self.refresh()
        JBApiContainer.log_info("Restarting " + self.debug_str())
        JBApiContainer.DCKR.restart(self.dockid, timeout=5)
        self.refresh()
        JBApiContainer.log_info("Restarted " + self.debug_str())

    def kill(self):
        JBApiContainer.log_info("Killing " + self.debug_str())
        JBApiContainer.DCKR.kill(self.dockid)
        self.refresh()
        JBApiContainer.log_info("Killed " + self.debug_str())

    def delete(self):
        JBApiContainer.log_info("Deleting " + self.debug_str())
        self.refresh()
        if self.is_running() or self.is_restarting():
            self.kill()

        JBApiContainer.DCKR.remove_container(self.dockid)
        JBApiContainer.log_info("Deleted " + self.debug_str())
        JBApiContainer.deregister_api_container(self.get_api_name(), self.get_name())
