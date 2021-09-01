from __future__ import absolute_import
from __future__ import print_function
import os
import sys
import numpy as np
import librosa
import random

import ghostvlad.ghostvlad.ghostvlad_model as model
import ghostvlad.ghostvlad.toolkits as toolkits

# ===========================================
#        Parse the argument
# ===========================================
import argparse
parser = argparse.ArgumentParser()
# set up training configuration.
parser.add_argument('--gpu', default='', type=str)
parser.add_argument('--resume', default=r'ghostvlad/pretrained_models/ghostvlad_weights.h5', type=str)
parser.add_argument('--data_path', default='4persons', type=str)
# set up network configuration.
parser.add_argument('--net', default='resnet34s', choices=['resnet34s', 'resnet34l'], type=str)
parser.add_argument('--ghost_cluster', default=2, type=int)
parser.add_argument('--vlad_cluster', default=8, type=int)
parser.add_argument('--bottleneck_dim', default=512, type=int)
parser.add_argument('--aggregation_mode', default='gvlad', choices=['avg', 'vlad', 'gvlad'], type=str)
# set up learning rate, training loss and optimizer.
parser.add_argument('--loss', default='softmax', choices=['softmax', 'amsoftmax'], type=str)
parser.add_argument('--test_type', default='normal', choices=['normal', 'hard', 'extend'], type=str)
parser.add_argument('--csv_file', default='', type=str)
parser.add_argument('--verbose', default='True', choices=['True', 'False'], type=str)

global args_gv
args_gv = parser.parse_args('')

class FeaturesExtractor():

    def __init__(self, ghostvlad_weights_path, verbose=False):
        if verbose:
            print("\tInstantiating GhostVlad...")
        toolkits.initialize_GPU(args_gv)
        params = {'dim': (257, None, 1), 'nfft': 512, 'min_slice': 720, 'win_length': 400,
                  'hop_length': 160, 'n_classes': 5994, 'sampling_rate': 16000, 'normalize': True,}
        self.network_eval = model.vggvox_resnet2d_icassp(input_dim=params['dim'], num_class=params['n_classes'], mode='eval', args=args_gv)

        # load the model if the imag_model == real_model.
        # NOTE weights should be passed using the argument '--resume', this is a modified constructor.
        if os.path.isfile(ghostvlad_weights_path):
            if verbose:
                print("\tLoading GhostVlad weights...")
            self.network_eval.load_weights(os.path.join(ghostvlad_weights_path), by_name=True)
            self.network_eval.trainable = False
            if verbose:
                print("\tGhostVlad weights loaded successfully.")
        else:
            raise IOError("No checkpoint found at '{}'".format(ghostvlad_weights_path))
        if verbose:
            print("\tGhostVlad instantiated successfully.")


    # ===============================================
    #       code from Arsha for loading data.
    # ===============================================
    def load_wav(self, vid_path, sr):
        wav, sr_ret = librosa.load(vid_path, sr=sr)
        assert sr_ret == sr

        intervals = librosa.effects.split(wav, top_db=20)
        wav_output = []
        for sliced in intervals:
            wav_output.extend(wav[sliced[0]:sliced[1]])
        wav_output = np.array(wav_output)
        return wav_output

    def lin_spectogram_from_wav(self, wav, hop_length, win_length, n_fft=1024):
        linear = librosa.stft(wav, n_fft=n_fft, win_length=win_length, hop_length=hop_length) # linear spectrogram
        return linear.T

    def load_data(self, audio_path, win_length=400, sr=16000, hop_length=160, n_fft=512):
        win_time = 300
        win_spec = win_time//(1000//(sr//hop_length)) # win_length in spectrum
        hop_spec = win_spec//2

        wavs = np.array([])
        wav = self.load_wav(audio_path, sr=sr) # VAD
        wavs = np.concatenate((wavs, wav))

        linear_spect = self.lin_spectogram_from_wav(wavs, hop_length, win_length, n_fft)
        mag, _ = librosa.magphase(linear_spect)  # magnitude
        mag_T = mag.T
        freq, time = mag_T.shape
        spec_mag = mag_T

        utterance_specs = []

        cur_spec = 0
        while(True):
            if(cur_spec+win_spec>time):
                break
            spec_mag = mag_T[:, cur_spec:cur_spec+win_spec]

            # preprocessing, subtract mean, divided by time-wise var
            mu = np.mean(spec_mag, 0, keepdims=True)
            std = np.std(spec_mag, 0, keepdims=True)
            spec_mag = (spec_mag - mu) / (std + 1e-5)
            utterance_specs.append(spec_mag)
            cur_spec += hop_spec
        return utterance_specs


    def features_extractor(self, audio_path):
        utterance_specs = self.load_data(audio_path)
        feats = []
        for spec in utterance_specs:
            spec = np.expand_dims(np.expand_dims(spec, 0), -1)
            v = self.network_eval.predict(spec)
            feats += [v]
        if (len(feats) > 0):
            feats = np.array(feats)[:,0,:].astype(float)
            feats = np.array(feats).astype(float)
        return feats
