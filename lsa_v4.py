# # Learning Standards Analysis
#
# Simeon Wong
# MAT188 2023F at the University of Toronto

# %%
import pandas as pd
import numpy as np
import glob
from itertools import compress
import wwparse
from tqdm import tqdm
import re
import argparse
import multiprocessing as mp
import psutil
import functools
import os, os.path

nthreads = psutil.cpu_count(logical=False) - 1

def extract_tutorial_number(x: str):
    rel = re.search(r'TUT(\d{4})', x)

    if rel is None:
        return pd.NA
    else:
        return int(rel.group(1))


def grade_by_ls(args, lsref):
    this_student, this_student_scores = args

    this_standards_achieved = pd.Series(index=pd.MultiIndex.from_frame(
        lsref[['modality', 'standard']].drop_duplicates()),
                                        name=this_student)

    for this_idx, this_standard in lsref.iterrows():
        question_keys = [x.strip() for x in this_standard['reqs'].split(',')]

        if '|' in question_keys[0]:
            n_correct_required = int(question_keys[0].split('|')[0])
            question_keys[0] = question_keys[0].split('|')[1]
            ratio_required = n_correct_required / len(question_keys)
        else:
            ratio_required = 1

        # get correctness for each question
        question_isgraded = [
            ~np.any(this_student_scores.loc[x, 'is_graded'] == False)
            if x in this_student_scores.index else True for x in question_keys
        ]
        question_iscorrect = [
            np.any(this_student_scores.loc[x, 'correct'])
            if x in this_student_scores.index else False for x in question_keys
        ]

        # check if the required number of questions are correct
        if np.sum(question_isgraded) == 0:
            ls_cor = np.nan
        else:
            corsum = np.nansum(question_iscorrect)
            ls_cor = int(
                (corsum >= 1)
                and (corsum / np.sum(question_isgraded) >= ratio_required))

        # if all requirements are met, set this standard to true
        this_standards_achieved[tuple(this_standard[['modality',
                                                     'standard']])] = ls_cor

    return this_standards_achieved


