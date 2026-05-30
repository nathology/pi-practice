# Pull all of the software that needed

Get a bunch of required software by copy and pasting the 
following into the ssh terminal

```bash
sudo apt update && sudo apt install -y \
  git \
  vim \
  python3-pip \
  python3-venv \
  python3-dev \
  build-essential \
  libfreetype-dev \
  libjpeg-dev \
  libopenjp2-7-dev \
  libtiff-dev \
  libportaudio2 \
  alsa-utils \
  python3-lgpio

```

Pull the rest of the code from the git repo

'''bash
ssh-keygen -t ed25519 -C "your_name@example.com"

# copy this into a new SSH key in github
cat ~/.ssh/id_ed25519.pub

# clone the repo
mkdir -p ~/repo
cd ~/repo
git clone git@github.com:nathology/pi-practice.git
cd pi-practice
git checkout hello-world
git pull
'''

Now that we have cloned the repo, let's run the setup script contained there

'''bash
chmod +x setup-pi.sh
source setup-pi.sh
'''

reboot the machine to update any configs that were changed

'''bash
sudo reboot
'''

Try a hello world on the screen

'''bash
~/voice_env/bin/python oled_hello.py
'''
