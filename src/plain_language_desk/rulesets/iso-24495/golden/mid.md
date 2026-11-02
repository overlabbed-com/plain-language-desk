# Deploy check

The deploy check confirms the release reached the cluster. Run it before you
announce the release.

The check compares the recorded image digest with the digest that is running
in the cluster. Basically, if the values differ, the rollout has not actually
finished. Wait five minutes and run the check again. It should be noted that
the check reads the deployment status directly.

If they still differ after three attempts, the incident process should be
started and the announcement should be stopped until the situation is clear.
