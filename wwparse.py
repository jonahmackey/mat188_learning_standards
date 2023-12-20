# %% [markdown]
# # Webwork Parser
#
# Simeon Wong
# MAT188 2023F at the University of Toronto

# %%
# Imports
import pandas as pd
from bs4 import BeautifulSoup
import re
import os.path
import numpy as np

# %% [markdown]
# ### Parse HTML to get table


def parse_html(filename: str, save_csv: bool = True, stacked: bool = True):
    '''
    Parse HTML file exported from the WeBWorK student progress screen to get student scores.

    :param filename: path to HTML file
    :param save_csv: whether to save the parsed DataFrame as a CSV file
    :param stacked: whether to return a stacked DataFrame (one row per problem) or a wide DataFrame (one row per student, as per the HTML file)
    :return: DataFrame with columns ['login_name', 'problem_num', 'score', 'n_incor', 'webwork_set']
    '''

    # read student progress export
    with open(filename, "r", encoding="utf-8") as file:
        content = file.read()

    # Parsing the content with BeautifulSoup
    soup = BeautifulSoup(content, 'html.parser')

    # Finding all tables in the HTML
    tables = soup.find_all('table')

    # Getting the progress table
    progress_table = tables[0]

    # Extracting headers and rows from the table
    headers = [
        header.get_text()
        for header in progress_table.find_all('tr')[0].find_all('td')
    ]

    # get col indices of important columns
    # login_name_col = np.where(['Login Name' in x for x in headers])[0][0]
    problem_scores_col = np.where(['Problems' in x for x in headers])[0][0]
    score_col = np.where(['Score' in x for x in headers])[0][0]
    total_col = np.where(['Out Of' in x for x in headers])[0][0]

    n_problems = len(headers[problem_scores_col].split())

    rows = progress_table.find_all('tr')[1:]  # excluding the header row

    # Function to extract student data from a row
    # utorid_re = re.compile(r'^(?=.{4,8}$)[a-z]{2}[a-z]*\d*$')

    def extract_student_data(row):
        data = {}

        try:
            rowtd = row.find_all('td')
            data["login_name"] = rowtd[-1].get_text()

            # Extracting student name, email
            # name_email_cell = rowtd[email_col]
            # data["email"] = name_email_cell.find_all('a')[-1].get_text()

            # Extracting total scores
            data["total_score"] = float(rowtd[score_col].get_text())
            
            if rowtd[total_col].get_text().isdigit():
                data["total_outof"] = float(rowtd[total_col].get_text())
            else:
                return {}

            # Extracting problem scores and attempts
            problems_data = row.find_all(
                'td')[problem_scores_col].get_text().split()
            for i in range(n_problems):
                score = problems_data[i]
                # Setting score to 0 if it's not a valid number
                if not score.replace('.', '', 1).isdigit():
                    score = np.nan
                data[f"problem{i+1}_score"] = float(score)

                # check if there's a number of incorrect attempts
                if len(problems_data) > n_problems:
                    data[f"problem{i+1}_n_incor"] = int(
                        problems_data[i + n_problems])

        except Exception as e:
            print('Error parsing row:')
            print(e)
            print(row)

        return data

    # Extracting data for each student
    students_data = [extract_student_data(row) for row in rows]

    # Creating a DataFrame
    df = pd.DataFrame(students_data)
    df = df[['login_name', 'total_score', 'total_outof'] +
            [col for col in df.columns if 'problem' in col]]

    if stacked:
        # get problem indices
        problems = list(
            set([
                int(re.match(r'problem(\d+)+_', col).group(1))
                for col in df.columns if 'problem' in col
            ]))

        all_data = []

        for prob in problems:
            col_names = [x for x in df.columns if f'problem{prob}_' in x]
            col_names.insert(0, 'login_name')

            col_names_clean = [
                x.replace(f'problem{prob}_', '') for x in col_names
            ]

            sub_df = df[col_names].copy()
            sub_df.columns = col_names_clean

            sub_df['problem_num'] = prob
            all_data.append(sub_df)

        final_df = pd.concat(all_data).reset_index(drop=True)
        # final_df = final_df[['login_name', 'problem_num', 'score', 'n_incor']]

        # add webwork number
        fname_re = re.search(r'mat188\-2023f\-([a-z]{2}\d+)r?\.html',
                                       filename)
        final_df['set_id'] = fname_re.group(1)

        final_df['score_key'] = final_df.apply(
            lambda r: f'{r["set_id"]}-{r["problem_num"]:.0f}', axis=1)

    else:
        final_df = df

    if save_csv:
        final_df.to_csv(os.path.splitext(filename)[0] + '_scores.csv',
                        index=False)

    return final_df
