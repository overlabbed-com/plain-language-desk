# Deploy check

The deploy check confirms the release reached the cluster. Run it before you
announce the release.

The check compares the recorded image digest with the digest which is running
in the cluster; if the values differ, the rollout has not finished. Wait five
minutes and then run the check again, and you should look at the deployment
status directly.

If they still differ after three attempts, the incident process should be
started and the announcement should be stopped.
