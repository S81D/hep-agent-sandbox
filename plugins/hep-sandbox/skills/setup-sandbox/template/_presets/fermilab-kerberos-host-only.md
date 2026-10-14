<!-- Remote-access preset: Fermilab via Kerberos, host-only.
     Fermilab SSH uses Kerberos (GSSAPI), not SSH keys, so agent forwarding cannot reach it.
     The container gets no Kerberos client config and no FNAL hosts; agents draft commands
     and the user runs them from a Mac terminal. render.py splits this file on the markers. -->
<!-- policy -->
- The container has **no Fermilab access by design** (no Kerberos). Fermilab logins are host-only.
- When remote work is needed, give the user complete, copy-pasteable command blocks to run in a Mac
  terminal: real values filled in (paths, tarball names, job IDs, tags), in order, with a line on
  the expected output. Never "see README §X" or "same as before with -N 10".
- When files must reach a gpvm, end with the exact list of files to `scp` (from `git status`).
- Grid and dCache are shared resources. Never propose campaign-scale submissions (jobsub_submit,
  condor_submit, sbatch, qsub with N > 1) without first stating the job count and data volume.
  Do not submit jobs merely to test syntax.
- Check with the user before anything grid-related that creates, destroys, moves, generates, or
  submits things.
<!-- ssh_config -->
# Fermilab (*.fnal.gov) is intentionally NOT configured: FNAL logins use Kerberos,
# and FNAL access is host-only by design. Run FNAL ssh/scp from a macOS terminal.
<!-- quickstart -->
| Fermilab (`kinit`, `ssh <gpvm>`, jobsub) | **Mac** terminal only |