def load_data(args: argparse.Namespace):
    #######################################################################
    ## Data loading

    # import table of learning standards
    lsref = pd.read_excel('../Data/standards_lookup_table.xlsx',
                          sheet_name='grading')
    lsref = lsref.set_index('standard').stack().reset_index()
    lsref.columns = ['standard', 'modality', 'reqs']

    # ignore exams
    if not args.compute_exams:
        lsref = lsref[lsref['modality'] != 'exam']

    # load tutorial SBG assignments
    tut_day_tbl = pd.read_excel('../Data/standards_lookup_table.xlsx',
                                sheet_name='tut_dates',
                                index_col='tutorial')
    tut_sbg_assigned = pd.read_excel('../Data/standards_lookup_table.xlsx',
                                     sheet_name='sbg_assigned',
                                     index_col=0)

    # load roster
    roster = pd.read_csv('../Data/mat188-2023f-roster.csv')
    gradebook = pd.read_csv(r"../Data/mat188-2023f-gradebook.csv")
    gradebook = gradebook[~gradebook['SIS User ID'].isna()]
    gradebook = gradebook[['SIS User ID',
                           'Section']].set_index(['SIS User ID'])
    gradebook['tut'] = gradebook['Section'].apply(extract_tutorial_number)
    gradebook['tut_day'] = gradebook['tut'].apply(
        lambda x: tut_day_tbl.loc[x, 'day'])

    roster = roster[roster['UTORid'].isin(
        gradebook.index)]  # drop students who dropped the course

    if args.debug:
        roster = pd.concat(
            (roster[:20], roster[-20:]
             ))  # DEBUGGING: only keep first and last 20 students for speed

    scores = None

    ##### WEBWORK #####
    for filename in glob.glob('../Data/*.html'):
        print(f'Loading {filename}...')
        this_score = wwparse.parse_html(filename, save_csv=False)

        # a question is correct if all parts are correct
        this_score['correct'] = this_score['score'] == 100

        scores = pd.concat([scores, this_score], ignore_index=True)

    ##### TUTORIALS #####
    # get a list of all questions from tutorials
    # - use this to compute which questions are graded by
    all_tut_qs = lsref.loc[lsref['modality'] == 'tutorial', 'reqs'].unique()
    all_tut_qs = [x.split(',') for x in all_tut_qs]
    all_tut_qs = sum(all_tut_qs, [])
    all_tut_qs = [x.split('|')[1] if '|' in x else x for x in all_tut_qs]
    all_tut_qs = [x.strip() for x in all_tut_qs]
    all_tut_qs = list(set(all_tut_qs))

    all_tut_qs_sbg = [
        int(re.search(r'tut\d+\-(\d+)\-\w+', x).group(1)) for x in all_tut_qs
    ]
    all_tut_qs_wk = [
        int(re.search(r'tut(\d+)\-\d+\-\w+', x).group(1)) for x in all_tut_qs
    ]

    def compute_tut_is_graded(utorid: str):
        ''' For a given tutorial day, compute which questions are graded for a given student '''
        tut_day = gradebook.loc[utorid, 'tut_day']

        stu_scores = pd.DataFrame(
            data={
                'login_name': [utorid] * len(all_tut_qs),
                'score_key':
                all_tut_qs,
                'is_graded': [(wk in tut_sbg_assigned.columns) and (
                    tut_sbg_assigned.loc[tut_day, wk] == sbg) for q, sbg, wk in
                              zip(all_tut_qs, all_tut_qs_sbg, all_tut_qs_wk)],
            })

        return stu_scores

    tut_is_graded = list(map(compute_tut_is_graded, tqdm(roster['UTORid'].unique(), desc='SBGs graded by student')))
    tut_is_graded = pd.concat(tut_is_graded, ignore_index=True)

    # load tutorial data
    tut_scores = None
    for filename in glob.glob('../Data/Tutorials-Processed/*TUT*/*_SBG.xlsx'):
        print(f'Loading {filename}...')
        this_score = pd.read_excel(filename)

        # remove sum rows at the bottom
        this_score = this_score[~(this_score['First Name'].isna() & this_score['Last Name'].isna())]

        # merge with roster
        this_score = this_score.merge(roster[['Email', 'UTORid']],
                                      how='left',
                                      on='Email')
        this_score = this_score.rename(columns={'UTORid': 'login_name'})

        # remove empty login names
        this_score = this_score[~this_score['login_name'].isna()
                                & (this_score['login_name'] != '')]

        ls_cols = [x for x in this_score.columns if '|' in x]
        this_score = this_score[ls_cols + ['login_name']]

        for ccol in ls_cols:
            ckey = ccol.split('|')[1].strip()
            this_score = this_score.rename(columns={ccol: ckey})

        # stack into long format
        this_score = this_score.melt(id_vars='login_name',
                                     var_name='score_key',
                                     value_name='correct')

        # check if this LS was tested for this student for this tutorial by matching it to the SBG column
        this_score['ls'] = this_score['score_key'].apply(
            lambda x: re.search(r'.*\d+\-(\d+)\-\w+', x).group(1)).astype(int)
        this_score.drop(columns=['ls'], inplace=True)

        # concat
        tut_scores = pd.concat([tut_scores, this_score], ignore_index=True)

    # merge with list of required questions for each student
    tut_scores = tut_scores.groupby(['login_name',
                                     'score_key']).max().reset_index()
    tut_scores = tut_scores.set_index(['login_name', 'score_key'])['correct']
    tut_is_graded['correct'] = tut_is_graded.apply(
        lambda x: tut_scores.loc[(x['login_name'], x['score_key'])]
        if (x['login_name'], x['score_key']) in tut_scores.index else False,
        axis=1)
    tut_is_graded['correct'] = tut_is_graded['correct'].fillna(False)
    # tut_is_graded['correct'][~tut_is_graded['is_graded']] = np.nan

    scores = pd.concat([scores, tut_is_graded], ignore_index=True)

    # load midterm data
    if args.compute_exams:
        for filename in glob.glob('../Data/*Midterm*/*.csv'):
            print(f'Loading {filename}...')
            this_score = pd.read_csv(filename)

            # remove sum rows
            this_score = this_score[~this_score['SID'].isna()]

            # merge with roster
            this_score = this_score.merge(roster[['Email', 'UTORid']],
                                          how='left',
                                          on='Email')
            this_score = this_score.rename(columns={'UTORid': 'login_name'})

            # parse score key
            ls_cols = [x for x in this_score.columns if '|' in x]
            this_score = this_score[['login_name'] + ls_cols]
            this_score.columns = ['login_name'
                                  ] + [x.split('|')[1] for x in ls_cols]

            # stack into long format
            this_score = this_score.melt(id_vars='login_name',
                                         var_name='score_key',
                                         value_name='correct')

            # check if correct has type string, convert to int
            this_score['correct'] = this_score['correct'].map({
                'TRUE': 1,
                'FALSE': 0,
                True: 1,
                False: 0
            })

            # concat
            scores = pd.concat([scores, this_score], ignore_index=True)

    # load manually scored items
    manual_scores = pd.read_excel('../Data/mat188-2023f-manualscores.xlsx')
    scores = pd.concat((scores, manual_scores), ignore_index=True)

    # remove score rows without an associated utorid
    scores = scores[scores['login_name'] != ''].dropna(subset=['login_name'])

    # save for debugging
    scores.to_csv('../Output/debug_raw_scores.csv')

    return scores, roster, lsref

