import requests
from bs4 import BeautifulSoup
from enum import Enum
try:
   from account import GSAccount
except ModuleNotFoundError:
   from .account import GSAccount

try:
   from course import GSCourse
except ModuleNotFoundError:
   from .course import GSCourse

'''
Various Gradescope Paths (as intercepted from the submissions.html page)
  "paths": {
    "course_path": "/courses/569119",
    "submission_path": "/courses/569119/assignments/3394470/submissions/204639411",
    "submission_status_path": "/courses/569119/assignments/3394470/submissions/204639411/status.json",
    "submission_react_path": "/courses/569119/assignments/3394470/submissions/204639411.json?content=react",
    "graded_pdf_path": "/courses/569119/assignments/3394470/submissions/204639411.pdf",
    "pdf_attachment_status_path": "/courses/569119/assignments/3394470/submissions/204639411/pdf_attachment_status.json",
    "select_pages_path": "/courses/569119/assignments/3394470/submissions/204639411/select_pages",
    "regrade_requests_path": "/courses/569119/assignments/3394470/submissions/204639411/regrade_requests",
    "resubmit_path": "/courses/569119/assignments/3394470/submissions",
    "original_file_path": null,
    "ownerships_path": "/courses/569119/assignments/3394470/submissions/204639411/ownerships",
    "many_ownerships_path": "/courses/569119/assignments/3394470/submissions/204639411/ownerships/many",
    "resubmit_new_path": "/courses/569119/assignments/3394470/submissions/new?owner_id=2646268",
    "resubmit_images_path": "/courses/569119/assignments/3394470/submissions/submit_images?owner_id=2646268",
    "panda_submission_path": "/courses/569119/assignments/3394470/submissions/204639411/panda_submission",
    "new_public_key_path": "/public_keys/new",
    "submission_zip_path": "/courses/569119/assignments/3394470/submissions/204639411.zip",
    "ssh_session_path": "/courses/569119/assignments/3394470/submissions/204639411/ssh_sessions",
    "rerun_autograder_path": "/courses/569119/assignments/3394470/submissions/204639411/regrade",
    "leaderboard_path": "/courses/569119/assignments/3394470/leaderboard",
    "configure_autograder_path": "/courses/569119/assignments/3394470/configure_autograder"
  },
'''

class ConnState(Enum):
    INIT = 0
    LOGGED_IN = 1

class GSConnection():
    '''The main connection class that keeps state about the current connection.'''
        
    def __init__(self):
        '''Initialize the session for the connection.'''
        self.session = requests.Session()
        self.state = ConnState.INIT
        self.account = None

    def login(self, email, pswd):
        '''
        Login to gradescope using email and password.
        Note that the future commands depend on account privilages.
        '''
        init_resp = self.session.get("https://www.gradescope.com/")
        parsed_init_resp = BeautifulSoup(init_resp.text, 'html.parser')
        for form in parsed_init_resp.find_all('form'):
            if form.get("action") == "/login":
                for inp in form.find_all('input'):
                    if inp.get('name') == "authenticity_token":
                        auth_token = inp.get('value')

        login_data = {
            "utf8": "✓",
            "session[email]": email,
            "session[password]": pswd,
            "session[remember_me]": 0,
            "commit": "Log In",
            "session[remember_me_sso]": 0,
            "authenticity_token": auth_token,
        }
        login_resp = self.session.post("https://www.gradescope.com/login", params=login_data)
        if len(login_resp.history) != 0:
            if login_resp.history[0].status_code == requests.codes.found:
                self.state = ConnState.LOGGED_IN
                self.account = GSAccount(email, self.session)
                return True
        else:
            return False

    def get_account(self):
        '''
        Gets and parses account data after login. Note will return false if we are not in a logged in state, but 
        this is subject to change.
        '''
        if self.state != ConnState.LOGGED_IN:
            return False # Should raise exception
        # Get account page and parse it using bs4
        account_resp = self.session.get("https://www.gradescope.com/account")
        parsed_account_resp = BeautifulSoup(account_resp.text, 'html.parser')

        # Get instructor course data
        # choose next_sibling with class = 'courseList'
        instructor_courses = [sibling for sibling in parsed_account_resp.find('h1', class_ ='pageHeading').next_siblings if 'courseList' in sibling.get("class")][0]
        #  import ipdb; ipdb.set_trace()
        for course in instructor_courses.find_all('a', class_ = 'courseBox'):
            shortname = course.find('h3', class_ = 'courseBox--shortname').text
            name = course.find('div', class_ = 'courseBox--name').text
            cid = course.get("href").split("/")[-1]
            year = None
            print(cid, name, shortname)
            for tag in course.parent.previous_siblings:
                if 'courseList--term' in tag.get("class"):
                    year = tag.string
                    break
            if year is None:
                return False # Should probably raise an exception.
            self.account.add_class(cid, name, shortname, year, instructor = True)

        student_courses = [sibling for sibling in parsed_account_resp.find('h1', class_ ='pageHeading', string = "Student Courses").next_siblings if 'courseList' in sibling.get("class")][0]
        for course in student_courses.find_all('a', class_ = 'courseBox'):
            shortname = course.find('h3', class_ = 'courseBox--shortname').text
            name = course.find('div', class_ = 'courseBox--name').text
            cid = course.get("href").split("/")[-1]
            
            year= None
            for tag in course.parent.previous_siblings:
                if 'courseList--term' in tag.get("class"):
                    year = tag.string
                    break
            if year is None:
                return False # Should probably raise an exception.
            self.account.add_class(cid, name, shortname, year)


# THIS IS STRICTLY FOR DEVELOPMENT TESTING :( Sorry for leaving it in.
if __name__=="__main__":
    conn = GSConnection()
    conn.login("shivam@tamu.edu", "v97T@$uUafbaYa7jKK")
    print(conn.state)
    conn.get_account()

    course = conn.account.instructor_courses['569119']
    course._lazy_load_assignments()

    ass = course.assignments['[HW Redemption] Image Scaling']
    #  ass.get_submissions()
    #  sub = ass.submissions[0]

    #  for sub in ass.submissions:
        #  if 'Shivam' in sub.name:
            #  break

    print(f"Now submitting for student")
    ass.post_submission('202602737.zip', '3447483')


    #TODO: ((2023-11-24)) Currently stuck at processing the submission. 
    #Work going on in submission.py
    #Seems like we only have access to that particular submission and not the submission history
    #Also, I am not able to POST the submission


    import ipdb; ipdb.set_trace()







