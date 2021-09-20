#! /usr/bin/env python3
# -*- coding: UTF-8 -*-

"""
Main script handling voice.

Author : R. Tedesco, V. Scotti - Politecnico di Milano
Date   : 2021-01-13
Version: v0.6

The whole software stack is composed by:
- This script, usually run as a systemd service (see info files)
- PerVoice Audioma ASR: service and configuration files (see Audioma manual)
- PATHOSnet classifier
- AUD classifier


DESCRIPTION:
    THREAD Receive
    - do
        - get new file list from folder Voice
        - for each file
            - if the sensor who sent the file is not in "stop"
                - move to folder ASR
            - else
                - delete the file
            - sleep so that, in total, the current loop lasts 1 second
    - while not STOP

    THREAD Classify
    - do
        - get new file list from folders ASR
        - for each pair of wav and txt files
            - read wav and txt files
            - move (asynchronously) the files to folder ClassifierTempStorage
            - use classifier
            - send class to app
            - sleep so that, in total, the current loop lasts 1 second
    - while not STOP

    THREAD UserRegistration
    - do
        - wait for message of new user
        - update data structure
        - update Pickle file
    - while not STOP

    THERAD StartStop
    -do
        - wait for start/stop message about a sensor group
        - update "start/stop" status for a given sensor group
    - while not STOP


TO STOP THE PROCESS (see: https://www.gnu.org/software/libc/manual/html_node/Termination-Signals.html):
- use the SIGTERM signal (command: "kill -15 [PID of the process]) or use the "jobs" command for managing jobs
- or press CTRL-C, when in foreground mode (i.e., SIGINT)


NOTICE:
All data folders must be placed into the LUKS partition, mounted at: /securestorage


SEE ALSO:
https://docs.python.org/2/library/signal.html
https://stackoverflow.com/questions/1112343/how-do-i-capture-sigint-in-python
https://realpython.com/intro-to-python-threading/
https://stackoverflow.com/a/46098711
https://docs.python.org/3/library/logging.html
https://stackoverflow.com/a/24862213
http://effbot.org/zone/thread-synchronization.htm
https://stackoverflow.com/questions/6953351/thread-safety-in-pythons-dictionary
https://stackoverflow.com/questions/16249440/changing-file-permission-in-python


REQUIRED LIBRARIES/PACKETS:
- Python library: PyCryptodome - Handles encryption
- Python library: Pyzmq - Communication with Apps
- Packet FFmpeg (the "ffmpeg" command must be in PATH) - Transcodes FLAC into WAV
"""


import logging
import subprocess
import os
import stat
import signal
import sys
import threading
import time
from os import listdir
import shutil
from os import path
import pickle
import dataclasses
from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA
import base64
import re
import zmq  # The ZeroMQ library
import json
from datetime import datetime
from typing import Dict

# Path extension to include PoliMI and AUD classifiers
sys.path.extend(["/home/workingage/WACode/polimi", "/home/workingage/WACode"])  # TODO uncomment
from pathosnet import pathosnet_multimodal_classifier, pathosnet_voice_classifier  # The PATHOSnet library # TODO remove polimi
from aud import aud_classifier  # The Audeering library


#################################### BEGIN CONFIGURATION ####################################

#### LOGGING MODE ####
runAs = "systemd"   # could be "background", "systemd", "foreground"; if "systemd", be sure to properly set the corresponding systemd service definition file
loggingFileAbsolutePath = "/home/workingage/WACode/workingAgeVoiceService.log"   # used by "background" and "systemd"
LogFileAppendMode = False  # could be True or False; False means that whenever the script restarts, the log file is overwritten
# Logging level: you’re telling the library you want to handle all events from that level on up
# Levels: CRITICAL > ERROR > WARNING > INFO > DEBUG > NOTSET
loggingLevel = logging.DEBUG
# loggingLevel = logging.INFO

#### SECURE STORAGE PATHS AND POLLING TIME ####
voiceFolderAbsolutePath = "/securestorage/voice/"       # contains FLAC files copied by Raspberry PIs ("voice" is lowercase)
ASRVoiceFolderAbsolutePath = "/securestorage/ASRVoice/" # contains WAV files transcoded from FLAC files
ASRTextFolderAbsolutePath = "/securestorage/ASRText/"   # contains transcribed XML
classificationFolderAbsolutePath = "/securestorage/Classification/"   # contains EMO files with class
storageFolderAbsolutePath = "/securestorage/Storage/"              # contains FLAC, TXT and EMO files for long-term storage
checkPeriod = 2  # Checks the folder every 2 seconds max

#### SENSOR-USER ASSOCIATION FILE ####
userDataPickleFileAbsolutePathName = "/home/workingage/WACode/user_data.pkl"  # DO NOT CHANGE THE FILE NAME !!!

#### ZEROMQ PROXY ####
zeroMQProxyHostName = "zeromqproxy.workingage.eu"
zeroMQProxyPortNumberForPub = "5560"  # DO NOT CHANGE THE PORT NUMBER !!!
zeroMQProxyPortNumberForSub = "5559"  # DO NOT CHANGE THE PORT NUMBER !!!

#### TIMER FOR ASSUMING STOP MODE ####
# If a user leaves without stopping its data recordings, "stop" is assumed after this time threshold
stopThreshold = 10 * 60  # seconds to wait between two "start" messages, before assuming "stop"

#### PATHOSNET CONFIGURATION ####
PATHOSnetVGGisAcousticFeaturesModelAbsolutePath = "/home/workingage/WACode/polimi/checkpoints/weights_vggish.h5"  # Path to the model for acoustic features VGGish
PATHOSnetGhostVladAcousticFeaturesModelAbsolutePath = "/home/workingage/WACode/polimi/ghostvlad/pretrained_models/ghostvlad_weights.h5"  # Path to the model for acoustic features GhostVlad
PATHOSnetEspModelWeightsAbsolutePath = "/home/workingage/WACode/polimi/checkpoints/pathosnet_esp_multimodal.h5"  # Path to the weights of the model for Spanish emotion recognition from voice and text
PATHOSnetEspWordEmbeddingsAbsolutePath = "/home/workingage/WACode/polimi/MUSE/data/wiki.es.vec"  # Path to the spanish word embeddings
PATHOSnetElModelWeightsAbsolutePath = "/home/workingage/WACode/polimi/checkpoints/pathosnet_el_audio.h5"  # Path to the weights of the model for Greek emotion recognition from voice
PATHOSnetModelLang = "El"  # Language code to interact with the dict, either "Esp", "El" or "Eng" (Greek and English does not work with transcription)

