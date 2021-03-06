from WMCore.Wrappers import JsonWrapper
from WMCore.Services.Service import Service

class ReqMgr(Service):

    """
    API for dealing with retrieving information from RequestManager dataservice

    """

    def __init__(self, url, header = {}):
        """
        responseType will be either xml or json
        """

        httpDict = {}
        # url is end point
        httpDict['endpoint'] = "%s/data" % url

        # cherrypy converts request.body to params when content type is set
        # application/x-www-form-urlencodeds
        httpDict.setdefault("content_type", 'application/json')
        httpDict.setdefault('cacheduration', 0)
        httpDict.setdefault("accept_type", "application/json")
        httpDict.update(header)
        self.encoder = JsonWrapper.dumps
        Service.__init__(self, httpDict)
        # This is only for the unittest: never set it true unless it is unittest
        self._noStale = False

        
    def _getResult(self, callname, clearCache = True,
                   args = None, verb = "GET", encoder = JsonWrapper.loads, 
                   decoder = JsonWrapper.loads,
                   contentType = None):
        """
        _getResult_
        
        """
        result = ''
        file = callname.replace("/", "_")
        if clearCache:
            self.clearCache(file, args, verb)

        f = self.refreshCache(file, callname, args, encoder = encoder,
                              verb = verb, contentType = contentType)
        result = f.read()
        f.close()

        if result and decoder:
            result = decoder(result)
            
        data = result['result']    
        if len(data) == 0:
            return {}
        elif len(data) == 1:
            return data[0]
        else:
            return data
    
    def _createQuery(self, queryDict):
        """
        _createQuery
        :param queryDict: is the format of {name: values} fair. value can be sting, int or list
        :type queryDict: dict
        :returns: url query string
        
        """
        if self._noStale:
            args = "_nostale=true&"
        else:
            args = ""
        for name, values in queryDict.items():
            if isinstance(values, basestring) or isinstance(values, int):
                values = [values]
            for val in values:
                args +='%s=%s&' % (name, val)
        
        return args.rstrip('&')

    def getRequestByNames(self, names):

        """
        _getRequestByNames_
        
        :param names: list or sting of request name(s)
        :type statusList: list, str
        :returns:  list of dict or list of request names depending on the detail value
         -- [{'test_RequestString-OVERRIDE-ME_141125_142331_4966': {'BlockBlacklist': [],
                                                                    'BlockWhitelist': [],
                                                                    'CMSSWVersion': 'CMSSW_4_4_2_patch2',
                                                                    ....
                                                                    '_id': 'test_RequestString-OVERRIDE-ME_141125_142331_4966',
                                                                    'inputMode': 'couchDB'}}]
        TODO: need proper error handling if status is not 200 from orignal reporting.

        """
        
        query = self._createQuery({'name': names})
        callname = 'request?%s' % query
        return self._getResult(callname, verb = "GET")

    def getRequestByStatus(self, statusList):
        """
        _getRequestByStatus_
        
        :param statusList: list of status
        :type statusList: list
        :param detail: boolean of request list.
        :type detail: boolean
        :returns:  list of dict or list of request names depending on the detail value
         -- [{'test_RequestString-OVERRIDE-ME_141125_142331_4966': {'BlockBlacklist': [],
                                                                    'BlockWhitelist': [],
                                                                    'CMSSWVersion': 'CMSSW_4_4_2_patch2',
                                                                    ....
                                                                    '_id': 'test_RequestString-OVERRIDE-ME_141125_142331_4966',
                                                                    'inputMode': 'couchDB'}}]
        TODO: need proper error handling if status is not 200 from orignal reporting.
        """
        
        query = self._createQuery({'status': statusList})
        callname = 'request?%s' % query
        return  self._getResult(callname, verb = "GET")
        
    def getRequestTasks(self, name):

        """
        _getRequestTasks_
        
        :param name: request name
        :type string: str
        :returns:  list of dict or list of request names depending on the detail value
         -- {result:[{requestTask}, {requestTask}]}
        """
        
        callname = 'splitting/%s' % name
        return self._getResult(callname, verb = "GET")

    def getConfig(self, name):

        """
        _getConfig_
        
        :param name: request name
        :type string: str
        :returns:  list of dict or list of request names depending on the detail value
         -- {result:[config_string]}
        """
        
        callname = 'workload_config/%s' % name
        return self._getResult(callname, verb = "GET")

    def insertRequests(self, requestDict):
        """
        _insertRequests_
        
        :param requestDict: request argument dictionary
        :type requestDict: dict
        :returns:  list of dictionary -- [{'test_RequestString-OVERRIDE-ME_141125_142331_4966': {'BlockBlacklist': [],
                                                                    'BlockWhitelist': [],
                                                                    'CMSSWVersion': 'CMSSW_4_4_2_patch2',
                                                                    ....
                                                                    '_id': 'test_RequestString-OVERRIDE-ME_141125_142331_4966',
                                                                    'inputMode': 'couchDB'}}]
        TODO: need proper error handling if status is not 200 from orignal reporting.
        """
        return self["requests"].post('request', requestDict)[0]['result']

    def updateRequestStatus(self, request, status):
        """
        _updateRequestStatus_
        
        :param request: request(workflow name)
        :type reqeust: str
        :param status: status of workflow to update (i.e. 'assigned')
        :type status: str
        :returns:  list of dictionary -- [{'test_RequestString-OVERRIDE-ME_141125_142331_4966': {'BlockBlacklist': [],
                                                                    'BlockWhitelist': [],
                                                                    'CMSSWVersion': 'CMSSW_4_4_2_patch2',
                                                                    ....
                                                                    '_id': 'test_RequestString-OVERRIDE-ME_141125_142331_4966',
                                                                    'inputMode': 'couchDB'}}]
        TODO: need proper error handling if status is not 200 from orignal reporting.
        """
        
        status = {"RequestStatus": status}
        status["RequestName"] = request
        return self["requests"].put('request', status)[0]['result']
    
    def updateRequestStats(self, request, stats):
        """
        put initial stats for request
        param: stats: dict of {'total_jobs': 100, 'input_lumis': 100,
                               'input_events': 100, 'input_num_files': 100}
        specific to ReqMgr app. not implemented for T0
        """
        #TODO: add stats validation here
        
        self.updateRequestProperty(request, stats)

    def updateRequestProperty(self, request, propDict):
        """
        _updateRequestProperty_
        :param request: request(workflow name)
        :type reqeust: str
        :param propDict: request property with key value -- {"SiteWhitelist": ["ABC"], "SiteBlacklist": ["A"], "RequestStatus": "assigned"}
        :type propDict: dict
        :returns:  list of dictionary -- [{'test_RequestString-OVERRIDE-ME_141125_142331_4966': {'BlockBlacklist': [],
                                                                    'BlockWhitelist': [],
                                                                    'CMSSWVersion': 'CMSSW_4_4_2_patch2',
                                                                    ....
                                                                    '_id': 'test_RequestString-OVERRIDE-ME_141125_142331_4966',
                                                                    'inputMode': 'couchDB'}}]                                                 
        """
        propDict["RequestName"] = request
        return self["requests"].put('request/%s' % request, propDict)[0]['result']
    
        
