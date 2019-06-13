#!/usr/bin/env bash

legacy_root=/home/pi/Legacy

# Debian packages
echo "Installing system packages"
sudo apt-get update
sudo apt-get install -y \
     git \
     build-essential python3-dev python3-pip \
     audacity \
     gimp \
     inkscape \
     musescore \
     pitivi \
     synfigstudio \
     vlc vlc-plugin-fluidsynth \
     libsdl1.2-dev libsdl-image1.2-dev libsdl-mixer1.2-dev libsdl-ttf2.0-dev libpng-dev libjpeg-dev libtiff5-dev libportmidi-dev \
     ruby-sdl ruby-chunky-png

# Clone repos
echo "Cloning git repos"
git clone https://github.com/synesthesiam/legacy-2019.git "${legacy_root}"
git clone https://github.com/synesthesiam/artwork.git "${HOME}/Pictures"

# Python libraries
echo "Creating virtual environment"
"${legacy_root}/create-venv.sh"

# Ruby spi gem
echo "Installing gems"
sudo gem install --local "${legacy_root}/etc/spi-0.1.1.gem"
