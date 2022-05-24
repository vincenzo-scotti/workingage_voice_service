import os
import subprocess

import pandas as pd

SOURCE_PATH = '/securestorage/Storage/'
DEST_PATH = '/securestorage/short_term_tests_data/'

N_SUBJECTS = 10  # TODO set correct value

EXCEL_FILE_PATH = '/home/workingage/WACode/'  # TODO complete path

COLUMNS = ['audio_file_path', 'transcription', 'emotion_label']


def main():

    if not os.path.exists(DEST_PATH):
        os.mkdir(DEST_PATH)

    df = pd.concat([pd.read_excel(EXCEL_FILE_PATH, sheet_name=i) for i in range(N_SUBJECTS)])

    data = []
    for _, row in df.iterrows():
        source_file_path = os.path.join(SOURCE_PATH, row.file_id)
        out_file_name = os.path.splitext(row.file_id)[0] + '.wav'
        dest_file_path = os.path.join(DEST_PATH, out_file_name)

        subprocess.run(['ffmpeg', '-y', '-i', source_file_path, dest_file_path])

        try:
            transcription = row.transcription
        except:
            transcription = ""

        data.append((out_file_name, transcription, row.emotion_label))

    df = pd.DataFrame(data, columns=COLUMNS, )
    df.to_csv(os.path.join(DEST_PATH, 'metadata.csv'), index=False)

    return 0

if __name__ == '__main__':
    main()
