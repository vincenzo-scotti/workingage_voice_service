#! /usr/bin/env python3
# -*- coding: UTF-8 -*-

################
# ZeroMQ Proxy #
################

# https://zeromq.org/languages/python/

import zmq
import signal
import sys
import threading

global backend, frontend, context


# Adapted from: https://gist.github.com/kianby/e1d455e5fb2a14f8dee3c02c337527f5
def proxyThread():
    global backend, frontend, context

    context = zmq.Context()

    # Socket facing SUBSCRIBERS
    frontend = context.socket(zmq.XPUB)
    frontend.bind("tcp://*:5559")

    # Socket facing PUBLISHERS
    backend = context.socket(zmq.XSUB)
    backend.bind("tcp://*:5560")

    print('ZeroMQ proxy running. Press CTRL-C or send SIGINT for stopping')
    print('\tWaiting for Publishers on port 5560')
    print('\tWaiting for Subscribers on port 5559')
    zmq.proxy(frontend, backend)


def signal_handler(sig, frame):
    """
    Handles the SIGINT signal: stops threads and quits the process.
    :param sig:  the signal number.
    :param frame: the current stack frame.
    :return: nothing.
    """

    global backend, frontend, context

    # Stop proxy
    frontend.close()
    backend.close()
    context.term()

    # exit
    print('SIGINT RECEIVED. ZeroMq proxy exiting.')
    sys.exit(0)


def main():
    # Start the proxy thread
    receiver = threading.Thread(target=proxyThread, daemon=True)
    receiver.start()

    # The app will terminate on SIGINT signal
    signal.signal(signal.SIGINT, signal_handler)
    signal.pause()  # just wait for signals, forever


if __name__ == "__main__":
    main()