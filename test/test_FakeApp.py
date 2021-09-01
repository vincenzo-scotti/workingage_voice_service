#! /usr/bin/env python3
# -*- coding: UTF-8 -*-

#########################
# To test my service, through a fake App
#########################

import base64
import json
import sys
import signal
import threading
import time
from datetime import datetime

import zmq
from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA

global decryptor

userPseudoID = "U550e8400-e29b-41d4-a716-446655440000"
sensorGroupID = "S76c91ee3-323b-47f3-b595-79a3d533d9a6"  # sensorGroupID of the noiseBox
publicKey = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQCoqoQXllytlX4a6gZQNLnsm5bXBU7J7E6IX9DT6iW/Unwi2j9649r/LoNpA7Se2IhGQhsP12B2T3a+655UhqOs6rsobY69mWd3ZeWmRjKshD10//vDrV2mXE2AqQdFqksHTogsA76ikfgZWMpoQGRXHN/taWaw1clTyxIVe0JcG9Hn8TYaKlsm7coq98fhe353HhJoBpSXq/lkJqeAAF1rMNtl4WftzG9VO1zx9crRQIiP1g9yIkw8ioB7cWqiCk0tNOHyjKG8Yt9qxF7plZtitcsiJaHYvM3h/UxQInmge0CXkt73HZ38SArZzv5cQejpurMkk/vktsjpgc/HSsFDv1qnWrUhrIlpUKL3j0i68JzG1+uxGvAHVMU+7m/9CnRyc4FXCDw/FmyUyJmP6bykqrWEqkm6Q8nNU6Rdu+wu+8HwNkxwST09+xfgrLofu/v0WZMyOWyFo82p1JOE1oBkBA7DILXCs+SCKfS+DrsjoF2UVLPbW9kaw5jAKcshYDE7mcbQ+enHUtbjqjiTGVm7LECPpcPTi08tVEaA7jZXrCKDfM4bke6RFRRZOppawctwv0nDJuywvBCDGv6lRvrEkxavXD0HQ73Dmz5cuahg+rpVB+W+equtD6tzMnlqWiJDXJyjCqo2m5WhVLcLYve/mGrXFnpgAXSGlmR8tL8v4Q== fakeapp_123456"
privateKey = "-----BEGIN OPENSSH PRIVATE KEY-----\n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\n-----END OPENSSH PRIVATE KEY-----\n"

zeroMQHostName = "127.0.0.1"   # at run time it will become "zeromqproxy.workingage.eu"
zeroMQPortNumberForPub = "5560"  # DO NOT CHANGE THE PORT NUMBER !!!
zeroMQPortNumberForSub = "5559"  # DO NOT CHANGE THE PORT NUMBER !!!

userRegistrationThreadStatus = "stop"
startStopThreadStatus = "stop"
receiveInfoThreadStatus = "stop"
keyboardThreadStatus = "stop"

currentKey = ""


def userRegistrationThread():
    global userRegistrationThreadStatus, currentKey

    context = zmq.Context()

    # Connect as PUBLISHER for the "adduser" message
    publisher = context.socket(zmq.PUB)
    publisher.connect("tcp://{}:{}".format(zeroMQHostName, zeroMQPortNumberForPub))  # Connect to ZeroMQ proxy server

    # Connect to ZeroMQ as a SUBSCRIBER for the "useradded" message
    subscriber = context.socket(zmq.SUB)
    subscriber.connect("tcp://{}:{}".format(zeroMQHostName,zeroMQPortNumberForSub))  # Connect to ZeroMQ proxy server
    subscriber.setsockopt_string(zmq.SUBSCRIBE, userPseudoID + "/addeduser") # receives messages with topic like: "U550e8400-e29b-41d4-a716-446655440000/addeduser"

    while not userRegistrationThreadStatus == "requestToStop":
        if currentKey == "1":
            # send adduser message
            topic = "adduser/" + sensorGroupID
            payload = json.dumps({
                                    "userpseudoid": userPseudoID,
                                    "sensorgroupid": sensorGroupID,
                                    "rsa4096publickey": publicKey
                                })
            publisher.send_multipart([bytes(topic, encoding='utf-8'), bytes(payload, encoding='utf-8')])
            print("sent: " + topic + "\n" + payload)

            # wait for "addeduser" message
            message_as_utf8 = subscriber.recv_multipart() # this is not encrypted; it's an array of 2 UTF-8 encoded byte sequences
            payload_as_utf8 = message_as_utf8[1]  # only consider the payload
            payload = payload_as_utf8.decode('utf-8')   # get Python3 string
            addedUserInfo = json.loads(payload)
            print("received: " + message_as_utf8[0].decode('utf-8') + "\n" + addedUserInfo["sender"])
            currentKey = ""

    userRegistrationThreadStatus = "stop"


