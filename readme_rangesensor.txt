Rangesensor is installed as daemon

Start Daemon:
	sudo systemctl start rangesensor.service
Stop Daemon:
	sudo systemctl stop rangesensor.service
Status of Daemon:
	sudo systemctl status rangesensor.service

Control script of rangesensor resides in 
/home/rainer/rangesensor.py and can be edited directly there.
After editing the Daemon needs to be restarted with

	sudo systemctl restart rangesensor.service

and checked if running with

	sudo systemctl status rangesensor.service

The daemon service file is under

	/lib/systemd/system/rangesensor.service

