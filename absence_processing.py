#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import json
import questionary
import pandas as pd
from pathlib import Path
import tempfile
from thefuzz import fuzz
import os
import pickle
import sys
sys.setrecursionlimit(10000) # required for making pickling work TODO: remove this later

# Google Sheets related imports
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

#Canvas API related imports
from canvasapi import Canvas

# Gradescope related imports
from gradescope_api.pyscope import *
GRADESCOPE_USERNAME = os.environ.get("GRADESCOPE_USERNAME")
GRADESCOPE_PASSWORD = os.environ.get("GRADESCOPE_PASSWORD")
if not GRADESCOPE_USERNAME or not GRADESCOPE_PASSWORD:
    print("You gotta set the Gradescope username and password in your environment bro! I won't proceed without it.")
    print("Run the following commands in your terminal:")
    print("export GRADESCOPE_USERNAME=<your username>")
    print("export GRADESCOPE_PASSWORD=<your password>")
    print("You can also set these in your ~/.bashrc or ~/.zshrc file")
    raise SystemExit(101)


def questionary_select(objs: dict, prompt="Make a choice:"):
    '''
    Prompts the user to select from a list of items
    objs: dict
          Keys are string representation for the object
          Values are actual objects to be selected
    prompt: str: The prompt string
    '''
    keys = list(objs.keys())
    choices = [str(index)+"___"+choice for index, choice in enumerate(keys)]
    selected = questionary.select(
        prompt,
        choices=choices).ask()
    selected = int(selected.split('___')[0])
    return objs[keys[selected]]


