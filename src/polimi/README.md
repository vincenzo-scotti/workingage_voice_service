# PHATHOSnet v2

Release of the code for the PATHOSnet multimodal neural network for emotion recognition.
Developed by [ARCSlab](https://arcslab.dei.polimi.it) at [PoliMI](https://www.polimi.it).

The implemented network is described in the paper "[Combining Deep and Unsupervised Features for Multilingual Speech Emotion Recognition](https://link.springer.com/chapter/10.1007%2F978-3-030-68790-8_10)"
Please, read the paper for the description of the work and all the references and credits.

## Requirements

It is suggested to install the environment in using Python 3.7.
Package requirements can be found in the `requirements.txt` file inside this directory.
For sake of completeness are reported also here:
```
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
```

## Usage

At run-time use the following code snippets.

Links to download the files with the weights can be found in the `README.md` in the following directories:
- `./checkpoints/`
- `./ghostvlad/pretrained_models/`
- `./MUSE/data/`

(Paths are expressed considering this directory as start point)

### Spanish (ESP)

Multimodal version of PATHOSnet for emotion recognition

Paths to weight files
```python
model_weights_path = "./checkpoints/pathosnet_esp_multimodal.h5" 
vggish_weights_path = "./checkpoints/weights_vggish.h5" 
ghostvlad_weights_path = "./ghostvlad/pretrained_models/ghostvlad_weights.h5" 
word_embeddings_path = "./MUSE/data/wiki.es.vec"
```

Create an instance of the multimodal classifier
```python
from pathosnet import pathosnet_multimodal_classifier

classifier = pathosnet_multimodal_classifier(
    model_weights_path, 
    word_embeddings_path, 
    vggish_weights_path, 
    ghostvlad_weights_path
)
```

Predict label
```python
audio_file_path: str = "..."
transcription: str = "..."

multilabel_prediction, binary_prediction = classifier(audio_file_path, transcription)
# multilabel_prediction is a dictionary: label: str -> predicted_score: float
# binary_prediction is a dictionary: label: str -> predicted_score: float
```


Extract the predicted label
```python
sorted(multilabel_prediction, key=lambda k: -multilabel_prediction[k])[0]
sorted(binary_prediction, key=lambda k: -binary_prediction[k])[0]
```

### Greek (EL)

Voice-analysis version of PATHOSnet for emotion recognition

Paths to weight files
```python
model_weights_path = "./checkpoints/pathosnet_el_audio.h5" 
vggish_weights_path = "./checkpoints/weights_vggish.h5" 
ghostvlad_weights_path = "./ghostvlad/pretrained_models/ghostvlad_weights.h5"
```

Create an instance of the voice classifier
```python
from pathosnet import pathosnet_voice_classifier

classifier = pathosnet_multimodal_classifier(
    model_weights_path, 
    vggish_weights_path, 
    ghostvlad_weights_path
)
```

Predict label
```python
audio_file_path: str = "..."

multilabel_prediction, binary_prediction = classifier(audio_file_path)
# multilabel_prediction is a dictionary: label: str -> predicted_score: float
# binary_prediction is a dictionary: label: str -> predicted_score: float
```


Extract the predicted label
```python
sorted(multilabel_prediction, key=lambda k: -multilabel_prediction[k])[0]
sorted(binary_prediction, key=lambda k: -binary_prediction[k])[0]
```

## Example

Look at the `pathonset_test.py` for an example of how to use the code.

## Cite work

If you are willing to use our code, please cite our work through the following BibTeX entry:
```latex
@inproceedings{scotti2020combining,
  author    = {Vincenzo Scotti and
               Federico Galati and
               Licia Sbattella and
               Roberto Tedesco},
  editor    = {Alberto Del Bimbo and
               Rita Cucchiara and
               Stan Sclaroff and
               Giovanni Maria Farinella and
               Tao Mei and
               Marco Bertini and
               Hugo Jair Escalante and
               Roberto Vezzani},
  title     = {{Combining Deep and Unsupervised Features for Multilingual Speech Emotion
               Recognition}},
  booktitle = {Pattern Recognition. {ICPR} International Workshops and Challenges
               - Virtual Event, January 10-15, 2021, Proceedings, Part {II}},
  series    = {Lecture Notes in Computer Science},
  volume    = {12662},
  pages     = {114--128},
  publisher = {Springer},
  year      = {2020},
  url       = {https://link.springer.com/chapter/10.1007\%2F978-3-030-68790-8_10},
  doi       = {10.1007/978-3-030-68790-8\_10},
}
```

