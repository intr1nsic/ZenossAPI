import json
import urllib
import urllib2
from collections import defaultdict

ROUTERS = {
    'MessagingRouter': 'messaging',
    'EventsRouter': 'evconsole',
    'ProcessRouter': 'process',
    'ServiceRouter': 'service',
    'DeviceRouter': 'device',
    'NetworkRouter': 'network',
    'TemplateRouter': 'template',
    'DetailNavRouter': 'detailnav',
    'ReportRouter': 'report',
    'MibRouter': 'mib',
    'ZenPackRouter': 'zenpack'
}

ALERT_MAPPINGS = {
    1: 'Debug',
    2: 'Info',
    3: 'Warning',
    4: 'Error',
    5: 'Critical',
}

class ZenossAPI(object):

    def __init__(self, host=None, username=None, password=None, port='8080', debug=False, *args, **kwargs):
        """
        Initialize the API connection, log in, and store authentication cookie
        """

        self.username = username
        self.password = password
        self.port = port
        self.host = host + ":" + self.port

        # Use the HTTPCookieProcessor as urllib2 does not save cookies by default
        self.urlOpener = urllib2.build_opener(urllib2.HTTPCookieProcessor())
        if debug: self.urlOpener.add_handler(urllib2.HTTPHandler(debuglevel=1))
        self.reqCount = 1

        # Contruct POST params and submit login.
        loginParams = urllib.urlencode(dict(
                        __ac_name = self.username,
                        __ac_password = self.password,
                        submitted = 'true',
                        came_from = self.host + '/zport/dmd'))
        self.urlOpener.open(self.host + '/zport/acl_users/cookieAuthHelper/login',
                            loginParams)

    def _router_request(self, router, method, data=[]):

        if router not in ROUTERS:
            raise Exception('Router "' + router + '" not available.')

        # Contruct a standard URL request for API calls
        req = urllib2.Request(self.host + '/zport/dmd/' +
                              ROUTERS[router] + '_router')

        # NOTE: Content-type MUST be set to 'application/json' for these requests
        req.add_header('Content-type', 'application/json; charset=utf-8')

        # Convert the request parameters into JSON
        reqData = json.dumps([dict(
                    action=router,
                    method=method,
                    data=data,
                    type='rpc',
                    tid=self.reqCount)])

        # Increment the request count ('tid'). More important if sending multiple
        # calls in a single request
        self.reqCount += 1

        # Submit the request and convert the returned JSON to objects
        return json.loads(self.urlOpener.open(req, reqData).read())

    def _raw_request(self, url):

        if not url:
            raise Exception('URL must be specified')

        self.reqCount += 1
        req = urllib2.Request(self.host + url)
        return self.urlOpener.open(req).read()

    def get_devices(self, deviceClass='/zport/dmd/Devices', params={}, start=0, limit=100, sort='name'):

        return self._router_request('DeviceRouter', 'getDevices',
                                    data=[{'uid': deviceClass,
                                           'sort': sort,
                                           'params': params,
                                           'start': start,
                                           'limit': limit, }])['result']

    def get_events(self, limit=100, start=0, device=None, component=None, eventClass=None):

        data = dict(start=0, limit=100, dir='DESC', sort='severity',
                                                                uid='/zport/dmd')
        data['params'] = dict(severity=[5,4,3,2], eventState=[0,1])
        data['limit'] = limit
        data['start'] = start
        # Added for bug ZEN-2812
        data['keys'] = [
                        "eventState",
                        "severity",
                        "device",
                        "component",
                        "eventClass",
                        "summary",
                        "firstTime",
                        "lastTime",
                        "count",
                        "evid",
                        "eventClassKey",
                        "message",
                ]

        if device: data['params']['device'] = device
        if component: data['params']['component'] = component
        if eventClass: data['params']['eventClass'] = eventClass

        return self._router_request('EventsRouter', 'query', [data])['result']

    def remove_device(self, uid=None, action='delete', deleteEvents=True, deletePerf=True):
        """
        Remove a device from zenoss
        """

        if uid is None:
            raise Exception('UID must be set')

        data = dict(
                    uids = [uid],
                    hashcheck = 1,
                    action = action,
                    deleteEvents = deleteEvents,
                    deletePerf = deletePerf,
        )

        return self._router_request('DeviceRouter', 'removeDevices', [data])

    def set_state(self, uid=None, state=None):
        """
        Set the device to said production state
        """

        if uid is None:
            raise Exception("UID must be set")

        if state is None and state is int:
            raise Exception("State must be set and must be an integer")

        data = dict(
                    uid = [uid],
                    productionState = state,
        )

        return self._router_request('DeviceRouter', 'setInfo', [data])

    def get_event_summary(self):

        # Grab all of our events
        events = self.get_events(limit=5000)

        evt_summary = defaultdict(int)

        # Map our values and
        for evt in events['events']:
            evt_summary[ALERT_MAPPINGS[int(evt['severity'])]] += 1

        return dict(evt_summary)

    def add_device(self, deviceName, deviceClass, productionState=1000, model=True):

        data = dict(
                    deviceName=deviceName,
                    deviceClass=deviceClass,
                    model=model,
                    productionState=productionState)

        return self._router_request('DeviceRouter', 'addDevice', [data])

    def getGraphDefs(self, uid):

        data = dict(uid=uid)
        return self._router_request('DeviceRouter', 'getGraphDefs', [data])

    def getGraph(self, url):

        return self._raw_request(url)

    def create_event_on_device(self, device, severity, summary):

        if severity not in ('Critical', 'Error', 'Warning', 'Info', 'Debug', 'Clear'):
            raise Exception('Severity "' + severity +'" is not valid.')

        data = dict(device=device, summary=summary, severity=severity,
                    component='', evclasskey='', evclass='')
        return self._router_request('EventsRouter', 'add_event', [data])