def gsheets(sheetID, sheetRange) -> list:
    '''
    Gets the Google Sheet
    '''
    creds = None
    # The file google_token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('google_token.json'):
        creds = Credentials.from_authorized_user_file('google_token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'google_credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('google_token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('sheets', 'v4', credentials=creds)

        # Processing the second sheet
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=sheetID, range=sheetRange).execute()
        values = result.get('values', [])

        return values

    except HttpError as err:
        print(err)
        return None


def canvas_init():
    '''
    Initializes the canvas object and returns the course object, and the userdb
    '''

    if os.path.exists('canvas_token.json'):
        with open('canvas_token.json', 'r') as f:
            API_KEY = json.load(f)['API_KEY']
    else:
        API_KEY = questionary.password("Enter your Canvas API key:").ask()
        print("This key is being saved for future use in the current folder inside canvas_token.json file. Make sure it stays safe.")
        with open('canvas_token.json', 'w') as f:
            json.dump({"API_KEY": API_KEY}, f)

    API_URL = "https://canvas.tamu.edu"
    canvas = Canvas(API_URL, API_KEY)

    #Getting Courses and selecting one of them
    print("Loading the Canvas courses for you. This may take a few seconds.")
    courses = list(canvas.get_courses())
    choices = [str(i)+"___"+c.name+". ID = "+str(c.id) for i,c in enumerate(courses)]
    selected = questionary.select(
        "Select Canvas course:",
        choices=choices).ask()
    selected = int(selected.split('___')[0])
    course = courses[selected]

    #Preparing the USER-DB, a dict of the form: {id: {'name': name, 'email': email}}
    users = course.get_users()
    userdb = {}
    for user in users:
        userdb[user.id] = {'name': user.short_name, 
                           'email': user.email}

    return course, userdb

def canvas_get_assignment_submissions(course, prompt="Select assignment:") -> list:
    '''
    Returns submissions for an assignment for a course
    '''
    #Getting asses and selecting one of them
    print("Loading the Canvas assignments for you. This may take a few seconds.")
    asses = list(course.get_assignments())
    choices = [str(i)+"___"+ass.name+". ID = "+str(ass.id) for i,ass in enumerate(asses)]
    selected = questionary.select(
        prompt,
        choices=choices).ask()
    selected = [ int(selected.split('___')[0]), ]
    asses = [asses[i] for i in selected]

    subs = [] #Submissions
    for ass in asses:
        subs += ass.get_submissions(include="submission_comments")

    return subs


def gradescope_init():

    conn = GSConnection()
    conn.login(GRADESCOPE_USERNAME, GRADESCOPE_PASSWORD)

    print(conn.state)
    conn.get_account()

    courses = []
    #conn.account.instructor_courses is a dict. Iterate over its key and value
    for _, course in conn.account.instructor_courses.items():
        courses.append(course)

    # prompt the user to choose a course
    choices = { c.name+". ID = "+str(c.cid) : c for i,c in enumerate(courses) }
    course = questionary_select(choices, "Select the Gradescope course:")

    # course = conn.account.instructor_courses['569119']
    course._lazy_load_assignments()

    # ass = course.assignments['[HW Redemption] Image Scaling']
    return course


def gsheets_init(homework_name_tokens, gs_ass_mapping):
    '''
    Loads the data from GSheets and returns the dataframe containing unprocessed absences
    '''
    '''
    newdf.columns
    Index(['Timestamp', 'Email Address', 'Name', 'UIN', 'CSCE Section',
           'Instructor', 'Type of request',
           'Please explain your absence or make an appeal for why it should be an excused absence.',
           'Explicit Starting Date stated in the documentation.',
           'Explicit Ending Date stated in the documentation', 'Things impacted',
           'If a LW or HW assignment was affected, what was the name of the assignment?',
           'Upload any documentation related to your absence or your request for an excused absence.',
           'Number of Days', 'Homework Name', 'Labwork Date', 'Unnamed: 16',
           'Unnamed: 17', 'Request Processed', 'Post Request Details'],
          dtype='object')
    '''
    # types of requests:
    #  ['Homework Late Day Pool' 'Excused Absence' 'Labwork Free Absence']
    get = questionary.confirm("Do you want to download the latest data from Google Sheets?").ask()
    if get:
        # Get the latest data from Google Sheets
        print("Getting the latest data from Google Sheets...")
        # Get the latest data from Google Sheets
        sheetID = "1_m7eO_dYJjXwajyGFqEwn7GB4LmbDOMk0Ru6ALLpBfY"
        sheetRange = "Form Responses 1!A:T"
        values = gsheets(sheetID, sheetRange)
        if values:
            # Convert to a dataframe
            df = pd.DataFrame(values[1:], columns=values[0])
            # Save the dataframe
            df.to_csv("absence.csv", index=False)
            print("Data saved to data/absence.csv")
        else:
            print("Error getting data from Google Sheets")
    else:
        print("Using existing data in absence.csv")
    # filter the rows
    df = pd.read_csv("absence.csv")
    df.index = df.index + 2
    df.fillna('', inplace=True)

    desired_row_ranges = [[620, 669], [1015, 1049], [1340, 1374], [1685, 1724]] #These rows are allocated to me
    newdf = df.loc[desired_row_ranges[0][0]:desired_row_ranges[0][1], :]
    for row_range in desired_row_ranges[1:]:
        newdf = newdf.append(df.loc[row_range[0]:row_range[1], :])
    newdf = newdf[newdf["Type of request"] == "Homework Late Day Pool"]
    # remove with column "Request Processed" as "Yes", "Pending", "No"
    newdf = newdf[newdf["Request Processed"] != "Yes"]
    newdf = newdf[newdf["Request Processed"] != "Pending"]
    newdf = newdf[newdf["Request Processed"] != "No"]
    # remove rows if there are more than one row with the same email and homework name
    newdf = newdf.drop_duplicates(subset=["Email Address", "Homework Name"], keep=False)

    donedf = df[df["Request Processed"] == "Yes"]
    donedf = donedf[donedf["Type of request"] == "Homework Late Day Pool"]

    # refine the column Homework Name using intermediary tokens and mapping
    def refine_homework_name(x):
        for token in homework_name_tokens:
            if token.lower() in x.lower():
                best_match, _ = find_best_match(token, gs_ass_mapping.keys())
                return best_match
        return x
    newdf["Homework Name"] = newdf["Homework Name"].apply(lambda x: refine_homework_name(x))
    donedf["Homework Name"] = donedf["Homework Name"].apply(lambda x: refine_homework_name(x))

    return newdf, donedf


# Function to find the best match using fuzzywuzzy
def find_best_match(variant, originals) -> (str, int):
    '''
    variant: The variant string
    originals: The list of original strings to compare against
    '''
    best_match, highest_score = None, 0
    for original in originals:
        if original.lower() in variant.lower():
            return original, 100
        score = fuzz.ratio(original, variant)
        if score > highest_score:
            best_match, highest_score = original, score
    return best_match, highest_score


def process_late_hw(row, gs_assignments_actual, gs_assignments_redemption, gs_ass_mapping, 
                    homework_name_tokens, canvas_late_submissions, userdb):
    '''
    Process late homework
    '''
    #  import ipdb; ipdb.set_trace()
    # get the assignment name
    hw_name = row['Homework Name']
    email = row['Email Address']

    # get the Gradescope HW name using intermediary tokens
    best_match, highest_score = find_best_match(hw_name, homework_name_tokens)
    if highest_score < 90:
        print(f"Can't process Homework Late Day Pool for {row['Name']}. \
                Best match for {hw_name} is {best_match} with score {highest_score}")
        return False
    #  hw_name = best_match
    hw_name, _ = find_best_match(best_match, gs_assignments_actual.keys())

    # get the assignment objects
    hw_actual = gs_assignments_actual[hw_name]
    hw_redemption = gs_assignments_redemption[gs_ass_mapping[hw_name]]
    #  if not hw_redemption.submissions:
        #  print(f"Getting submissions for {hw_redemption.name}. Wait a while...")
        #  hw_redemption.get_submissions()
    #  submission = next(sub for sub in hw_redemption.submissions if sub.email == email)

    # get the highest scoring submission from the redemption assignment, and get its zip file
    submission_redemption = hw_redemption.get_submission(email=email)
    submission_actual = hw_actual.get_submission(email=email)
    if submission_actual:
        if submission_actual.score == submission_redemption.score:
            print("This homework has probably been processed. \
                  I see that there is a submission already uploaded on the original homework.")
            return False
    submission_zip_resp = course_gs.session.get('https://www.gradescope.com/courses/'+
                                                course_gs.cid+'/assignments/'+hw_redemption.aid+
                                                '/submissions/'+submission_redemption.subid+'.zip')
    with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_file:
        temp_file.write(submission_zip_resp.content)
        temp_file_path = temp_file.name  # Store the temporary file path

    # Compare the submission time of the submission with the due date of actual homework
    # if the submission is within the 4 days after due date, then we can post the submission
    time_diff = submission_redemption.time - hw_actual.due_date
    late_days = time_diff.days + 1
    if late_days > 4:
        print(f"Submission for {row['Name']} is not within 4 days of due date")
        os.remove(temp_file_path)
        return False

    # get the late days from canvas by matching user email
    canvas_sub = next(sub for sub in canvas_late_submissions if email == userdb[sub.user_id]['email'])
    if not canvas_sub.score:
        late_score = 0
    else:
        late_score = int(canvas_sub.score)
    if late_score + late_days > 10:
        print(f"Can't process Homework Late Day Pool for {row['Name']}. \
                Late days requested: {late_days}, Late days used: {late_score}")
        os.remove(temp_file_path)
        return False

    print(f"Processing Homework Late Day Pool for {row['Name']}. \
            Late days requested: {late_days}, Late days used: {late_score}")
    
    # Now we have the zip file from Redemption HW. We gotta transfer it to Actual
    new_submission = hw_actual.post_submission(temp_file_path, submission_redemption.student_id)
    if new_submission:
        print(f"Successfully posted submission for {row['Name']} with rowNum: {index}")
    else:
        print(f"Failed to post submission for {row['Name']} with rowNum: {index}")
        os.remove(temp_file_path)
        return False

    # compare the scores of the two submissions; if they aren't equal, then something went wrong
    if new_submission.score != submission_redemption.score:
        print(f"Score of new submission ({new_submission.score}) is not equal to score of old submission ({submission_redemption.score}). Exiting.")
        os.remove(temp_file_path)
        return False
    
    # Now we update the late days score in Canvas, along with the comments
    comments = f"{hw_name}: late by {late_days} days."
    if canvas_sub.edit(submission={'posted_grade': late_score+late_days}, comment={'text_comment':comments}):
    # if canvas_sub.edit(submission={'posted_grade': late_score+late_days, 'comment[text_comment]': comments}):
        print(f"Successfully updated Canvas submission for {row['Name']} with rowNum: {index}")
        print(f"Everything has been done for this one. You may now update the Google Sheet entry for this one.")
        os.remove(temp_file_path)
        return True
    else:
        print(f"Failed to update Canvas submission for {row['Name']} with rowNum: {index}")
        return False



if __name__ == '__main__':

    pickle_use = False
    # check if data.pkl exists. If it does, load it. If not, initialize everything
    if Path('data.pkl').is_file():
        pickle_use = questionary.confirm("Do you want to load the data from an existing data.pkl?").ask()
        if pickle_use:
            with open('data.pkl', 'rb') as f:
                course_gs, gs_assignments_actual, gs_assignments_redemption, gs_ass_mapping, course_canvas, userdb = pickle.load(f)

    if not pickle_use:
        # Gradescope Init Stuff
        while True:
            course_gs = gradescope_init()
            print(f'You selected "{course_gs.shortname}" for the semester {course_gs.year}')
            if questionary.confirm("Is this the correct Gradescope course?").ask():
                break
            else:
                print("Please select the correct course.")
                continue
        gs_assignments_redemption = {ass_name : ass for ass_name, ass in course_gs.assignments.items() if "Redemption" in ass_name}
        gs_assignments_remaining = {ass_name : ass  for ass_name, ass in course_gs.assignments.items()  if "Redemption" not in ass_name}
        gs_assignments_actual = {}
        gs_ass_mapping = {} # Actual -> Redemption mapping
        for redemption_ass in gs_assignments_redemption.keys():
            ass_name, _ = find_best_match(redemption_ass, gs_assignments_remaining.keys())
            gs_assignments_actual[ass_name] = gs_assignments_remaining[ass_name]
            gs_ass_mapping[ass_name] = redemption_ass

        # Canvas Init Stuff
        course_canvas, userdb = canvas_init()

    with open('data.pkl', 'wb') as f:
        pickle.dump([course_gs, gs_assignments_actual, gs_assignments_redemption, gs_ass_mapping, course_canvas, userdb], f)

    # This should not be pickled
    canvas_late_submissions = canvas_get_assignment_submissions(course_canvas,
                                                 prompt="Select the Canvas Assignment which records the late days for HW:")

    # Google Sheets Init Stuff
    homework_name_tokens = [ "Scaling", "Stitching", "Calculator", "Dungeon", "Crawler", 
                            "CPPeers", "CPPers", "Rover", ]
    newdf, donedf = gsheets_init(homework_name_tokens, gs_ass_mapping)
    #  homework_names = list(newdf["Homework Name"].unique())
    #  ['Image Scaling', 'Image Scaling part1', 'Image scaling', '[HW Redemption] Image Scaling', 'HW Image', 'Image Scaling Part 1', 'Image Scaling ', 'image scaling', '[HW] Image Scaling', '', 'String_Calculator', 'String Calculator', 'Dungeon Crawler ', 'Dungeon Crawler', 'HW Dungeon Crawler', 'Image Stitching', 'Dungeons and crawlers', 'Dungeon crawler', 'Dunegon Crawler', 'dungeonCrawler', '[HW] Hello CPPeers!', '[HW Redemption] Hello CPPeers!', 'Hello CPPeers!', 'Hello CPPeers! ( I looked at my gmail to see how many late days were used, it was 3 then 3 again now 2, therefore I have used 8/10 days now and have 2 remaining.)', 'Hello Cppers', 'Hello CPPers', 'Hello CPPeers', 'Hello CPPers!', 'Hi CPPERS', 'CPPeers', 'CPPEERS', 'Mars Rover', '[HW] Mars Rover', 'Mars Rover ', 'Mars Rover (I previously requested 2 but I actually need 4)', 'HW: Mars Rover (MyString)']

    # these intermediary names help in mapping HW names in Google Sheet to HW names in Gradescope

    #  iterate over each row and process based on the type of request
    for index, row in newdf.iterrows():
        if row["Type of request"] == "Homework Late Day Pool":
            print("---------------------------------------------------")
            email = row['Email Address']
            hw = row['Homework Name']
            print(f"Processing Homework Late Day Pool for {hw} for student {row['Name']} with index {index}")

            # if same email and hw exist in the same row in donedf, then skip this row
            #  import ipdb; ipdb.set_trace()
            if donedf[(donedf["Email Address"] == email) & (donedf["Homework Name"] == hw)].shape[0] > 0:
                print(f"This user {email} has already been processed for this homework {hw}. Skipping this one for now.")
                print("---------------------------------------------------")
                continue

            if not questionary.confirm("Do you want to process this one?").ask():
                print(f"Skipping this one for now.")
                print("---------------------------------------------------")
                continue

            while True:
                if process_late_hw(row, gs_assignments_actual, gs_assignments_redemption, gs_ass_mapping, 
                    homework_name_tokens, canvas_late_submissions, userdb):
                    print(f"Operation successful for {row['Name']} with index {index}")
                    break
                else:
                    if questionary.confirm("Failed to process Homework Late Day Pool for this one. \
                                        Do you want to try again?").ask():
                        print(f"Trying again for {row['Name']} with index {index}")
                        continue
                    else:
                        print(f"Skipping this one for now.")
                        break
                print("---------------------------------------------------")

        else:
            print("---------------------------------------------------")
            print(f"Can't process Excused Absence for {row['Name']} with index {index} \
                  for the type of request {row['Type of request']}")
            print("---------------------------------------------------")







    import ipdb; ipdb.set_trace()


    










