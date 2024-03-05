from typing import Optional

import os
import os.path
import shutil
import pandas as pd
import datetime
import argparse

from tqdm import tqdm


def build_tex(row: pd.Series, args: argparse.Namespace, filename: Optional[str] = None, ):
    filename = filename or row.name

    # row.dropna(inplace=True)
    subset_cols = row.drop('student', level=0).drop('fraction_achieved', level=0)


    with open("./tex_files/ls_report_page.tex", "r") as f:
        template = f.read()

    # make replacements
    template = template.replace(
        "REPLfullnameREPL",
        f"{row[('student', 'first_name')]} {row[('student', 'last_name')]}")
    template = template.replace("REPLutoridREPL",
                                str(row[('student', 'student_id')]))

    # build summary table
    summary_data = subset_cols.groupby(level='modality').agg(
        ['count', 'sum'])

    summary_tex = []
    for modality, (total, achieved) in summary_data.iterrows():
        summary_tex.append(
            f'{modality} & {achieved:.0f} & {total:.0f} \\\\ \\midrule')
    template = template.replace("REPLsummarytableREPL", '\n'.join(summary_tex))

    # build detailed table
    rows = []
    for modality, key in subset_cols.index:
        if row[(modality, key)] == 0:
            achieved = 'No'
        elif row[(modality, key)] == 1:
            achieved = 'Yes'
        else:
            achieved = r'\textit{Not tested}'

        tblrow = f'\\PulledLS{{{key}}} & {achieved} & {modality} \\\\ \\midrule'
        rows.append(tblrow)

    template = template.replace("REPLdetailedtableREPL", '\n'.join(rows))

    with open(f"{args.output_path}/ls_reports/tex/combined.tex", "a") as f:
        f.write(template)

def run(args: argparse.Namespace):
    student_progress = pd.read_csv(f'{args.output_path}/standards_achieved.csv',
                                   header=[0, 1],
                                   index_col=0)


    roster = pd.read_csv(f'{args.data_path}/mat188-2023f-roster.csv',
                        index_col=3)['Student Number']
    student_progress[('student',
                    'student_id')] = [roster[x] for x in student_progress.index]

    if not os.path.exists(f'{args.output_path}/ls_reports/tex'):
        os.makedirs(f'{args.output_path}/ls_reports/tex')

    if not os.path.exists(f'{args.output_path}/ls_reports/pdf'):
        os.makedirs(f'{args.output_path}/ls_reports/pdf')

    # insert an empty first row into the dataframe
    templaterow = pd.DataFrame(columns=student_progress.columns,
                            index=['_template'])
    templaterow.iloc[0, :-3] = 0
    templaterow[[('student', 'first_name'), ('student', 'last_name'),
                ('student', 'student_id')]] = ' '
    student_progress = pd.concat([templaterow, student_progress])

    # write header
    if os.path.exists(f'{args.output_path}/ls_reports/tex/combined.tex'):
        os.remove(f'{args.output_path}/ls_reports/tex/combined.tex')

    shutil.copy('./tex_files/ls_report_header.tex', f'{args.output_path}/ls_reports/tex/combined.tex')

    # for testing, only build first 20 students
    if args.debug:
        student_progress = student_progress.iloc[::len(student_progress) // 20]

    for ri, row in tqdm(student_progress.iterrows(),
                        desc='Building reports',
                        total=len(student_progress)):
        filename = ri

        build_tex(row, args, filename=filename)

    # end document
    with open(f"{args.output_path}/ls_reports/tex/combined.tex", "a") as f:
        f.write("\n\\end{document}")

    # compile
    t1 = datetime.datetime.now()
    os.system(
        f'pdflatex -output-directory {args.output_path}/ls_reports/pdf {args.output_path}/ls_reports/tex/combined.tex'
    )

    # remove everything that doesn't end with pdf
    for f in [f'{args.output_path}/ls_reports/pdf/combined.aux', f'{args.output_path}/ls_reports/pdf/combined.log', f'{args.output_path}/ls_reports/pdf/combined.out']:
        if os.path.exists(f):
            os.remove(f)

    print(f'Built PDF in {(datetime.datetime.now() - t1).total_seconds()} s.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Build learning standard reports.')
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Run in debug mode, only generate 20 reports for testing.')
    args = parser.parse_args()

    run(args)
    