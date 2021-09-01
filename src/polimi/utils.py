"""Compute input examples for VGGish from audio waveform."""

import numpy as np
import resampy

import mel_features
import params
import csv
import io

############################################
#       VGGISH INPUT
############################################

try:
  import soundfile as sf

  def wav_read(wav_file):
    wav_data, sr = sf.read(wav_file, dtype='int16')
    return wav_data, sr

except ImportError:

  def wav_read(wav_file):
    raise NotImplementedError('WAV file reading requires soundfile package.')


def waveform_to_examples(data, sample_rate):
  """Converts audio waveform into an array of examples for VGGish.

  Args:
    data: np.array of either one dimension (mono) or two dimensions
      (multi-channel, with the outer dimension representing channels).
      Each sample is generally expected to lie in the range [-1.0, +1.0],
      although this is not required.
    sample_rate: Sample rate of data.

  Returns:
    3-D np.array of shape [num_examples, num_frames, num_bands] which represents
    a sequence of examples, each of which contains a patch of log mel
    spectrogram, covering num_frames frames of audio and num_bands mel frequency
    bands, where the frame length is params.STFT_HOP_LENGTH_SECONDS.
  """
  # Convert to mono.
  if len(data.shape) > 1:
    data = np.mean(data, axis=1)
  # Resample to the rate assumed by VGGish.
  if sample_rate != params.SAMPLE_RATE:
    data = resampy.resample(data, sample_rate, params.SAMPLE_RATE)

  # Compute log mel spectrogram features.
  log_mel = mel_features.log_mel_spectrogram(
      data,
      audio_sample_rate=params.SAMPLE_RATE,
      log_offset=params.LOG_OFFSET,
      window_length_secs=params.STFT_WINDOW_LENGTH_SECONDS,
      hop_length_secs=params.STFT_HOP_LENGTH_SECONDS,
      num_mel_bins=params.NUM_MEL_BINS,
      lower_edge_hertz=params.MEL_MIN_HZ,
      upper_edge_hertz=params.MEL_MAX_HZ)

  # Frame features into examples.
  features_sample_rate = 1.0 / params.STFT_HOP_LENGTH_SECONDS
  example_window_length = int(round(
      params.EXAMPLE_WINDOW_SECONDS * features_sample_rate))
  example_hop_length = int(round(
      params.EXAMPLE_HOP_SECONDS * features_sample_rate))
  log_mel_examples = mel_features.frame(
      log_mel,
      window_length=example_window_length,
      hop_length=example_hop_length)
  return log_mel_examples


def wavfile_to_examples(wav_file):
  """Convenience wrapper around waveform_to_examples() for a common WAV format.

  Args:
    wav_file: String path to a file, or a file-like object. The file
    is assumed to contain WAV audio data with signed 16-bit PCM samples.

  Returns:
    See waveform_to_examples.
  """
  wav_data, sr = wav_read(wav_file)
  assert wav_data.dtype == np.int16, 'Bad sample type: %r' % wav_data.dtype
  samples = wav_data / 32768.0  # Convert to [-1.0, +1.0]
  return waveform_to_examples(samples, sr)




############################################
#       TEXT FEATURES
############################################

class Embedder():
    def __init__(self, path):
        embedding, id2word, word2id = load_vec(path)
        self.embedding = embedding
        self.word2id = word2id
        self.id2word = id2word
    def getEmbedding(self, word):
        return self.embedding[self.word2id[word]]

def extract_text_features(phrase, wv, check=False):
    list_features = []
    for word in phrase:
        try:
            wrd = word.lower()
            w = wv.getEmbedding(wrd)
            list_features.append(w)
        except KeyError:
            try:
                wrd = wrd[0:-1]
                w = wv.getEmbedding(wrd)
                list_features.append(w)
            except KeyError:
                list_features.append(wv.getEmbedding( 'unknown' ))
                if check: 
                    print("Unknown Word Found: ", word)

    return list_features

def load_vec(emb_path, nmax=50000):
    vectors = []
    word2id = {}
    with io.open(emb_path, 'r', encoding='utf-8', newline='\n', errors='ignore') as f:
        next(f)
        for i, line in enumerate(f):
            word, vect = line.rstrip().split(' ', 1)
            vect = np.fromstring(vect, sep=' ')
            assert word not in word2id, 'word found twice'

            vectors.append(vect)
            word2id[word] = len(word2id)
            if len(word2id) == nmax:
                break
        id2word = {v: k for k, v in word2id.items()}
        embeddings = np.vstack(vectors)
        return embeddings, id2word, word2id

def read_text(text_file):
    reader = csv.reader(text_file)
    text = []
    for line in reader:
        text = line[0].split(' ')
    return text
############################################
#       AUDIO FEATURES
############################################

