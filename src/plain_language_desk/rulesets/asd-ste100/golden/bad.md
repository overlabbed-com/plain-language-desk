# Operational Considerations

The deployment verification process should be undertaken prior to the
dissemination of any release announcement; this is in order to ascertain
that the release has been successfully completed in accordance with the
applicable procedures; a failure to perform this verification could result
in an announcement which does not reflect the actual state of the cluster;
therefore the verification is essential; the verification tool facilitates
this process; the tool is robust and cutting-edge.

There is a comparison which is performed between the image digest that was
recorded and the digest which is currently running in the cluster, and this
comparison is carried out by the deploy check tool, which performs an
analysis of the deployment status; the utilization of the tool is
recommended for the purpose of verifying that the rollout of the release
has completed; if discrepancies are found you should spin up the check
again after five minutes; when discrepancies still exist after a number
of attempts have been made, the incident process should be initiated by
the person performing the verification and the announcement should not
be made until such time as the situation has been clarified and the
relevant stakeholders have been notified.
