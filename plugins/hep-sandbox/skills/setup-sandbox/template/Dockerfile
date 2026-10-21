# HEP development container: Python + ROOT (conda-forge), C/C++, LaTeX, git, ssh client,
# and the Claude Code / Codex CLIs. Security design: docs/DESIGN.md in hep-agent-sandbox.
#
# Pinned for reproducibility: the base image (by digest), micromamba, the conda env
# (setup/environment.yml; exact builds recorded in setup/conda-<platform>.lock after the
# first build),
# Claude Code and Codex versions.
#
# The digest is the multi-arch index for ubuntu:24.04 as resolved on 2026-10-06, so the
# same line also works for linux/amd64. Note that `apt-get install` still fetches the
# current Ubuntu 24.04 package versions at build time.
FROM ubuntu:24.04@sha256:534baea6a22c03a63003dbc8dbe78fe34bc0d7e595d9a9dc9834884ff530eb55

# Set automatically by Docker BuildKit: arm64 on Apple Silicon, amd64 on Intel.
ARG TARGETARCH

ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=1000
# Host path of ~/hep, passed in from devcontainer.json. Used only to create a symlink so
# absolute host paths (/Users/<you>/hep/...) written in analysis code also resolve here.
ARG HOST_HEP=/Users/you/hep

ARG MICROMAMBA_VERSION=2.9.0-0
ARG CLAUDE_CODE_VERSION=2.1.291
ARG CODEX_VERSION=0.160.1

ENV DEBIAN_FRONTEND=noninteractive \
    TZ={{timezone}} \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# ubuntu:24.04 ships a default 'ubuntu' user with UID/GID 1000; remove it so 'vscode' can use 1000.
RUN userdel --remove ubuntu