#### CLASSIFICATION MODE ####
classificationMode = "binary"  # should be either "binary" or "multilabel";  holds for both AUD and POLIMI classifiers

#################################### END CONFIGURATION ####################################


# Classification constants ---------------------------------------------------------------------------------------------
LABELS = ['Happiness', 'Anger', 'Sadness', 'Neutral']
AUDEERING_LABELS = ['happy', 'angry', 'sad', 'neutral']
AUDEERING_LABELS_CONVERSION_DICT = dict(zip(LABELS, AUDEERING_LABELS))
BINARY_LABELS = ['Positive', 'Negative']
LABELS_CONVERSION_DICT = {'Positive': ['Happiness', 'Neutral'], 'Negative': ['Anger', 'Sadness']}
BINARY_CONVERSION_DICT = {'Happiness': 'Positive', 'Anger': 'Negative', 'Sadness': 'Negative', 'Neutral': 'Positive'}
LANG = PATHOSnetModelLang
POLIMI_WEIGHTS_DICT = {"Esp": 0.466, "El": 0.469, "Eng": 0.0}
POLIMI_PREDICTION_WEIGHT = POLIMI_WEIGHTS_DICT[LANG]
AUD_WEIGHTS_DICT = {"Esp": 0.534, "El": 0.531, "Eng": 1.0}
AUD_PREDICTION_WEIGHT = AUD_WEIGHTS_DICT[LANG]
ENSEBMBLE_BINARY_CLASSIFICATION_THRESHOLD_DICT = {"Esp": 0.4, "El": 0.4, "Eng": 0.4}
ENSEBMBLE_BINARY_CLASSIFICATION_THRESHOLD = ENSEBMBLE_BINARY_CLASSIFICATION_THRESHOLD_DICT[LANG]
# End classification constants -----------------------------------------------------------------------------------------

# PATHOSnet initialization
# Dictionary to retrieve the functions and arguments to instantiate a model starting from the language
PATHOSnetModelGetterDict = {"Esp": {"model_getter": pathosnet_multimodal_classifier,
                                    "args": (PATHOSnetEspModelWeightsAbsolutePath, PATHOSnetEspWordEmbeddingsAbsolutePath, PATHOSnetVGGisAcousticFeaturesModelAbsolutePath, PATHOSnetGhostVladAcousticFeaturesModelAbsolutePath)},
                            "El": {"model_getter": pathosnet_voice_classifier,
                                   "args": (PATHOSnetElModelWeightsAbsolutePath, PATHOSnetVGGisAcousticFeaturesModelAbsolutePath, PATHOSnetGhostVladAcousticFeaturesModelAbsolutePath)},
                            "Eng": {"model_getter": pathosnet_voice_classifier,
                                    "args": (PATHOSnetElModelWeightsAbsolutePath, PATHOSnetVGGisAcousticFeaturesModelAbsolutePath, PATHOSnetGhostVladAcousticFeaturesModelAbsolutePath)}}  # For English we use ony a dummy model, predictions will be done only using Audeering voice model
# Instance of a PATHOSnet model for emotion classification
import tensorflow as tf         # Needed; otherwise, TF does not make the graph available on another thread
graph = tf.get_default_graph()  #   see: https://stackoverflow.com/a/50467697
PATHOSnetClassifier = PATHOSnetModelGetterDict[PATHOSnetModelLang]["model_getter"](*PATHOSnetModelGetterDict[PATHOSnetModelLang]["args"], verbose=True)

# Thread status
receiverThreadStatus = "stop"
classifierThreadStatus = "stop"
userRegistrationThreadStatus = "stop"
userConsentThreadStatus = "stop"
startStopThreadStatus = "stop"

# Data structure containing inf in users and sensors; stored into the Pickle file; see: userDataPickleFileAbsolutePathName
@dataclasses.dataclass
class UserDatumType:  # Data class type: info known for each user
    userPseudoID: str
    encryptor: PKCS1_OAEP.PKCS1OAEP_Cipher
    publickey: RSA.RsaKey
    consentDataCollection: bool = True  # Default consent flag of a user
    consentHeadsetAndCamera: bool = False  # Default consent flag of a user
    consentScientificPurposes: bool = False  # Default consent flag of a user
    consentPublication: bool = False  # Default consent flag of a user
userData: Dict[str, UserDatumType] = {}  # key is the SensorGroupID, value is the UserDatum type
userDataLock = threading.Lock()  # because userData is used by different threads
userFileLock = threading.Lock()  # because user data file is used by different threads

# the state of each user: start or stop; if a user is not into the dictionary, default is STOP
userState = {}  # key is the UserPseudoID, value is "start:"+timestamp; if a SensorGroupID is not here, it is in "stop" state
userStateLock = threading.Lock()  # because userState is used by different threads

# misc
currentTimestamp = datetime.now().strftime("%Y%m%d%H%M%S")
global LOG


############# THREADS #############

