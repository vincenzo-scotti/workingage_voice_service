# WorkingAge voice service
Codebase for the voice service of the [WorkingAge](https://www.workingage.eu) tool

## Speech emotion recognition

This is the code of the module for speech emotion recognition integrated in the PoliMI edge server.
The module communicates through the ZeroMQ platform.
The generated JSON payload with the recognized emotion has the following format:

```json
{
  "probability": 0.79340570,
  "timeStamp": "20211231235959",
  "sensorType": "Microphone",
  "values": 
  {
    "sensor": "EmoState",
    "value": "Positive"
  }
}
```

The payload is sent through the ZeroMQ publisher using the `user pseudo ID` as topic, e.g. `U550e8400-e29b-41d4-a716-446655440000`.

## Installation

We suggest to use Python 3.7 as environment.
[FFmpeg](https://www.ffmpeg.org) is expected to be installed and present in `PATH`

To install the required packages use the `requirements.txt` file.
```bash
pip3 install -r requirements.txt
```

If you're not using a virtual environment, it is suggested to install with the user-only option
```bash
pip3 install --user -r requirements.txt
```

## Usage

Service can be run in different modes.

### Background

To run in background mode
```bash
nohup python3 workingAgeVoiceService.py &
```

### SystemD

To run as a SystemD service (preferred)
```bash
sudo systemctl enable workingage.service
sudo systemctl start workingage.service
```
Service configuration file should be `/lib/systemd/system/workingage.service` for Debian/Ubuntu-based systems 
and in `/usr/lib/systemd/system/workingage.service` for CentOS/Fedora/RHEL-based systems.

Additional commands to interact with the SystemD service

```bash
journalctl -u workingage  # check status

sudo systemctl enable workingage.service
sudo systemctl disable workingage.service
sudo systemctl start workingage.service
sudo systemctl stop workingage.service
sudo systemctl restart workingage.service
sudo systemctl status workingage.service
```

For starting and configuring the `workingAgeVoiceService.py` as a systemd service, see:
- https://tecadmin.net/setup-autorun-python-script-using-systemd/
- https://www.golinuxcloud.com/run-systemd-service-specific-user-group-linux/

### Foreground

To run in foreground mode

```bash
python3 workingAgeVoiceService.py
```

## Additional notes
During tests, when using a local ZeroMQ proxy, to check its status issue the command:

```bash
netstat -a | grep -e:5559 -e:5560
```

