# %% [markdown]
# # Learning Standards Parser
# 
# ** ! this notebook file contains confidential information ! **
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

def parse_html(filename:str, save_csv:bool=True):
    '''
    Parse HTML file exported from the WeBWorK student progress screen to get student scores.

    :param filename: path to HTML file
    :param save_csv: whether to save the parsed DataFrame as a CSV file
    :return: DataFrame with columns ['login_name', 'problem_num', 'score', 'n_incor', 'webwork_set']
    '''
    # %%
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
    headers = [header.get_text() for header in progress_table.find_all('th')]
    rows = progress_table.find_all('tr')[1:]  # excluding the header row

    # %% [markdown]
    # ### Iterate through table rows and format into DataFrame

    # %%
    # Function to extract student data from a row
    utorid_re = re.compile(r'^(?=.{4,8}$)[a-z]{2}[a-z]*\d*$')
    def extract_student_data(row):
        data = {}
        
        try:
            data["login_name"] = row.find_all('td', string=utorid_re)[0].get_text()

            # Extracting student name, email
            name_email_cell = row.find_all('td')[0]
            data["email"] = name_email_cell.find_all('a')[-1].get_text()
            
            # Extracting total scores
            data["total_score"] = float(row.find_all('td')[1].get_text())
            data["total_outof"] = float(row.find_all('td')[2].get_text())
            
            # Extracting problem scores and attempts
            problems_data = row.find_all('td')[3].get_text().split()
            for i in range(len(problems_data) // 2):
                score = problems_data[i]
                # Setting score to 0 if it's not a valid number
                if not score.replace('.', '', 1).isdigit():
                    score = np.nan
                data[f"problem{i+1}_score"] = float(score)
                data[f"problem{i+1}_n_incor"] = int(problems_data[i + len(problems_data) // 2])
        except Exception as e:
            print(e)
            print(row)
        
        return data

    # Extracting data for each student
    students_data = [extract_student_data(row) for row in rows]

    # Creating a DataFrame
    df = pd.DataFrame(students_data)

    # Keeping only the columns specified by the user
    df = df[['login_name', 'email', 'total_score', 'total_outof'] + [col for col in df.columns if 'problem' in col]]
    df.head()

    # %%
    # get problem indices
    problems = list(set([int(re.match(r'problem(\d+)_',col).group(1)) for col in df.columns if 'problem' in col]))

    all_data = []

    for prob in problems:
        sub_df = df[['login_name', f'problem{prob}_score', f'problem{prob}_n_incor']].copy()
        sub_df.columns = ['login_name', 'score', 'n_incor']
        sub_df['problem_num'] = prob
        all_data.append(sub_df)

    final_df = pd.concat(all_data).reset_index(drop=True)
    final_df = final_df[['login_name', 'problem_num', 'score', 'n_incor']]

    # add webwork number
    final_df['webwork_set'] = int(re.match(r'ww(\d+)', os.path.splitext(filename)[0].split('-')[-1]).group(1))

    if save_csv:
        final_df.to_csv(os.path.splitext(filename)[0] + '_scores.csv', index=False)

    return final_df

