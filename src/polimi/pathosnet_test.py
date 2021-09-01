import params

import os
import sys
from argparse import ArgumentParser

import pandas as pd
import numpy as np

from sklearn.metrics import classification_report, roc_auc_score, accuracy_score, balanced_accuracy_score
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support, roc_curve

from pathosnet import pathosnet_multimodal_classifier, pathosnet_voice_classifier


def main(arguments):
    # Read command line arguments   ------------------------------------------------------------------------------------
    args_parser = ArgumentParser()
    # Data arguments
    args_parser.add_argument('--csv_file', type=str, required=True,
                             help="Path to the csv file hosting the information about the test data.")
    args_parser.add_argument('--data_path', type=str, required=True,
                             help="Path to the main directory hosting the data to label.")
    # Data frame content arguments
    args_parser.add_argument('--audio_file_path_col_name', type=str, default='audio_file_path',
                             help="Name of the column hosting the audio file path in the data frame.")
    args_parser.add_argument('--transcription_col_name', type=str, default='transcription',
                             help="Name of the column hosting the transcription in the data frame.")
    args_parser.add_argument('--label_col_name', type=str, default='emotion_label',
                             help="Name of the column hosting the label in the data frame.")
    # Model paths arguments
    args_parser.add_argument('--model_weights_path', type=str, required=True,
                             help="Path to the h5 file hosting PATHOSnet model weights.")
    args_parser.add_argument('--vggish_weights_path', type=str, required=True,
                             help="Path to the h5 file hosting VGGish model weights.")
    args_parser.add_argument('--ghostvlad_weights_path', type=str, required=True,
                             help="Path to the h5 file hosting GhostVlad model weights.")
    args_parser.add_argument('--word_embeddings_path', type=str,
                             help="Path to the file hosting the word embeddings, used only in multimodal analysis.")
    # Model related arguments
    args_parser.add_argument('--modality', type=str, default='multimodal', choices=['multimodal', 'voice'],
                             help="Modality to use in the analysis.")
    # Output arguments
    args_parser.add_argument('--output_id', type=str, required=True,
                             help="Additional identifier for the output files to recognize the experiment.")
    # Misc arguments
    args_parser.add_argument('--verbose', type=bool, default=False,
                             help="Whether to be verbose or not.")
    
    args = args_parser.parse_args(arguments)

    # Load data  -------------------------------------------------------------------------------------------------------
    if args.verbose:
        print("Loading CSV file...")
    data_df = pd.read_csv(args.csv_file)
    if args.verbose:
        print("CSV file loaded.\n")

    # Load models  -----------------------------------------------------------------------------------------------------
    if args.verbose:
        print("Loading model...")
    classifier_args = (args.model_weights_path,)
    if args.modality == 'multimodal':
        classifier_args = classifier_args + (args.word_embeddings_path,)
    classifier_args = classifier_args + (args.vggish_weights_path,  args.ghostvlad_weights_path)
    if args.modality == 'multimodal':
        classifier = pathosnet_multimodal_classifier(*classifier_args, verbose=args.verbose)
    else:
        classifier = pathosnet_voice_classifier(*classifier_args, verbose=args.verbose)
    if args.verbose:
        print("Model loaded.\n")

    # Perform analysis  ------------------------------------------------------------------------------------------------
    output_data = []
    if args.verbose:
        print("Starting analysis of {} files...".format(data_df.shape[0]))
    for index, row in data_df.iterrows():
        if args.verbose:
            print("Analysisng item {}/{}.".format(index + 1, data_df.shape[0]))
        # Get arguments
        input_args = (os.path.join(args.data_path, row[args.audio_file_path_col_name]),)
        if args.modality == 'multimodal':
            input_args = input_args + (row[args.transcription_col_name],)
        # Extract dictionary with label proabilities
        multilabel_prediction, binary_prediction = classifier(*input_args)
        output_data.append(input_args +
                           (row[args.label_col_name], sorted(multilabel_prediction,
                                                             key=lambda k: -multilabel_prediction[k])[0]) +
                           tuple(multilabel_prediction.values()) +
                           (params.BINARY_CONVERSION_DICT[row[args.label_col_name]],
                            sorted(binary_prediction, key=lambda k: -binary_prediction[k])[0]) +
                           tuple(binary_prediction.values()))

    if args.verbose:
        print("Analysis finished.\n")

    # Save results   ---------------------------------------------------------------------------------------------------
    if args.verbose:
        print("Saving results...")
    output_df_path = os.path.splitext(args.csv_file)[0] + '_results_' + args.output_id
    output_df_path_ = output_df_path + '.csv'
    i = 1
    while os.path.isfile(output_df_path_):
        output_df_path_ = output_df_path + '_' + str(i) + '.csv'
    output_df_path = output_df_path_
    output_df_columns = ['File path'] + (['Trascription'] if args.modality == 'multimodal' else []) + \
                        ['Target label', 'Predicted label'] + [l + ' probability' for l in params.LABELS] + \
                        ['Target binary label', 'Predicted binary label'] + \
                        [l + ' probability' for l in params.BINARY_LABELS]
    analysis_df = pd.DataFrame(data=output_data, columns=output_df_columns)
    analysis_df.to_csv(path_or_buf=output_df_path, index=False)
    if args.verbose:
        print("Results saved in {} file.\n".format(output_df_path))

    # Compute test scores  ---------------------------------------------------------------------------------------------

    if args.verbose:
        print("Computing test scores...")
    output_scores_path = os.path.splitext(args.csv_file)[0] + '_scores_' + args.output_id
    output_scores_path_ = output_scores_path + '.txt'
    i = 1
    while os.path.isfile(output_scores_path_):
        output_scores_path_ = output_scores_path + '_' + str(i) + '.txt'
    output_scores_path = output_scores_path_
    # Multi-label
    y_hat = analysis_df[[l + ' probability' for l in params.LABELS]].to_numpy()
    y = np.zeros(y_hat.shape, dtype=np.float)
    map_dict = dict(zip(params.LABELS, range(len(params.LABELS))))
    for index, row in analysis_df.iterrows():
        y[index, map_dict[row['Target label']]] = 1.0
    # Binary-label
    y_hat_binary = analysis_df[[l + ' probability' for l in params.BINARY_LABELS]].to_numpy()
    y_binary = np.zeros(y_hat_binary.shape, dtype=np.float)
    map_dict = dict(zip(params.BINARY_LABELS, range(len(params.BINARY_LABELS))))
    for index, row in analysis_df.iterrows():
        y_binary[index, map_dict[row['Target binary label']]] = 1.0
    fpr, tpr, thresholds = roc_curve(y_binary[:, 0], y_hat_binary[:, 0])
    threshold = thresholds[np.argmin(np.linalg.norm(np.array([0., 1.] -
                                                             np.concatenate([fpr.reshape(-1, 1), tpr.reshape(-1, 1)],
                                                                           axis=-1)), axis=-1))]

    with open(output_scores_path, 'w') as f:
        f.write("MULTIPLE LABELS -----------------------------------------------------\n\n")
        f.write(str(classification_report(np.argmax(y, axis=-1), np.argmax(y_hat, axis=-1),
                                          target_names=params.LABELS, output_dict=True)))
        f.write("\n\n")
        f.write(str({'accuracy': accuracy_score(np.argmax(y, axis=-1), np.argmax(y_hat, axis=-1)),
                     'weighted accuracy': balanced_accuracy_score(np.argmax(y, axis=-1), np.argmax(y_hat, axis=-1))}))
        f.write("\n\n")
        f.write(str({'auc of roc score': roc_auc_score(y, y_hat, multi_class='ovr')}))
        f.write("\n\n")
        f.write(str({'confusion matrix': confusion_matrix(np.argmax(y, axis=-1), np.argmax(y_hat, axis=-1),
                                                          normalize='true')}))
        f.write("\n\n")
        f.write("---------------------------------------------------------------------\n\n")
        f.write("BINARY LABELS -------------------------------------------------------\n\n")
        f.write(str(dict(zip(['precision', 'recall', 'fscore'],
                             precision_recall_fscore_support(np.argmax(y_binary, axis=-1),
                                                             np.argmax(y_hat_binary, axis=-1),
                                                             average='weighted')[:3]))))
        f.write("\n\n")
        f.write(str({'accuracy': accuracy_score(np.argmax(y_binary, axis=-1), np.argmax(y_hat_binary, axis=-1)),
                     'weighted accuracy': balanced_accuracy_score(np.argmax(y_binary, axis=-1),
                                                                  np.argmax(y_hat_binary, axis=-1))}))
        f.write("\n\n")
        f.write(str({'auc of roc score': roc_auc_score(y_binary, y_hat_binary, multi_class='ovr')}))
        f.write("\n\n")
        f.write(str({'confusion matrix': confusion_matrix(np.argmax(y_binary, axis=-1),
                                                          np.argmax(y_hat_binary, axis=-1),
                                                          normalize='true')}))
        f.write("\n\n")
        f.write("Threshold {}\n\n".format(threshold))
        f.write(str(dict(zip(['precision', 'recall', 'fscore'],
                             precision_recall_fscore_support(y_binary[:, 0], y_hat_binary[:, 0] >= threshold,
                                                             average='weighted')[:3]))))
        f.write("\n\n")
        f.write(str({'accuracy': accuracy_score(y_binary[:, 0], y_hat_binary[:, 0] >= threshold),
                     'weighted accuracy': balanced_accuracy_score(y_binary[:, 0], y_hat_binary[:, 0] >= threshold)}))
        f.write("\n\n")
        f.write(str({'confusion matrix': confusion_matrix(y_binary[:, 0], y_hat_binary[:, 0] >= threshold,
                                                          normalize='true')}))
        f.write("\n\n")
        f.write("---------------------------------------------------------------------\n\n")
    if args.verbose:
        print("Test scores computed and saved in {} file.\n".format(output_scores_path))

    return 0


if __name__ == '__main__':
    main(sys.argv[1:])
