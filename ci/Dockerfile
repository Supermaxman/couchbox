# The CI and development image: Ubuntu 26.10 with everything Couchbox's tests use.
#   docker build -t couchbox-dev -f ci/Dockerfile .
#   docker run --rm -v "$PWD:/src" -w /src couchbox-dev pytest
FROM ubuntu:26.10
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends \
      python3 python3-pytest python3-pytest-cov python3-dbus-fast python3-evdev python3-requests python3-websocket \
      python3-pyside6.qtquick python3-pyside6.qtdbus python3-mpv python3-dbus python3-gi \
      qml6-module-qtquick qml6-module-qtquick-controls qml6-module-qtquick-layouts qml6-module-qtquick-window \
      qml6-module-qtqml-workerscript qml6-module-qtquick-templates qml6-module-qtcore qml6-module-qtquick-shapes \
      qml6-module-qtquick-effects qml6-module-qt5compat-graphicaleffects qml6-module-org-kde-layershell qt6-declarative-dev-tools qt6-image-formats-plugins \
      openssh-client cryptsetup-bin e2fsprogs util-linux librsvg2-bin fonts-inter fonts-noto-core fonts-noto-color-emoji \
      shellcheck shfmt python3-pip qrencode devscripts debhelper dh-python lintian fakeroot build-essential jq git ca-certificates \
      xvfb libgl1 libegl1 libglx-mesa0 libgl1-mesa-dri plasma-bigscreen qml6-module-org-kde-plasma-plasma5support \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --break-system-packages ruff==0.12.0 reuse==5.0.2
