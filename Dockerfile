FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# ---- system dependencies ----
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    swi-prolog \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# ---- install clingo via pip (official method) ----
RUN pip3 install clingo

# ---- working directory ----
WORKDIR /app

# ---- copy project ----
COPY . /app

# ---- install embedded Popper properly ----
RUN pip3 install ./external/popper

# ---- install python deps ----
RUN pip3 install --no-cache-dir -r requirements.txt \
    && pip3 install parsimonious pyswip

CMD ["/bin/bash"]