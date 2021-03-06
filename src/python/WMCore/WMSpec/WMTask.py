#!/usr/bin/env python
"""
_WMTask_

Object containing a set of executable Steps which form a template for a
set of jobs.

Equivalent of a WorkflowSpec in the ProdSystem.
"""

import os.path
import time

import WMCore.WMSpec.Utilities as SpecUtils
import WMCore.WMSpec.Steps.StepFactory as StepFactory

from WMCore.Configuration import ConfigSection
from WMCore.Lexicon import lfnBase
from WMCore.WMSpec.ConfigSectionTree import ConfigSectionTree, TreeHelper
from WMCore.WMSpec.WMStep import WMStep, WMStepHelper
from WMCore.WMSpec.Steps.ExecuteMaster import ExecuteMaster
from WMCore.WMSpec.Steps.BuildMaster import BuildMaster
from WMCore.DataStructs.Workflow import Workflow as DataStructsWorkflow
from WMCore.DataStructs.LumiList import LumiList


def getTaskFromStep(stepRef):
    """
    _getTaskFromStep_

    Traverse up the step tree until finding the first WMTask entry,
    return it wrapped in a WMTaskHelper

    """
    nodeData = stepRef
    if isinstance(stepRef, WMStepHelper):
        nodeData = stepRef.data

    taskNode = SpecUtils.findTaskAboveNode(nodeData)
    if taskNode is None:
        msg = "Unable to find Task containing step\n"
        # TODO: Replace with real exception class
        raise RuntimeError(msg)

    return WMTaskHelper(taskNode)


def buildLumiMask(runs, lumis):
    """
    Runs are saved in the spec as a list of integers.
    The lumi mask associated to each run is saved as a list of strings
    where each string is in a format like '1,4,23,45'

    The method convert these parameters in the corresponding lumiMask,
    e.g.:  runs=['3','4'], lumis=['1,4,23,45', '5,84,234,445'] => lumiMask = {'3':[[1,4],[23,45]],'4':[[5,84],[234,445]]}
    """

    if len(runs) != len(lumis):
        raise ValueError("runs and lumis must have same length")
    for lumi in lumis:
        if len(lumi.split(',')) % 2:
            raise ValueError("Needs an even number of lumi in each element of lumis list")

    lumiLists = [map(list, list(zip([int(y) for y in x.split(',')][::2], [int(y) for y in x.split(',')][1::2]))) for x
                 in lumis]
    strRuns = [str(run) for run in runs]

    lumiMask = dict(list(zip(strRuns, lumiLists)))

    return lumiMask