def receiverThread():
    """
    Wait for FLAC files copied (via scp) by the AUC noiseBox device, and move them to the folder there ASR waits for them.
    :return: Nothing.
    """
    global receiverThreadStatus, currentTimestamp, voiceFolderAbsolutePath, \
        ASRVoiceFolderAbsolutePath, userStateLock, userState, userData

    receiverThreadStatus = "run"
    LOG.info("receiverThread() - Thread receiver running...")
    alreadyLoggedWarning = False
    while not receiverThreadStatus == "requestToStop":
        startTime = time.time()
        flacFiles = [f for f in listdir(voiceFolderAbsolutePath) if f.endswith("flac")]  # only file names, without path
        if flacFiles != [] and not userData:
            if not alreadyLoggedWarning:
                LOG.warning("receiverThread() - FLAC files present but Pickle file empty: I can't process any FLAC file. Waiting...")
                alreadyLoggedWarning = True  # To avoid logging a lot of time the same warning...
            time.sleep(checkPeriod)
            continue
        for flacFile in flacFiles:
            LOG.info("receiverThread() - received FLAC file: " + flacFile)
            # Set sensorGroupID from file name like: S4188c841-e28a-4865-b233-d39a465358ff_20201022T23_23_45_345656.flac
            sensorGroupID = re.search('^(S[^_]+)_', flacFile).group(1)  # like S4188c841-e28a-4865-b233-d39a465358ff
            # Is sensorGroupID known?
            userDataLock.acquire()
            found = userData.get(sensorGroupID)
            userDataLock.release()
            if found is not None:
                # process sensor group if it is "start"
                userStateLock.acquire()
                state = userState.get(found.userPseudoID, "notfound")
                if "start" in state: # user is registered and is in start mode
                    lastStart = int(state.split(":")[1])  # extract timestamp of the last start message
                    if (datetime.now() - datetime.strptime(str(lastStart), "%Y%m%d%H%M%S")).total_seconds() <= stopThreshold:
                        try:
                            currentTimestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                            LOG.debug("receiverThread() - Received FLAC file: " + flacFile)
                            pre, _ = os.path.splitext(flacFile)
                            wavFile = pre + '.wav'
                            # ffmpeg must be in PATH
                            result = subprocess.check_output('ffmpeg -y -i %s %s' % (voiceFolderAbsolutePath + flacFile, voiceFolderAbsolutePath + wavFile), stderr=subprocess.STDOUT, shell=True)
                            LOG.debug("receiverThread() - Converted into WAV file: " + wavFile)
                        except subprocess.CalledProcessError as e:
                            result = None
                            LOG.error("receiverThread() - Command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))
                        finally:
                            # check whether the FLAC file was empty or not correct
                            if result is None or "Output file is empty" in result.decode('utf-8') or "not contain any stream" in result.decode('utf-8'):
                                os.remove(voiceFolderAbsolutePath + flacFile)  # remove void/corrupted FLAC file
                                if path.exists(voiceFolderAbsolutePath + wavFile):
                                    os.remove(voiceFolderAbsolutePath + wavFile)   # remove void WAV file, if created
                            else:
                                shutil.move(voiceFolderAbsolutePath + wavFile, ASRVoiceFolderAbsolutePath + wavFile)  # Move wav file to the next step
                                # if found.consentHeadsetAndCamera:
                                #     # shutil.move(voiceFolderAbsolutePath + flacFile, storageFolderAbsolutePath + flacFile)  # Move flac file to the storage
                                #     LOG.debug("receiverThread() - Moved WAV file: %s and FLAC file: %s" % (wavFile, flacFile))
                                # else:
                                #     os.remove(voiceFolderAbsolutePath + flacFile)  # Delete flac file if the user did not give consent to store
                                #     LOG.debug("receiverThread() - Moved WAV file: %s and removed FLAC file: %s" % (wavFile, flacFile))
                                os.remove(voiceFolderAbsolutePath + flacFile)  # Delete flac file if the user did not give consent to store
                                LOG.debug("receiverThread() - Moved WAV file: %s and removed FLAC file: %s" % (wavFile, flacFile))
                    else: # user is registered but is inferred in stop mode
                        userState.pop(found.userPseudoID)  # remove sensorGroupID, since it is inferred as stopped
                        os.remove(voiceFolderAbsolutePath + flacFile)  # FLAC file removed as the sensor group is in "stop" mode
                        LOG.info("receiverThread() - sensorGroupID '{}' assumed as stopped: no 'start' messages received within time threshold".format(sensorGroupID))
                else: # user is registered but is in stop mode (i.e., "notfound", means user is in stop mode)
                    os.remove(voiceFolderAbsolutePath + flacFile)  # FLAC file removed as the sensor group is in "stop" mode
                    LOG.info("receiverThread() - FLAC file: {} deleted, as {} is in 'stop' mode".format(flacFile, sensorGroupID))
                userStateLock.release()
            else:  # user is not registered
                LOG.error("receiverThread() - Received sensor ID '{}' not found in data structure containing the Pickle file: ignoring it".format(sensorGroupID))

        delta = checkPeriod - (time.time() - startTime)
        time.sleep(delta if delta > 0 else 0)  # wait no longer than checkPeriod seconds

    LOG.info("receiverThread() - Thread receiver stopped.")
    receiverThreadStatus = "stop"


# def simulatedASRThread():
#     """
#     This thread simulates the ASR: waits for a new wav file and creates the corresponding txt file with transcription.
#     NB: this simulation creates multiple txt for the same wav; the actual ASR should run only on NEW wav arrival
#     :return: Nothing.
#     """
#     global simulatedASRThreadStatus, ASRVoiceFolderAbsolutePath, ASRTextFolderAbsolutePath
#
#     simulatedASRThreadStatus = "run"
#     LOG.info("simulatedASRThread() - Thread ASR running...")
#     while not simulatedASRThreadStatus == "requestToStop":
#         wavFiles = [f for f in listdir(ASRVoiceFolderAbsolutePath) if f.endswith("wav")]
#         for wavFile in wavFiles:
#
#             #  BEGIN ASR SIMULATION
#             pre, _ = os.path.splitext(wavFile) # only file names, without path
#             time.sleep(2)
#             with open(ASRTextFolderAbsolutePath + pre + '.txt', 'w', encoding='utf-8') as f:
#                 f.write("pippo\n")
#             #  END ASR SIMULATION
#
#     LOG.info("simulatedASRThread() - Thread ASR stopped.")
#     simulatedASRThreadStatus = "stop"


def classifierThread():
    """
    Waits for txt and wav files on the ASR folder, read them, runs the emotion classifier code,
    and copy the wav, txt and emo files to the temporary folder for encryption.
    :return: Nothing.
    """

    global classifierThreadStatus, currentTimestamp, \
        ASRTextFolderAbsolutePath, classificationFolderAbsolutePath, \
        userData, userDataLock

    classifierThreadStatus = "run"
    LOG.info("classifierThread() - Thread classifier running...")

    # Connect to ZeroMQ as a PUBLISHER
    context = zmq.Context()
    publisher = context.socket(zmq.PUB)
    publisher.connect("tcp://{}:{}".format(zeroMQProxyHostName, zeroMQProxyPortNumberForPub))  # Connect to ZeroMQ proxy server

    while not classifierThreadStatus == "requestToStop":
        startTime = time.time()

        # If Spanish, work on each transcribed XML files
        if PATHOSnetModelLang == "Esp":
            pvtFiles = [f for f in listdir(ASRTextFolderAbsolutePath) if f.endswith("pvt")]  # only file names, without path
            for pvtFile in pvtFiles:
                # Get XML file and extract words
                with open(ASRTextFolderAbsolutePath + pvtFile, 'r', encoding='utf-8') as f:
                    xmlContent = f.readlines()
                    transcription = ""
                    for line in xmlContent:
                        if "<Token time=" in line:
                            search = re.search('<Token time="[\d\.]+" length="[\d\.]+" data="(.+)"/>', line)
                            if search:
                                transcription = transcription + search.group(1) if transcription == "" else transcription + " " + search.group(1)

                    LOG.info("classifierThread() - Transcription: {}".format(transcription))

                pre, _ = os.path.splitext(pvtFile)
                wavFile = pre + ".wav"

                # if pvt exists, I'm sure the corresponding wav file exists, too. In any case, just check...
                if not path.exists(ASRVoiceFolderAbsolutePath + wavFile):
                    LOG.warning("classifierThread() - WAV file '{}' should exist but was not found".format(ASRVoiceFolderAbsolutePath + wavFile))
                    continue

                LOG.info("classifierThread() - Classifying '{}' file '{}'".format(PATHOSnetModelLang, ASRVoiceFolderAbsolutePath + wavFile))
                label, probability = classify(wavFile, transcription)
                LOG.info("classifierThread() - Class is '{}' with probability '{}'".format(label, probability))

                sensorGroupID = re.search('^(S[^_]+)_', pvtFile).group(1)  # like S4188c841-e28a-4865-b233-d39a465358ff
                sendHighLevelInfo(sensorGroupID, currentTimestamp, label, probability, publisher)  # send message with emotion to the App

                userDataLock.acquire()
                found = userData.get(sensorGroupID)
                userDataLock.release()

                os.remove(ASRVoiceFolderAbsolutePath + wavFile)  # WAV file not needed anymore; the FLAC is already into the storage folder
                if found is not None:
                    # if found.consentScientificPurposes:
                    #     shutil.move(ASRTextFolderAbsolutePath + pvtFile, storageFolderAbsolutePath + pvtFile)  # move the pvt file fo the storage folder
                    # else:
                    #     os.remove(ASRTextFolderAbsolutePath + pvtFile)  # Delete pvt file if the user did not give consent to store transcriptions
                    os.remove(ASRTextFolderAbsolutePath + pvtFile)  # Delete pvt file if the user did not give consent to store transcriptions
                else:
                    os.remove(ASRTextFolderAbsolutePath + pvtFile)  # Delete pvt file if the user is not found
                    LOG.error("classifierThread() - Received sensor ID '{}' not found in data structure containing the Pickle file: ignoring it".format(sensorGroupID))
        # If Greek, work on each wav files
        elif PATHOSnetModelLang == "El" or PATHOSnetModelLang == "Eng":
            wavFiles = [f for f in listdir(ASRVoiceFolderAbsolutePath) if f.endswith("wav")]
            for wavFile in wavFiles:
                LOG.info("classifierThread() - Classifying '{}' file '{}'".format(PATHOSnetModelLang, ASRVoiceFolderAbsolutePath + wavFile))
                label, probability = classify(wavFile)
                LOG.info("classifierThread() - Class is '{}' with probability '{}'".format(label,probability))

                sensorGroupID = re.search('^(S[^_]+)_', wavFile).group(1)  # like S4188c841-e28a-4865-b233-d39a465358ff
                sendHighLevelInfo(sensorGroupID, currentTimestamp, label, probability, publisher)  # send message with emotion to the App

                os.remove(ASRVoiceFolderAbsolutePath + wavFile)  # WAV file not needed anymore; the FLAC is already into the storage folder

        delta = checkPeriod - (time.time() - startTime)
        time.sleep(delta if delta > 0 else 0)  # wait no longer than checkPeriod seconds

    LOG.info("classifierThread() - Thread classifier stopped.")
    classifierThreadStatus = "stop"


def userRegistrationThread():
    """
    Subscribes for messages of new user registration, and handles the Pickle file (and the userData structure)
    :return: Nothing.
    """
    global userData, userRegistrationThreadStatus, userDataPickleFileAbsolutePathName, userDataLock, userFileLock

    LOG.info("userRegistrationThread() - Thread for App registration running...")
    userRegistrationThreadStatus = "run"

    # Connect to ZeroMQ as a SUBSCRIBER
    context = zmq.Context()
    subscriber = context.socket(zmq.SUB)
    subscriber.connect("tcp://{}:{}".format(zeroMQProxyHostName, zeroMQProxyPortNumberForSub))  # Connect to ZeroMQ proxy server
    subscriber.setsockopt_string(zmq.SUBSCRIBE, "adduser") # receives messages with topic like: "adduser/S4188c841-e28a-4865-b233-d39a465358ff"

    # Connect as publisher for the "ack" message
    publisher = context.socket(zmq.PUB)
    publisher.connect("tcp://{}:{}".format(zeroMQProxyHostName, zeroMQProxyPortNumberForPub))  # Connect to ZeroMQ proxy server

    while not userRegistrationThreadStatus == "requestToStop":
        try:
            message_as_utf8 = subscriber.recv_multipart() # Blocking receive; this is not encrypted; it's an array of 2 UTF-8 encoded byte sequences
        except zmq.ZMQError as e:      # if any error, discard the message and restart from the beginning of the loop
            LOG.warning("userRegistrationThread() - recv_multipart() error: '{}'".format(e))
            continue
        LOG.info("userRegistrationThread() - Registering new App: {}".format(message_as_utf8))
        payload_as_utf8 = message_as_utf8[1]  # only consider the payload
        payload = payload_as_utf8.decode('utf-8')   # get Python3 string

        # Example payload sent with the "adduser" topic
        # {
        #   "userpseudoid": "U550e8400-e29b-41d4-a716-446655440000",
        #   "sensorgroupid": "S4188c841-e28a-4865-b233-d39a465358ff",
        #   "rsa4096publickey": "ssh-rsa AAAAB3NzaC1yc2…GgtShbs9649r/Loufhl…"
        # }
        newUserInfo = json.loads(payload)

        # send back an "ack" message
        topic = newUserInfo["userpseudoid"] + "/addeduser"
        payload = json.dumps({
                                'sender': 'voice.workingage.eu'
                              })
        LOG.debug("userRegistrationThread() - To send 'ack' to the registraton message, with topic: '{}', payload: '{}'".format(topic, payload))
        publisher.send_multipart([bytes(topic, encoding='utf-8'), bytes(payload, encoding='utf-8')])  # two sequences of bytes encoded in UTF-8

        # If the userData structure is still empty (i.e., the Pickle file didn't exist when the script was launched)
        if not userData:
            userDatum = UserDatumType(newUserInfo["userpseudoid"], PKCS1_OAEP.new(RSA.importKey(newUserInfo["rsa4096publickey"])), RSA.importKey(newUserInfo["rsa4096publickey"]))
            userDataLock.acquire()
            userData[newUserInfo["sensorgroupid"]] = userDatum
            userDataLock.release()
        # the userData exists, just modify it
        else:
            userDataLock.acquire()
            try:
                # if the new user pseudo ID is already present in userData, remove its entry and its sensor group ID
                for sensorGroupID, userDatum in userData.items():
                    if userDatum.userPseudoID == newUserInfo["userpseudoid"]:
                        LOG.warning("userRegistrationThread() - UserPseudoID '{}' already present. Removing"
                                        .format(userData[newUserInfo["sensorgroupid"]].userPseudoID))
                        userData.pop(sensorGroupID, None)
                        break

                # if the sensor group ID was already assigned, update it with the data of the new user pseudo ID
                if newUserInfo["sensorgroupid"] in userData:
                    LOG.warning("userRegistrationThread() - SensorGroupID '{}' already assigned (to UserPseudoID '{}'). Substituting"
                                    .format(newUserInfo["sensorgroupid"],  userData[newUserInfo["sensorgroupid"]].userPseudoID))
                    # update the info for the sensor group ID
                    LOG.info("userRegistrationThread() - Executing PKCS1_OAEP.new()")
                    updatedUserData = UserDatumType(newUserInfo["userpseudoid"], PKCS1_OAEP.new(RSA.importKey(newUserInfo["rsa4096publickey"])), RSA.importKey(newUserInfo["rsa4096publickey"]))
                    userData[sensorGroupID] = updatedUserData
                    LOG.info("userRegistrationThread() - Completed PKCS1_OAEP.new()")
                    userData[newUserInfo["sensorgroupid"]] = updatedUserData
                # else, simply add the new user
                else:
                    userDatum = UserDatumType(newUserInfo["userpseudoid"], PKCS1_OAEP.new(RSA.importKey(newUserInfo["rsa4096publickey"])), RSA.importKey(newUserInfo["rsa4096publickey"]))
                    userData[newUserInfo["sensorgroupid"]] = userDatum
            finally:
                userDataLock.release()

        LOG.info("userRegistrationThread() - New App registered with user pseudo ID: '{}', sensor group ID: '{}', public key: '{}'"
                     .format(newUserInfo["userpseudoid"], newUserInfo["sensorgroupid"], newUserInfo["rsa4096publickey"]))

        # Pickle file to be re-created or just modified
        write_user_data_file()
        LOG.info("userRegistrationThread() - Users Pickle file written")

        # No sleep here! Just go waiting for the next message

    # Actually, since the thread is usually blocked int the recv_multipart() call, this code is unlikely to be executed...
    LOG.info("userRegistrationThread() - Thread for App registration stopped.")
    userRegistrationThreadStatus = "stop"


def userConsentThread():
    """
    Subscribes for messages of user consent forms, and handles the Pickle file (and the userData structure)
    :return: Nothing.
    """
    global userData, userConsentThreadStatus, userDataPickleFileAbsolutePathName, userFileLock

    LOG.info("userConsentThread() - Thread for User consent running...")
    userConsentThreadStatus = "run"

    # Connect to ZeroMQ as a SUBSCRIBER
    context = zmq.Context()
    subscriber = context.socket(zmq.SUB)
    subscriber.connect(
        "tcp://{}:{}".format(zeroMQProxyHostName, zeroMQProxyPortNumberForSub))  # Connect to ZeroMQ proxy server
    subscriber.setsockopt_string(zmq.SUBSCRIBE,
                                 "privacy")  # receives messages with topic like: "privacy/S4188c841-e28a-4865-b233-d39a465358ff"

    # Connect as publisher for the "ack" message
    publisher = context.socket(zmq.PUB)
    publisher.connect(
        "tcp://{}:{}".format(zeroMQProxyHostName, zeroMQProxyPortNumberForPub))  # Connect to ZeroMQ proxy server

    while not userConsentThreadStatus == "requestToStop":
        try:
            message_as_utf8 = subscriber.recv_multipart()  # Blocking receive; this is not encrypted; it's an array of 2 UTF-8 encoded byte sequences
        except zmq.ZMQError as e:  # if any error, discard the message and restart from the beginning of the loop
            LOG.warning("userConsentThread() - recv_multipart() error: '{}'".format(e))
            continue
        LOG.info("userConsentThread() - Registering User consent: {}".format(message_as_utf8))
        topic_as_utf8 = message_as_utf8[0]  # consider the topic; e.g.: sensor.management/S4188c841-e28a-4865-b233-d39a465358ff
        topic = topic_as_utf8.decode('utf-8')  # get Python3 string
        sensorGroupID = topic.split("/")[1]
        payload_as_utf8 = message_as_utf8[1]  # only consider the payload
        payload = payload_as_utf8.decode('utf-8')  # get Python3 string

        # Example payload sent with the "privacy" topic
        # {
        #   "userpseudoid": "U550e8400-e29b-41d4-a716-446655440000",
        #   "datacollection": true,
        #   "headsetandcamera": true,
        #   "scientificpurposes": true,
        #   "publication": false
        # }
        newUserConsentInfo = json.loads(payload)
        # NOTE: no "ack" message is required

        # If the userData structure is still empty (i.e., the Pickle file didn't exist when the script was launched)
        if not userData:
            LOG.warning("userConsentThread() - No user data available. Skipping consent update of  SensorGroupID '{}'"
                        .format(sensorGroupID))  # In this case we cannot do anything because the user data structure is empty or does not exist
        # the userData exists, just modify it
        else:
            userDataLock.acquire()
            try:
                assert newUserConsentInfo["userpseudoid"] == userData[sensorGroupID].userPseudoID
                # Look for the user connected to the sensor in the topic of the message and update its consent data
                userData[sensorGroupID].consentDataCollection = newUserConsentInfo["datacollection"]
                userData[sensorGroupID].consentHeadsetAndCamera = newUserConsentInfo["headsetandcamera"]
                userData[sensorGroupID].consentScientificPurposes = newUserConsentInfo["scientificpurposes"]
                userData[sensorGroupID].consentPublication = newUserConsentInfo["publication"]

                LOG.info(
                    "userConsentThread() - New User consent info registered with sensor group ID: '{}'. Updated values: Consent to data collection '{}', Consent to Headset and Camera '{}', Consent to Scientific Purposes '{}', Consent to Publication '{}'"
                        .format(sensorGroupID, newUserConsentInfo["datacollection"], newUserConsentInfo["headsetandcamera"], newUserConsentInfo["scientificpurposes"], newUserConsentInfo["publication"]))
            except KeyError:
                LOG.warning("userConsentThread() - No user with SensorGroupID '{}' was found. Skipping this consent".format(sensorGroupID))  # In this case we cannot do anything because the user registration still has not happened, it will go with default consent.
                pass
            except AssertionError:
                LOG.warning("userConsentThread() - Mismatch between registered UserPseudoID {} and received UserPseudoID {} for SensorGroupID '{}'. Skipping this consent".format(userData[sensorGroupID].userPseudoID, newUserConsentInfo["userpseudoid"], sensorGroupID))
            finally:
                userDataLock.release()

        # Write Pickle file to be re-created
        write_user_data_file()
        LOG.info("userConsentThread() - Pickle file written")

        # No sleep here! Just go waiting for the next message

    # Actually, since the thread is usually blocked int the recv_multipart() call, this code is unlikely to be executed...
    LOG.info("userConsentThread() - Thread for User consent stopped.")
    userConsentThreadStatus = "stop"


def startStopThread():
    """
    Subscribes for messages require the voice server to start/stop processing a given SensorGroupID
    :return: Nothing.
    """
    global startStopThreadStatus, userState, userStateLock

    LOG.info("startStopThread() - Thread for start/stop running...")
    startStopThreadStatus = "run"

    # Connect to ZeroMQ as a SUBSCRIBER
    context = zmq.Context()
    subscriber = context.socket(zmq.SUB)
    subscriber.connect("tcp://{}:{}".format(zeroMQProxyHostName, zeroMQProxyPortNumberForSub))  # Connect to ZeroMQ proxy server
    subscriber.setsockopt_string(zmq.SUBSCRIBE, "sensor.management") # receives messages for starting/stopping

    while not startStopThreadStatus == "requestToStop":
        try:
            message_as_utf8 = subscriber.recv_multipart() # Blocking receive; this is not encrypted; it's an array of 2 UTF-8 encoded byte sequences
        except zmq.ZMQError as e:   # if any error, discard the message and restart from the beginning of the loop
            LOG.warning("startStopThread() - recv_multipart() error: '{}'".format(e))
            continue
        LOG.info("startStopThread() - Receiving start/stop: {}".format(message_as_utf8))
        topic_as_utf8 = message_as_utf8[0]  # consider the topic; e.g.: sensor.management/S4188c841-e28a-4865-b233-d39a465358ff
        topic = topic_as_utf8.decode('utf-8')  # get Python3 string
        sensorGroupID = topic.split("/")[1]  # extract sensor group ID; e.g.: S4188c841-e28a-4865-b233-d39a465358ff
        payload_as_utf8 = message_as_utf8[1]  # consider the payload
        payload = payload_as_utf8.decode('utf-8')   # get Python3 string

        # Example payload sent with the "sensor.management" topic
        # {
        #   "action": "stop",
        #   "userpseudoid": "U550e8400-e29b-41d4-a716-446655440000"
        # }
        sensorManagementInfo = json.loads(payload)

        userStateLock.acquire()
        try:
            assert sensorManagementInfo["userpseudoid"] == userData[sensorGroupID].userPseudoID
            if sensorManagementInfo["action"] == "start":  # "start" received
                userState[sensorManagementInfo["userpseudoid"]] = "start:" + datetime.now().strftime(
                    "%Y%m%d%H%M%S")  # insert or update, with current timestamp
            elif sensorManagementInfo["action"] == "stop":  # "stop" received
                userState.pop(sensorManagementInfo["userpseudoid"], None)  # remove userPseudoID, if present
            else:
                LOG.warning("startStopThread() - Receiving unknown/wrong action: {}".format(message_as_utf8))
        except AssertionError:
            LOG.error("startStopThread() - Receiving message with mismatch between userPseudoID and SensorGroupID: {}".format(message_as_utf8))
        userStateLock.release()

    # Actually, since the thread is usually blocked int the recv_multipart() call, this code is unlikely to be executed...
    LOG.info("startStopThread() - Thread for start/stop stopped.")
    startStopThreadStatus = "stop"


############# UTILITY FUNCTIONS #############

def sendHighLevelInfo(currentSensorGroupID, currentTimestamp, label, probability, publisher):
    """
    Send emotion to the right user App, via ZeroMQ.
    :param currentSensorGroupID: the SensorGroupID of the sensor that sent the WAV file with voice
    :param currentTimestamp: the timestamp to use
    :param label: the emotion
    :param probability: the probability of the emotion
    :param publisher: the ZeroMQ publisher object
    :return: Nothing.
    """
    userDataLock.acquire()
    userDatum = userData.get(currentSensorGroupID)
    userDataLock.release()
    if userDatum is not None:  # it should be there because I checked into receiverThread(), but just in case...
        topic = userDatum.userPseudoID
        payload = json.dumps({'probability': probability,
                              'timeStamp': currentTimestamp,
                              'sensorType': 'Microphone',
                              'values': {'sensor': 'EmoState',
                                         'value': label
                                         }
                              })
        LOG.debug("classifierThread() - To send topic: '{}', payload: '{}'".format(topic, payload))
        payload_as_utf8 = payload.encode('utf-8')
        encrypted_payload_as_bytes = userDatum.encryptor.encrypt(payload_as_utf8)
        encrypted_payload_base64 = base64.standard_b64encode(encrypted_payload_as_bytes).decode('utf-8')
        publisher.send_multipart([bytes(topic, encoding='utf-8'), bytes(encrypted_payload_base64, encoding='utf-8')])  # two sequences of bytes encoded in UTF-8
        LOG.debug("classifierThread() - Sent topic: '{}', encrypted payload: '{}'".format(topic, encrypted_payload_base64))
    else:  # if not found, it... disappeared! Something unexpected happened
        LOG.error("classifierThread() - ERROR Received sensor ID '{}' no longer in data structure containing the Pickle file".format(currentSensorGroupID))


def audeeringClassifier(audio_file_path):
    """
    Audeering Classifier
    :param audio_file_path: the WAV file containing voice
    :return: Multilabel and binary-label predictions
    """
    # Perform the classification
    prediction = aud_classifier.classify(audio_file_path)
    if "no_speech" in prediction:
        prob = 1 - prediction["no_speech"]
        prediction["neutral"] = prediction["no_speech"]
        prediction.pop("no_speech")
        prediction["happy"] = prob / 3
        prediction["angry"] = prob / 3
        prediction["sad"] = prob / 3

    multilabel_prediction = dict([(l, prediction[AUDEERING_LABELS_CONVERSION_DICT[l]]) for l in LABELS])
    binary_prediction = {k: sum([multilabel_prediction[l] for l in LABELS_CONVERSION_DICT[k]]) for k in BINARY_LABELS}

    return multilabel_prediction, binary_prediction


def classify(wavFile, transcription = ""):
    """
    Classify wavfile and transcription
    :param wavFile: the WAV file containing voice
    :param transcription: the optional transcription
    :return: label, probability
    """
    global classificationFolderAbsolutePath, classificationMode

    # Begin classification ---------------------------------------------------------------------------------------------
    # Run PATHOSnet
    with graph.as_default():  # Needed; otherwise, TF does not retrieve the graph from this thread
        if PATHOSnetModelLang == 'Esp':
            multilabelPredictionProbabilitiesPolimi, binaryPredictionProbabilitiesPolimi = PATHOSnetClassifier(ASRVoiceFolderAbsolutePath + wavFile, transcription)  # transcription is ignored, if Greek
        elif PATHOSnetModelLang == 'El':
            multilabelPredictionProbabilitiesPolimi, binaryPredictionProbabilitiesPolimi = PATHOSnetClassifier(ASRVoiceFolderAbsolutePath + wavFile)  # transcription is ignored, if Greek
        elif PATHOSnetModelLang == 'Eng':
            multilabelPredictionProbabilitiesPolimi = {l: 0.0 for l in LABELS}
            binaryPredictionProbabilitiesPolimi = {l: 0.0 for l in BINARY_LABELS}

    # Run Audeering model
    multilabelPredictionProbabilitiesAud, binaryPredictionProbabilitiesAud = audeeringClassifier(ASRVoiceFolderAbsolutePath + wavFile)

    # Compute ensemble
    multilabelPredictionProbabilitiesEnsemble =  {l: (POLIMI_PREDICTION_WEIGHT * multilabelPredictionProbabilitiesPolimi[l]) + (AUD_PREDICTION_WEIGHT * multilabelPredictionProbabilitiesAud[l]) for l in LABELS}
    binaryPredictionProbabilitiesEnsemble = {l: (POLIMI_PREDICTION_WEIGHT * binaryPredictionProbabilitiesPolimi[l]) + (AUD_PREDICTION_WEIGHT * binaryPredictionProbabilitiesAud[l]) for l in BINARY_LABELS}

    if classificationMode == "binary":
        label = 'Positive' if binaryPredictionProbabilitiesEnsemble['Positive'] > ENSEBMBLE_BINARY_CLASSIFICATION_THRESHOLD else 'Negative'
        probability = binaryPredictionProbabilitiesEnsemble[label]
    elif classificationMode == "multilabel":
        label = sorted(multilabelPredictionProbabilitiesEnsemble, key=lambda k: -multilabelPredictionProbabilitiesEnsemble[k])[0]
        probability = multilabelPredictionProbabilitiesEnsemble[label]
    # End classification -----------------------------------------------------------------------------------------------

    # Save classified emotion to a .emo textual file
    pre, _ = os.path.splitext(wavFile)
    emoFile = pre + '.emo'
    with open(classificationFolderAbsolutePath + emoFile, 'w', encoding='utf-8') as f:
        f.write(label + "\t" + str(probability) + "\n")
    shutil.move(classificationFolderAbsolutePath + emoFile, storageFolderAbsolutePath + emoFile) # move emo file to the storage area

    return label, probability


def read_user_data_file():
    """
    Try to reads the Pickle file, once. Beware that external editing of the Pickle file will not be read by the script until next start
    :return: Nothing.
    """
    global userData, userDataLock, userFileLock

    # Try to read Pickle file with user data
    if os.path.exists(userDataPickleFileAbsolutePathName):
        userDataLock.acquire()  # protects the userData structure from concurrent access, while filling it
        userFileLock.acquire()  # protects the user data file from concurrent access, while reading it
        LOG.info("userRegistrationThread() - Reading Pickle file")
        with open(userDataPickleFileAbsolutePathName, "rb") as pickleFile:
            userDataRaw = pickle.load(pickleFile)
        userData = {key: UserDatumType(
            userpseudoid,
            sensorgroupid,
            PKCS1_OAEP.new(RSA.importKey(publickey)),
            RSA.importKey(publickey),
            *consent
        ) for key, (userpseudoid, sensorgroupid, publickey, *consent) in userDataRaw.items()}
        userFileLock.release()
        userDataLock.release()
    else:
        LOG.warning("user_data_read_file() - Pickle file does not exist; will be created")


def write_user_data_file():
    """
        Try to write the Pickle file, once.
        :return: Nothing.
    """
    global userData, userDataLock, userFileLock

    # Try to write Pickle file with user data            LOG.info("userRegistrationThread() - Reading Pickle file")
    userDataLock.acquire()  # protects the userData structure from concurrent access, while filling it
    userFileLock.acquire()  # protects the user data file from concurrent access, while reading it
    writeData = {key: (
        userData.userPseudoID,
        userData.publickey.exportKey(),
        userData.consentDataCollection,
        userData.consentHeadsetAndCamera,
        userData.consentScientificPurposes,
        userData.consentPublication
    ) for key, userData in userData.items()}
    with open(userDataPickleFileAbsolutePathName, "wb") as pickleFile:
        pickle.dump(writeData, pickleFile)
    # the file is writable/readable/executable only by the owner
    os.chmod(userDataPickleFileAbsolutePathName, stat.S_IWUSR | stat.S_IRUSR | stat.S_IXUSR)
    userFileLock.release()
    userDataLock.release()


def signal_handler(sig, frame):
    """
    Handles the SIGINT signal: stops threads and quits the process.
    :param sig:  the signal number.
    :param frame: the current stack frame.
    :return: nothing.
    """
    global receiverThreadStatus, userConsentThreadStatus, simulatedASRThreadStatus, classifierThreadStatus, userRegistrationThreadStatus, startStopThreadStatus

    LOG.info('signal_handler() - SIGINT/SIGTERM RECEIVED. Stopping threads...')

    # ask threads to stop
    receiverThreadStatus = "requestToStop"
    userConsentThreadStatus = "requestToStop"
    classifierThreadStatus = "requestToStop"
    userRegistrationThreadStatus = "requestToStop"
    startStopThreadStatus = "requestToStop"

    # wait until all thread are stopped or until a timer (5 seconds) fires
    currTime = datetime.now()
    while (receiverThreadStatus != "stop" or userConsentThreadStatus != "stop" or classifierThreadStatus != "stop" \
            or userRegistrationThreadStatus != "stop" or startStopThreadStatus != "stop") \
            and (datetime.now() - currTime).total_seconds() <= 5:
        time.sleep(1)

    # userRegistrationThread(), userConsentThread() and startStopThread() are likely to be blocked into the recv-multipart() function;
    # if so, they do not terminate their 'while' loop, their status is still "requestToStop" and no
    # logging message is generated by them.
    if userRegistrationThreadStatus != "stop":
        LOG.info("signal_handler() - userRegistrationThread() blocked into recv_multipart(); will be killed.")
    if userConsentThreadStatus != "stop":
        LOG.info("signal_handler() - userConsentThread() blocked into recv_multipart(); will be killed.")
    if startStopThreadStatus != "stop":
        LOG.info("signal_handler() - startStopThread() blocked into recv_multipart(); will be killed.")

    # exit and terminate all threads still running
    LOG.info('signal_handler() - SIGINT/SIGTERM RECEIVED. Exiting 👋🏻')
    logging.shutdown()
    sys.exit(0)


def init_logging(log_file=None, append=False, loglevel=logging.INFO):
    """
    Initialize the logger
    :param log_file: the file where the log should be written; if None, the log is written on stderr
    :param append: when writing to a file, append or not.
    :param loglevel: the log level.
    :return: Nothing.
    """
    global LOG

    class StdIOLogger(object):
        """
        Custom object to enable writing stdout and stderr to log file.
        Adapted from https://stackoverflow.com/questions/19425736/how-to-redirect-stdout-and-stderr-to-logger-in-python
        """

        def __init__(self, logger, log_level):
            self.logger = logger
            self.log_level = log_level
            self.linebuf = ''

        def write(self, buf):
            for line in buf.rstrip().splitlines():
                self.logger.log(self.log_level, line.rstrip())

        def flush(self):
            pass

    # adapted from: https://www.programcreek.com/python/example/136/logging.basicConfig
    # define a Handler which writes to a file
    if log_file is not None:
        logging.basicConfig(level=loglevel,
                            format="%(asctime)s %(levelname)s %(threadName)s %(name)s %(message)s",
                            filename=log_file,
                            filemode='a' if append else 'w')
    # define a Handler which writes messages to sys.stderr
    else:
        logging.basicConfig(level=loglevel, format="%(asctime)s %(levelname)s %(threadName)s %(name)s %(message)s")

    LOG = logging.getLogger("WALog")

    # Redirect stdout as log INFO
    sys.stdout = StdIOLogger(LOG, logging.INFO)
    # Redirect stderr as log ERROR
    sys.stderr = StdIOLogger(LOG, logging.ERROR)


############# THE MAIN #############

# BACKGROUND mode: issue the command:
#     nohup python3 workingAgeVoiceService.py &

# SYSTEMD mode: for starting workingAgeVoiceService.py as a systemd service, see:
#     https://tecadmin.net/setup-autorun-python-script-using-systemd/
#     https://www.golinuxcloud.com/run-systemd-service-specific-user-group-linux/
#
# Commands:
#     sudo systemctl status/start/stop/enable/disable workingage.service
#     journalctl -u workingage
# Service configuration in file:
#     /lib/systemd/system/workingage.service

# FOREGROUND mode: just for testing. Be sure that neither the BACKGROUND nor the SYSTEMD modes are used.
# Issue the command:
#     python3 workingAgeVoiceService.py

# During tests, when using a local ZeroMQ proxy, to check its status issue the command:
#     netstat -a | grep -e:5559 -e:5560

def main():
    # Configuring the logger
    if runAs == "background":
        init_logging(log_file=loggingFileAbsolutePath, append=LogFileAppendMode, loglevel=loggingLevel)
        LOG.info('Running as background job; PID: ' + str(os.getpid()))
    elif runAs == "systemd":
        init_logging(log_file=loggingFileAbsolutePath, append=LogFileAppendMode, loglevel=loggingLevel)
        LOG.info('Running as systemd service; use "journalctl -u workingage" and "sudo systemctl status workingage.service" to check status.')
        LOG.info('Running as systemd job; PID: ' + str(os.getpid()))
    elif runAs == "foreground":
        init_logging(loglevel=loggingLevel)
        LOG.info('Running as foreground process.')

    LOG.info("Edge Cloud Voice manager. Press CTRL-C or send SIGINT/SIGTERM to stop.")

    # try reading the Pickle file, if already present, just once
    read_user_data_file()

    # Starting the thread that will wait for new user registrations
    userRegistration = threading.Thread(target=userRegistrationThread, daemon=True)
    userRegistration.start()

    # Starting the thread that will wait for user consent message
    userConsent = threading.Thread(target=userConsentThread, daemon=True)
    userConsent.start()

    # Starting the receiver thread: waits for FLAC files copied by the AUD noiseBox
    receiver = threading.Thread(target=receiverThread, daemon=True)
    receiver.start()

    # Starting the thread handling the start/stop message
    startStop = threading.Thread(target=startStopThread, daemon=True)
    startStop.start()

    # Starting the thread that will run the classifier
    classifier = threading.Thread(target=classifierThread, daemon=True)
    classifier.start()

    # The app will terminate on SIGINT or SIGTERM signals
    signal.signal(signal.SIGINT, signal_handler)    # i.e., CTRL-C
    signal.signal(signal.SIGTERM, signal_handler)   # from systemd, on service stopping
    signal.pause()  # just wait for signals, forever
    

if __name__ == "__main__":
    main()
