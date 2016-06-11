import os
import json
import requests
import logging
from functools import wraps
from werkzeug.wrappers import Request, Response
from werkzeug.serving import run_simple
from jsonrpc import JSONRPCResponseManager, dispatcher
from voidpp_tools.daemon import Daemon

logger = logging.getLogger(__name__)

def rpc(method):
    """
    Decorator function for register method for RPC.
    Must be used a RemoteControllerDeamon (-derived) class method!
    """
    @wraps(method)
    def rpc_wrapper(*args, **kwargs):
        controller_instance = args[0]

        if not isinstance(controller_instance, RemoteControllerDeamon):
            raise Exception("'rpc' decorator must use in a RemoteControllerDeamon (-derived) class method!")

        # Decide the call origin: if the current pid is the daemon pid, this is server side,
        # so call registered method. If not, start a jsonrpc request.
        call_from_server = os.getpid() == controller_instance.get_pid()

        logger.debug("Initiate RPC method '%s' in '%s'", method.__name__, 'daemon' if call_from_server else 'cli')

        if call_from_server:
            return method(*args, **kwargs)
        else:
            url = "http://{}:{}/jsonrpc".format(controller_instance.host, controller_instance.port)
            headers = {'content-type': 'application/json'}

            payload = {
                "method": method.__name__,
                "params": kwargs,
                "jsonrpc": "2.0",
                "id": 0,
            }
            try:
                response = requests.post(url, data=json.dumps(payload), headers=headers).json()
                if 'result' in response:
                    return response['result']
                else:
                    logger.error("There is an error during rpc call. Response:\n%s", json.dumps(response, indent=4))
                    return "Error: {}. (see logs for details)".format(response['error']['message'])
            except requests.exceptions.ConnectionError as e:
                logger.error("Command server not runnning (%s), args: %s, kwargs: %s", e, args, kwargs)
                return None

    rpc_wrapper.registered_for_rpc = method
    return rpc_wrapper

class RemoteControllerDeamon(Daemon):
    """
    Example: (handler.py)

        class Handler(RemoteControllerDeamon):

            def __init__(self, pid, logger):
                super(Handler, self).__init__(pid, logger)

            @rpc
            def reload(self, param1):
                return 'reload: {}'.format(param1)

        handler = Handler('/tmp/handler.pid', logging)

        # add argument parser, etc

    Workflow:
        $ python handler.py start
        >>> handler.start()                             # (pid:100) create daemon process with pid = 42
        $ python handler.py reload p1value
        >>> print(handler.reload(param1 = 'p1value'))   # (pid:101) will not call the Handler.reload function instead of this:
        >>> requests.post(jsonrpcdata)                  # (pid:101) pid is not the daemon pid, perform a jsonrpc request (def rpc_wrapper)
        >>> JSONRPCResponseManager.handle(jsonrpcdata)  # (pid:42) handle jsonrpc request
        >>> handler.reload(param1 = 'p1value')          # (pid:42) create a jsonrpc response
        >>> return response['result']                   # (pid:101) handle jsonrpc respone, prints the response content
        reload: p1value
    """

    def __init__(self, pidfile, logger, port = 64042, host = 'localhost'):
        """Create a daemon which is controllable via jsonrpc with decorator

        Args:
            pidfile (str): path to create pid file
            logger (logging.Logger): logger for the daemon
            port (int):
            host (str):
        """
        super(RemoteControllerDeamon, self).__init__(pidfile, logger)
        self.__port = port
        self.__host = host
        for name in dir(self):
            method = getattr(self, name)
            if hasattr(method, 'registered_for_rpc'):
                self.register_method(method, method.registered_for_rpc.__name__)

    @property
    def port(self):
        return self.__port

    @property
    def host(self):
        return self.__host

    @Request.application
    def command_handler(self, request):
        response = JSONRPCResponseManager.handle(request.data, dispatcher)
        return Response(response.json, mimetype = 'application/json')

    def register_method(self, method, name = None):
        dispatcher[name if name else method.__name__] = method

    def run(self):
        run_simple(self.__host, self.__port, self.command_handler)