class WMTaskHelper(TreeHelper):
    """
    _WMTaskHelper_

    Util wrapper containing tools & methods for manipulating the WMTask
    data object.
    """

    def __init__(self, wmTask):
        TreeHelper.__init__(self, wmTask)
        self.startTime = None
        self.endTime = None
        self.monitoring = None

    def addTask(self, taskName):
        """
        _addTask_

        Add a new task as a subtask with the name provided and
        return it wrapped in a TaskHelper

        """
        node = WMTaskHelper(WMTask(taskName))
        self.addNode(node)
        pName = "%s/%s" % (self.getPathName(), taskName)
        node.setPathName(pName)
        return node

    def taskIterator(self):
        """
        _taskIterator_

        return output of nodeIterator(self) wrapped in TaskHelper instance

        """
        for x in self.nodeIterator():
            yield WMTaskHelper(x)

    def childTaskIterator(self):
        """
        _childTaskIterator_

        Iterate over all the first generation child tasks.
        """
        for x in self.firstGenNodeChildIterator():
            yield WMTaskHelper(x)

    def setPathName(self, pathName):
        """
        _setPathName_

        Set the path name of the task within the workload
        Used internally when addin tasks to workloads or subtasks

        """
        self.data.pathName = pathName

    def getPathName(self):
        """
        _getPathName_

        get the path name of this task reflecting its
        structure within the workload and task tree

        """
        return self.data.pathName

    def name(self):
        """
        _name_

        Retrieve the name of this task.
        """
        return self.data._internal_name

    def listPathNames(self):
        """
        _listPathNames

        """
        for t in self.taskIterator():
            yield t.getPathName()

    def listNames(self):
        """
        _listPathNames

        """
        for t in self.taskIterator():
            yield t.name()

    def makeWorkflow(self):
        """
        _makeWorkflow_

        Create a WMBS compatible Workflow structure that represents this
        task and the information contained within it

        """
        workflow = DataStructsWorkflow()
        workflow.task = self.getPathName()
        return workflow

    def steps(self):
        """get WMStep structure"""
        if self.data.steps.topStepName is None:
            return None
        step = getattr(self.data.steps, self.data.steps.topStepName, None)
        return WMStepHelper(step)

    def getTopStepName(self):
        """
        _getTopStepName_

        Retrieve the name of the top step.
        """
        return self.data.steps.topStepName

    def setStep(self, wmStep):
        """set topStep to be the step instance provided"""
        stepData = wmStep
        if isinstance(wmStep, WMStepHelper):
            stepData = wmStep.data
            stepHelper = wmStep
        else:
            stepHelper = WMStepHelper(wmStep)

        stepName = stepHelper.name()
        stepHelper.setTopOfTree()
        setattr(self.data.steps, stepName, stepData)
        setattr(self.data.steps, "topStepName", stepName)
        return

    def listAllStepNames(self):
        """
        _listAllStepNames_

        Get a list of all the step names contained in this task.
        """
        step = self.steps()
        if step:
            return step.allNodeNames()
        else:
            return []

    def getStep(self, stepName):
        """get a particular step from the workflow"""
        if self.data.steps.topStepName is None:
            return None
        topStep = self.steps()
        return topStep.getStep(stepName)

    def makeStep(self, stepName):
        """
        _makeStep_

        create a new WMStep instance, install it as the top step and
        return the reference to the new step wrapped in a StepHelper

        """
        newStep = WMStep(stepName)
        self.setStep(newStep)
        return WMStepHelper(newStep)

    def applyTemplates(self):
        """
        _applyTemplates_

        For each step, load the appropriate template and install the default structure

        TODO: Exception handling

        """
        for step in self.steps().nodeIterator():
            stepType = step.stepType
            template = StepFactory.getStepTemplate(stepType)
            template(step)

    def getStepHelper(self, stepName):
        """
        _getStepHelper_

        Get the named step, look up its type specific helper and retrieve
        the step wrapped in the type based helper.

        """
        step = self.getStep(stepName)
        stepType = step.stepType()
        template = StepFactory.getStepTemplate(stepType)
        helper = template.helper(step.data)
        return helper

    def getOutputModulesForTask(self):
        """
        _getOutputModulesForTask_

        Retrieve all the output modules in the given task.
        """
        outputModules = []
        for stepName in self.listAllStepNames():
            outputModules.append(self.getOutputModulesForStep(stepName))
        return outputModules

    def getIgnoredOutputModulesForTask(self):
        """
        _getIgnoredOutputModulesForTask_

        Retrieve the ignored output modules in the given task.
        """
        ignoredOutputModules = []
        for stepName in self.listAllStepNames():
            stepHelper = self.getStepHelper(stepName)
            ignoredOutputModules.extend(stepHelper.getIgnoredOutputModules())
        return ignoredOutputModules

    def getOutputModulesForStep(self, stepName):
        """
        _getOutputModulesForStep_

        Retrieve all the output modules for the particular step.
        """
        step = self.getStep(stepName)

        if hasattr(step.data, "output"):
            if hasattr(step.data.output, "modules"):
                return step.data.output.modules

        return ConfigSection()

    def build(self, workingDir):
        """
        _build_

        Invoke the build process to create the job in the working dir provided

        """
        master = BuildMaster(workingDir)
        master(self)
        return

    def setupEnvironment(self):
        """
        _setupEnvironment_

        I don't know if this should go here.
        Setup the environment variables mandated in the WMTask
        """

        if not hasattr(self.data, 'environment'):
            # No environment to setup, pass
            return

        envDict = self.data.environment.dictionary_()

        for key in envDict.keys():
            if str(envDict[key].__class__) == "<class 'WMCore.Configuration.ConfigSection'>":
                # At this point we do not support the
                # setting of sub-sections for environment variables
                continue
            else:
                os.environ[key] = envDict[key]

        return

    def execute(self, wmbsJob):
        """
        _execute_

        Invoke execution of the steps

        """
        self.startTime = time.time()
        self.setupEnvironment()
        master = ExecuteMaster()
        master(self, wmbsJob)
        self.endTime = time.time()
        return

    def setInputReference(self, stepRef, **extras):
        """
        _setInputReference_

        Add details to the input reference for the task providing
        input to this task.
        The reference is the step in the input task, plus
        any extra information.


        """
        stepId = SpecUtils.stepIdentifier(stepRef)
        setattr(self.data.input, "inputStep", stepId)
        [setattr(self.data.input, key, val)
         for key, val in extras.items()]
        return

    def setInputStep(self, stepName):
        """
        _setInputStep_

        Set the name of the step used who's output is used as input for this
        task.
        """
        self.data.input.inputStep = stepName
        return

    def getInputStep(self):
        """
        _getInputStep_

        Retrieve the name of the input step, if there is one.
        """
        return getattr(self.data.input, "inputStep", None)

    def inputReference(self):
        """
        _inputReference_

        Get information about the input reference for this task.

        """
        return self.data.input

    def setFirstEventAndLumi(self, firstEvent, firstLumi):
        """
        _setFirstEventAndLumi_

        Set an arbitrary first event and first lumi
        Only used by production workflows
        """

        if not hasattr(self.data, "production"):
            self.data._section("production")
        setattr(self.data.production, "firstEvent", firstEvent)
        setattr(self.data.production, "firstLumi", firstLumi)

    def getFirstEvent(self):
        """
        _getFirstEvent_

        Get first event to produce for the task
        """
        if hasattr(self.data, "production"):
            if hasattr(self.data.production, "firstLumi"):
                return self.data.production.firstEvent
        return 1

    def getFirstLumi(self):
        """
        _getFirstLumi_

        Get first lumi to produce for the task
        """
        if hasattr(self.data, "production"):
            if hasattr(self.data.production, "firstLumi"):
                return self.data.production.firstLumi
        return 1

    def setSplittingParameters(self, **params):
        """
        _setSplittingParameters_

        Set the job splitting parameters.
        """
        [setattr(self.data.input.splitting, key, val)
         for key, val in params.items()]
        return

    def setSplittingAlgorithm(self, algoName, **params):
        """
        _setSplittingAlgorithm_

        Set the splitting algorithm name and arguments.  Clear out any old
        splitting parameters while preserving the parameters for ACDC
        resubmission which are:
          collectionName, filesetName, couchURL, couchDB, owner, group

        This also needs to preserve the parameter we use to set the initial
        LFN counter, whether or not we merge across runs and the runWhitelist:
          initial_lfn_counter
          merge_across_runs
          runWhitelist

        Preserve parameters which can be set up at request creation and if not
        specified should remain unchanged, at the moment these are:
            include_parents
            lheInputFiles

        Also preserve the performance section.
        """
        setACDCParams = {}
        for paramName in ["collectionName", "filesetName", "couchURL",
                          "couchDB", "owner", "group", "initial_lfn_counter",
                          "merge_across_runs", "runWhitelist"]:
            if hasattr(self.data.input.splitting, paramName):
                setACDCParams[paramName] = getattr(self.data.input.splitting,
                                                   paramName)
        preservedParams = {}
        for paramName in ["lheInputFiles", "include_parents", "deterministicPileup"]:
            if hasattr(self.data.input.splitting, paramName):
                preservedParams[paramName] = getattr(self.data.input.splitting,
                                                     paramName)
        performanceConfig = getattr(self.data.input.splitting, "performance", None)

        delattr(self.data.input, "splitting")
        self.data.input.section_("splitting")
        self.data.input.splitting.section_("performance")

        setattr(self.data.input.splitting, "algorithm", algoName)
        self.setSplittingParameters(**preservedParams)
        self.setSplittingParameters(**params)
        self.setSplittingParameters(**setACDCParams)
        if performanceConfig is not None:
            self.data.input.splitting.performance = performanceConfig
        return

    def jobSplittingAlgorithm(self):
        """
        _jobSplittingAlgorithm_

        Retrieve the job splitting algorithm name.
        """
        return getattr(self.data.input.splitting, "algorithm", None)

    def jobSplittingParameters(self, performance=True):
        """
        _jobSplittingParameters_

        Retrieve the job splitting parameters.  This will combine the job
        splitting parameters specified in the spec with the site white list
        and black list as those are passed to the job splitting code.
        If required, also extract the performance parameters and pass them in the dict.
        """
        datadict = getattr(self.data.input, "splitting")
        if performance:
            splittingParams = datadict.dictionary_whole_tree_()
        else:
            splittingParams = datadict.dictionary_()
            if "performance" in splittingParams:
                del splittingParams['performance']
        splittingParams["siteWhitelist"] = self.siteWhitelist()
        splittingParams["siteBlacklist"] = self.siteBlacklist()
        splittingParams["trustSitelists"] = self.getTrustSitelists().get('trustlists')

        if "runWhitelist" not in splittingParams.keys() and self.inputRunWhitelist() != None:
            splittingParams["runWhitelist"] = self.inputRunWhitelist()
        if "runBlacklist" not in splittingParams.keys() and self.inputRunBlacklist() != None:
            splittingParams["runBlacklist"] = self.inputRunBlacklist()

        return splittingParams

    def setJobResourceInformation(self, timePerEvent=None, sizePerEvent=None, memoryReq=None):
        """
        _setJobResourceInformation_

        Set the values to estimate the required computing resources for a job,
        the three key values are main memory usage, time per processing unit (e.g. time per event) and
        disk usage per processing unit (e.g. size per event).
        """
        performanceParams = getattr(self.data.input.splitting, "performance")
        if timePerEvent or getattr(performanceParams, "timePerEvent", None):
            performanceParams.timePerEvent = timePerEvent or getattr(performanceParams, "timePerEvent")
        if sizePerEvent or getattr(performanceParams, "sizePerEvent", None):
            performanceParams.sizePerEvent = sizePerEvent or getattr(performanceParams, "sizePerEvent")

        # special handling for memory overwrite during assignment
        if isinstance(memoryReq, dict):
            taskMemory = memoryReq.get(self.name())
        else:
            taskMemory = memoryReq
        if taskMemory or getattr(performanceParams, "memoryRequirement", None):
            performanceParams.memoryRequirement = taskMemory or getattr(performanceParams, "memoryRequirement")

        for task in self.childTaskIterator():
            task.setJobResourceInformation(memoryReq=memoryReq)

        return

    def addGenerator(self, generatorName, **settings):
        """
        _addGenerator_


        """
        if 'generators' not in self.data.listSections_():
            self.data.section_('generators')
        if generatorName not in self.data.generators.listSections_():
            self.data.generators.section_(generatorName)

        helper = TreeHelper(getattr(self.data.generators, generatorName))
        helper.addValue(settings)

        return

    def listGenerators(self):
        """
        _listGenerators_

        """
        generators = getattr(self.data, "generators", None)
        if generators is None:
            return []
        return generators.listSections_()

    def getGeneratorSettings(self, generatorName):
        """
        _getGeneratorSettings_

        Extract the settings from the generator fields
        """
        generators = getattr(self.data, "generators", None)
        if generators is None:
            return {}
        generator = getattr(generators, generatorName, None)
        if generator is None:
            return {}

        confValues = TreeHelper(generator)
        args = {}
        tempArgs = confValues.pythoniseDict(sections=False)
        for entry in tempArgs.keys():
            args[entry.split('%s.' % generatorName)[1]] = tempArgs[entry]
        return args

    def addInputACDC(self, serverUrl, databaseName, collectionName,
                     filesetName):
        """
        _addInputACDC_

        Set the ACDC input information for this task.
        """
        self.data.input.section_("acdc")
        self.data.input.acdc.server = serverUrl
        self.data.input.acdc.database = databaseName
        self.data.input.acdc.collection = collectionName
        self.data.input.acdc.fileset = filesetName
        return

    def getInputACDC(self):
        """
        _getInputACDC_

        Retrieve the ACDC input configuration.
        """
        if not hasattr(self.data.input, "acdc"):
            return None

        return {"server": self.data.input.acdc.server,
                "collection": self.data.input.acdc.collection,
                "fileset": self.data.input.acdc.fileset,
                "database": self.data.input.acdc.database}

    def addInputDataset(self, **options):
        """
        _addInputDataset_

        Add details of an input dataset to this Task.
        This dataset will be used as input for the first step
        in the task

        options should contain at least:
          - primary - primary dataset name
          - processed - processed dataset name
          - tier - data tier name

        optional args:
          - dbsurl - dbs url if not global
          - block_whitelist - list of whitelisted fileblocks
          - block_blacklist - list of blacklisted fileblocks
          - run_whitelist - list of whitelist runs
          - run_blacklist - list of blacklist runs
        """
        self.data.input.section_("dataset")
        self.data.input.dataset.dbsurl = None
        self.data.input.dataset.section_("blocks")
        self.data.input.dataset.blocks.whitelist = []
        self.data.input.dataset.blocks.blacklist = []
        self.data.input.dataset.section_("runs")
        self.data.input.dataset.runs.whitelist = []
        self.data.input.dataset.runs.blacklist = []

        primary = options.get("primary", None)
        processed = options.get("processed", None)
        tier = options.get("tier", None)

        if primary is None or processed is None or tier is None:
            msg = "Primary, Processed and Tier must be set"
            raise RuntimeError(msg)

        self.data.input.dataset.primary = primary
        self.data.input.dataset.processed = processed
        self.data.input.dataset.tier = tier

        for opt, arg in options.items():
            if opt in ['primary', 'processed', 'tier']:
                continue
            elif opt == 'block_blacklist':
                self.setInputBlockBlacklist(arg)
            elif opt == 'block_whitelist':
                self.setInputBlockWhitelist(arg)
            elif opt == 'dbsurl':
                self.data.input.dataset.dbsurl = arg
            elif opt == "run_whitelist":
                self.setInputRunWhitelist(arg)
            elif opt == "run_blacklist":
                self.setInputRunBlacklist(arg)
            else:
                setattr(self.data.input.dataset, opt, arg)

        return

    def inputDatasetDBSURL(self):
        """
        _inputDatasetDBSURL_

        Retrieve the DBS URL for the input dataset if it exists, none otherwise.
        """
        if hasattr(self.data.input, "dataset"):
            return self.data.input.dataset.dbsurl
        return None

    def setInputBlockWhitelist(self, blockWhitelist):
        """
        _setInputBlockWhitelist_

        Set the block white list for the input dataset.  This must be called
        after setInputDataset().
        """
        self.data.input.dataset.blocks.whitelist = blockWhitelist
        return

    def inputBlockWhitelist(self):
        """
        _inputBlockWhitelist_

        Retrieve the block white list for the input dataset if it exists, none
        otherwise.
        """
        if hasattr(self.data.input, "dataset"):
            return self.data.input.dataset.blocks.whitelist
        return None

    def setInputBlockBlacklist(self, blockBlacklist):
        """
        _setInputBlockBlacklist_

        Set the block black list for the input dataset.  This must be called
        after setInputDataset().
        """
        self.data.input.dataset.blocks.blacklist = blockBlacklist
        return

    def inputBlockBlacklist(self):
        """
        _inputBlockBlacklist_

        Retrieve the block black list for the input dataset if it exsits, none
        otherwise.
        """
        if hasattr(self.data.input, "dataset"):
            return self.data.input.dataset.blocks.blacklist
        return None

    def setInputRunWhitelist(self, runWhitelist):
        """
        _setInputRunWhitelist_

        Set the run white list for the input dataset.  This must be called
        after setInputDataset().
        """
        self.data.input.dataset.runs.whitelist = runWhitelist
        return

    def inputRunWhitelist(self):
        """
        _inputRunWhitelist_

        Retrieve the run white list for the input dataset if it exists, none
        otherwise.
        """
        if hasattr(self.data.input, "dataset"):
            return self.data.input.dataset.runs.whitelist
        return None

    def setInputRunBlacklist(self, runBlacklist):
        """
        _setInputRunBlacklist_

        Set the run black list for the input dataset.  This must be called
        after setInputDataset().
        """
        self.data.input.dataset.runs.blacklist = runBlacklist
        return

    def inputRunBlacklist(self):
        """
        _inputRunBlacklist_

        Retrieve the run black list for the input dataset if it exists, none
        otherwise.
        """
        if hasattr(self.data.input, "dataset"):
            return self.data.input.dataset.runs.blacklist
        return None

    def addProduction(self, **options):
        """
        _addProduction_

        Add details of production job related information.

        options should contain at least:
        TODO: Not sure what is necessary data ask Dave
        optional
        - totalevents - total events in dataset

        """
        if not hasattr(self.data, "production"):
            self.data.section_("production")

        for opt, arg in options.items():
            setattr(self.data.production, opt, arg)

    def inputDataset(self):
        """
        _inputDataset_

        Get the input.dataset structure from this task

        """
        return getattr(self.data.input, "dataset", None)

    def getInputDatasetPath(self):
        """
        _getInputDatasetPath_

        Get the input dataset path because it's useful
        """

        if hasattr(self.data.input, 'dataset'):
            ds = getattr(self.data.input, 'dataset')
            return '/%s/%s/%s' % (ds.primary, ds.processed, ds.tier)
        return None

    def siteWhitelist(self):
        """
        _siteWhitelist_

        Accessor for the site white list for the task.
        """
        return self.data.constraints.sites.whitelist

    def setSiteWhitelist(self, siteWhitelist):
        """
        _setSiteWhitelist_

        Set the set white list for the task.
        """
        self.data.constraints.sites.whitelist = siteWhitelist
        return

    def siteBlacklist(self):
        """
        _siteBlacklist_

        Accessor for the site white list for the task.
        """
        return self.data.constraints.sites.blacklist

    def setSiteBlacklist(self, siteBlacklist):
        """
        _setSiteBlacklist_

        Set the site black list for the task.
        """
        self.data.constraints.sites.blacklist = siteBlacklist
        return

    def getTrustSitelists(self):
        """
        _getTrustSitelists_

        Get the input and pileup flag for 'trust site lists' in the task.
        """

        # handle backward compatibility for the request which doesn't contain trustPUlists
        try:
            trustPUlists = self.data.constraints.sites.trustPUlists
        except AttributeError:
            trustPUlists = False
        return {'trustlists': self.data.constraints.sites.trustlists,
                'trustPUlists': trustPUlists}

    def setTrustSitelists(self, trustSitelists, trustPUSitelists):
        """
        _setTrustSitelists_

        Set the input and the pileup flags for 'trust site lists' in the task.
        """
        self.data.constraints.sites.trustlists = trustSitelists
        self.data.constraints.sites.trustPUlists = trustPUSitelists
        return

    def listOutputDatasetsAndModules(self):
        """
        _listOutputDatasetsAndModules_

        Get the output datasets per output module for this task
        """
        outputDatasets = []
        for stepName in self.listAllStepNames():
            stepHelper = self.getStepHelper(stepName)

            if not getattr(stepHelper.data.output, "keep", True):
                continue

            if stepHelper.stepType() == "CMSSW":
                for outputModuleName in stepHelper.listOutputModules():
                    outputModule = stepHelper.getOutputModule(outputModuleName)
                    outputDataset = "/%s/%s/%s" % (outputModule.primaryDataset,
                                                   outputModule.processedDataset,
                                                   outputModule.dataTier)
                    outputDatasets.append({"outputModule": outputModuleName,
                                           "outputDataset": outputDataset})

        return outputDatasets

    def setSubscriptionInformation(self, custodialSites=None, nonCustodialSites=None,
                                   autoApproveSites=None,
                                   custodialSubType="Replica", nonCustodialSubType="Replica",
                                   custodialGroup="DataOps", nonCustodialGroup="DataOps",
                                   priority="Low", primaryDataset=None,
                                   useSkim=False, isSkim=False,
                                   dataTier=None, deleteFromSource=False):
        """
        _setSubscriptionsInformation_

        Set the subscription information for this task's datasets
        The subscriptions information is structured as follows:
        data.subscriptions.outputModules is a list of all output modules with configured datasets
        data.subscriptions.<outputModule>.dataset
        data.subscriptions.<outputModule>.custodialSites
        data.subscriptions.<outputModule>.nonCustodialSites
        data.subscriptions.<outputModule>.autoApproveSites
        data.subscriptions.<outputModule>.priority
        data.subscriptions.<outputModule>.custodialSubType
        data.subscriptions.<outputModule>.nonCustodialSubType

        The filters arguments allow to define a dataTier and primaryDataset. Only datasets
        matching those values will be configured.
        """

        if not hasattr(self.data, "subscriptions"):
            self.data.section_("subscriptions")
            self.data.subscriptions.outputModules = []

        outputDatasets = self.listOutputDatasetsAndModules()

        for entry in outputDatasets:
            outputDataset = entry["outputDataset"]
            outputModule = entry["outputModule"]

            dsSplit = outputDataset.split('/')

            primDs = dsSplit[1]

            procDsSplit = dsSplit[2].split('-')
            skim = (len(procDsSplit) == 4)

            tier = dsSplit[3]

            if primaryDataset and primDs != primaryDataset:
                continue
            if useSkim and isSkim != skim:
                continue
            if dataTier and tier != dataTier:
                continue

            if outputModule not in self.data.subscriptions.outputModules:
                self.data.subscriptions.outputModules.append(outputModule)
                outputModuleSection = self.data.subscriptions.section_(outputModule)
                outputModuleSection.dataset = outputDataset
                outputModuleSection.custodialSites = []
                outputModuleSection.nonCustodialSites = []
                outputModuleSection.autoApproveSites = []
                outputModuleSection.custodialSubType = "Replica"
                outputModuleSection.nonCustodialSubType = "Replica"
                outputModuleSection.custodialGroup = "DataOps"
                outputModuleSection.nonCustodialGroup = "DataOps"
                outputModuleSection.priority = "Low"
                outputModuleSection.deleteFromSource = False

            outputModuleSection = getattr(self.data.subscriptions, outputModule)
            if custodialSites is not None:
                outputModuleSection.custodialSites = custodialSites
            if nonCustodialSites is not None:
                outputModuleSection.nonCustodialSites = nonCustodialSites
            if autoApproveSites is not None:
                outputModuleSection.autoApproveSites = autoApproveSites
            outputModuleSection.priority = priority
            outputModuleSection.deleteFromSource = deleteFromSource
            outputModuleSection.custodialSubType = custodialSubType
            outputModuleSection.nonCustodialSubType = nonCustodialSubType
            outputModuleSection.custodialGroup = custodialGroup
            outputModuleSection.nonCustodialGroup = nonCustodialGroup

        return

    def updateSubscriptionDataset(self, outputModuleName, outputModuleInfo):
        """
        _updateSubscriptionDataset_

        Updates the dataset in the subscription information for the given output module,
        if the given output module doesn't exist it does nothing.
        """
        if not hasattr(self.data, "subscriptions"):
            return

        if hasattr(self.data.subscriptions, outputModuleName):
            subscriptionInfo = getattr(self.data.subscriptions, outputModuleName)
            subscriptionInfo.dataset = '/%s/%s/%s' % (getattr(outputModuleInfo, "primaryDataset"),
                                                      getattr(outputModuleInfo, "processedDataset"),
                                                      getattr(outputModuleInfo, "dataTier"))
        return

    def getSubscriptionInformation(self):
        """
        _getSubscriptionInformation_

        Get the subscription configuration for the task
        return a dictionary with the following structure
        {<dataset> : {CustodialSites : [],
                      NonCustodialSites : [],
                      AutoApproveSites : [],
                      Priority : "Low",
                      CustodialSubType : "Replica",
                      NonCustodialSubType : "Replica"
                     }
        }
        """
        if not hasattr(self.data, "subscriptions"):
            return {}

        subInformation = {}
        for outputModule in self.data.subscriptions.outputModules:
            outputModuleSection = getattr(self.data.subscriptions, outputModule)
            dataset = outputModuleSection.dataset
            subInformation[dataset] = {"CustodialSites": outputModuleSection.custodialSites,
                                       "NonCustodialSites": outputModuleSection.nonCustodialSites,
                                       "AutoApproveSites": outputModuleSection.autoApproveSites,
                                       "Priority": outputModuleSection.priority,
                                       # These might not be present in all specs
                                       "CustodialGroup": getattr(outputModuleSection, "custodialGroup", "DataOps"),
                                       "NonCustodialGroup": getattr(outputModuleSection, "nonCustodialGroup",
                                                                    "DataOps"),
                                       "DeleteFromSource": getattr(outputModuleSection, "deleteFromSource", False),
                                       # Specs assigned before HG1303 don't have the CustodialSubtype
                                       "CustodialSubType": getattr(outputModuleSection, "custodialSubType", "Replica"),
                                       "NonCustodialSubType": getattr(outputModuleSection, "nonCustodialSubType",
                                                                      "Replica")}
        return subInformation

    def parentProcessingFlag(self):
        """
        _parentProcessingFlag_

        accessor for parentProcessing information (two file input)
        """
        return self.jobSplittingParameters().get("include_parents", False)

    def totalEvents(self):
        """
        _totalEvents_

        accessor for total events in the given dataset
        """
        # TODO: save the total events for  the production job
        return int(self.data.production.totalEvents)
        # return self.data.input.dataset.totalEvents

    def dbsUrl(self):
        """
        _dbsUrl_
        if local dbs url is set for the task, return it
        otherwise return None
        """
        if getattr(self.data.input, "dataset", False):
            return getattr(self.data.input.dataset, "dbsurl", None)
        else:
            return None

    def setTaskType(self, taskType):
        """
        _setTaskType_

        Set the type field of this task
        """
        self.data.taskType = taskType

    def taskType(self):
        """
        _taskType_

        Get the task Type setting
        """
        return self.data.taskType

    def completeTask(self, jobLocation, logLocation):
        """
        _completeTask_

        Combine all the logs from all the steps in the task to a single log

        If necessary, output to Dashboard
        """
        import WMCore.FwkJobReport.Report as Report

        finalReport = Report.Report()
        # We left the master report somewhere way up at the top
        testPath = os.path.join(jobLocation, '../../', logLocation)
        if os.path.exists(testPath):
            # If a report already exists, we load it and
            # append our steps to it
            finalReport.load(testPath)
        taskSteps = self.listAllStepNames()
        for taskStep in taskSteps:
            reportPath = os.path.join(jobLocation, taskStep, "Report.pkl")
            if os.path.isfile(reportPath):
                stepReport = Report.Report()
                stepReport.unpersist(reportPath, taskStep)
                finalReport.setStep(taskStep, stepReport.retrieveStep(taskStep))
            else:
                # Then we have a missing report
                # This should raise an alarm bell, as per Steve's request
                # TODO: Change error code
                finalReport.addStep(reportname=taskStep, status=1)
                finalReport.addError(stepName=taskStep, exitCode=99999, errorType="ReportManipulatingError",
                                     errorDetails="Could not find report file for step %s!" % taskStep)

        finalReport.data.completed = True
        finalReport.persist(logLocation)

        return

    def taskLogBaseLFN(self):
        """
        _taskLogBaseLFN_

        Get the base LFN for the task's log archive file.
        """
        return getattr(self.data, "logBaseLFN", "/store/temp/WMAgent/unmerged")

    def setTaskLogBaseLFN(self, logBaseLFN):
        """
        _setTaskLogBaseLFN_

        Set the base LFN for the task's log archive file.
        """
        self.data.logBaseLFN = logBaseLFN
        return

    def addNotification(self, target):
        """
        _addNotification_

        Add a target to be notified on workflow completion
        """

        self.data.notifications.targets.append(target)
        return

    def getNotifications(self):
        """
        _getNotifications_

        Get all targets for notification at workflow completion
        """

        return self.data.notifications.targets

    def _setPerformanceMonitorConfig(self):
        """
        if config section for the PerformanceMonitor. If not set, it will set one
        """
        if self.monitoring != None:
            return

        self.monitoring = self.data.section_("watchdog")
        if not hasattr(self.data.watchdog, 'monitors'):
            self.data.watchdog.monitors = []
        if 'PerformanceMonitor' not in self.monitoring.monitors:
            self.monitoring.monitors.append('PerformanceMonitor')
            self.monitoring.section_("PerformanceMonitor")
        return

    def setMaxRSS(self, maxRSS):
        if isinstance(maxRSS, dict):
            maxRSS = maxRSS.get(self.name(), None)

        if maxRSS:
            self._setPerformanceMonitorConfig()
            self.monitoring.PerformanceMonitor.maxRSS = int(maxRSS)
            for task in self.childTaskIterator():
                task.setMaxRSS(maxRSS)
        return

    def setMaxVSize(self, maxVSize):
        if isinstance(maxVSize, dict):
            maxVSize = maxVSize.get(self.name(), None)

        if maxVSize:
            self._setPerformanceMonitorConfig()
            self.monitoring.PerformanceMonitor.maxVSize = int(maxVSize)
            for task in self.childTaskIterator():
                task.setMaxVSize(maxVSize)
        return

    def setPerformanceMonitor(self, maxRSS=None, maxVSize=None,
                              softTimeout=None, gracePeriod=None):
        """
        _setPerformanceMonitor_

        Set/Update the performance monitor options for the task
        """
        if not maxRSS and not maxVSize and not softTimeout and not gracePeriod:
            # if no values is specified do nothing
            return

        self.setMaxRSS(maxRSS)
        self.setMaxVSize(maxVSize)
        if softTimeout:
            self._setPerformanceMonitorConfig()
            self.monitoring.PerformanceMonitor.softTimeout = int(softTimeout)
            if gracePeriod:
                self.monitoring.PerformanceMonitor.hardTimeout = int(softTimeout + gracePeriod)
        return

    def getSwVersion(self):
        """
        _getSwVersion_

        Get the CMSSW version for the first CMSSW step of workload.
        """

        for stepName in self.listAllStepNames():
            stepHelper = self.getStepHelper(stepName)
            if stepHelper.stepType() == "CMSSW":
                return stepHelper.getCMSSWVersion()
        return None

    def getScramArch(self):
        """
        _getScramArch_

        Get the scram architecture for the first CMSSW step of workload.
        """

        for stepName in self.listAllStepNames():
            stepHelper = self.getStepHelper(stepName)
            if stepHelper.stepType() == "CMSSW":
                return stepHelper.getScramArch()
        return None

    def setPrimarySubType(self, subType):
        """
        _setPrimarySubType_

        Set the subType that should be used by WorkQueue for the
        primary subscription
        """

        self.data.parameters.primarySubType = subType
        return

    def getPrimarySubType(self):
        """
        _getPrimarySubType_

        Retrieve the primary subType
        If not available, use the taskType
        """

        return getattr(self.data.parameters, 'primarySubType',
                       self.taskType())

    def getConfigCacheIDs(self):
        """
        _getConfigCacheIDs_

        Search constituent steps for ConfigCacheID
        """

        IDs = []
        for stepName in self.listAllStepNames():
            stepHelper = self.getStepHelper(stepName)
            ID = stepHelper.getConfigCacheID()
            if ID:
                IDs.append(ID)
        return IDs

    def setProcessingVersion(self, procVer, parentProcessingVersion=0):
        """
        _setProcessingVersion_

        Set the task processing version
        """
        if isinstance(procVer, dict):
            taskProcVer = procVer.get(self.name(), parentProcessingVersion)
        else:
            taskProcVer = procVer

        self.data.parameters.processingVersion = int(taskProcVer)
        for task in self.childTaskIterator():
            task.setProcessingVersion(procVer, taskProcVer)
        return

    def getProcessingVersion(self):
        """
        _getProcessingVersion_

        Get the task processing version
        """
        return getattr(self.data.parameters, 'processingVersion', 0)

    def setProcessingString(self, procString, parentProcessingString=None):
        """
        _setProcessingString_

        Set the task processing string
        """
        if isinstance(procString, dict):
            taskProcString = procString.get(self.name(), parentProcessingString)
        else:
            taskProcString = procString

        self.data.parameters.processingString = taskProcString

        for task in self.childTaskIterator():
            task.setProcessingString(procString, taskProcString)
        return

    def getProcessingString(self):
        """
        _getProcessingString_

        Get the task processing string
        """
        return getattr(self.data.parameters, 'processingString', None)

    def setNumberOfCores(self, cores):
        """
        _setNumberOfCores_

        Set number of cores for each CMSSW step in this task and its children
        """
        if self.taskType() in ['Processing', 'Production', 'Skim']:
            if isinstance(cores, dict):
                taskCores = cores.get(self.name())
            else:
                taskCores = cores

            if taskCores:
                for stepName in self.listAllStepNames():
                    stepHelper = self.getStepHelper(stepName)
                    if stepHelper.stepType() == "CMSSW":
                        stepHelper.setNumberOfCores(taskCores)

        for task in self.childTaskIterator():
            task.setNumberOfCores(cores)

        return

    def setAcquisitionEra(self, era, parentAcquisitionEra=None):
        """
        _setAcquistionEra_

        Set the task acquisition era
        """
        if isinstance(era, dict):
            taskEra = era.get(self.name(), parentAcquisitionEra)
        else:
            taskEra = era

        self.data.parameters.acquisitionEra = taskEra

        for task in self.childTaskIterator():
            task.setAcquisitionEra(era, taskEra)
        return

    def getAcquisitionEra(self):
        """
        _getAcquisitionEra_

        Get the task acquisition era
        """
        return getattr(self.data.parameters, 'acquisitionEra', None)

    def setLumiMask(self, lumiMask={}, override=True):
        """
        Attach the given LumiMask to the task
        At this point the lumi mask is just the compactList dict not the LumiList object
        """

        if not lumiMask:
            return

        runs = getattr(self.data.input.splitting, 'runs', None)
        lumis = getattr(self.data.input.splitting, 'lumis', None)
        if not override and runs and lumis:  # Unless instructed, don't overwrite runs and lumis which may be there from a task already
            return

        runs = []
        lumis = []
        for run, runLumis in lumiMask.items():
            runs.append(int(run))
            lumiList = []
            for lumi in runLumis:
                lumiList.extend([str(l) for l in lumi])
            lumis.append(','.join(lumiList))

        self.data.input.splitting.runs = runs
        self.data.input.splitting.lumis = lumis

        for task in self.childTaskIterator():
            task.setLumiMask(lumiMask, override)

        return

    def getLumiMask(self):
        """
            return the lumi mask
        """
        runs = getattr(self.data.input.splitting, 'runs', None)
        lumis = getattr(self.data.input.splitting, 'lumis', None)
        if runs and lumis:
            return LumiList(wmagentFormat=(runs, lumis))

        return {}

    def _propMethodMap(self):
        """
        internal mapping methop which maps which method need to be call for each
        property.
        For now only contains properties which updates in assignment stage.
        """
        propMap = {"ProcessingVersion": self.setProcessingVersion,
                   "AcquisitionEra": self.setAcquisitionEra,
                   "ProcessingString": self.setProcessingString,
                   "MaxRSS": self.setMaxRSS,
                   "MaxVSize": self.setMaxVSize
                  }
        return propMap

    def setProperties(self, properties):
        """
        set task properties (only for assignment stage but make it more general)
        """
        for prop, value in properties.items():
            self._propMethodMap()[prop](value)

    def deleteChild(self, childName):
        """
        _deleteChild_

        Remove the child task from the tree, if it exists
        """
        self.deleteNode(childName)

    def setPrepID(self, prepID):
        """
        _setPrepID_

        Set the prepID to for all the tasks below
        """
        # if prepID doesn exist set it, if exist ignore.
        if not self.getPrepID() and prepID:
            self.data.prepID = prepID

        prepID = self.getPrepID()
        # set child prepid
        if prepID:
            for task in self.childTaskIterator():
                task.setPrepID(prepID)

    def getPrepID(self):
        """
        _getPrepID_

        Get the prepID for the workflow
        """
        return getattr(self.data, 'prepID', None)

    def setLFNBase(self, mergedLFNBase, unmergedLFNBase):
        """
        _setLFNBase_

        Set the merged and unmerged base LFNs for all tasks.
        """
        self.data.mergedLFNBase = mergedLFNBase
        self.data.unmergedLFNBase = unmergedLFNBase
        for task in self.childTaskIterator():
            task.setLFNBase(mergedLFNBase, unmergedLFNBase)

        return

    def _getLFNBase(self):
        """
        private method getting lfn base.
        lfn base should be set by workflow
        """
        return (getattr(self.data, 'mergedLFNBase', "/store/data"),
                getattr(self.data, 'unmergedLFNBase', "/store/unmerged"))

    def updateLFNsAndDatasets(self, runNumber=None):
        """
        _updateLFNsAndDatasets_

        Update all the output LFNs and data names for all tasks in the workflow.
        This needs to be called after updating the acquisition era, processing
        version or merged/unmerged lfn base.
        """
        mergedLFNBase, unmergedLFNBase = self._getLFNBase()

        taskType = self.taskType()
        for stepName in self.listAllStepNames():
            stepHelper = self.getStepHelper(stepName)

            if stepHelper.stepType() == "CMSSW":
                for outputModuleName in stepHelper.listOutputModules():
                    outputModule = stepHelper.getOutputModule(outputModuleName)
                    filterName = getattr(outputModule, "filterName", None)
                    if self.getProcessingString():
                        processingEra = "%s-v%i" % (self.getProcessingString(), self.getProcessingVersion())
                    else:
                        processingEra = "v%i" % self.getProcessingVersion()
                    if filterName:
                        processedDataset = "%s-%s-%s" % (self.getAcquisitionEra(),
                                                         filterName,
                                                         processingEra)
                        processingString = "%s-%s" % (filterName,
                                                      processingEra)
                    else:
                        processedDataset = "%s-%s" % (self.getAcquisitionEra(),
                                                      processingEra)
                        processingString = processingEra

                    unmergedLFN = "%s/%s/%s/%s/%s" % (unmergedLFNBase,
                                                      self.getAcquisitionEra(),
                                                      getattr(outputModule, "primaryDataset"),
                                                      getattr(outputModule, "dataTier"),
                                                      processingString)
                    mergedLFN = "%s/%s/%s/%s/%s" % (mergedLFNBase,
                                                    self.getAcquisitionEra(),
                                                    getattr(outputModule, "primaryDataset"),
                                                    getattr(outputModule, "dataTier"),
                                                    processingString)

                    if runNumber != None and runNumber > 0:
                        runString = str(runNumber).zfill(9)
                        lfnSuffix = "/%s/%s/%s" % (runString[0:3],
                                                   runString[3:6],
                                                   runString[6:9])
                        unmergedLFN += lfnSuffix
                        mergedLFN += lfnSuffix

                    lfnBase(unmergedLFN)
                    lfnBase(mergedLFN)
                    setattr(outputModule, "processedDataset", processedDataset)

                    # Once we change an output module we must update the subscription information
                    self.updateSubscriptionDataset(outputModuleName, outputModule)

                    # For merge tasks, we want all output to go to the merged LFN base.
                    if taskType == "Merge":
                        setattr(outputModule, "lfnBase", mergedLFN)
                        setattr(outputModule, "mergedLFNBase", mergedLFN)

                        if getattr(outputModule, "dataTier") in ["DQM", "DQMIO"]:
                            datasetName = "/%s/%s/%s" % (getattr(outputModule, "primaryDataset"),
                                                         processedDataset,
                                                         getattr(outputModule, "dataTier"))
                            self.updateDatasetName(datasetName)
                    else:
                        setattr(outputModule, "lfnBase", unmergedLFN)
                        setattr(outputModule, "mergedLFNBase", mergedLFN)

        self.setTaskLogBaseLFN(unmergedLFNBase)

        # do the samething for all the child
        for task in self.childTaskIterator():
            task.updateLFNsAndDatasets(runNumber=runNumber)

        return

    def updateDatasetName(self, datasetName):
        """
        _updateDatasetName_

        Updates the dataset name argument of the mergeTask's harvesting
        children tasks
        """
        for task in self.childTaskIterator():
            if task.taskType() == "Harvesting":
                for stepName in task.listAllStepNames():
                    stepHelper = task.getStepHelper(stepName)

                    if stepHelper.stepType() == "CMSSW":
                        cmsswHelper = stepHelper.getTypeHelper()
                        cmsswHelper.setDatasetName(datasetName)

        return


class WMTask(ConfigSectionTree):
    """
    _WMTask_

    workload management task.
    Allow a set of processing job specifications that are interdependent
    to be modelled as a tree structure.

    """

    def __init__(self, name):
        ConfigSectionTree.__init__(self, name)
        self.objectType = self.__class__.__name__
        self.pathName = None
        self.taskType = None
        self.prepID = None
        self.section_("steps")
        self.steps.topStepName = None
        self.section_("parameters")
        self.section_("pythonLibs")
        self.section_("constraints")
        self.section_("input")
        self.section_("notifications")
        self.section_("subscriptions")
        self.notifications.targets = []
        self.input.sandbox = None
        self.input.section_("splitting")
        self.input.splitting.algorithm = None
        self.input.splitting.section_("performance")
        self.constraints.section_("sites")
        self.constraints.sites.whitelist = []
        self.constraints.sites.blacklist = []
        self.constraints.sites.trustlists = False
        self.constraints.sites.trustPUlists = False
        self.subscriptions.outputModules = []
        self.input.section_("WMBS")


def makeWMTask(taskName):
    """
    _makeWMTask_

    Convienience method to instantiate a new WMTask with the name
    provided and wrap it in a helper

    """
    return WMTaskHelper(WMTask(taskName))
