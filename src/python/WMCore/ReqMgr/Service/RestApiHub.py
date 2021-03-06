"""
Module defines REST API methods and their handles.
Implementation of handles is in corresponding modules, not here.

"""
from __future__ import print_function, division

import cherrypy

from WMCore.Configuration import Configuration
from WMCore.REST.Server import RESTApi

from WMCore.ReqMgr.ReqMgrCouch import ReqMgrCouch
from WMCore.ReqMgr.Service.Auxiliary import Info, \
        ReqMgrConfigData, Software
from WMCore.ReqMgr.Service.RequestAdditionalInfo import RequestSpec, \
        WorkloadConfig, WorkloadSplitting
from WMCore.ReqMgr.Service.Request import Request, RequestStatus, RequestType
from WMCore.ReqMgr.Service.WMStatsInfo import WMStatsInfo



class RestApiHub(RESTApi):
    """
    Server object for REST data access API.
    
    """
    def __init__(self, app, config, mount):
        """
        :arg app: reference to application object; passed to all entities.
        :arg config: reference to configuration; passed to all entities.
        :arg str mount: API URL mount point; passed to all entities."""
        
        RESTApi.__init__(self, app, config, mount)
        
        cherrypy.log("ReqMgr entire configuration:\n%s" % Configuration.getInstance())    
        cherrypy.log("ReqMgr REST hub configuration subset:\n%s" % config)
        
        self.db_handler = ReqMgrCouch(config) 
        # Makes raw format as default
        #self.formats.insert(0, ('application/raw', RawFormat()))
        self._add({"about": Info(app, self, config, mount),
                   "info": Info(app, self, config, mount),
                   "app_config": ReqMgrConfigData(app, self, config, mount),
                   "request": Request(app, self, config, mount),
                   "software": Software(app, self, config, mount),
                   "status": RequestStatus(app, self, config, mount),
                   "type": RequestType(app, self, config, mount),
                   "spec_template": RequestSpec(self, app, config, mount),
                   "workload_config": WorkloadConfig(self, app, config, mount),
                   "splitting": WorkloadSplitting(self, app, config, mount),
                   "wmstats_info": WMStatsInfo(self, app, config, mount)
                  })