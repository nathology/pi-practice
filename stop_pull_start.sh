# stop the service
sudo systemctl stop gamepi.service

# pull the new code 
cd ~/repo/pi-practice
git pull

# turn the automated boot manager back on
sudo systemctl start gamepi.service