# Base development tools. Deliberately no sudo: the agent user must not be able
# to become root. Python comes from the conda env below, not from apt.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential gcc g++ clang cmake make gdb pkg-config \
        git git-lfs openssh-client rsync curl wget ca-certificates \
        vim nano neovim tmux bash-completion less file procps \
        unzip xz-utils bzip2 tzdata \
    && rm -rf /var/lib/apt/lists/*

# LaTeX: a curated TeX Live subset rather than texlive-full (~5 GB).
# texlive-publishers provides REVTeX 4-2 (APS journals, common in HEP).
RUN apt-get update && apt-get install -y --no-install-recommends \
        latexmk biber \
        texlive-latex-base texlive-latex-recommended texlive-latex-extra \
        texlive-fonts-recommended lmodern cm-super-minimal \
        texlive-science texlive-pictures texlive-bibtex-extra texlive-publishers \
        texlive-xetex texlive-luatex texlive-plain-generic \
    && rm -rf /var/lib/apt/lists/*

# micromamba: a single static binary that creates conda environments (no base Python needed).
# The checksum file is published alongside each binary in the official release.
ENV MAMBA_ROOT_PREFIX=/opt/conda
RUN case "${TARGETARCH}" in \
        arm64) MAMBA_PLATFORM=linux-aarch64 ;; \
        amd64) MAMBA_PLATFORM=linux-64 ;; \
        *) echo "Unsupported architecture: ${TARGETARCH}" >&2; exit 1 ;; \
    esac \
    && release_url=https://github.com/mamba-org/micromamba-releases/releases/download/${MICROMAMBA_VERSION} \
    && curl -fsSL -o /usr/local/bin/micromamba "${release_url}/micromamba-${MAMBA_PLATFORM}" \
    && expected_sha=$(curl -fsSL "${release_url}/micromamba-${MAMBA_PLATFORM}.sha256" | awk '{print $1}') \
    && echo "${expected_sha}  /usr/local/bin/micromamba" | sha256sum -c - \
    && chmod 0755 /usr/local/bin/micromamba

# The pinned HEP conda env (ROOT, numpy, uproot, awkward, ...). Owned by root, so the agent
# cannot modify it; persistent package changes go through setup/environment.yml + rebuild.
COPY setup/environment.yml /tmp/environment.yml
RUN micromamba create --yes --prefix /opt/conda/envs/hep --file /tmp/environment.yml \
    && micromamba clean --all --yes \
    && rm /tmp/environment.yml

# Codex CLI: the official statically linked (musl) release binary.
RUN case "${TARGETARCH}" in \
        arm64) CODEX_TRIPLE=aarch64-unknown-linux-musl ;; \
        amd64) CODEX_TRIPLE=x86_64-unknown-linux-musl ;; \
        *) echo "Unsupported architecture: ${TARGETARCH}" >&2; exit 1 ;; \
    esac \
    && curl -fsSL "https://github.com/openai/codex/releases/download/rust-v${CODEX_VERSION}/codex-${CODEX_TRIPLE}.tar.gz" \
        | tar -xz -C /tmp \
    && install -m 0755 "/tmp/codex-${CODEX_TRIPLE}" /usr/local/bin/codex \
    && rm "/tmp/codex-${CODEX_TRIPLE}"

# Agent utilities, in their own layer so the TeX and conda layers above stay cached.
# poppler-utils: Claude Code renders page ranges of PDFs longer than 10 pages with pdftoppm and
#   fails without it; pdftotext/pdfinfo/pdfimages cover bulk text and figure extraction.
# bc, time: calculator and GNU time (/usr/bin/time -v reports peak memory), asked for in agent
#   surveys.
# lib*: shared libraries of Playwright's headless Chromium (setup/page-check.py): the Ubuntu 24.04
#   Chromium list in Playwright's own dependency table (what `playwright install-deps chromium`
#   installs). libgbm1 pulls in mesa and libllvm20 (~180 MB). fonts-*: without any system font,
#   pages render with missing text and wrong widths.
RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils bc time \
        libasound2t64 libatk-bridge2.0-0t64 libatk1.0-0t64 libatspi2.0-0t64 libcairo2 \
        libcups2t64 libdbus-1-3 libdrm2 libgbm1 libglib2.0-0t64 libnspr4 libnss3 \
        libpango-1.0-0 libx11-6 libxcb1 libxcomposite1 libxdamage1 libxext6 libxfixes3 \
        libxkbcommon0 libxrandr2 \
        fonts-liberation fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Headless Chromium for Playwright, the build that matches the conda env's playwright. It lives in
# a root-owned folder outside $HOME, so it survives rebuilds and agents cannot replace it (~100 MB
# download from Playwright's CDN). Chromium's own sandbox needs privileges this container drops,
# so Playwright runs it with --no-sandbox; the container is the boundary (docs/DESIGN.md).
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright
RUN /opt/conda/envs/hep/bin/python -m playwright install --only-shell chromium \
    && chmod -R a+rX /opt/ms-playwright

# Non-root development user.
RUN groupadd --gid ${USER_GID} ${USERNAME} \
    && useradd --uid ${USER_UID} --gid ${USER_GID} --create-home --shell /bin/bash ${USERNAME} \
    # Pre-create the named-volume mount points so Docker initializes the volumes owned by vscode.
    # ~/builds holds compiled software (Geant4, MARLEY, ...) so it survives container rebuilds.
    && install -d -o ${USERNAME} -g ${USERNAME} /home/${USERNAME}/.claude /home/${USERNAME}/.codex \
        /home/${USERNAME}/builds \
    && install -d -o ${USERNAME} -g ${USERNAME} /workspace/hep \
    # Path parity: /Users/<you>/hep -> /workspace/hep. Only ~/hep is reachable this way;
    # nothing else under /Users exists in the container.
    && mkdir -p "$(dirname "${HOST_HEP}")" \
    && ln -s /workspace/hep "${HOST_HEP}"

# Interactive shells: activate the conda env properly (runs its activate.d scripts).
# Non-interactive processes (agents, VS Code) get the env through PATH below.
RUN printf '\n# HEP conda env\neval "$(micromamba shell hook --shell bash)"\nmicromamba activate /opt/conda/envs/hep\n' \
        >> /etc/bash.bashrc

USER ${USERNAME}

# Claude Code CLI via the official native installer, pinned to a version
# (installs to ~/.local/bin/claude). Auto-update is disabled in managed-settings.json.
RUN curl -fsSL https://claude.ai/install.sh | bash -s ${CLAUDE_CODE_VERSION}

# NODE_PATH: Node does not search the env's global node_modules on its own, so without it
# `require('katex')` fails in agents' build scripts.
ENV PATH=/home/${USERNAME}/.local/bin:/opt/conda/envs/hep/bin:${PATH} \
    CONDA_PREFIX=/opt/conda/envs/hep \
    NODE_PATH=/opt/conda/envs/hep/lib/node_modules

# Agent policy, ssh config and the page-check tool: root-owned and read-only to the vscode
# user. These come last so editing them does not invalidate the large layers above.
USER root
COPY setup/ssh_config /etc/ssh/ssh_config.d/50-hep.conf
COPY setup/known_hosts /etc/ssh/ssh_known_hosts
COPY setup/managed-settings.json /etc/claude-code/managed-settings.json
COPY setup/page-check.py /usr/local/bin/page-check
RUN chmod 0644 /etc/ssh/ssh_config.d/50-hep.conf /etc/ssh/ssh_known_hosts \
        /etc/claude-code/managed-settings.json \
    && chmod 0755 /usr/local/bin/page-check \
    # The policy text is a symlink into the read-only infrastructure/ mount, not a copy: edits
    # made on the Mac apply from the next session without a rebuild, and agents still cannot
    # change it. managed-settings.json stays a copy because Claude Code refuses to start when
    # that file exists but cannot be read (e.g. a dangling symlink if ~/hep is not mounted).
    && mkdir -p /etc/hep-agent \
    && ln -s /workspace/hep/infrastructure/hep-devcontainer/setup/agent-policy.md /etc/claude-code/CLAUDE.md \
    && ln -s /workspace/hep/infrastructure/hep-devcontainer/setup/agent-policy.md /etc/hep-agent/AGENTS.md

USER ${USERNAME}
WORKDIR /workspace/hep
