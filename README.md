# Installation of Distribution on SD-Card
At least the Raspbian Buster distribution is recommended to have the most recent Python 3.7 support. See [Link](https://www.raspberrypi.org/documentation/installation/installing-images/)
Then we extend the image to the full SD-card with gparted.
Afterwards we modify the image to enable headless startup and SSH. See [Link](https://www.raspberrypi.org/documentation/configuration/wireless/headless.md)

# Change of hostname

This is described under [Link](https://blog.jongallant.com/2017/11/raspberrypi-change-hostname/)

# Change of default user pi to username \<user>

To increase security we change the default username "pi" as described under [Link](https://thepihut.com/blogs/raspberry-pi-tutorials/how-to-change-the-default-account-username-and-password).  The description is given below.

By default your raspberry pi pi comes with an account 'pi' with the password 'raspberry'. For security reasons it's probably a good idea to change the password, but you may also wish to change the username as well. There are a couple of different ways to change the default username but I found the following method the easiest. 

First login into the headless RaspBerry Pi with

    ssh pi@<hostname>

The default password is "raspberry".

In order to change the username 'pi' we will have to log in a the root user since it's not possible to rename an account while your logged into it. To log in as root user first we have to enable it, to do so type the following command whilst logged in as the default pi user:

    sudo passwd root

Choose a secure password for the root user. You can disable the root account later if you wish.
If we want to login as root via ssh we have to uncomment the  line with the command PermitRootLogin in the sshd configuration under "/etc/ssh/sshd_config" and change it as follows:

    PermitRootLogin yes
    
Then restart the sshd daemon (this works even if you are login via ssh!)

    sudo systemctl restart ssh

Now logout of the user pi using the command:

    logout
    
And then logout back in as the user 'root' using the password you just created. 

    ssh root@<hostname>

Befor we can rename the the default pi user name we need to stop all processes running under pi and then immediately rename the user 'pi' to '\<user>', replace \<user> with whatever you want.

    killall -u pi;usermod -l <user> pi

This is required since the user pi is quite persistent to restart some processes and thus needs to prevented from this.

Now the user name has been changed the user's home directory name should also be changed to reflect the new login name:

    usermod -m -d /home/<user> <user>

Now logout and login back in as \<user>. You can change the default password from raspberry to something more secure by typing following command and entering a new password when prompted:

    exit
    ssh <user>@<hostname>
    passwd

If you wish you can disable the root user account again but first double check newname still has 'sudo' privileges. Check the following update command works:

    sudo apt update

and update already the distribution to the most recent package versions:

    sudo apt upgrade
    sudo apt autoremove
    
If it works then you can disable the root account by locking the password:

    sudo passwd -l root
    
And thats it!

# Installation of pigpio

To enable a better timing accuracy we install the pigpio library for the gpio access of the rangesensor.py script.

    sudo apt install pigpio

it seems that the default parameter of the pigpiod daemon to only enable local access to the daemon "-l" is buggy thus we change the service definition file "/lib/systemd/system/pigpiod.service" as follows

    -ExecStart=/usr/bin/pigpiod -l
    +ExecStart=/usr/bin/pigpiod -n 127.0.0.1

and then restart the service

    sudo systemctl restart pigpiod
    
# Installation of WiringPi-Python Bindings

As alternative high accuracy timing GPIO Library we install the WiringPi Python bindings ([Link](https://github.com/WiringPi/WiringPi-Python)). The wiringpi library is already preinstalled and provides the nice GPIO utility  ([Link](http://wiringpi.com/the-gpio-utility/)) .

    sudo -H pip3 install wiringpi

# Installation of VL53L1X ToF Sensor Python Bindings

    sudo pip install smbus2
    sudo pip install vl53l1x

Examples for scripts using the python bindings can be found on the [GitHub Repository of the VL53L1x Python bindings](https://github.com/pimoroni/vl53l1x-python)

# Installation of Samba Share

We follow the description under [Link](https://www.elektronik-kompendium.de/sites/raspberry-pi/2007071.htm)

The smb.conf looks as follows

    [global]
    workgroup = WASSERBWG
    security = user
    encrypt passwords = yes
    client min protocol = SMB2
    client max protocol = SMB3

    [Home]
    comment = Samba-Rainer-Freigabe
    path = /home/<user>
    read only = no

# Install RPi Monitor

See Instructions under [Link](https://www.bjoerns-techblog.de/2017/07/rpi-monitor-fuer-den-raspberry-pi-installieren/)

# Install Jupyter Notebook server as a service

Installation Tutorial can be found under [Link](https://naysan.ca/2019/09/07/jupyter-notebook-as-a-service-on-ubuntu-18-04-with-python-3/)

# Install git

See Instructions under [Link](https://linuxize.com/post/how-to-install-git-on-raspberry-pi/)

Pull this repository and install public SSH key for upload into the accountsettings of this sourceforge site.

# Run rangesensor as service

Tutorial see [Link](https://tecadmin.net/setup-autorun-python-script-using-systemd/)


The wiki uses [Markdown](/p/wasserbehaelter-fuellstand/wiki/markdown_syntax/) syntax.
