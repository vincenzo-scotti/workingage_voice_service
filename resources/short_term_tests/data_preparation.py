import os
import subprocess

import pandas as pd

SOURCE_PATH = '/securestorage/original_short_term_tests_data/'
DEST_PATH = '/securestorage/short_term_tests_data/'

N_SUBJECTS = 7  # EL is 5, ESP is 7

EXCEL_FILE_PATH = '/securestorage/original_short_term_tests_data/metadata.xlsx'

COLUMNS = ['audio_file_path', 'transcription', 'emotion_label']


def main():

    if not os.path.exists(DEST_PATH):
        os.mkdir(DEST_PATH)

    df = pd.concat([pd.read_excel(EXCEL_FILE_PATH, sheet_name=f'sheet_{i}') for i in range(N_SUBJECTS)])
    # Get column names of other parts
    part_cols = sorted([col_name for col_name in df.columns if col_name.startswith('part_')])
    # Remove missing file rows
    df = df[df.file_id.notna()]
    # Substitute NaNs with empty string
    df = df.fillna("")

    data = []
    for _, row in df.iterrows():
        source_file_path = os.path.join(SOURCE_PATH, row.file_id)
        out_file_name = os.path.splitext(row.file_id)[0] + '.wav'
        dest_file_path = os.path.join(DEST_PATH, out_file_name)
        # Prepare ffmpeg conversion command
        cmd = ['ffmpeg', '-y', '-i', source_file_path]
        # If the file is composed by multiple parts merge them
        if not all(part == '' for part in row[part_cols]):
            n = 1
            for part_id in part_cols:
                additional_file_name = row[part_id]
                if not additional_file_name == '':
                    cmd += ['-i', os.path.join(SOURCE_PATH, additional_file_name)]
                    n += 1
            cmd += [
                '-filter_complex',
                f'{str().join(f"[{i}:0]" for i in range(n))}concat=n={n}:v=0:a=1[out]',
                '-map',
                '[out]'
            ]
        cmd.append(dest_file_path)
        subprocess.run(cmd)

        try:
            transcription = row.transcription
        except:
            transcription = ""

        data.append((out_file_name, transcription, row.emotion_label))
    # Save the meta data into a CSV file
    out_df = pd.DataFrame(data, columns=COLUMNS)
    out_df.to_csv(os.path.join(DEST_PATH, 'metadata.csv'), index=False)

    return 0


if __name__ == '__main__':
    main()

"""
for _, row in out_df.iterrows():
    if not os.path.exists(os.path.join(DEST_PATH, row.audio_file_path)):
        print(row.audio_file_path)
"""

