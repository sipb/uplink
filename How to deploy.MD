# Uplink Server Deployment
# Automatic Deployment
1. Run the **deploy.sh** script from your local machine, have the sudo password ready
2. Enter ssh authentication when prompted, as well as sudo password to restart the mattermost process
3. Mattermost should be redeployed once the script finishes and ssh is terminated. 
# Manual Deployment
1. Ssh into uplink-common@rhombi.mit.edu, make sure you have your Kerb tickets. 
2. In **~/uplink-server**, run **make build**
3. Afterwards, run **make package**
4. Go to the **dist/** folder, send **mattermost-enterprise-linux-amd64.tar.gz** to your **local machin**e with **scp**, then send it over to uplink-common@uplink.mit.edu:~
5. **Backup the current server folder in /opt** by changing its name to something else (i.e. mattermost2)
6. Run **tar -xvzf** on the file, then **mv it to /opt**. You should end up with a directory called mattermost/ in /opt.
7. In **mattermost/**, run **sudo mkdir data**.
8. Then, **copy the file config.json** in the home directory of uplink-common **to /opt/mattermost/config**, overwrite the existing config.json. 
9. **Run bin/mattermost** to execute the binary for mattermost, if it shows no error and says something like “Server is listening on :8065”, then it should be good.
10. Start the uplink server by running **sudo systemctl start uplink.service**
11. Done.

# Webapp 
1. In **uplink-common@rhombi.mit.edu**, run **make build in ~/uplink-webapp**, then **make test** if you want to make sure everything is working (4 tests will fail due to the name and description of uplink not matching mattermost defaults)
2. Go to **dist/**, run __tar -cvf dist.tar *__
3. Send it over to your local machine with **scp**, then send it over to uplink-common@uplink.mit.edu.
4. Go to **/opt/mattermost**, run **rm -rf * in client directory**, then unzip dist.tar in here with tar **-xvf dist.tar**
5. Done.
