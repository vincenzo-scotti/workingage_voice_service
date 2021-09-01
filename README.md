# WorkingAge voice service
Codebase for the voice service of the [WorkingAge](https://www.workingage.eu) tool

## Speech emotion recognition

Emotion recognition module that is integrated in the polimi server
The `sample_api.py` demonstrates how to use the api.
Either you get a probabilities and classes in a json format:

```json
{
    'angry': 0.5550436,
    'sad': 0.07934057,
    'happy': 0.30479267,
    'neutral': 0.060823184
}
```

or if no-speech is detected, you get

```json
{
    'no_speech': prob-of-no-speech
}
```

## Installation

We suggest to use Python 3.7 as environment.
[FFmpeg](https://www.ffmpeg.org) is expected to be installed and present in `PATH`

To install the required packages use the `requirements.txt` file.
```bash
pip3 install -r requirements.txt
```

If you're not using a virtual environment, it is suggested to install with 
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
Service configuration file should be `/lib/systemd/system/workingage.service` 

Additional commands to interact with the SystemD service

```bash
journalctl -u workingage  # check status

sudo systemctl enable workingage.service
sudo systemctl disable workingage.service
sudo systemctl start workingage.service
sudo systemctl stop workingage.service
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

