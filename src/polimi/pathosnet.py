from model import get_pathosnet_multimodal, get_pathosnet_voice, get_vggish
from ghostvlad.ghostvlad.ghostvlad_features_extractor import FeaturesExtractor
import utils 
import params
import numpy as np


def pathosnet_multimodal_classifier(pathosnet_weights_path, word_embeddings_path,
                                    vggish_weights_path, ghostvlad_weights_path, verbose=False):

    # Load models
    pathosnet = get_pathosnet_multimodal(pathosnet_weights_path=pathosnet_weights_path, verbose=verbose)
    vggish = get_vggish(vggish_weights_path, verbose=verbose)
    ghostvlad = FeaturesExtractor(ghostvlad_weights_path, verbose=verbose)
    embedder = utils.Embedder(word_embeddings_path)

    # Use closures to keep models loaded
    def classifier(audio_file_path, transcription):
        # Prepare the data
        # GhostVlad features
        input_ghost = ghostvlad.features_extractor(audio_file_path)
        if (len(input_ghost) == 0):
            input_ghost = np.zeros((1, 512))
        input_ghost = np.expand_dims(input_ghost, axis=0)
        # VGGish features
        input_vggish = vggish.predict(np.expand_dims(utils.wavfile_to_examples(audio_file_path), axis=-1))
        if (len(input_vggish) == 0):
            input_vggish = np.zeros((1, 128))
        input_vggish = np.expand_dims(input_vggish, axis=0)
        # Word embeddings
        input_text = np.asarray(utils.extract_text_features(transcription, embedder))
        if (len(input_text) == 0):
            input_text = np.zeros((1, 300))
        input_text = np.expand_dims(input_text, axis=0)

        # Perform the classification
        prediction = pathosnet.predict([input_vggish, input_text, input_ghost, input_text])[0]

        multilabel_prediction = dict(zip(params.LABELS, prediction))
        binary_prediction = {k: sum([multilabel_prediction[l] for l in params.LABELS_CONVERSION_DICT[k]])
                             for k in params.BINARY_LABELS}

        return multilabel_prediction, binary_prediction

    return classifier


def pathosnet_voice_classifier(pathosnet_weights_path, vggish_weights_path, ghostvlad_weights_path, verbose=False):

    # Load models
    pathosnet = get_pathosnet_voice(pathosnet_weights_path=pathosnet_weights_path, verbose=verbose)
    vggish = get_vggish(vggish_weights_path, verbose=verbose)
    ghostvlad = FeaturesExtractor(ghostvlad_weights_path, verbose=verbose)

    # Use closures to keep models loaded
    def classifier(audio_file_path):
        # Prepare the data
        # GhostVlad features
        input_ghost = ghostvlad.features_extractor(audio_file_path)
        if (len(input_ghost) == 0):
            input_ghost = np.zeros((1, 512))
        input_ghost = np.expand_dims(input_ghost, axis=0)
        # VGGish features
        input_vggish = vggish.predict(np.expand_dims(utils.wavfile_to_examples(audio_file_path), axis=-1))
        if (len(input_vggish) == 0):
            input_vggish = np.zeros((1, 128))
        input_vggish = np.expand_dims(input_vggish, axis=0)

        # Perform the classification
        prediction = pathosnet.predict([input_vggish, input_ghost])[0]

        multilabel_prediction = dict(zip(params.LABELS, prediction))
        binary_prediction = {k: sum([multilabel_prediction[l] for l in params.LABELS_CONVERSION_DICT[k]])
                             for k in params.BINARY_LABELS}

        return multilabel_prediction, binary_prediction

    return classifier