def run(args: argparse.Namespace):
    scores, roster, lsref = load_data(args)

    #######################################################################
    # Which learning standards has each student achieved?
    # remove requirements that don't have associated questions in our score db
    uniq_scorekey = scores['score_key'].unique()
    for this_idx, this_standard in lsref.iterrows():
        if (this_standard['reqs'] == '') or pd.isna(this_standard['reqs']):
            continue

        # parse standards
        if '|' in this_standard['reqs']:
            n_req, reqstr = this_standard['reqs'].split('|')[0:2]
            n_req = int(n_req)
            reqs = reqstr.split(',')
        else:
            reqs = this_standard['reqs'].split(',')
            n_req = len(reqs)

        in_db = [tr in uniq_scorekey for tr in reqs]

        # only keep standards that have questions in the db
        reqs = list(compress(reqs, in_db))

        n_req = min(n_req, len(reqs))

        # reconstruct reqs string
        if n_req > 0:
            lsref.loc[this_idx, 'reqs'] = str(n_req) + '|' + (','.join(reqs))
        else:
            lsref.loc[this_idx, 'reqs'] = pd.NA

    # remove empty standards with no associated items
    lsref = lsref[~lsref['reqs'].isna()]

    # initialize output table
    standards_achieved = pd.DataFrame(index=scores['login_name'].unique(),
                                      columns=pd.MultiIndex.from_frame(lsref[[
                                          'modality', 'standard'
                                      ]].drop_duplicates()))

    # with multiple threads, call the grading function for each student
    with mp.Pool(nthreads) as p:
        standards_achieved = pd.concat(tqdm(
            p.imap_unordered(
                functools.partial(grade_by_ls, lsref=lsref),
                zip(roster['UTORid'].unique(), [
                    scores[scores['login_name'] == this_student].set_index(
                        'score_key')
                    for this_student in roster['UTORid'].unique()
                ]),
                chunksize=10,
            ),
            total=len(roster['UTORid'].unique()),
            desc='Evaluating learning standards by student'),
                                       axis=1).T

    # compute fraction standards achieved across each modality
    modalities = lsref['modality'].unique()
    for this_modality in modalities:
        this_modality_standards = standards_achieved.loc[:, this_modality]
        standards_achieved.loc[:,
                               ('fraction_achieved',
                                this_modality)] = this_modality_standards.mean(
                                    axis=1, skipna=True)

    # Join student names for easy lookup
    roster.set_index('UTORid', inplace=True)
    standards_achieved = standards_achieved[standards_achieved.index.isin(
        roster.index)]
    standards_achieved[('student',
                        'first_name')] = roster.loc[standards_achieved.index,
                                                    'First Name']
    standards_achieved[('student',
                        'last_name')] = roster.loc[standards_achieved.index,
                                                   'Last Name']
    standards_achieved.sort_index(axis=0, inplace=True)

    standards_achieved.to_csv('../Output/standards_achieved.csv')



#######################################################################
# Parse arguments
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--compute-exams', action='store_true')
    parser.add_argument('--generate-reports', action='store_true')
    args = parser.parse_args()

    if not os.path.exists('../Output'):
        os.makedirs('../Output')

    run(args)

    if args.generate_reports:
        import make_ls_report_v2
        make_ls_report_v2.run(args)
