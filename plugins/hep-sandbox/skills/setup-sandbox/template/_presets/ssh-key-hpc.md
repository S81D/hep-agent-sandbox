<!-- Remote-access preset: SSH-key clusters. The listed hosts accept the user's SSH key, so the
     forwarded Mac ssh-agent lets agents log in while the key is loaded. This gives agents real
     remote access: only choose it for hosts where that is acceptable.
     render.py splits this file on the markers and fills in {{hpc_hosts_list}}. -->
<!-- policy -->
- You may `ssh` to these configured hosts, which accept the user's SSH key through the forwarded
  agent (only while the user has the key loaded on the Mac): {{hpc_hosts_list}}.
- Read-only inspection (`ls`, `cat`, `tail` of logs, queue status) is fine.
- Ask before submitting jobs, transferring more than about 1 GB, deleting or moving anything
  remote, or changing remote configuration.
- Shared computing resources cost other people. Never propose large submissions without first
  stating the job count and data volume, and do not submit jobs merely to test syntax.
<!-- ssh_config -->
# The remote hosts below accept the user's SSH key via the forwarded agent.
# ForwardAgent stays off: the agent never travels beyond these hosts.
<!-- quickstart -->
| Remote clusters ({{hpc_hosts_list}}) | Container terminal: `ssh <alias>` (key must be loaded on the Mac) |
