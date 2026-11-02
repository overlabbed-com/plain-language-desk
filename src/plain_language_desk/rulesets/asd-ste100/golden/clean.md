# Run the deploy check

The deploy check confirms the release reached the cluster. Run it before you
announce the release. The check reads the deployment status and compares two
image digests.

Follow these steps:

1. Read the recorded digest from the release notes.
2. Query the cluster for the running digest.
3. Compare the two values.

If the values differ, the rollout has not finished. Wait five minutes. Run
the check again. If they differ after three attempts, open an incident. Stop
the announcement.
