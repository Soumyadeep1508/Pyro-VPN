Before running this script, ensure you have the following installed on your Kali Linux system:

Python 3 and PyQt5:

sudo apt-get install python3 

python3-pyqt5

A Pixelated Font (e.g., "VT323"):

sudo apt-get install fonts-vt323

Running the Script:

Ensure all prerequisites are installed.

Run it:

python3 Pyro.py

Use the GUI:

Click "Import Config" to add an .ovpn file.

Select a config from the list and click "Connect".

Enter credentials if prompted.

Monitor the status and logs.

Click "Disconnect" to stop the VPN.


Interactions:

Import: Opens a file dialog to select and import an .ovpn file.

Connect: Starts OpenVPN with the selected config.

Disconnect: Stops the VPN.

Status/Log Updates: Reflects connection state and logs in real-time.

Authentication: Prompts for credentials if needed.











