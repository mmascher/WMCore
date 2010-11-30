import urllib
import logging
import os
import pwd
from urllib import urlencode

from WMCore.Wrappers import JsonWrapper
from WMCore.Services.Service import Service

try:
    # Python 2.6
    import json
except ImportError:
    # Prior to 2.6 requires simplejson
    import simplejson as json

from WMQuality.Emulators.EmulatorSetup import emulatorHook 

# emulator hook is used to swap the class instance 
# when emulator values are set. 
# Look WMQuality.Emulators.EmulatorSetup module for the values
@emulatorHook
class RequestManager(Service):

    """
    API for dealing with retrieving information from RequestManager dataservice   
    
    """

    def __init__(self, dict = {}, secure = False):
        """
        responseType will be either xml or json
        """

        if not dict.has_key('endpoint'):
            #TODO needs to change proper default location
            dict['endpoint'] = "%scmssrv49.fnal.gov:8585/reqMgr/" % \
                                ((secure and "https://" or "http://"))

        dict['accept_type'] = 'text/json'
        dict.setdefault('cacheduration', 0)

        Service.__init__(self, dict)

    def _getResult(self, callname, clearCache = True,
                   args = None, verb = "GET", encoder = None,
                   contentType = None):
        """
        _getResult_

        retrieve JSON/XML formatted information given the service name and the
        argument dictionaries

        TODO: Probably want to move this up into Service
        """
        result = ''
        file = callname.replace("/", "_")
        if clearCache:
            self.clearCache(file, args, verb)

        f = self.refreshCache(file, callname, args, encoder = encoder, 
                              verb = verb, contentType = contentType)
        result = f.read()
        f.close()

#        if self.responseType == "json":
#            decoder = json.JSONDecoder()
#            return decoder.decode(result)

        if result:
            result = JsonWrapper.loads(result)
        return result

    def getRequest(self, requestName = None):

        """
        _getRequest_

        """
        args = {}
        args['requestName'] = requestName

        callname = 'request'
        return self._getResult(callname, args = args, verb = "GET")

    def getAssignment(self, teamName = None, request = None):

        args = {}
        # server only take teamname if both are specified.
        if teamName:
            args['teamName'] = teamName
        elif request:
            args['request'] = request

        callname = 'assignment'
        return self._getResult(callname, args = args, verb = "GET")

    def putWorkQueue(self, requestName, prodAgentUrl = None):
        args = {}

        callname = 'workQueue'
        args['request'] = requestName
        args['url'] = str(prodAgentUrl)
        return self._getResult(callname, args = args, verb = "PUT")

    def putTeam(self, team):
        args = {'team': team}
        callname = 'team'
        return self._getResult(callname, args = args, verb = "PUT")

    def reportRequestProgress(self, requestName, **kargs):
        """Update ReqMgr with request progress"""
        callname = 'request'
        args = {}
        args = {'requestName' : requestName}
        args.update(kargs)

        return self._getResult(callname, args = args, verb = "POST")

    def reportRequestStatus(self, requestName, status):
        """Update reqMgr about request"""
        callname = 'request' 
        args = {}
        args["requestName"] = requestName
        args["status"] = status
        return self._getResult(callname, args = args, verb = "PUT")

    def sendMessage(self, request, msg):
        """Attach a message to the request"""
        callname = "message/%s" %  request
        return self._getResult(callname, args = msg, verb = "PUT", 
                               encoder = JsonWrapper.dumps, 
                               contentType = 'application/json')
