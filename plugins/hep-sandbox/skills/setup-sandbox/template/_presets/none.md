<!-- Remote-access preset: none. No remote compute hosts are reachable from the container;
     agents draft remote commands and the user runs them from a Mac terminal.
     render.py splits this file on the markers. -->
<!-- policy -->
- No remote machines are configured for this container.
- When remote work is needed, give the user complete, copy-pasteable command blocks to run in a Mac
  terminal: real values filled in (paths, job IDs, tags), in order, with a line on the expected
  output.
- Shared computing resources (grids, batch clusters, shared storage) cost other people. Never
  propose large submissions without first stating the job count and data volume, and do not
  submit jobs merely to test syntax.
<!-- ssh_config -->
# No remote compute hosts are configured; the container only reaches GitHub over SSH.
<!-- quickstart -->
| Remote clusters | **Mac** terminal (none configured in the container) |