def startStopThread():
    global startStopThreadStatus, currentKey

    # Connect as PUBLISHER for the start/stop messages
    context = zmq.Context()
    publisher = context.socket(zmq.PUB)
    publisher.connect("tcp://{}:{}".format(zeroMQHostName, zeroMQPortNumberForPub))  # Connect to ZeroMQ proxy server

    while not startStopThreadStatus == "requestToStop":
        if currentKey in ["2", "3"]:
            topic = "sensor.management/" + sensorGroupID
            if currentKey == "2":
                payload = json.dumps({
                                        "action": "start"
                                    })
            else: # 3
                payload = json.dumps({
                                        "action": "stop"
                                    })
            publisher.send_multipart([bytes(topic, encoding='utf-8'), bytes(payload, encoding='utf-8')])
            print("sent:" + topic + "\n" + payload)
            currentKey = ""

    startStopThreadStatus = "stop"


def receiveInfoThread():
    global receiveInfoThreadStatus, decryptor

    # Connect to ZeroMQ as a SUBSCRIBER for the high-level info message
    context = zmq.Context()
    subscriber = context.socket(zmq.SUB)
    subscriber.connect("tcp://{}:{}".format(zeroMQHostName,zeroMQPortNumberForSub))  # Connect to ZeroMQ proxy server
    subscriber.setsockopt_string(zmq.SUBSCRIBE, userPseudoID)

    while not receiveInfoThreadStatus == "requestToStop":
        message_as_utf8 = subscriber.recv_multipart()
        if not "addeduser" in message_as_utf8[0].decode('utf-8'):
            print("received: ", message_as_utf8)
            encrypted_payload_base64_utf8 = message_as_utf8[1]
            encrypted_payload_as_bytes = base64.standard_b64decode(encrypted_payload_base64_utf8)
            decrypted_payload_as_utf8 = decryptor.decrypt(encrypted_payload_as_bytes)
            decrypted_payload = decrypted_payload_as_utf8.decode('utf-8')
            print("decrypted: ", str(decrypted_payload))

    receiveInfoThreadStatus = "stop"


def keyboardThread():
    global keyboardThreadStatus, currentKey

    while not keyboardThreadStatus == "requestToStop":
        currentKey = input("[1] register, [2] start, [3] stop. Key:")
        time.sleep(5) # wait 5 s before showing the prompt again...

    keyboardThreadStatus = "stop"


def signal_handler(sig, frame):
    """
    Handles the SIGINT signal: stops threads and quits the process.
    :param sig:  the signal number.
    :param frame: the current stack frame.
    :return: nothing.
    """
    global userRegistrationThreadStatus, startStopThreadStatus, receiveInfoThreadStatus, keyboardThreadStatus

    print('signal_handler() - SIGINT RECEIVED. Stopping threads...')

    # ask threads to stop
    userRegistrationThreadStatus = "requestToStop"
    startStopThreadStatus = "requestToStop"
    receiveInfoThreadStatus = "requestToStop"
    keyboardThreadStatus = "requestToStop"

    # wait until all thread are stopped, or until a timer fires
    currTime = datetime.now()
    while (userRegistrationThreadStatus != "stop" or startStopThreadStatus != "stop" or receiveInfoThreadStatus != "stop" or keyboardThreadStatus != "stop") and (datetime.now() - currTime).total_seconds() <= 5:
        time.sleep(1)

    # exit
    print('signal_handler() - SIGINT RECEIVED. Exiting.')
    sys.exit(0)


def main():
    global decryptor

    # Prepare the decryptor
    #privatekey = RSA.importKey(open("./id_rsa4096_123456").read())  # private key for 123456
    privatekey = RSA.importKey(privateKey)  # private key for 123456
    decryptor = PKCS1_OAEP.new(privatekey)

    # Starting the thread that registes users
    userRegistration = threading.Thread(target=userRegistrationThread, daemon=True)
    userRegistration.start()

    # Starts the thread sending the start/stop messages
    startStop = threading.Thread(target=startStopThread, daemon=True)
    startStop.start()

    # Starts the thread receiving high-level info
    receiveInfo = threading.Thread(target=receiveInfoThread, daemon=True)
    receiveInfo.start()

    # Starts the keyboard thread
    keyboard = threading.Thread(target=keyboardThread, daemon=True)
    keyboard.start()

    # The app will terminate on SIGINT signal
    print("FakeApp. Press CTRL-C or send SIGINT to stop.")
    signal.signal(signal.SIGINT, signal_handler)
    signal.pause()  # just wait for signals, forever


if __name__ == "__main__":
    main()