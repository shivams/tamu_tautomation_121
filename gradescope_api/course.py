from enum import Enum
from bs4 import BeautifulSoup
try:
   from person import GSPerson
   from person import GSRole
except ModuleNotFoundError:
   from .person import GSPerson
   from .person import GSRole
try:
   from assignment import GSAssignment
except ModuleNotFoundError:
   from .assignment import GSAssignment

import json
from datetime import datetime
import pytz

TIMEZONE = 'America/Chicago'

class LoadedCapabilities(Enum):
    ASSIGNMENTS = 0
    ROSTER = 1

class GSCourse():

    def __init__(self, cid, name, shortname, year, session):
        '''Create a course object that has lazy eval'd assignments'''
        self.cid = cid
        self.name = name
        self.shortname = shortname
        self.year = year
        self.session = session
        self.assignments = {}
        self.roster = {} # TODO: Maybe shouldn't dict. 
        self.state = set() # Set of already loaded entitites (TODO what is the pythonic way to do this?)

    # ~~~~~~~~~~~~~~~~~~~~~~PEOPLE~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def add_person(self, name, email, role, sid = None, notify = False):
        self._check_capabilities({LoadedCapabilities.ROSTER})
        
        membership_resp = self.session.get('https://www.gradescope.com/courses/' + self.cid + '/memberships')
        parsed_membership_resp = BeautifulSoup(membership_resp.text, 'html.parser')

        authenticity_token = parsed_membership_resp.find('meta', attrs = {'name': 'csrf-token'} ).get('content')
        person_params = {
            "utf8": "✓",
            "user[name]" : name,
            "user[email]" : email,
            "user[sid]" : "" if sid is None else sid, 
            "course_membership[role]" : role.value,
            "button" : ""
        }
        if notify:
            person_params['notify_by_email'] = 1
        # Seriously. Why is this website so inconsistent as to where the csrf token goes?????????
        add_resp = self.session.post('https://www.gradescope.com/courses/' + self.cid + '/memberships',
                                     data = person_params,
                                     headers = {'x-csrf-token': authenticity_token})

        # TODO this is highly wasteful, need to likely improve this. 
        self.roster = {}
        self._lazy_load_roster()

    def remove_person(self, name):
        self._check_capabilities({LoadedCapabilities.ROSTER})
        
        membership_resp = self.session.get('https://www.gradescope.com/courses/' + self.cid + '/memberships')
        parsed_membership_resp = BeautifulSoup(membership_resp.text, 'html.parser')

        authenticity_token = parsed_membership_resp.find('meta', attrs = {'name': 'csrf-token'} ).get('content')
        remove_params = {
            "_method" : "delete",
            "authenticity_token" : authenticity_token
        }
        remove_resp = self.session.post('https://www.gradescope.com/courses/'+self.cid+'/memberships/'
                                     +self.roster[name].data_id,
                                     data = remove_params,
                                     headers = {'x-csrf-token': authenticity_token})

        # TODO this is highly wasteful, need to likely improve this. 
        self.roster = {}
        self._lazy_load_roster()

    def change_person_role(self, name, role):
        self._check_capabilities({LoadedCapabilities.ROSTER})
        
        membership_resp = self.session.get('https://www.gradescope.com/courses/' + self.cid + '/memberships')
        parsed_membership_resp = BeautifulSoup(membership_resp.text, 'html.parser')

        authenticity_token = parsed_membership_resp.find('meta', attrs = {'name': 'csrf-token'} ).get('content')
        role_params = {
            "course_membership[role]" : role.value,
        }
        role_resp = self.session.patch('https://www.gradescope.com/courses/'+self.cid+'/memberships/'
                                     +self.roster[name].data_id+'/update_role' ,
                                     data = role_params,
                                     headers = {'x-csrf-token': authenticity_token})

        # TODO this is highly wasteful, need to likely improve this. 
        self.roster = {}
        self._lazy_load_roster()

    # ~~~~~~~~~~~~~~~~~~~~~~ASSIGNMENTS~~~~~~~~~~~~~~~~~~~~~~~~~~

    def add_assignment(self,
                       name,
                       release,
                       due,
                       template_file,
                       student_submissions = True,
                       late_submissions = False,
                       group_submissions = 0):
        self._check_capabilities({LoadedCapabilities.ASSIGNMENTS})
        
        assignment_resp = self.session.get('https://www.gradescope.com/courses/'+self.cid+'/assignments')
        parsed_assignment_resp = BeautifulSoup(assignment_resp.text, 'html.parser')
        authenticity_token = parsed_assignment_resp.find('meta', attrs = {'name': 'csrf-token'} ).get('content')

        # TODO Make this less brittle and make sure to support all options properly
        assignment_params = {
            "authenticity_token" : authenticity_token,
            "assignment[title]" : name,
            "assignment[student_submission]" : student_submissions,
            "assignment[release_date_string]" : release,
            "assignment[due_date_string]" : due,
            "assignment[allow_late_submissions]" : 1 if late_submissions else 0,
            "assignment[submission_type]" : "image", # TODO What controls this?
            "assignment[group_submission]" : group_submissions
        }
        assignment_files = {
            "template_pdf" : open(template_file, 'rb')
        }
        assignment_resp = self.session.post('https://www.gradescope.com/courses/'+self.cid+'/assignments',
                                            files = assignment_files,
                                            data = assignment_params)

        # TODO this is highly wasteful, need to likely improve this. 
        self.assignments = {}
        self._lazy_load_assignments()
        
    def remove_assignment(self, name):
        self._check_capabilities({LoadedCapabilities.ASSIGNMENTS})
        
        assignment_resp = self.session.get('https://www.gradescope.com/courses/'+self.cid+'/assignments/'
                                           +self.assignments[name].aid+'/edit')
        parsed_assignment_resp = BeautifulSoup(assignment_resp.text, 'html.parser')
        authenticity_token = parsed_assignment_resp.find('meta', attrs = {'name': 'csrf-token'} ).get('content')

        remove_params = {
            "_method" : "delete",
            "authenticity_token" : authenticity_token
        }

        remove_resp = self.session.post('https://www.gradescope.com/courses/'+self.cid+'/assignments/'
                                     +self.assignments[name].aid,
                                     data = remove_params)

        # TODO this is highly wasteful, need to likely improve this. 
        self.assignments = {}
        self._lazy_load_assignments()

    # ~~~~~~~~~~~~~~~~~~~~~~HOUSEKEEPING~~~~~~~~~~~~~~~~~~~~~~~~~

    def _lazy_load_assignments(self):
        '''
        Load the assignment dictionary from assignments. This is done lazily to avoid slowdown caused by getting
        all the assignments for all classes. Also makes us less vulnerable to blocking.
        '''
        #  import ipdb; ipdb.set_trace()
        assignment_resp = self.session.get('https://www.gradescope.com/courses/'+self.cid+'/assignments')
        parsed_assignment_resp = BeautifulSoup(assignment_resp.text, 'html.parser')


        # find an element having a property called 'data-react-class' with value 'AssignmentsTable'
        assignment_table = parsed_assignment_resp.find('div', attrs = {'data-react-class':'AssignmentsTable'}).get('data-react-props')

        # assignment_table is a json string, so we need to parse it
        assignment_table = json.loads(assignment_table)['table_data']

        '''
      "table_data": [
        {
          "className": "js-assignmentTableAssignmentRow",
          "type": "assignment",
          "id": "assignment_3087411",
          "container_id": null,
          "version_index": null,
          "is_versioned_assignment": false,
          "version_name": null,
          "title": "Demo",
          "url": "/courses/569119/assignments/3087411",
          "edit_url": "/courses/569119/assignments/3087411/edit",
          "edit_actions_url": "/courses/569119/assignments/3087411/edit#assignment-actions",
          "has_section_overrides": false,
          "total_points": "100.0",
          "student_submission": true,
          "submission_window": {
            "release_date": "2023-08-17T09:40",
            "due_date": "2023-08-18T09:40",
            "hard_due_date": null,
            "time_limit": null
          },
          "created_at": "Aug 17",
          "num_active_submissions": 0,
          "grading_progress": 0,
          "is_published": false,
          "regrade_requests_open": true,
          "regrade_requests_possible": false,
          "regrade_request_url": "/courses/569119/assignments/3087411/regrade_requests",
          "open_regrade_request_count": 0,
          "due_or_created_at_date": "2023-08-18T09:40"
        },
        {
          "className": "js-assignmentTableAssignmentRow",
          "type": "assignment",
          "id": "assignment_3090821",
          "container_id": null,
          "version_index": null,
          "is_versioned_assignment": false,
          "version_name": null,
          "title": "[LW] Setup",
          "url": "/courses/569119/assignments/3090821",
          "edit_url": "/courses/569119/assignments/3090821/edit",
          "edit_actions_url": "/courses/569119/assignments/3090821/edit#assignment-actions",
          "has_section_overrides": false,
          "total_points": "3.0",
          "student_submission": true,
          "submission_window": {
            "release_date": "2023-08-21T07:30",
            "due_date": "2023-09-03T23:59",
            "hard_due_date": "2023-12-12T23:59",
            "time_limit": null
          },
          "created_at": "Aug 17",
          "num_active_submissions": 942,
          "grading_progress": 100,
          "is_published": false,
          "regrade_requests_open": true,
          "regrade_requests_possible": false,
          "regrade_request_url": "/courses/569119/assignments/3090821/regrade_requests",
          "open_regrade_request_count": 0,
          "due_or_created_at_date": "2023-12-12T23:59"
        },
        {
          "className": "js-assignmentTableAssignmentRow table--row-assignmentWithSection",
          "type": "assignment",
          "id": "assignment_3179344",
          "container_id": null,
          "version_index": null,
          "is_versioned_assignment": false,
          "version_name": null,
          "title": "[LW] Boolean Logic",
          "url": "/courses/569119/assignments/3179344",
          "edit_url": "/courses/569119/assignments/3179344/edit",
          "edit_actions_url": "/courses/569119/assignments/3179344/edit#assignment-actions",
          "has_section_overrides": true,
          "total_points": "60.0",
          "student_submission": true,
          "submission_window": {
            "release_date": "2023-08-28T00:00",
            "due_date": "2023-09-01T23:59",
            "hard_due_date": "2023-12-12T23:59",
            "time_limit": null
          },
          "created_at": "Aug 26",
          "num_active_submissions": 989,
          "grading_progress": 100,
          "is_published": false,
          "regrade_requests_open": true,
          "regrade_requests_possible": false,
          "regrade_request_url": "/courses/569119/assignments/3179344/regrade_requests",
          "open_regrade_request_count": 0,
          "due_or_created_at_date": "2023-12-12T23:59"
        },
        {
          "id": "section_667186",
          "parent_id": "assignment_3179344",
          "type": "section",
          "className": "table--row-assignmentSection",
          "title": "csce-121-508",
          "student_submission": true,
          "submission_window": {
            "visible": true,
            "release_date": "2023-08-28T00:00",
            "due_date": "2023-09-01T23:59",
            "hard_due_date": "2023-12-12T23:59",
            "time_limit": null
          },
          "created_at": "Aug 26",
          "num_active_submissions": 23
        }
        ]
        '''

        # filter the table_data to only get assignments having classname 'js-assignmentTableAssignmentRow' in them
        assignment_table = [assignment for assignment in assignment_table if 'js-assignmentTableAssignmentRow' in assignment['className']]

        #  assignment_table = []
        #  for assignment_row in parsed_assignment_resp.findAll('tr', class_ = 'js-assignmentTableAssignmentRow'):
            #  row = []
            #  for td in assignment_row.findAll('td'):
                #  row.append(td)
            #  assignment_table.append(row)
        
        for row in assignment_table:
            name = row['title']
            aid = row['id'].split('_')[1]
            points = row['total_points']
            # TODO: (released,due) = parse(row[2])
            submissions = row['num_active_submissions']
            percent_graded = row['grading_progress']
            complete = True if row['grading_progress'] == 100 else False
            regrades_on  = False if row['regrade_requests_open'] == False else True
            due_date = row['submission_window']['due_date']
            if due_date:
                due_date = datetime.strptime(due_date, "%Y-%m-%dT%H:%M")
                due_date = pytz.timezone(TIMEZONE).localize(due_date)
            else:
                due_date = None
            # TODO make these types reasonable
            # (name, aid, points, percent_graded, complete, regrades_on, course, due_date)
            self.assignments[name] = GSAssignment(name=name, aid=aid, points=points, 
                                                  percent_graded=percent_graded, complete=complete,
                                                  regrades_on=regrades_on, course=self, due_date=due_date)

        self.state.add(LoadedCapabilities.ASSIGNMENTS)
        pass

    def _lazy_load_roster(self):
        '''
        Load the roster list  This is done lazily to avoid slowdown caused by getting
        all the rosters for all classes. Also makes us less vulnerable to blocking.
        '''
        membership_resp = self.session.get('https://www.gradescope.com/courses/' + self.cid + '/memberships')
        parsed_membership_resp = BeautifulSoup(membership_resp.text, 'html.parser')

        roster_table = []
        for student_row in parsed_membership_resp.find_all('tr', class_ = 'rosterRow'):
            row = []
            for td in student_row('td'):
                row.append(td)
            roster_table.append(row)
        
        for row in roster_table:
            name = row[0].text.rsplit(' ', 1)[0]
            data_id = row[0].find('button', class_ = 'rosterCell--editIcon').get('data-id')
            if len(row) == 6:
                email = row[1].text
                role = row[2].find('option', selected="selected").text
                submissions = int(row[3].text)
                linked = True if 'statusIcon-active' in row[4].find('i').get('class') else False
            else:
                email = row[2].text
                role = row[3].find('option', selected="selected").text
                submissions = int(row[4].text)
                linked = True if 'statusIcon-active' in row[5].find('i').get('class') else False
            # TODO Make types reasonable.
            self.roster[name] = GSPerson(name, data_id, email, role, submissions, linked)
        self.state.add(LoadedCapabilities.ROSTER)
        
    def _check_capabilities(self, needed):
        '''
        checks if we have the needed data loaded and gets them lazily.
        '''
        missing = needed - self.state
        if LoadedCapabilities.ASSIGNMENTS in missing:
            self._lazy_load_assignments()
        if LoadedCapabilities.ROSTER in missing:
            self._lazy_load_roster()

    def delete(self):
        course_edit_resp = self.session.get('https://www.gradescope.com/courses/'+self.cid+'/edit')
        parsed_course_edit_resp = BeautifulSoup(course_edit_resp.text, 'html.parser')

        authenticity_token = parsed_course_edit_resp.find('meta', attrs = {'name': 'csrf-token'} ).get('content')

        print(authenticity_token)

        delete_params = {
            "_method": "delete",
            "authenticity_token": authenticity_token
        }
        print(delete_params)

        delete_resp = self.session.post('https://www.gradescope.com/courses/'+self.cid,
                                        data = delete_params,
                                        headers={
                                            'referer': 'https://www.gradescope.com/courses/'+self.cid+'/edit',
                                            'origin': 'https://www.gradescope.com'
                                        })
        
        # TODO make this less brittle 
