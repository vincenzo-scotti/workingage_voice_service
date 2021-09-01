PHATHOSnet v2 - PoliMI

Packages required:

numba==0.48
numpy==1.18.2
scipy==1.4.1
pandas==1.0.3
scikit-learn==0.22.2.post1
librosa==0.7.2
soundfile==0.10.3.post1
h5py==2.10.0
tensorflow==1.14.0
keras==2.2.5

Look at test.sh for usage to test.

At run-time:

ESP
model_weights_path = "./checkpoints/pathosnet_esp_multimodal.h5" 
vggish_weights_path = "./checkpoints/weights_vggish.h5" 
ghostvlad_weights_path = "./ghostvlad/pretrained_models/ghostvlad_weights.h5" 
word_embeddings_path = "./MUSE/data/wiki.es.vec"

Get classifier:
from pathosnet import pathosnet_multimodal_classifier
Classifier = pathosnet_multimodal_classifier(model_weights_path, word_embeddings_path, vggish_weights_path, ghostvlad_weights_path)

Predict as:
multilabel_prediction, binary_prediction = classifier(audio_file_path: str, transcription: str) -> dictionary['label': 'predicted_score']

To know predicted label:
sorted(multilabel_prediction, key=lambda k: -multilabel_prediction[k])[0]
sorted(binary_prediction, key=lambda k: -binary_prediction[k])[0]

EL
model_weights_path = "./checkpoints/pathosnet_el_audio.h5" 
vggish_weights_path = "./checkpoints/weights_vggish.h5" 
ghostvlad_weights_path = "./ghostvlad/pretrained_models/ghostvlad_weights.h5" 

Get classifier:
from pathosnet import pathosnet_voice_classifier
Classifier = pathosnet_voice_classifier(model_weights_path, vggish_weights_path, ghostvlad_weights_path)

Predict as:
multilabel_prediction, binary_prediction = classifier(audio_file_path: str) -> dictionary['label': 'predicted_score']

To know predicted label:
sorted(multilabel_prediction, key=lambda k: -multilabel_prediction[k])[0]
sorted(binary_prediction, key=lambda k: -binary_prediction[k])[0]