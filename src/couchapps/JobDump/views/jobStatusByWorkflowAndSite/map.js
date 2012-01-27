function(doc) {
    
  function statusMap(){
      var status;
      switch (doc['states'][lastStateIndex].newstate) {
          case 'created':
              if (doc['states'][lastStateIndex].oldstate == 'new') {
                  status = 'queued_first';
              } else if (doc['states'][lastStateIndex].oldstate == 'jobcooloff') {
                  status = 'queued_retry';
              } else {
                  throw "not valid transition";
              };
              break;
          case 'jobcooloff':
              status = 'cooloff';
              break;
          case 'executing':
              if (doc['states'][lastStateIndex - 1].oldstate == 'new') {
                  status = 'submitted_first';
              } else if (doc['states'][lastStateIndex - 1].oldstate == 'jobcooloff') {
                  status = 'submitted_retry';
              } else {
                  throw "not valid transition";
              };
              break;
          case 'success':
              status = 'success';
              break;
          case 'exhausted':
              if (doc['states'][lastStateIndex].oldstate == 'jobfailed') {
                  status = 'failure_exception';
              } else if (doc['states'][lastStateIndex].oldstate == 'submitfailed') {
                  status = 'failure_submit';
              } else if (doc['states'][lastStateIndex].oldstate == 'createfailed') {
                  status = 'failure_create';
              } else {
                  throw "not valid transition";
              };
              break;
          case 'killed':
              status = 'canceled';
              break;
          case 'cleanout':
              if (doc['states'][lastStateIndex].oldstate == 'success') {
                  status = 'success';
              } else if (doc['states'][lastStateIndex].oldstate == 'exhausted') {
                  if (doc['states'][lastStateIndex - 1].oldstate == 'jobfailed') {
                      status = 'failure_exception';
                  } else if (doc['states'][lastStateIndex - 1].oldstate == 'submitfailed') {
                      status = 'failure_submit';
                  } else if (doc['states'][lastStateIndex - 1].oldstate == 'createfailed') {
                      status = 'failure_create';
                  } else {
                      throw "not valid transition";
                  };
              } else {
                  throw "not valid transition";
              };
              break;
          default:
              status = "transition";
      }
      return status;
  }
  
  if (doc['type'] == 'job') {
      var tmpSite = null;
      var siteLocation = null
      var lastStateIndex = 0;
      //var lastStateIndex = doc['states'].length - 1
      //search from last state. 
      //if job is retried in different site, it will only count the last site. 
      //if inter mediate site information is needed modify code (don't break)
      
      //TODO need to get the last number by comparing the i. 11 might come first then 2
      // Is it depend on the interpreter? Otherwise this can be outside the loop
      for (var lastStateIndex in doc['states']) {
          tmpSite = doc['states'][lastStateIndex ].location
          if (tmpSite !== "Agent") {
              siteLocation  = tmpSite
          };
      };
      if (siteLocation == null) {
          // tmpSite should be 'Agent'
          siteLocation = tmpSite;
      };
      
      emit([doc['workflow'], statusMap(), siteLocation], 1)
  };
}

