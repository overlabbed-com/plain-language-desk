# Operational Considerations

It is important to note that the deployment verification process should be
undertaken prior to the dissemination of any release announcement, in order
to ascertain that the aforementioned release has been successfully completed.

There is a comparison that is performed between the image digest that was
recorded and the digest which is currently running in the cluster, and this
is done by the deploy check, which is a tool that facilitates the
verification of deployments in a timely manner. The utilization of this tool
is recommended.

Should discrepancies be identified between the values, it is likely that the
rollout has not been totally completed at the present time, and in that event
it would be advisable to wait for a period of five minutes before proceeding
to re-run the check that was previously described, and if discrepancies still
exist after a number of attempts have been made, then the incident process
should be initiated by the person who is performing the verification, and the
announcement should not be made until such time as the situation has been
clarified and the relevant parties have been notified of the actual status.
